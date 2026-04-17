"""
Data, Crawler results, and Twitter search API routes.

- get_data: delegates to legacy api_handlers (handles both LOCAL and S3 modes).
- crawler_results / twitter_search: direct implementation for LOCAL_MODE;
  falls back to legacy api_handlers for S3 mode.
"""

import glob
import json
import logging
import os
import re
import secrets
from datetime import datetime

import requests
from flask import jsonify, request

from . import data_bp, csrf_protect
from .. import limiter
from ..config import Config
from ..services.local_data import decimal_default

logger = logging.getLogger(__name__)

_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_@-]{1,128}$')


# ---------------------------------------------------------------------------
# Local helpers (used when Config.LOCAL_MODE is True)
# ---------------------------------------------------------------------------

def _fetch_tweets_from_crawler(twitter_crawler_endpoint: str, keyword: str):
    """Twitter 크롤러 API를 호출하여 트윗 데이터를 가져옴."""
    tweets, replies = [], []
    try:
        response = requests.post(
            f"{twitter_crawler_endpoint}/crawl",
            json={'keywords': [keyword]},
            timeout=30,
            verify=True,
        )
        if response.status_code != 200:
            return tweets, replies
        data = response.json()
        results = data.get('results', [])
        if not results:
            return tweets, replies
        keyword_result = results[0]
        tweets = keyword_result.get('tweets', [])
        replies = keyword_result.get('replies', [])
    except Exception as e:
        logger.error("Error calling Twitter crawler: %s", e, exc_info=True)
    return tweets, replies


def _load_tweets_from_local_files(keyword: str):
    """로컬 파일 시스템에서 키워드와 관련된 트위터 데이터를 로드."""
    tweets, replies = [], []
    twitter_data_dir = os.path.join(Config.LOCAL_DATA_DIR, 'twitter')
    if not os.path.exists(twitter_data_dir):
        return tweets, replies
    for file_path in glob.glob(os.path.join(twitter_data_dir, '**/*.json'), recursive=True):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if keyword.lower() not in json.dumps(data, ensure_ascii=False).lower():
                continue
            if 'tweets' in data:
                tweets.extend(data['tweets'])
            if 'data' in data:
                for item in data['data']:
                    if 'tweet' in item:
                        tweets.append(item['tweet'])
                    if 'replies' in item:
                        replies.extend(item['replies'])
        except Exception as e:
            logger.error("Error reading twitter data file %s: %s", file_path, e, exc_info=True)
    return tweets, replies


def _save_youtube_result(result: dict, timestamp: str):
    """YouTube 크롤러 결과를 로컬 파일 시스템에 저장."""
    channel_handle = result.get('channel')
    if not channel_handle:
        return False, None
    channel_clean = channel_handle.lstrip('@').lower()
    if not _SAFE_ID_RE.match(channel_clean):
        logger.warning("Invalid channel handle rejected: %s", channel_clean)
        return False, None
    save_dir = os.path.join(Config.LOCAL_DATA_DIR, 'youtube', channel_clean)
    os.makedirs(save_dir, exist_ok=True)
    filepath = os.path.join(save_dir, f"{timestamp}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info("Saved YouTube crawler result to %s", filepath)
    return True, channel_handle


def _save_dcinside_result(result: dict, timestamp: str):
    """DCInside 크롤러 결과를 로컬 파일 시스템에 저장."""
    gallery_id = result.get('gallery_id')
    if not gallery_id or not _SAFE_ID_RE.match(gallery_id):
        return False
    save_dir = os.path.join(Config.LOCAL_DATA_DIR, 'dcinside', gallery_id)
    os.makedirs(save_dir, exist_ok=True)
    filepath = os.path.join(save_dir, f"{timestamp}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info("Saved DCInside crawler result to %s", filepath)
    return True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@data_bp.route('/api/data/<path:s3_key>', methods=['GET'])
@limiter.limit("60 per minute")
def get_data(s3_key):
    """S3 키(또는 로컬 경로)로 데이터 조회."""
    return jsonify({"error": "S3 mode not supported. Set LOCAL_MODE=true"}), 501


@data_bp.route('/api/crawler/results', methods=['POST'])
@limiter.limit("10 per minute")
def crawler_results():
    """크롤러 결과 저장 엔드포인트 (DCInside + YouTube)."""
    token = request.headers.get('X-Crawler-Token', '')
    expected = os.environ.get('CRAWLER_INTERNAL_TOKEN', '')
    if not expected:
        return jsonify({'error': 'CRAWLER_INTERNAL_TOKEN not configured'}), 503
    if not secrets.compare_digest(token, expected):
        return jsonify({'error': 'Unauthorized'}), 401

    if not Config.LOCAL_MODE:
        return jsonify({"error": "S3 mode not supported. Set LOCAL_MODE=true"}), 501

    try:
        body = request.get_json(force=True, silent=True) or {}
        results = body.get('results', [])
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

        saved_count = 0
        youtube_channels_saved = []

        for result in results:
            saved, channel_handle = _save_youtube_result(result, timestamp)
            if saved:
                saved_count += 1
                youtube_channels_saved.append(channel_handle)
                continue
            if _save_dcinside_result(result, timestamp):
                saved_count += 1

        return jsonify({
            'message': f'Saved {saved_count} results',
            'saved_count': saved_count,
            'youtube_channels': youtube_channels_saved,
        }), 200
    except Exception as e:
        logger.error("Error saving crawler results: %s", e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@data_bp.route('/api/twitter/search', methods=['POST'])
@limiter.limit("60 per minute")
@csrf_protect
def twitter_search():
    """Twitter 키워드 검색 엔드포인트."""
    if not Config.LOCAL_MODE:
        return jsonify({"error": "S3 mode not supported. Set LOCAL_MODE=true"}), 501

    try:
        body = request.get_json(force=True, silent=True) or {}
        action = body.get('action', 'search')
        if action not in ('search', 'bulk_search'):
            return jsonify({'error': 'Invalid action'}), 400

        twitter_crawler_endpoint = os.environ.get(
            'TWITTER_CRAWLER_ENDPOINT', 'http://twitter-crawler:5000'
        )
        MAX_KEYWORD_LENGTH = 100

        if action == 'bulk_search':
            MAX_BULK_KEYWORDS = 20
            keywords = body.get('keywords', [])
            if not isinstance(keywords, list) or len(keywords) > MAX_BULK_KEYWORDS:
                return jsonify({'error': f'keywords must be a list of max {MAX_BULK_KEYWORDS} items'}), 400
            keywords = [k for k in keywords if isinstance(k, str) and k.strip() and len(k) <= MAX_KEYWORD_LENGTH]
            if not keywords:
                return jsonify({'error': 'At least one valid keyword is required'}), 400
            bulk_results = {}
            for keyword in keywords:
                try:
                    tweets, replies = _fetch_tweets_from_crawler(twitter_crawler_endpoint, keyword)
                    local_tweets, local_replies = _load_tweets_from_local_files(keyword)
                    tweets.extend(local_tweets)
                    replies.extend(local_replies)
                    bulk_results[keyword] = {
                        'tweets': tweets,
                        'replies': replies,
                        'total_tweets': len(tweets),
                    }
                except Exception as e:
                    logger.error("Error searching keyword '%s': %s", keyword, e, exc_info=True)
                    bulk_results[keyword] = {'tweets': [], 'replies': [], 'error': 'Internal server error'}
            return (
                json.dumps({'results': bulk_results}, default=decimal_default, ensure_ascii=False),
                200,
                {'Content-Type': 'application/json'},
            )

        keyword = (body.get('keyword', '') or '').strip()
        if not keyword or len(keyword) > MAX_KEYWORD_LENGTH:
            return jsonify({'error': 'Keyword must be 1-100 characters'}), 400

        tweets, replies = _fetch_tweets_from_crawler(twitter_crawler_endpoint, keyword)
        local_tweets, local_replies = _load_tweets_from_local_files(keyword)
        tweets.extend(local_tweets)
        replies.extend(local_replies)

        return (
            json.dumps(
                {
                    'tweets': tweets,
                    'replies': replies,
                    'keyword': keyword,
                    'total_tweets': len(tweets),
                    'total_replies': len(replies),
                },
                default=decimal_default,
                ensure_ascii=False,
            ),
            200,
            {'Content-Type': 'application/json'},
        )
    except Exception as e:
        logger.error("Error in Twitter search: %s", e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
