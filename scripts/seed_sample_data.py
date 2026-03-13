#!/usr/bin/env python3
"""
Seed sample data for sns-monitor local development.

Usage:
    python scripts/seed_sample_data.py          # skip existing files
    python scripts/seed_sample_data.py --force  # overwrite existing files
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Resolve project root relative to this script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DATA_DIR = PROJECT_ROOT / "local-data"


def write_json(path: Path, data: dict, force: bool) -> bool:
    """Write JSON to path. Returns True if written, False if skipped."""
    if path.exists() and not force:
        print(f"  SKIP (exists): {path.relative_to(PROJECT_ROOT)}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  WRITE: {path.relative_to(PROJECT_ROOT)}")
    return True


def youtube_channel_1() -> dict:
    """Sample YouTube channel - ExampleCreator."""
    base_date = datetime(2025, 1, 10, 15, 0, 0)
    return {
        "channel_id": "UCxxxxExampleCreator1",
        "channel_handle": "@example-creator-1",
        "channel_title": "ExampleCreator",
        "statistics": {
            "subscriberCount": 150000,
            "viewCount": 5000000,
            "videoCount": 120,
        },
        "timestamp": "2025-01-15T12:00:00Z",
        "videos": [
            {
                "video": {
                    "video_id": "example_video_001",
                    "title": "ExampleCreator - Sample Video 1",
                    "published_at": (base_date).isoformat() + "Z",
                    "view_count": 125000,
                    "like_count": 8500,
                },
                "comments": [
                    {
                        "text": "Great content! Love this video.",
                        "author": "user1",
                        "like_count": 42,
                        "published_at": (base_date + timedelta(hours=1)).isoformat() + "Z",
                        "sentiment": "positive",
                        "video_id": "example_video_001",
                    },
                    {
                        "text": "Love the editing style",
                        "author": "user2",
                        "like_count": 35,
                        "published_at": (base_date + timedelta(hours=2)).isoformat() + "Z",
                        "sentiment": "positive",
                        "video_id": "example_video_001",
                    },
                    {
                        "text": "Amazing video, keep it up!",
                        "author": "user3",
                        "like_count": 28,
                        "published_at": (base_date + timedelta(hours=19)).isoformat() + "Z",
                        "sentiment": "positive",
                        "video_id": "example_video_001",
                    },
                ],
                "vtuber_stats": {
                    "total_vtuber_comments": 3,
                    "vtuber_total_likes": 105,
                },
                "content": "Sample video content description for video 1.",
            },
            {
                "video": {
                    "video_id": "example_video_002",
                    "title": "ExampleCreator - Sample Video 2",
                    "published_at": datetime(2025, 1, 5, 14, 0, 0).isoformat() + "Z",
                    "view_count": 89000,
                    "like_count": 6200,
                },
                "comments": [
                    {
                        "text": "Keep it up!",
                        "author": "user4",
                        "like_count": 15,
                        "published_at": datetime(2025, 1, 5, 16, 0, 0).isoformat() + "Z",
                        "sentiment": "positive",
                        "video_id": "example_video_002",
                    }
                ],
                "vtuber_stats": {
                    "total_vtuber_comments": 1,
                    "vtuber_total_likes": 15,
                },
                "content": "Sample video content description for video 2.",
            },
        ],
    }


def youtube_channel_2() -> dict:
    """Sample YouTube channel - Creator2."""
    pub_date = datetime(2025, 1, 12, 18, 0, 0)
    return {
        "channel_id": "UCxxxxCreator2",
        "channel_handle": "@example-creator-2",
        "channel_title": "Creator2",
        "statistics": {
            "subscriberCount": 280000,
            "viewCount": 12000000,
            "videoCount": 250,
        },
        "timestamp": "2025-01-15T12:00:00Z",
        "videos": [
            {
                "video": {
                    "video_id": "example_video_003",
                    "title": "Creator2 - Latest Content",
                    "published_at": pub_date.isoformat() + "Z",
                    "view_count": 210000,
                    "like_count": 15000,
                },
                "comments": [
                    {
                        "text": "Best creator ever! Absolutely love the content.",
                        "author": "fan1",
                        "like_count": 120,
                        "published_at": (pub_date + timedelta(hours=1)).isoformat() + "Z",
                        "sentiment": "positive",
                        "video_id": "example_video_003",
                    },
                    {
                        "text": "Just subscribed! Can't believe I missed this channel.",
                        "author": "fan2",
                        "like_count": 45,
                        "published_at": (pub_date + timedelta(hours=2)).isoformat() + "Z",
                        "sentiment": "positive",
                        "video_id": "example_video_003",
                    },
                ],
                "vtuber_stats": {
                    "total_vtuber_comments": 2,
                    "vtuber_total_likes": 165,
                },
                "content": "Latest video from Creator2 - high quality content showcase.",
            }
        ],
    }


def dcinside_gallery(gallery_id: str, gallery_name: str, crawled_at: str) -> dict:
    """Sample DCInside gallery data file."""
    return {
        "gallery_id": gallery_id,
        "gallery_name": gallery_name,
        "crawled_at": crawled_at,
        "keywords": ["sample", "content", "discussion"],
        "total_comments": 35,
        "positive_count": 22,
        "negative_count": 3,
        "data": [
            {
                "post": {
                    "post_id": f"{gallery_id}-1001",
                    "title": "Sample Discussion Post",
                    "author": "anonymous",
                    "date": "2025-01-15T10:30:00",
                    "view_count": 450,
                    "recommend_count": 12,
                    "comment_count": 8,
                    "url": f"https://example.com/gallery/{gallery_id}/1001",
                    "matched_keyword": "sample",
                },
                "content": "This is a sample post body. Discussion about the latest content and community updates.",
                "comments": [
                    {"text": "Great post!", "author": "user_a", "sentiment": "positive"},
                    {"text": "Agreed, very informative.", "author": "user_b", "sentiment": "positive"},
                ],
            },
            {
                "post": {
                    "post_id": f"{gallery_id}-1002",
                    "title": "Another Community Post",
                    "author": "user123",
                    "date": "2025-01-14T22:15:00",
                    "view_count": 320,
                    "recommend_count": 8,
                    "comment_count": 5,
                    "url": f"https://example.com/gallery/{gallery_id}/1002",
                    "matched_keyword": "content",
                },
                "content": "Community post discussing recent events and upcoming schedules.",
                "comments": [
                    {"text": "Thanks for sharing!", "author": "user_c", "sentiment": "positive"},
                ],
            },
            {
                "post": {
                    "post_id": f"{gallery_id}-1003",
                    "title": "Fan Art Showcase",
                    "author": "artist99",
                    "date": "2025-01-14T18:00:00",
                    "view_count": 890,
                    "recommend_count": 45,
                    "comment_count": 22,
                    "url": f"https://example.com/gallery/{gallery_id}/1003",
                    "matched_keyword": "discussion",
                },
                "content": "Showcasing fan art from the community. Amazing talent on display!",
                "comments": [
                    {"text": "Beautiful work!", "author": "fan_x", "sentiment": "positive"},
                    {"text": "Wow, so talented!", "author": "fan_y", "sentiment": "positive"},
                    {"text": "This is incredible art.", "author": "fan_z", "sentiment": "positive"},
                ],
            },
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Seed sample data for sns-monitor local dev")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    args = parser.parse_args()

    force = args.force
    written = 0
    skipped = 0

    print(f"Seeding sample data into: {LOCAL_DATA_DIR}")
    print(f"Force overwrite: {force}")
    print()

    # --- YouTube channels ---
    print("[YouTube channels]")
    channels_dir = LOCAL_DATA_DIR / "youtube" / "channels"

    result = write_json(channels_dir / "example-creator-1.json", youtube_channel_1(), force)
    written += result
    skipped += not result

    result = write_json(channels_dir / "example-creator-2.json", youtube_channel_2(), force)
    written += result
    skipped += not result

    print()

    # --- DCInside galleries ---
    # File naming convention: YYYY-MM-DD-HH-MM-SS.json (sorted descending = latest first)
    crawled_at = "2025-01-15T12:00:00"
    file_ts = "2025-01-15-12-00-00"

    print("[DCInside galleries]")
    galleries = [
        ("example-gallery-1", "Example Gallery 1"),
        ("example-gallery-2", "Example Gallery 2"),
    ]
    for gallery_id, gallery_name in galleries:
        gallery_dir = LOCAL_DATA_DIR / "dcinside" / gallery_id
        data = dcinside_gallery(gallery_id, gallery_name, crawled_at)
        result = write_json(gallery_dir / f"{file_ts}.json", data, force)
        written += result
        skipped += not result

    print()
    print(f"Done. {written} file(s) written, {skipped} file(s) skipped.")
    if skipped and not force:
        print("Run with --force to overwrite existing files.")


if __name__ == "__main__":
    main()
