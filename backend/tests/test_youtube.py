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
