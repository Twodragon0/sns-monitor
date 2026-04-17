"""
Dashboard API routes.
Migrated handlers use local_data service directly.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

from flask import jsonify, make_response, request

from . import dashboard_bp
from .. import limiter
from ..config import Config
from ..services.local_data import (
    load_metadata_files_local,
    parse_timestamp_for_today,
    load_channels_from_local,
    convert_item_to_scan,
    decimal_default,
)
from ..services.redis_client import get_redis

logger = logging.getLogger(__name__)

# In-memory stats cache (fallback when Redis is unavailable)
_stats_cache = {'data': None, 'expires': 0}
_STATS_TTL = 300  # 5 minutes


def _compute_stats():
    """Compute dashboard stats from metadata files."""
    metadata_dir = os.path.join(Config.LOCAL_DATA_DIR, 'metadata')
    items = load_metadata_files_local(metadata_dir)

    today = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today, datetime.min.time())

    today_items = 0
    analyzed_items = 0
    total_comments = 0

    for item in items:
        if parse_timestamp_for_today(item.get('timestamp', ''), today_start):
            today_items += 1

        if (item.get('synthesized_result') or
            item.get('sentiment') or
            item.get('sentiment_analysis') or
            item.get('insights')):
            analyzed_items += 1

        comments_value = item.get('total_comments', 0)
        if comments_value:
            total_comments += int(comments_value)

    return {
        'total_items': len(items),
        'today_items': today_items,
        'analyzed_items': analyzed_items,
        'total_comments': total_comments,
        'avg_sentiment': 'neutral',
    }


@dashboard_bp.route('/api/dashboard/stats', methods=['GET'])
@limiter.limit("60 per minute")
def dashboard_stats():
    """대시보드 통계 조회
    전체 수집 항목, 오늘 수집 수, 분석 완료 수, 댓글 총계 등 대시보드 통계를 반환합니다. Redis 또는 메모리 캐시(5분 TTL)를 사용합니다.
    ---
    tags:
      - 대시보드
    responses:
      200:
        description: 대시보드 통계
        schema:
          type: object
          properties:
            total_items:
              type: integer
              description: 전체 수집 항목 수
            today_items:
              type: integer
              description: 오늘 수집된 항목 수
            analyzed_items:
              type: integer
              description: 분석 완료된 항목 수
            total_comments:
              type: integer
              description: 수집된 댓글 총계
            avg_sentiment:
              type: string
              description: 평균 감성 (positive/neutral/negative)
    """
    global _stats_cache
    cache_key = 'sns-monitor:dashboard:stats'

    # Try Redis cache first
    redis_client = get_redis()
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                resp = make_response(jsonify(json.loads(cached)))
                resp.headers['Cache-Control'] = 'private, max-age=60'
                return resp
        except Exception as e:
            logger.debug("Redis cache read failed for stats: %s", e)

    # Try in-memory cache
    now = time.time()
    if _stats_cache['data'] and now < _stats_cache['expires']:
        resp = make_response(jsonify(_stats_cache['data']))
        resp.headers['Cache-Control'] = 'private, max-age=60'
        return resp

    # Compute fresh stats
    stats = {
        'total_items': 0, 'today_items': 0, 'analyzed_items': 0,
        'total_comments': 0, 'avg_sentiment': 'neutral',
    }
    try:
        stats = _compute_stats()
    except Exception as e:
        logger.error("Error getting stats: %s", e, exc_info=True)

    # Stamp freshness so the frontend knows when the data was computed
    stats['last_computed'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Store in caches
    _stats_cache = {'data': stats, 'expires': now + _STATS_TTL}
    if redis_client:
        try:
            redis_client.setex(cache_key, _STATS_TTL, json.dumps(stats))
        except Exception as e:
            logger.debug("Redis cache write failed for stats: %s", e)

    resp = make_response(jsonify(stats))
    resp.headers['Cache-Control'] = 'private, max-age=60'
    return resp


@dashboard_bp.route('/api/channels', methods=['GET'])
@limiter.limit("60 per minute")
def channels():
    """YouTube 채널 목록 조회
    로컬 데이터에서 수집된 YouTube 채널 목록을 반환합니다.
    ---
    tags:
      - 대시보드
    responses:
      200:
        description: 채널 목록
        schema:
          type: object
          properties:
            channels:
              type: array
              items:
                type: object
    """
    try:
        youtube_dir = os.path.join(Config.LOCAL_DATA_DIR, 'youtube')
        channel_list = load_channels_from_local(youtube_dir)
    except Exception as e:
        logger.error("Error getting channels: %s", e, exc_info=True)
        channel_list = []

    return jsonify({'channels': channel_list})


@dashboard_bp.route('/api/scans', methods=['GET'])
@limiter.limit("60 per minute")
def scans():
    """스캔 이력 조회 (페이지네이션)
    수집된 스캔 이력을 페이지네이션 및 플랫폼 필터와 함께 반환합니다.
    ---
    tags:
      - 대시보드
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: 페이지 번호 (1부터 시작)
      - name: limit
        in: query
        type: integer
        default: 50
        description: 페이지당 항목 수 (최대 200)
      - name: platform
        in: query
        type: string
        description: "플랫폼 이름으로 필터 (예: youtube, dcinside)"
    responses:
      200:
        description: 스캔 목록
        schema:
          type: object
          properties:
            scans:
              type: array
              items:
                type: object
            total:
              type: integer
            page:
              type: integer
            limit:
              type: integer
    """
    page = max(1, request.args.get('page', 1, type=int))
    limit = min(200, max(1, request.args.get('limit', 50, type=int)))
    platform_filter = request.args.get('platform', '', type=str).strip().lower()

    try:
        metadata_dir = os.path.join(Config.LOCAL_DATA_DIR, 'metadata')
        items = load_metadata_files_local(metadata_dir)

        if platform_filter:
            items = [i for i in items if i.get('platform', '').lower() == platform_filter]

        items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        total = len(items)

        start = (page - 1) * limit
        page_items = items[start:start + limit]

        scan_list = [convert_item_to_scan(item) for item in page_items]
    except Exception as e:
        logger.error("Error getting scans: %s", e, exc_info=True)
        scan_list = []
        total = 0

    return jsonify({
        'scans': scan_list,
        'total': total,
        'page': page,
        'limit': limit,
    })


# Group members and channel routes are now handled by members_bp (app/api/members.py).
