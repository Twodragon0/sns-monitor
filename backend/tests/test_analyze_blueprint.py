"""Tests for analyze.py blueprint routes."""

import pytest
from unittest.mock import patch, MagicMock


class TestAnalyzeUrl:
    """Tests for POST /api/analyze/url."""

    def test_missing_body_returns_400(self, client):
        resp = client.post("/api/analyze/url", content_type="application/json", data="")
        assert resp.status_code == 400
        assert "URL is required" in resp.get_data(as_text=True)

    def test_missing_url_field_returns_400(self, client):
        resp = client.post("/api/analyze/url", json={"other": "value"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "URL is required" in data["error"]

    def test_empty_url_returns_400(self, client):
        resp = client.post("/api/analyze/url", json={"url": "   "})
        assert resp.status_code == 400
        assert "URL is required" in resp.get_json()["error"]

    def test_url_too_long_returns_400(self, client):
        long_url = "https://example.com/" + "a" * 2048
        resp = client.post("/api/analyze/url", json={"url": long_url})
        assert resp.status_code == 400
        assert "too long" in resp.get_json()["error"]

    def test_invalid_url_format_returns_400(self, client):
        resp = client.post("/api/analyze/url", json={"url": "not-a-url"})
        assert resp.status_code == 400
        assert "Invalid URL format" in resp.get_json()["error"]

    def test_ftp_url_returns_400(self, client):
        resp = client.post("/api/analyze/url", json={"url": "ftp://example.com"})
        assert resp.status_code == 400
        assert "Invalid URL format" in resp.get_json()["error"]

    @patch("app.api.analyze._get_analyzer")
    def test_valid_youtube_url_success(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = {
            "platform": "youtube",
            "title": "Test Video",
            "view_count": 1000,
        }
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.post(
            "/api/analyze/url",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["platform"] == "youtube"

    @patch("app.api.analyze._get_analyzer")
    def test_valid_reddit_url_success(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = {"platform": "reddit", "subreddit": "python"}
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.post(
            "/api/analyze/url",
            json={"url": "https://www.reddit.com/r/python"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["platform"] == "reddit"

    @patch("app.api.analyze._get_analyzer")
    def test_valid_dcinside_url_success(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = {"platform": "dcinside", "gallery_id": "programming"}
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.post(
            "/api/analyze/url",
            json={"url": "https://gall.dcinside.com/board/lists?id=programming"},
        )
        assert resp.status_code == 200

    @patch("app.api.analyze._get_analyzer")
    def test_value_error_returns_400(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = ValueError("Unsupported platform")
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.post(
            "/api/analyze/url",
            json={"url": "https://unsupported.example.com/page"},
        )
        assert resp.status_code == 400
        assert "Unsupported platform" in resp.get_json()["error"]

    @patch("app.api.analyze._get_analyzer")
    def test_generic_exception_returns_500(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = RuntimeError("Unexpected crash")
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.post(
            "/api/analyze/url",
            json={"url": "https://www.youtube.com/watch?v=test"},
        )
        assert resp.status_code == 500
        assert "Internal server error" in resp.get_json()["error"]

    @patch("app.api.analyze._get_analyzer")
    def test_options_passed_to_analyzer(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = {"platform": "youtube"}
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.post(
            "/api/analyze/url",
            json={"url": "https://www.youtube.com/watch?v=test", "options": {"limit": 50}},
        )
        assert resp.status_code == 200
        mock_analyzer.analyze.assert_called_once_with(
            "https://www.youtube.com/watch?v=test", options={"limit": 50}
        )

    @patch("app.api.analyze._get_analyzer")
    def test_http_url_is_accepted(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = {"platform": "other"}
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.post(
            "/api/analyze/url",
            json={"url": "http://example.com/page"},
        )
        assert resp.status_code == 200


class TestListPlatforms:
    """Tests for GET /api/platforms."""

    @patch("app.api.analyze._get_analyzer")
    def test_list_platforms_success(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.list_platforms.return_value = [
            {"name": "youtube", "example": "https://youtube.com/watch?v=..."},
            {"name": "reddit", "example": "https://reddit.com/r/..."},
        ]
        mock_analyzer.get_api_usage.return_value = {"youtube": True}
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.get("/api/platforms")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "platforms" in data
        assert "api_usage" in data
        assert len(data["platforms"]) == 2

    @patch("app.api.analyze._get_analyzer")
    def test_list_platforms_empty(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.list_platforms.return_value = []
        mock_analyzer.get_api_usage.return_value = {}
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.get("/api/platforms")
        assert resp.status_code == 200
        assert resp.get_json()["platforms"] == []


class TestGetAnalyzer:
    """Tests for _get_analyzer lazy loading (lines 22-26)."""

    def test_get_analyzer_creates_instance(self):
        import app.api.analyze as analyze_module
        # Reset the cached analyzer
        original = analyze_module._platform_analyzer
        analyze_module._platform_analyzer = None

        try:
            mock_instance = MagicMock()
            with patch("app.services.platform_analyzer.PlatformAnalyzer", return_value=mock_instance):
                from app.api.analyze import _get_analyzer
                result = _get_analyzer()
                assert result is not None
        finally:
            analyze_module._platform_analyzer = original

    def test_get_analyzer_returns_cached_instance(self):
        import app.api.analyze as analyze_module
        mock_instance = MagicMock()
        analyze_module._platform_analyzer = mock_instance
        try:
            from app.api.analyze import _get_analyzer
            result = _get_analyzer()
            assert result is mock_instance
        finally:
            analyze_module._platform_analyzer = None


class TestSummarizeAnalysis:
    """Tests for POST /api/analyze/summarize."""

    def test_missing_result_field_returns_400(self, client):
        resp = client.post("/api/analyze/summarize", json={"other": "data"})
        assert resp.status_code == 400
        assert "required" in resp.get_json()["error"]

    def test_empty_body_returns_400(self, client):
        resp = client.post("/api/analyze/summarize", content_type="application/json", data="")
        assert resp.status_code == 400

    @patch("app.api.analyze.Config")
    def test_local_fallback_returns_summary(self, mock_config, client):
        mock_config.MIROFISH_ENDPOINT = "http://localhost:9999"
        mock_config.MIROFISH_SSL_VERIFY = False

        with patch("requests.post") as mock_req:
            mock_resp = MagicMock()
            mock_resp.ok = False
            mock_resp.status_code = 503
            mock_resp.text = "Service Unavailable"
            mock_req.return_value = mock_resp

            with patch("app.services.llm_analyzer.summarize_with_llm", side_effect=Exception("no llm")):
                resp = client.post(
                    "/api/analyze/summarize",
                    json={
                        "result": {
                            "platform": "youtube",
                            "title": "Test Video",
                            "view_count": 12345,
                            "comment_count": 500,
                            "analyzed_at": "2026-01-01T00:00:00",
                        }
                    },
                )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data
        assert data["source"] == "local"

    @patch("app.api.analyze.Config")
    def test_summarize_with_description(self, mock_config, client):
        mock_config.MIROFISH_ENDPOINT = "http://localhost:9999"
        mock_config.MIROFISH_SSL_VERIFY = False

        with patch("requests.post", side_effect=Exception("connection refused")):
            resp = client.post(
                "/api/analyze/summarize",
                json={
                    "result": {
                        "platform": "reddit",
                        "description": "A subreddit about Python programming",
                        "title": "r/python",
                        "comments": [
                            {"text": "Great post!"},
                            {"text": "Very helpful"},
                        ],
                        "analysis": {
                            "overall": "positive",
                            "sentiment": {"positive": 10, "neutral": 3, "negative": 1},
                            "total": 14,
                            "top_keywords": [
                                {"word": "python", "count": 5},
                                {"word": "code", "count": 3},
                            ],
                        },
                    }
                },
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data

    @patch("app.api.analyze.Config")
    def test_summarize_with_fetch_status_error(self, mock_config, client):
        mock_config.MIROFISH_ENDPOINT = "http://localhost:9999"
        mock_config.MIROFISH_SSL_VERIFY = False

        with patch("requests.post", side_effect=Exception("no connection")):
            resp = client.post(
                "/api/analyze/summarize",
                json={
                    "result": {
                        "platform": "naver_cafe",
                        "title": "Test Cafe",
                        "fetch_status": "blocked",
                        "fetch_reason": "Login required",
                    }
                },
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["source"] == "local"
        assert "수집" in data["summary"]

    @patch("app.api.analyze.Config")
    def test_summarize_with_posts(self, mock_config, client):
        mock_config.MIROFISH_ENDPOINT = "http://localhost:9999"
        mock_config.MIROFISH_SSL_VERIFY = False

        with patch("requests.post", side_effect=Exception("no connection")):
            resp = client.post(
                "/api/analyze/summarize",
                json={
                    "result": {
                        "platform": "dcinside",
                        "gallery_id": "programming",
                        "posts": [
                            {"title": "Post 1", "text": "content 1"},
                            {"title": "Post 2"},
                        ],
                    }
                },
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data

    @patch("app.api.analyze.Config")
    def test_summarize_mirofish_success(self, mock_config, client):
        mock_config.MIROFISH_ENDPOINT = "http://localhost:9999"
        mock_config.MIROFISH_SSL_VERIFY = False

        with patch("requests.post") as mock_req:
            mock_resp = MagicMock()
            mock_resp.ok = True
            mock_resp.json.return_value = {"report": "AI generated summary"}
            mock_req.return_value = mock_resp

            resp = client.post(
                "/api/analyze/summarize",
                json={"result": {"platform": "youtube", "title": "Test"}},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["source"] == "mirofish"
        assert "AI generated summary" in data["summary"]

    @patch("app.api.analyze.Config")
    def test_summarize_llm_success(self, mock_config, client):
        """LLM 경로가 summary를 반환하면 그 결과를 사용한다 (line 198)."""
        mock_config.MIROFISH_ENDPOINT = "http://localhost:9999"
        mock_config.MIROFISH_SSL_VERIFY = False

        with patch("requests.post", side_effect=Exception("no mirofish")):
            with patch("app.services.llm_analyzer.summarize_with_llm") as mock_llm:
                mock_llm.return_value = {"summary": "LLM 요약 결과", "source": "anthropic"}
                resp = client.post(
                    "/api/analyze/summarize",
                    json={
                        "result": {
                            "platform": "youtube",
                            "title": "Test Video",
                        }
                    },
                )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data

    @patch("app.api.analyze.Config")
    def test_fmt_num_none_returns_zero(self, mock_config, client):
        """_fmt_num(None) returns '0' (line 205)."""
        mock_config.MIROFISH_ENDPOINT = "http://localhost:9999"
        mock_config.MIROFISH_SSL_VERIFY = False

        with patch("requests.post", side_effect=Exception("no conn")):
            resp = client.post(
                "/api/analyze/summarize",
                json={
                    "result": {
                        "platform": "youtube",
                        "title": "Test",
                        "view_count": None,
                        "like_count": None,
                    }
                },
            )
        assert resp.status_code == 200

    @patch("app.api.analyze.Config")
    def test_fmt_num_non_numeric_returns_str(self, mock_config, client):
        """_fmt_num with non-numeric string returns str(v) (lines 209-210)."""
        mock_config.MIROFISH_ENDPOINT = "http://localhost:9999"
        mock_config.MIROFISH_SSL_VERIFY = False

        with patch("requests.post", side_effect=Exception("no conn")):
            resp = client.post(
                "/api/analyze/summarize",
                json={
                    "result": {
                        "platform": "youtube",
                        "title": "Test",
                        "view_count": "N/A",
                        "like_count": "unknown",
                    }
                },
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data

    @patch("app.api.analyze.Config")
    def test_summarize_with_content_field(self, mock_config, client):
        mock_config.MIROFISH_ENDPOINT = "http://localhost:9999"
        mock_config.MIROFISH_SSL_VERIFY = False

        with patch("requests.post", side_effect=Exception("no connection")):
            resp = client.post(
                "/api/analyze/summarize",
                json={
                    "result": {
                        "platform": "naver_cafe",
                        "title": "Some Article",
                        "content": "Long article body text here...",
                        "fetch_status": "ok",
                    }
                },
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data
        assert "수집된 본문" in data["summary"]
