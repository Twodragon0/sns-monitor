"""
Dashboard API routes.
Migrated handlers use local_data service directly.
Remaining handlers delegate to legacy api_handlers.
"""

import json
import logging
import os
from datetime import datetime, timezone

from flask import jsonify

from . import dashboard_bp
from .legacy_helpers import safe_legacy_call
from ..config import Config
from ..services.local_data import (
    load_metadata_files_local,
    parse_timestamp_for_today,
    load_channels_from_local,
    convert_item_to_scan,
    decimal_default,
)

logger = logging.getLogger(__name__)


@dashboard_bp.route('/api/dashboard/stats', methods=['GET'])
@safe_legacy_call
def dashboard_stats():
    """Dashboard statistics — migrated from api_handlers."""
    stats = {
        'total_items': 0,
        'today_items': 0,
        'analyzed_items': 0,
        'total_comments': 0,
        'avg_sentiment': 'neutral',
    }

    try:
        metadata_dir = os.path.join(Config.LOCAL_DATA_DIR, 'metadata')
        items = load_metadata_files_local(metadata_dir)

        today = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today, datetime.min.time())

        total_items = len(items)
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

        stats = {
            'total_items': total_items,
            'today_items': today_items,
            'analyzed_items': analyzed_items,
            'total_comments': total_comments,
            'avg_sentiment': 'neutral',
        }
    except Exception as e:
        logger.error("Error getting stats: %s", e, exc_info=True)

    return jsonify(stats)


@dashboard_bp.route('/api/channels', methods=['GET'])
@safe_legacy_call
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
@safe_legacy_call
def scans():
    """Scan list — migrated from api_handlers._handle_scans (LOCAL_MODE path)."""
    try:
        metadata_dir = os.path.join(Config.LOCAL_DATA_DIR, 'metadata')
        items = load_metadata_files_local(metadata_dir)
        items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        items = items[:100]

        scan_list = [convert_item_to_scan(item) for item in items]
        scan_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    except Exception as e:
        logger.error("Error getting scans: %s", e, exc_info=True)
        scan_list = []

    return jsonify({'scans': scan_list})


# Group members and channel routes are now handled by members_bp (app/api/members.py).
