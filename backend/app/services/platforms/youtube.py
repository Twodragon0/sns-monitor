"""YouTube platform analyzer mixin."""
import os
import re
import logging
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class YouTubeMixin:
    """YouTube video and channel analysis methods."""

    def _analyze_youtube(self, url):
        """Analyze YouTube video or channel."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Extract video ID
        video_id = None
        if "v" in params:
            video_id = params["v"][0]
        elif parsed.hostname and "youtu.be" in parsed.hostname:
            video_id = parsed.path.strip("/")

        # Extract channel handle
        channel_handle = None
        if "/@" in url or "/@" in parsed.path:
            match = re.search(r"/@([^/?]+)", url)
            if match:
                channel_handle = f"@{match.group(1)}"

        api_key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
        # Reject placeholder so we never send it to Google or leak it in errors
        if not api_key or api_key.lower() in (
            "your_youtube_api_key_here",
            "your-youtube-api-key",
            "",
        ):
            raise ValueError(
                "YouTube API key is not configured. Set YOUTUBE_API_KEY in .env with a key from "
                "https://console.cloud.google.com/apis/credentials"
            )

        if video_id:
            return self._analyze_youtube_video(video_id, api_key)
        elif channel_handle:
            return self._analyze_youtube_channel(channel_handle, api_key)
        else:
            raise ValueError("Could not extract video ID or channel handle from URL")

    # YouTube Data API v3 quota costs per endpoint
    _YT_QUOTA_COSTS = {
        "/search": 100,
        "/commentThreads": 1,
        "/videos": 1,
        "/channels": 1,
    }

    def _youtube_api_get(self, url, **kwargs):
        """YouTube API GET with weighted quota tracking."""
        cost = 1
        for endpoint, c in self._YT_QUOTA_COSTS.items():
            if endpoint in url:
                cost = c
                break
        for _ in range(cost):
            self._rate_incr("youtube")
        return self._session.get(url, **kwargs)

    def _analyze_youtube_video(self, video_id, api_key):
        """Fetch video info and comments."""
        base = "https://www.googleapis.com/youtube/v3"

        # Get video details
        resp = self._youtube_api_get(
            f"{base}/videos",
            params={
                "part": "snippet,statistics",
                "id": video_id,
                "key": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            raise ValueError(f"Video not found: {video_id}")

        video = items[0]
        snippet = video["snippet"]
        stats = video.get("statistics", {})

        # Get comments
        comments = []
        try:
            resp = self._youtube_api_get(
                f"{base}/commentThreads",
                params={
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": 100,
                    "order": "relevance",
                    "textFormat": "plainText",
                    "key": api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            for item in resp.json().get("items", []):
                comment = item["snippet"]["topLevelComment"]["snippet"]
                comments.append(
                    {
                        "text": comment.get("textDisplay", ""),
                        "author": comment.get("authorDisplayName", ""),
                        "like_count": comment.get("likeCount", 0),
                        "published_at": comment.get("publishedAt", ""),
                        "video_id": video_id,
                        "video_title": snippet.get("title", ""),
                    }
                )
        except Exception as e:
            logger.warning("Failed to fetch comments for %s: %s", video_id, e)

        return {
            "type": "video",
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "description": snippet.get("description", "")[:500],
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "comments": comments,
        }

    def _analyze_youtube_channel(self, channel_handle, api_key):
        """Fetch channel info and recent videos."""
        base = "https://www.googleapis.com/youtube/v3"
        handle = channel_handle.lstrip("@")

        # Get channel by handle
        resp = self._youtube_api_get(
            f"{base}/channels",
            params={
                "part": "snippet,statistics",
                "forHandle": handle,
                "key": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            raise ValueError(f"Channel not found: {channel_handle}")

        channel = items[0]
        stats = channel.get("statistics", {})

        # Get recent videos
        videos = []
        try:
            resp = self._youtube_api_get(
                f"{base}/search",
                params={
                    "part": "snippet",
                    "channelId": channel["id"],
                    "order": "date",
                    "maxResults": 10,
                    "type": "video",
                    "key": api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            for item in resp.json().get("items", []):
                videos.append(
                    {
                        "video_id": item["id"].get("videoId", ""),
                        "title": item["snippet"].get("title", ""),
                        "published_at": item["snippet"].get("publishedAt", ""),
                        "thumbnail": item["snippet"]
                        .get("thumbnails", {})
                        .get("medium", {})
                        .get("url", ""),
                    }
                )
        except Exception as e:
            logger.warning("Failed to fetch videos for %s: %s", channel_handle, e)

        # Optionally fetch comments for recent videos (channel-level comment view)
        comments = []
        # Limit to first N videos to avoid excessive API calls
        for video in videos[:5]:
            video_id = video.get("video_id")
            if not video_id:
                continue
            try:
                resp = self._youtube_api_get(
                    f"{base}/commentThreads",
                    params={
                        "part": "snippet",
                        "videoId": video_id,
                        "maxResults": 50,
                        "order": "relevance",
                        "textFormat": "plainText",
                        "key": api_key,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                for item in resp.json().get("items", []):
                    snippet = item["snippet"]["topLevelComment"]["snippet"]
                    comments.append(
                        {
                            "text": snippet.get("textDisplay", ""),
                            "author": snippet.get("authorDisplayName", ""),
                            "like_count": snippet.get("likeCount", 0),
                            "published_at": snippet.get("publishedAt", ""),
                            "video_id": video_id,
                            "video_title": video.get("title", ""),
                        }
                    )
            except Exception as e:
                logger.warning(
                    "Failed to fetch comments for channel %s video %s: %s",
                    channel_handle,
                    video_id,
                    e,
                )

        return {
            "type": "channel",
            "title": channel["snippet"].get("title", ""),
            "description": channel["snippet"].get("description", "")[:500],
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "thumbnail": channel["snippet"]
            .get("thumbnails", {})
            .get("high", {})
            .get("url", ""),
            "recent_videos": videos,
            # Aggregate collected comments across recent videos so frontend can
            # render channel-level comment list and sentiment analysis.
            "comment_count": len(comments),
            "comments": comments,
        }
