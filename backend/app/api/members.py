"""
Unified Group Members blueprint.

Handles /api/<group>/members and /api/<group>/channel routes for group-a, group-b, group-c.
In LOCAL_MODE: reads JSON files directly via local_data utilities.
In non-LOCAL_MODE: delegates to legacy api_handlers for S3 access.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from flask import request, Response, jsonify

from flask import Blueprint
from .. import limiter
from ..config import Config
from ..services.local_data import decimal_default, is_timestamp_comment

logger = logging.getLogger(__name__)

members_bp = Blueprint('members', __name__)

# ---------------------------------------------------------------------------
# Group config: maps group_id -> members JSON filename (under
#   LOCAL_DATA_DIR/vuddy/comprehensive_analysis/)
# ---------------------------------------------------------------------------
_GROUP_CONFIG = {
    'group-a': {
        'members_file': 'group-a-members.json',
        'channel_file': 'group-a-channel-members.json',
        'timestamp_field': 'updated_at',   # field that stores last-crawled date
        'comment_style': 'a',              # Group A has its own comment normalisation
    },
    'group-b': {
        'members_file': 'group-b-members.json',
        'channel_file': None,              # uses youtube/channels dir directly
        'timestamp_field': 'timestamp',
        'comment_style': 'bc',
    },
    'group-c': {
        'members_file': 'group-c-members.json',
        'channel_file': None,
        'timestamp_field': 'timestamp',
        'comment_style': 'bc',
    },
}

# ---------------------------------------------------------------------------
# Internal helpers (local, no S3)
# ---------------------------------------------------------------------------

def _load_members_json(group_id: str):
    """Load members JSON from local filesystem. Returns (data, last_crawled)."""
    cfg = _GROUP_CONFIG[group_id]
    filepath = os.path.join(
        Config.LOCAL_DATA_DIR,
        'vuddy', 'comprehensive_analysis',
        cfg['members_file'],
    )
    if not os.path.exists(filepath):
        return None, ''
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        ts_field = cfg['timestamp_field']
        last_crawled = data.get(ts_field, '') or data.get('timestamp', '') or data.get('updated_at', '')
        return data, last_crawled
    except Exception as e:
        logger.error("Error loading %s members data: %s", group_id, e, exc_info=True)
        return None, ''


def _process_country_stats_local(raw):
    """Normalise country_stats dict. Mirrors api_handlers._process_country_stats."""
    if not raw:
        return {}
    result = {}
    for key, value in raw.items():
        # Map legacy KR/US style keys to full names where needed; keep as-is otherwise
        result[key] = value
    return result


def _is_comment_within_cutoff(published_at: str, cutoff: datetime) -> bool:
    if not published_at:
        return True
    try:
        date_str = published_at.replace('Z', '+00:00')
        dt = datetime.fromisoformat(date_str)
        return dt.replace(tzinfo=None) >= cutoff
    except (ValueError, AttributeError):
        return True


def _build_comment_sample_bc(comment: dict) -> dict:
    video_id = comment.get('video_id', '')
    video_url = comment.get('video_url', '')
    if video_id and not video_url:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
    return {
        'text': comment.get('text', ''),
        'author': comment.get('author', '익명'),
        'like_count': comment.get('like_count', 0),
        'video_title': comment.get('video_title', ''),
        'video_id': video_id,
        'video_url': video_url,
        'sentiment': comment.get('sentiment', 'neutral'),
        'published_at': comment.get('published_at', comment.get('publishedAt', '')),
    }


def _process_comments_bc(creator_data: dict, cutoff: datetime) -> list:
    """Filter and normalise comment samples for group-b/c style."""
    samples = []
    for comment in creator_data.get('comment_samples', [])[:50]:
        pub = comment.get('published_at') or comment.get('publishedAt', '')
        if not _is_comment_within_cutoff(pub, cutoff):
            continue
        if is_timestamp_comment(comment.get('text', '')):
            continue
        samples.append(_build_comment_sample_bc(comment))
    return samples


def _normalize_video_id_url(video_id: str, video_url: str):
    """Simplified version of api_handlers._normalize_video_id_and_url."""
    if video_id and not video_url:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
    return video_id, video_url


def _calculate_sentiment_dist(sentiment_dist: dict) -> dict:
    total = sum(sentiment_dist.values()) if sentiment_dist else 0
    if total > 0:
        return {
            'positive': round(sentiment_dist.get('positive', 0) / total, 2),
            'negative': round(sentiment_dist.get('negative', 0) / total, 2),
            'neutral': round(sentiment_dist.get('neutral', 0) / total, 2),
        }
    return {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}


def _overall_sentiment(sentiment_dist: dict) -> str:
    if sentiment_dist:
        return max(sentiment_dist, key=sentiment_dist.get)
    return 'neutral'


# ---------------------------------------------------------------------------
# Members handlers (LOCAL_MODE)
# ---------------------------------------------------------------------------

def _build_creators_group_a(data: dict, last_crawled: str) -> list:
    creators = []
    for creator in data.get('creators', []):
        comment_samples = []
        for sample in creator.get('comment_samples', [])[:50]:
            vid_id, vid_url = _normalize_video_id_url(
                sample.get('video_id', '') or '',
                sample.get('video_url', ''),
            )
            comment_samples.append({
                'text': sample.get('text', ''),
                'author': sample.get('author', '익명'),
                'like_count': sample.get('likes', 0) or sample.get('like_count', 0),
                'video_title': sample.get('video_title', ''),
                'video_id': vid_id,
                'video_url': vid_url,
                'sentiment': sample.get('sentiment', 'neutral'),
                'published_at': sample.get('published_at', ''),
            })
        creator_info = {
            'name': creator.get('name', ''),
            'youtube_channel': creator.get('channel_handle', ''),
            'channel_title': creator.get('channel_title', ''),
            'total_comments': creator.get('total_comments', 0),
            'statistics': {'subscriberCount': creator.get('subscriber_count', 0)},
            'country_stats': {},
            'comment_samples': comment_samples,
            'video_links': [],
            'last_crawled': last_crawled,
            'analysis': {
                'sentiment': 'neutral',
                'sentiment_distribution': creator.get(
                    'sentiment_summary',
                    {'positive': 0.6, 'neutral': 0.3, 'negative': 0.1},
                ),
                'summary': f"총 {creator.get('total_comments', 0)}개의 댓글이 수집되었습니다.",
                'keywords': [],
                'overall_score': 50,
            },
        }
        creators.append(creator_info)
    return creators


def _build_creators_bc(data: dict, last_crawled: str) -> list:
    creators = []
    cutoff = datetime.now() - timedelta(days=14)
    for creator_data in data.get('creators', []):
        raw_country_stats = creator_data.get('country_stats', {})
        country_stats = _process_country_stats_local(raw_country_stats)

        creator_info = {
            'name': creator_data.get('name', ''),
            'youtube_channel': creator_data.get('youtube_channel', ''),
            'vuddy_channel': creator_data.get('vuddy_channel', ''),
            'total_comments': creator_data.get('total_comments', 0),
            'total_likes': creator_data.get('total_likes', 0),
            'total_blog_posts': creator_data.get('total_blog_posts', 0),
            'total_google_results': creator_data.get(
                'total_google_results',
                len(creator_data.get('google_links', [])),
            ),
            'youtube_search_status': 'success',
            'blog_search_status': 'success',
            'google_search_status': 'success',
            'comment_samples': _process_comments_bc(creator_data, cutoff),
            'video_links': [],
            'social_media': creator_data.get('social_media', []),
            'google_links': creator_data.get('google_links', []),
            'platform_links': creator_data.get('platform_links', []),
            'statistics': creator_data.get('statistics', {}),
            'country_stats': country_stats,
            'last_crawled': last_crawled,
        }

        for video in creator_data.get('video_links', [])[:10]:
            creator_info['video_links'].append({
                'title': video.get('title', ''),
                'url': video.get('url', ''),
                'channel': video.get('channel', creator_data.get('name', '')),
                'published_at': video.get('published_at', ''),
            })

        sentiment_dist = creator_data.get('sentiment_distribution', {})
        analysis_data = creator_data.get('analysis', {})
        creator_info['analysis'] = {
            'sentiment': _overall_sentiment(sentiment_dist),
            'sentiment_distribution': _calculate_sentiment_dist(sentiment_dist),
            'summary': analysis_data.get(
                'summary',
                f"총 {creator_info['total_comments']}개의 댓글이 수집되었습니다.",
            ),
            'keywords': analysis_data.get('keywords', []),
            'trends': analysis_data.get('trends', []),
            'insights': analysis_data.get('insights', []),
            'overall_score': creator_data.get('overall_score', 50),
            'analyzed_at': '',
        }
        creators.append(creator_info)
    return creators


def _handle_members_local(group_id: str) -> dict:
    """Build members response dict from local JSON."""
    data, last_crawled = _load_members_json(group_id)
    creators = []
    if data and 'creators' in data:
        cfg = _GROUP_CONFIG[group_id]
        if cfg['comment_style'] == 'a':
            creators = _build_creators_group_a(data, last_crawled)
        else:
            creators = _build_creators_bc(data, last_crawled)
        logger.info("Loaded %d %s members from JSON", len(creators), group_id)
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(
            {'creators': creators, 'last_crawled': last_crawled},
            default=decimal_default,
            ensure_ascii=False,
        ),
    }


# ---------------------------------------------------------------------------
# Channel handlers (LOCAL_MODE)
# ---------------------------------------------------------------------------

def _find_channel_files_local(youtube_dir: str, handle: str) -> list:
    """Scan youtube/channels dir for files matching the requested handle."""
    matches = []
    if not os.path.exists(youtube_dir):
        return matches
    for fname in os.listdir(youtube_dir):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(youtube_dir, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            ch = (data.get('channel_handle', '') or '').lower()
            if ch == handle.lower() or ch == handle.lstrip('@').lower():
                mtime = os.path.getmtime(fpath)
                matches.append((fpath, mtime, data))
        except Exception as e:
            logger.debug("Could not read channel file %s: %s", fpath, e)
    return matches


def _process_channel_videos(videos_list: list):
    videos = []
    total_comments = 0
    total_vtuber_comments = 0
    total_vtuber_likes = 0
    for video_info in (videos_list or []):
        if not isinstance(video_info, dict):
            continue
        video_data = video_info.get('video', {})
        video_comments = video_info.get('comments', [])
        vtuber_stats = video_info.get('vtuber_stats', {})
        videos.append({
            'video_id': video_data.get('video_id', '') or video_data.get('id', ''),
            'title': video_data.get('title', ''),
            'published_at': video_data.get('published_at', '') or video_data.get('publishedAt', ''),
            'view_count': video_data.get('view_count', 0) or video_data.get('viewCount', 0),
            'comments': video_comments,
            'vtuber_stats': vtuber_stats,
        })
        total_comments += len(video_comments)
        if vtuber_stats:
            total_vtuber_comments += vtuber_stats.get('total_vtuber_comments', 0)
            total_vtuber_likes += vtuber_stats.get('vtuber_total_likes', 0)
    return videos, total_comments, total_vtuber_comments, total_vtuber_likes


def _extract_channel_title(creator: dict) -> str:
    title = creator.get('channel_title', '')
    if not title:
        name = creator.get('name', '')
        title = name.split('(')[0].strip() if '(' in name else name
    return title


def _handle_channel_all_local(group_id: str, members_data) -> dict:
    """Return aggregated channel list when no specific handle is requested."""
    channels_data = []
    last_crawled = ''
    if members_data:
        last_crawled = (
            members_data.get('updated_at', '')
            or members_data.get('timestamp', '')
        )
        for creator in members_data.get('creators', []):
            channel_handle = (
                creator.get('channel_handle', '')
                or creator.get('youtube_channel', '')
            )
            channels_data.append({
                'channel_handle': channel_handle,
                'channel_title': _extract_channel_title(creator),
                'channel_thumbnail': creator.get('profile_image', ''),
                'subscriber_count': creator.get('subscriber_count', 0),
                'total_comments': creator.get('total_comments', 0),
                'total_videos': creator.get('total_videos', 0),
                'analysis_date': last_crawled,
                'videos': [],
                'comment_samples': creator.get('comment_samples', []),
            })
        logger.info("Loaded %d %s channels from JSON", len(channels_data), group_id)
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(
            {'channels': channels_data, 'last_crawled': last_crawled},
            default=decimal_default,
            ensure_ascii=False,
        ),
    }


def _handle_channel_all_group_a_local() -> dict:
    """Group A uses a separate channel-members file."""
    channels_data = []
    last_crawled = ''
    filepath = os.path.join(
        Config.LOCAL_DATA_DIR,
        'vuddy', 'comprehensive_analysis',
        'group-a-channel-members.json',
    )
    if not os.path.exists(filepath):
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'channels': [], 'last_crawled': ''}, ensure_ascii=False),
        }
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        last_crawled = data.get('updated_at', '') or data.get('timestamp', '')
        for creator in data.get('creators', []):
            channels_data.append({
                'channel_handle': creator.get('channel_handle', ''),
                'channel_title': creator.get('channel_title', creator.get('name', '')),
                'channel_thumbnail': creator.get('profile_image', ''),
                'subscriber_count': creator.get('subscriber_count', 0),
                'total_comments': creator.get('total_comments', 0),
                'total_videos': creator.get('total_videos', 0),
                'analysis_date': last_crawled or data.get('timestamp', ''),
                'videos': [],
                'comment_samples': creator.get('comment_samples', []),
            })
        logger.info("Loaded %d group-a channel members from JSON", len(channels_data))
    except Exception as e:
        logger.error("Error loading group-a channel members: %s", e, exc_info=True)
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(
            {'channels': channels_data, 'last_crawled': last_crawled},
            default=decimal_default,
            ensure_ascii=False,
        ),
    }


def _handle_channel_specific_local(group_id: str, requested_handle: str) -> dict:
    """Look up a specific channel handle in the local youtube/channels dir."""
    youtube_dir = os.path.join(Config.LOCAL_DATA_DIR, 'youtube', 'channels')
    matching = _find_channel_files_local(youtube_dir, requested_handle)
    channel_data = None
    if matching:
        matching.sort(key=lambda x: x[1], reverse=True)
        _, _, channel_data = matching[0]
        logger.info("Found channel data for %s in local dir", requested_handle)

    if group_id == 'group-a' and not channel_data:
        # Group A also triggers crawler
        _trigger_youtube_crawler(requested_handle)

    if channel_data:
        videos, total_comments, total_vtuber_comments, total_vtuber_likes = (
            _process_channel_videos(channel_data.get('videos', []))
        )
        last_crawled_date = (
            channel_data.get('timestamp', '')
            or channel_data.get('analysis_date', '')
        )
        result = {
            'channel_title': channel_data.get('channel_title', requested_handle),
            'channel_id': channel_data.get('channel_id', ''),
            'channel_handle': channel_data.get('channel_handle', requested_handle),
            'videos': videos,
            'total_comments': total_comments,
            'total_vtuber_comments': total_vtuber_comments,
            'total_vtuber_likes': total_vtuber_likes,
            'statistics': channel_data.get('statistics', {}),
            'last_crawled': last_crawled_date,
        }
    else:
        result = {
            'channel_title': requested_handle.replace('@', ''),
            'channel_id': '',
            'channel_handle': requested_handle,
            'videos': [],
            'total_comments': 0,
            'total_vtuber_comments': 0,
            'total_vtuber_likes': 0,
            'statistics': {},
            'last_crawled': '',
        }
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(result, default=decimal_default, ensure_ascii=False),
    }


def _trigger_youtube_crawler(requested_handle: str) -> None:
    """Fire-and-forget YouTube crawler trigger."""
    try:
        import requests as req_lib
    except ImportError:
        logger.warning("requests module not available, cannot trigger crawler")
        return
    try:
        url = os.environ.get('YOUTUBE_CRAWLER_ENDPOINT', 'http://youtube-crawler:5000/invoke')
        req_lib.post(
            url,
            json={
                'type': 'channel',
                'channels': [requested_handle],
                'max_videos': 10,
                'max_comments_per_video': 100,
            },
            timeout=5,
        )
        logger.info("Triggered YouTube crawler for %s", requested_handle)
    except Exception as e:
        logger.error("Error triggering YouTube crawler for %s: %s", requested_handle, e, exc_info=True)


def _handle_channel_local(group_id: str) -> dict:
    """Unified local channel handler."""
    query_params = dict(request.args) if request.args else {}
    requested_handle = query_params.get('channel_handle') or query_params.get('channel', '')

    if not requested_handle:
        if group_id == 'group-a':
            return _handle_channel_all_group_a_local()
        # group-b / group-c: aggregate from members JSON
        members_data, _ = _load_members_json(group_id)
        return _handle_channel_all_local(group_id, members_data)

    if not requested_handle.startswith('@'):
        requested_handle = '@' + requested_handle
    logger.debug("%s - Requested channel handle: %s", group_id, requested_handle)
    return _handle_channel_specific_local(group_id, requested_handle)


# ---------------------------------------------------------------------------
# Route factories
# ---------------------------------------------------------------------------

def _make_members_view(group_id: str):
    @limiter.limit("60 per minute")
    def view():
        if not Config.LOCAL_MODE:
            return jsonify({"error": "S3 mode not supported. Set LOCAL_MODE=true"}), 501
        try:
            result = _handle_members_local(group_id)
            return Response(
                result['body'],
                status=result.get('statusCode', 200),
                content_type='application/json',
            )
        except Exception as e:
            logger.error("Error in %s members handler: %s", group_id, e, exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500
    view.__name__ = f"{group_id.replace('-', '_')}_members"
    return view


def _make_channel_view(group_id: str):
    @limiter.limit("60 per minute")
    def view():
        if not Config.LOCAL_MODE:
            return jsonify({"error": "S3 mode not supported. Set LOCAL_MODE=true"}), 501
        try:
            result = _handle_channel_local(group_id)
            return Response(
                result['body'],
                status=result.get('statusCode', 200),
                content_type='application/json',
            )
        except Exception as e:
            logger.error("Error in %s channel handler: %s", group_id, e, exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500
    view.__name__ = f"{group_id.replace('-', '_')}_channel"
    return view


# Register routes for all three groups
for _gid in _GROUP_CONFIG:
    members_bp.add_url_rule(
        f'/api/{_gid}/members',
        endpoint=f'{_gid.replace("-", "_")}_members',
        view_func=_make_members_view(_gid),
        methods=['GET'],
    )
    members_bp.add_url_rule(
        f'/api/{_gid}/channel',
        endpoint=f'{_gid.replace("-", "_")}_channel',
        view_func=_make_channel_view(_gid),
        methods=['GET'],
    )
