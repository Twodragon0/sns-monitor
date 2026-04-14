"""
Vuddy creators API routes.
Migrated from api_handlers._handle_vuddy_creators for LOCAL_MODE.
Non-local mode falls back to legacy api_handlers.
"""

import json
import logging
import os
from collections import Counter
from decimal import Decimal

from flask import Blueprint, Response, jsonify

from ..config import Config
from ..services.local_data import decimal_default, is_timestamp_comment
from ..services.sentiment import (
    _calculate_sentiment_from_samples,
    calculate_sentiment_distribution,
    get_overall_sentiment,
)

logger = logging.getLogger(__name__)

vuddy_bp = Blueprint('vuddy', __name__)


# ---------------------------------------------------------------------------
# Internal helpers (LOCAL_MODE only)
# ---------------------------------------------------------------------------

def _process_country_stats(raw_country_stats):
    """국가별 통계 필드명 변환 및 처리"""
    country_stats = {}
    for country_code, stats in raw_country_stats.items():
        country_stats[country_code] = {
            'comments': stats.get('comment_count', stats.get('comments', 0)),
            'likes': stats.get('total_likes', stats.get('likes', 0)),
        }
    return country_stats


def _load_latest_metadata_local(platform, keyword=None):
    """로컬 파일에서 최신 메타데이터 로드"""
    metadata_dir = os.path.join(Config.LOCAL_DATA_DIR, 'metadata', platform)
    if not os.path.exists(metadata_dir):
        return None

    files = []
    for filename in os.listdir(metadata_dir):
        if not filename.endswith('.json'):
            continue
        filepath = os.path.join(metadata_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            if not keyword or metadata.get('keyword') == keyword:
                files.append((filepath, metadata))
        except Exception as e:
            logger.debug("Skipping vuddy file %s: %s", filepath, e)
            continue

    if not files:
        return None

    files.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
    return files[0][1]


def _get_analysis_result_local(creator_name):
    """로컬 파일에서 분석 결과 가져오기"""
    try:
        return _load_latest_metadata_local('vuddy', creator_name)
    except Exception as e:
        logger.error("Error loading metadata for %s: %s", creator_name, e, exc_info=True)
        return None


def _generate_summary_and_keywords(comment_samples, video_links):
    """댓글 샘플 기반 요약 및 키워드 생성"""
    if not comment_samples:
        return '', []

    comment_texts = [c.get('text', '') for c in comment_samples[:10]]
    positive_count = sum(1 for c in comment_samples if c.get('sentiment') == 'positive')
    negative_count = sum(1 for c in comment_samples if c.get('sentiment') == 'negative')
    neutral_count = sum(1 for c in comment_samples if c.get('sentiment') == 'neutral')

    all_words = []
    for text in comment_texts:
        all_words.extend([w for w in text.split() if len(w) > 1])

    word_freq = Counter(all_words)
    top_keywords = [word for word, count in word_freq.most_common(5) if count > 1]

    summary_parts = [f"총 {len(comment_samples)}개의 댓글 샘플이 수집되었습니다."]

    total_sentiment = positive_count + negative_count + neutral_count
    if total_sentiment > 0:
        pos_pct = int((positive_count / total_sentiment) * 100)
        neg_pct = int((negative_count / total_sentiment) * 100)
        neu_pct = int((neutral_count / total_sentiment) * 100)
        summary_parts.append(f"감성 분석 결과: 긍정 {pos_pct}%, 중립 {neu_pct}%, 부정 {neg_pct}%")

    if video_links:
        summary_parts.append(f"YouTube에서 {len(video_links)}개의 관련 영상을 찾았습니다.")

    if top_keywords:
        summary_parts.append(f"주요 키워드: {', '.join(top_keywords[:5])}")

    return ' '.join(summary_parts), top_keywords


def _generate_google_summary(google_links):
    """Google 검색 결과 요약 생성"""
    if not google_links:
        return ''

    parts = [f"Google 검색에서 {len(google_links)}개의 관련 결과를 찾았습니다."]

    snippets = [link.get('snippet', '') for link in google_links[:5] if link.get('snippet')]
    if snippets:
        words = []
        for snippet in snippets:
            words.extend([w for w in snippet.split() if len(w) > 2])

        top_kw = [w for w, _ in Counter(words).most_common(3) if Counter(words)[w] > 1]
        if top_kw:
            parts.append(f"Google 검색 주요 키워드: {', '.join(top_kw)}")

        topics = []
        for snippet in snippets[:3]:
            topics.append(snippet[:100] + '...' if len(snippet) > 50 else snippet)
        if topics:
            parts.append(f"주요 검색 내용: {' | '.join(topics[:2])}")

    return ' '.join(parts)


def _build_analysis_info(analysis_result, comment_samples, summary_text, top_keywords, google_summary_text):
    """분석 정보 빌드"""
    if analysis_result:
        sentiment_dist = analysis_result.get('sentiment_analysis', {}).get('sentiment_distribution', {})
        if sentiment_dist:
            sentiment_distribution = {}
            for key in ['positive', 'negative', 'neutral']:
                value = sentiment_dist.get(key, 0)
                sentiment_distribution[key] = float(value) if value else 0.0
        else:
            sentiment_distribution, _, _ = _calculate_sentiment_from_samples(comment_samples)

        overall_score = analysis_result.get('insights', {}).get('overall_score', 50)
        if isinstance(overall_score, Decimal):
            overall_score = int(overall_score)

        llm_summary = analysis_result.get('keyword_analysis', {}).get('summary', '')
        final_summary = llm_summary if llm_summary else summary_text
        if google_summary_text:
            final_summary += f" {google_summary_text}"

        llm_keywords = analysis_result.get('keyword_analysis', {}).get('keywords', [])
        final_keywords = llm_keywords if llm_keywords else top_keywords[:5]

        return {
            'sentiment': analysis_result.get('sentiment_analysis', {}).get('overall_sentiment', 'neutral'),
            'sentiment_distribution': sentiment_distribution,
            'summary': final_summary,
            'keywords': final_keywords,
            'trends': analysis_result.get('keyword_analysis', {}).get('trends', []),
            'insights': analysis_result.get('insights', {}).get('key_insights', []),
            'overall_score': overall_score,
            'analyzed_at': analysis_result.get('analyzed_at', ''),
        }

    if comment_samples:
        sentiment_distribution, overall_sentiment, calculated_score = _calculate_sentiment_from_samples(comment_samples)
        final_summary = summary_text if summary_text else '댓글 분석 중입니다. 곧 요약이 제공됩니다.'
        if google_summary_text:
            final_summary += f" {google_summary_text}"

        return {
            'sentiment': overall_sentiment,
            'sentiment_distribution': sentiment_distribution,
            'summary': final_summary,
            'keywords': top_keywords[:5],
            'trends': [],
            'insights': [],
            'overall_score': calculated_score,
            'analyzed_at': '',
        }

    return {
        'sentiment': 'neutral',
        'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0},
        'summary': '',
        'keywords': [],
        'trends': [],
        'insights': [],
        'overall_score': 50,
        'analyzed_at': '',
    }


def _process_creators_from_data(creators_data):
    """creators 배열에서 직접 정보 추출"""
    creators = []
    for creator_data in creators_data:
        raw_country_stats = creator_data.get('country_stats', {})
        country_stats = _process_country_stats(raw_country_stats)

        creator_info = {
            'name': creator_data.get('name', ''),
            'youtube_channel': creator_data.get('youtube_channel', ''),
            'vuddy_channel': creator_data.get('vuddy_channel', ''),
            'total_comments': creator_data.get('total_comments', 0),
            'total_likes': creator_data.get('total_likes', 0),
            'total_blog_posts': creator_data.get('total_blog_posts', 0),
            'total_google_results': creator_data.get(
                'total_google_results', len(creator_data.get('google_links', []))
            ),
            'youtube_search_status': 'success',
            'blog_search_status': 'success',
            'google_search_status': 'success',
            'comment_samples': [],
            'video_links': [],
            'social_media': creator_data.get('social_media', []),
            'google_links': creator_data.get('google_links', []),
            'platform_links': creator_data.get('platform_links', []),
            'soop_analysis': creator_data.get('soop_analysis'),
            'statistics': creator_data.get('statistics', {}),
            'country_stats': country_stats,
        }

        # 댓글 샘플 변환
        for comment in creator_data.get('comment_samples', [])[:10]:
            comment_text = comment.get('text', '')
            if is_timestamp_comment(comment_text):
                continue

            video_id = comment.get('video_id', '')
            video_url = comment.get('video_url', '')
            if video_id and not video_url:
                video_url = f"https://www.youtube.com/watch?v={video_id}"

            creator_info['comment_samples'].append({
                'text': comment_text,
                'author': comment.get('author', '익명'),
                'like_count': comment.get('like_count', 0),
                'published_at': comment.get('published_at', ''),
                'country': comment.get('country', 'Unknown'),
                'video_title': comment.get('video_title', ''),
                'video_id': video_id,
                'video_url': video_url,
                'sentiment': comment.get('sentiment', 'neutral'),
            })

        # 비디오 링크 변환
        for video in creator_data.get('video_links', [])[:10]:
            creator_info['video_links'].append({
                'title': video.get('title', ''),
                'url': video.get('url', ''),
                'channel': video.get('channel', creator_data.get('name', '')),
                'published_at': video.get('published_at', ''),
            })

        # 분석 결과 추가
        analysis_data = creator_data.get('analysis', {})
        sentiment_dist = creator_data.get('sentiment_distribution', {})
        sentiment_distribution = calculate_sentiment_distribution(sentiment_dist)
        overall_sentiment = get_overall_sentiment(sentiment_dist)

        creator_info['analysis'] = {
            'sentiment': overall_sentiment,
            'sentiment_distribution': sentiment_distribution,
            'summary': analysis_data.get('summary', f"총 {creator_info['total_comments']}개의 댓글이 수집되었습니다."),
            'keywords': analysis_data.get('keywords', []),
            'trends': analysis_data.get('trends', []),
            'insights': analysis_data.get('insights', []),
            'overall_score': creator_data.get('overall_score', 50),
            'analyzed_at': '',
        }

        creators.append(creator_info)

    return creators


def _handle_vuddy_creators_local():
    """LOCAL_MODE용 Vuddy 크리에이터 목록 처리"""
    creators = []
    vuddy_file = os.path.join(
        Config.LOCAL_DATA_DIR, 'vuddy', 'comprehensive_analysis', 'vuddy-creators.json'
    )

    if not os.path.exists(vuddy_file):
        logger.debug("vuddy-creators.json not found at %s", vuddy_file)
        return creators

    try:
        with open(vuddy_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info("Loaded vuddy-creators.json with %d creators", len(data.get('creators', [])))
    except Exception as e:
        logger.error("Error loading vuddy-creators.json: %s", e, exc_info=True)
        return creators

    if 'creators' in data:
        creators = _process_creators_from_data(data.get('creators', []))
    elif 'comprehensive_analysis' in data:
        # comprehensive_analysis 형식은 S3 의존 로직이므로 로컬에서는 빈 결과 반환
        logger.warning("comprehensive_analysis format not supported in LOCAL_MODE for vuddy blueprint")

    return creators


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@vuddy_bp.route('/api/vuddy/creators', methods=['GET'])
def vuddy_creators():
    """Vuddy 크리에이터 목록"""
    if not Config.LOCAL_MODE:
        return jsonify({"error": "S3 mode not supported. Set LOCAL_MODE=true"}), 501

    try:
        creators = _handle_vuddy_creators_local()
    except Exception as e:
        logger.error("Error getting vuddy creators: %s", e, exc_info=True)
        creators = []

    body = json.dumps({'creators': creators}, default=decimal_default, ensure_ascii=False)
    return Response(body, status=200, content_type='application/json')
