"""Tests for YouTube video and channel analysis."""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.services.platform_analyzer import PlatformAnalyzer


@pytest.fixture()
def analyzer():
    with patch.dict(
        "os.environ",
        {"YOUTUBE_API_KEY": "test_api_key", "REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""},
    ):
        pa = PlatformAnalyzer()
    return pa


def _json_response(data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.ok = status < 400
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


# ── URL parsing ────────────────────────────────────────────────


class TestYouTubeURLParsing:
    def test_raises_without_api_key(self):
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "", "REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}):
            pa = PlatformAnalyzer()
            with pytest.raises(ValueError, match="YouTube API key"):
                pa._analyze_youtube("https://www.youtube.com/watch?v=abc123")

    def test_raises_for_placeholder_key(self):
        with patch.dict(
            "os.environ",
            {"YOUTUBE_API_KEY": "your_youtube_api_key_here", "REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""},
        ):
            pa = PlatformAnalyzer()
            with pytest.raises(ValueError, match="YouTube API key"):
                pa._analyze_youtube("https://www.youtube.com/watch?v=abc123")

    def test_raises_for_unrecognized_url(self, analyzer):
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "test_api_key"}):
            with pytest.raises(ValueError, match="Could not extract"):
                analyzer._analyze_youtube("https://www.youtube.com/feed/trending")

    def test_extracts_video_id_from_watch(self, analyzer):
        analyzer._analyze_youtube_video = MagicMock(return_value={"type": "video"})
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "test_api_key"}):
            analyzer._analyze_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        analyzer._analyze_youtube_video.assert_called_once_with("dQw4w9WgXcQ", "test_api_key")

    def test_extracts_video_id_from_youtu_be(self, analyzer):
        analyzer._analyze_youtube_video = MagicMock(return_value={"type": "video"})
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "test_api_key"}):
            analyzer._analyze_youtube("https://youtu.be/dQw4w9WgXcQ")
        analyzer._analyze_youtube_video.assert_called_once_with("dQw4w9WgXcQ", "test_api_key")

    def test_extracts_channel_handle(self, analyzer):
        analyzer._analyze_youtube_channel = MagicMock(return_value={"type": "channel"})
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "test_api_key"}):
            analyzer._analyze_youtube("https://www.youtube.com/@TestChannel")
        analyzer._analyze_youtube_channel.assert_called_once_with("@TestChannel", "test_api_key")


# ── Video analysis ─────────────────────────────────────────────


class TestYouTubeVideoAnalysis:
    def test_returns_video_data(self, analyzer):
        video_resp = _json_response({
            "items": [{
                "snippet": {
                    "title": "Test Video",
                    "channelTitle": "Test Channel",
                    "publishedAt": "2024-01-01T00:00:00Z",
                    "description": "A test video description",
                    "thumbnails": {"high": {"url": "https://img.youtube.com/thumb.jpg"}},
                },
                "statistics": {"viewCount": "1000", "likeCount": "50", "commentCount": "10"},
            }]
        })
        comment_resp = _json_response({
            "items": [{
                "snippet": {
                    "topLevelComment": {
                        "snippet": {
                            "textDisplay": "Great video!",
                            "authorDisplayName": "User1",
                            "likeCount": 5,
                            "publishedAt": "2024-01-02T00:00:00Z",
                        }
                    }
                }
            }]
        })
        analyzer._session.get = MagicMock(side_effect=[video_resp, comment_resp])

        result = analyzer._analyze_youtube_video("abc123", "key")

        assert result["type"] == "video"
        assert result["title"] == "Test Video"
        assert result["view_count"] == 1000
        assert result["like_count"] == 50
        assert len(result["comments"]) == 1
        assert result["comments"][0]["text"] == "Great video!"

    def test_video_not_found(self, analyzer):
        analyzer._session.get = MagicMock(return_value=_json_response({"items": []}))
        with pytest.raises(ValueError, match="Video not found"):
            analyzer._analyze_youtube_video("bad_id", "key")

    def test_comments_failure_does_not_break_video(self, analyzer):
        video_resp = _json_response({
            "items": [{
                "snippet": {
                    "title": "Test",
                    "channelTitle": "Ch",
                    "publishedAt": "",
                    "description": "",
                    "thumbnails": {},
                },
                "statistics": {},
            }]
        })
        analyzer._session.get = MagicMock(side_effect=[video_resp, Exception("comment API down")])

        result = analyzer._analyze_youtube_video("vid1", "key")

        assert result["type"] == "video"
        assert result["comments"] == []

    def test_description_truncated_to_500_chars(self, analyzer):
        long_desc = "A" * 1000
        video_resp = _json_response({
            "items": [{
                "snippet": {
                    "title": "T",
                    "channelTitle": "C",
                    "publishedAt": "",
                    "description": long_desc,
                    "thumbnails": {},
                },
                "statistics": {},
            }]
        })
        comment_resp = _json_response({"items": []})
        analyzer._session.get = MagicMock(side_effect=[video_resp, comment_resp])

        result = analyzer._analyze_youtube_video("vid1", "key")

        assert len(result["description"]) == 500


# ── Channel analysis ────────────────────────────────────────────


class TestYouTubeChannelAnalysis:
    def _channel_resp(self, channel_id="UC_test123"):
        return _json_response({
            "items": [{
                "id": channel_id,
                "snippet": {
                    "title": "Test Channel",
                    "description": "Channel description",
                    "thumbnails": {"high": {"url": "https://img.youtube.com/channel_thumb.jpg"}},
                },
                "statistics": {
                    "subscriberCount": "50000",
                    "videoCount": "200",
                    "viewCount": "5000000",
                },
            }]
        })

    def _search_resp(self, video_ids=None):
        if video_ids is None:
            video_ids = ["vid1", "vid2"]
        items = [
            {
                "id": {"videoId": vid},
                "snippet": {
                    "title": f"Video {vid}",
                    "publishedAt": "2024-01-01T00:00:00Z",
                    "thumbnails": {"medium": {"url": f"https://img.youtube.com/{vid}.jpg"}},
                },
            }
            for vid in video_ids
        ]
        return _json_response({"items": items})

    def _comment_thread_resp(self, texts=None):
        if texts is None:
            texts = ["Nice!", "Great!"]
        items = [
            {
                "snippet": {
                    "topLevelComment": {
                        "snippet": {
                            "textDisplay": t,
                            "authorDisplayName": f"User_{i}",
                            "likeCount": i,
                            "publishedAt": "2024-01-02T00:00:00Z",
                        }
                    }
                }
            }
            for i, t in enumerate(texts)
        ]
        return _json_response({"items": items})

    def test_returns_channel_data(self, analyzer):
        channel_resp = self._channel_resp()
        search_resp = self._search_resp(["vid1"])
        comment_resp = self._comment_thread_resp(["Hello!"])
        analyzer._session.get = MagicMock(
            side_effect=[channel_resp, search_resp, comment_resp]
        )

        result = analyzer._analyze_youtube_channel("@TestChannel", "key")

        assert result["type"] == "channel"
        assert result["title"] == "Test Channel"
        assert result["subscriber_count"] == 50000
        assert result["video_count"] == 200
        assert result["view_count"] == 5000000
        assert len(result["recent_videos"]) == 1
        assert result["recent_videos"][0]["video_id"] == "vid1"

    def test_channel_not_found_raises(self, analyzer):
        analyzer._session.get = MagicMock(return_value=_json_response({"items": []}))
        with pytest.raises(ValueError, match="Channel not found"):
            analyzer._analyze_youtube_channel("@NonExistent", "key")

    def test_channel_with_multiple_videos_and_comments(self, analyzer):
        channel_resp = self._channel_resp()
        # 3 videos in search
        search_resp = self._search_resp(["v1", "v2", "v3"])
        # comment responses for each video
        cmt1 = self._comment_thread_resp(["Good"])
        cmt2 = self._comment_thread_resp(["Bad"])
        cmt3 = self._comment_thread_resp(["OK"])
        analyzer._session.get = MagicMock(
            side_effect=[channel_resp, search_resp, cmt1, cmt2, cmt3]
        )

        result = analyzer._analyze_youtube_channel("@Chan", "key")

        assert result["type"] == "channel"
        assert len(result["recent_videos"]) == 3
        assert result["comment_count"] == 3
        assert len(result["comments"]) == 3

    def test_search_failure_returns_empty_videos(self, analyzer):
        channel_resp = self._channel_resp()
        analyzer._session.get = MagicMock(
            side_effect=[channel_resp, Exception("search API down")]
        )

        result = analyzer._analyze_youtube_channel("@Chan", "key")

        assert result["type"] == "channel"
        assert result["recent_videos"] == []
        assert result["comments"] == []

    def test_comment_fetch_failure_skips_video(self, analyzer):
        channel_resp = self._channel_resp()
        search_resp = self._search_resp(["v1", "v2"])
        cmt_ok = self._comment_thread_resp(["Good"])
        # Second video's comment fetch fails
        analyzer._session.get = MagicMock(
            side_effect=[channel_resp, search_resp, cmt_ok, Exception("comment fail")]
        )

        result = analyzer._analyze_youtube_channel("@Chan", "key")

        assert result["type"] == "channel"
        # Only comments from v1 collected
        assert result["comment_count"] == 1

    def test_video_without_video_id_skipped(self, analyzer):
        """Videos with empty video_id should be skipped in comment fetching."""
        channel_resp = self._channel_resp()
        # Search returns item with no videoId
        search_resp = _json_response({
            "items": [{
                "id": {},  # no videoId key
                "snippet": {
                    "title": "No ID Video",
                    "publishedAt": "",
                    "thumbnails": {},
                },
            }]
        })
        analyzer._session.get = MagicMock(side_effect=[channel_resp, search_resp])

        result = analyzer._analyze_youtube_channel("@Chan", "key")

        assert result["type"] == "channel"
        assert result["comments"] == []

    def test_description_truncated_to_500_chars(self, analyzer):
        long_desc = "B" * 1000
        channel_resp = _json_response({
            "items": [{
                "id": "UC_test",
                "snippet": {
                    "title": "Ch",
                    "description": long_desc,
                    "thumbnails": {},
                },
                "statistics": {},
            }]
        })
        search_resp = _json_response({"items": []})
        analyzer._session.get = MagicMock(side_effect=[channel_resp, search_resp])

        result = analyzer._analyze_youtube_channel("@Ch", "key")

        assert len(result["description"]) == 500

    def test_analyze_youtube_dispatches_to_channel(self, analyzer):
        analyzer._analyze_youtube_channel = MagicMock(return_value={"type": "channel"})
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "test_api_key"}):
            analyzer._analyze_youtube("https://www.youtube.com/@SomeChannel/videos")
        analyzer._analyze_youtube_channel.assert_called_once()

    def test_channel_with_more_than_5_videos_limits_comment_fetch(self, analyzer):
        """Comment fetching is limited to first 5 videos."""
        channel_resp = self._channel_resp()
        search_resp = self._search_resp(["v1", "v2", "v3", "v4", "v5", "v6"])
        # Only 5 comment responses expected (videos[:5])
        cmt_responses = [self._comment_thread_resp([f"comment{i}"]) for i in range(5)]
        analyzer._session.get = MagicMock(
            side_effect=[channel_resp, search_resp] + cmt_responses
        )

        result = analyzer._analyze_youtube_channel("@BigChannel", "key")

        assert len(result["recent_videos"]) == 6
        # 5 comments from 5 videos
        assert result["comment_count"] == 5
