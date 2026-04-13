"""
Dashboard API routes.
Migrated handlers use local_data service directly.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

from flask import jsonify, request

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
    """Dashboard statistics with caching (Redis or in-memory, 5-min TTL)."""
    global _stats_cache
    cache_key = 'sns-monitor:dashboard:stats'

    # Try Redis cache first
    redis_client = get_redis()
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return jsonify(json.loads(cached))
        except Exception as e:
            logger.debug("Redis cache read failed for stats: %s", e)

    # Try in-memory cache
    now = time.time()
    if _stats_cache['data'] and now < _stats_cache['expires']:
        return jsonify(_stats_cache['data'])

    # Compute fresh stats
    stats = {
        'total_items': 0, 'today_items': 0, 'analyzed_items': 0,
        'total_comments': 0, 'avg_sentiment': 'neutral',
    }
    try:
        stats = _compute_stats()
    except Exception as e:
        logger.error("Error getting stats: %s", e, exc_info=True)

    # Store in caches
    _stats_cache = {'data': stats, 'expires': now + _STATS_TTL}
    if redis_client:
        try:
            redis_client.setex(cache_key, _STATS_TTL, json.dumps(stats))
        except Exception as e:
            logger.debug("Redis cache write failed for stats: %s", e)

    return jsonify(stats)


@dashboard_bp.route('/api/channels', methods=['GET'])
@limiter.limit("60 per minute")
def channels():
    """Channel list — migrated from api_handlers."""
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
    """Scan list with pagination and optional platform filter.

    Query params:
        page (int): Page number, 1-based (default: 1)
        limit (int): Items per page, max 200 (default: 50)
        platform (str): Filter by platform name (optional)
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
