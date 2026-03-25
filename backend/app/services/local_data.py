"""
Shared data access utilities for local filesystem and JSON handling.

Extracted from api_handlers.py to be reusable by Blueprint modules.
"""

import glob
import json
import logging
import os
import re
from datetime import datetime
from decimal import Decimal

from ..config import Config

logger = logging.getLogger(__name__)


def decimal_default(obj):
    """Decimal to JSON-serializable type."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def convert_decimal(obj):
    """Recursively convert Decimal values in dicts/lists."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal(item) for item in obj]
    return obj


def load_metadata_files_local(metadata_dir=None):
    """Load metadata JSON files from local data directory."""
    if metadata_dir is None:
        metadata_dir = os.path.join(Config.LOCAL_DATA_DIR, 'metadata')
    items = []
    if not os.path.exists(metadata_dir):
        return items

    for platform_dir in os.listdir(metadata_dir):
        platform_path = os.path.join(metadata_dir, platform_dir)
        if not os.path.isdir(platform_path):
            continue

        for filename in os.listdir(platform_path):
            if not filename.endswith('.json'):
                continue

            filepath = os.path.join(platform_path, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    item = json.load(f)
                    items.append(item)
            except Exception as e:
                logger.error("Error loading metadata file %s: %s", filepath, e, exc_info=True)

    return items


def parse_timestamp_for_today(timestamp_str, today_start):
    """Parse timestamp and check if it is from today."""
    if not timestamp_str:
        return False

    try:
        if 'T' in timestamp_str:
            item_date = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if item_date.tzinfo:
                item_date = item_date.replace(tzinfo=None)
        else:
            item_date = datetime.strptime(timestamp_str[:19], '%Y-%m-%d %H:%M:%S')

        return item_date >= today_start
    except (ValueError, TypeError):
        return False


def load_channels_from_local(youtube_dir=None):
    """Load YouTube channel list from local data directory."""
    if youtube_dir is None:
        youtube_dir = os.path.join(Config.LOCAL_DATA_DIR, 'youtube')
    channels = []
    if not os.path.exists(youtube_dir):
        return channels

    search_dirs = [
        youtube_dir,
        os.path.join(youtube_dir, 'channels'),
    ]
    seen = set()
    for base_dir in search_dirs:
        if not os.path.isdir(base_dir):
            continue
        for file_path in glob.glob(os.path.join(base_dir, '**', '*.json'), recursive=True):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                channel_id = data.get('channel_handle') or data.get('channel_id') or data.get('channel', '')
                channel_title = data.get('channel_title', '') or channel_id
                if not channel_id and not channel_title:
                    continue
                key = (channel_id or channel_title).strip()
                if key in seen:
                    continue
                seen.add(key)
                videos = data.get('videos', [])
                total_comments = 0
                for v in videos:
                    raw = v.get('comments') or v.get('comment_count') or 0
                    total_comments += int(raw) if raw else 0
                channels.append({
                    'channel': channel_id or channel_title,
                    'channel_title': channel_title or channel_id,
                    'videos_analyzed': len(videos),
                    'total_comments': total_comments,
                    'vtuber_comments': 0,
                    'vtuber_likes': 0,
                    's3_key': '',
                    'last_updated': data.get('last_updated', data.get('timestamp', '')),
                })
            except Exception as e:
                logger.debug("Skip non-channel JSON %s: %s", file_path, e)
    return channels


def is_timestamp_comment(text):
    """Check if a comment is a timestamp list (song list, chapters)."""
    if not text:
        return False

    timestamp_pattern = r'\d{1,2}:\d{2}(?::\d{2})?'
    timestamps = re.findall(timestamp_pattern, text)
    if len(timestamps) >= 3:
        return True

    lines = text.strip().split('\n')
    if len(lines) < 3:
        return False

    timestamp_lines = sum(1 for line in lines if re.match(r'^\s*\d{1,2}:\d{2}', line.strip()))
    return timestamp_lines >= 3
