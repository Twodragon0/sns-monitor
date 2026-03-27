"""Tests for app/services/platforms/threads.py - ThreadsMixin coverage."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.platform_analyzer import PlatformAnalyzer


@pytest.fixture()
def analyzer():
    with patch.dict(
        "os.environ",
        {"YOUTUBE_API_KEY": "", "REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""},
    ):
        pa = PlatformAnalyzer()
    return pa


def _make_resp(ok=True, status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


# ── _analyze_threads routing ────────────────────────────────────


class TestAnalyzeThreadsRouting:
    def test_profile_url_returns_profile_type(self, analyzer):
        result = analyzer._analyze_threads("https://www.threads.net/@testuser")
        assert result["type"] == "profile"
        assert "testuser" in result["username"]

    def test_post_url_uses_html_scrape_when_no_token(self, analyzer):
        analyzer._fetch_threads_html = MagicMock(return_value={"type": "post", "content": "x"})
        with patch.dict("os.environ", {"THREADS_ACCESS_TOKEN": ""}):
            result = analyzer._analyze_threads("https://www.threads.net/@user/post/AbCd1234")
        analyzer._fetch_threads_html.assert_called_once()
        assert result["type"] == "post"

    def test_post_url_tries_api_first_when_token_set(self, analyzer):
        analyzer._fetch_threads_api = MagicMock(return_value={"type": "post", "source": "threads_api"})
        with patch.dict("os.environ", {"THREADS_ACCESS_TOKEN": "mytoken"}):
            result = analyzer._analyze_threads("https://www.threads.net/@user/post/XyZ789")
        analyzer._fetch_threads_api.assert_called_once()
        assert result["source"] == "threads_api"

    def test_api_failure_falls_back_to_html(self, analyzer):
        analyzer._fetch_threads_api = MagicMock(return_value=None)
        analyzer._fetch_threads_html = MagicMock(return_value={"type": "post", "source": "html_scraping"})
        with patch.dict("os.environ", {"THREADS_ACCESS_TOKEN": "tok"}):
            result = analyzer._analyze_threads("https://www.threads.net/@user/post/CODE")
        analyzer._fetch_threads_html.assert_called_once()

    def test_t_shortcode_url_is_treated_as_post(self, analyzer):
        analyzer._fetch_threads_html = MagicMock(return_value={"type": "post"})
        with patch.dict("os.environ", {"THREADS_ACCESS_TOKEN": ""}):
            analyzer._analyze_threads("https://www.threads.net/t/AbCdEfGh")
        analyzer._fetch_threads_html.assert_called_once()

    def test_threads_com_post_url(self, analyzer):
        analyzer._fetch_threads_html = MagicMock(return_value={"type": "post"})
        with patch.dict("os.environ", {"THREADS_ACCESS_TOKEN": ""}):
            result = analyzer._analyze_threads("https://www.threads.com/@johndoe/post/PostCode")
        assert result is not None

    def test_profile_url_has_correct_description(self, analyzer):
        result = analyzer._analyze_threads("https://www.threads.net/@someprofile")
        assert "프로필" in result["description"] or "게시글" in result["description"]


# ── _fetch_threads_api ──────────────────────────────────────────


class TestFetchThreadsApi:
    def _setup_analyzer(self, analyzer, me_data, threads_data, post_data=None, insights_data=None, replies_data=None):
        me_resp = _make_resp(json_data=me_data)
        threads_resp = _make_resp(json_data=threads_data)
        post_resp = _make_resp(json_data=post_data or {})
        insights_resp = _make_resp(json_data=insights_data or {"data": []})
        replies_resp = _make_resp(json_data=replies_data or {"data": []})

        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if url.endswith("/me"):
                return me_resp
            if "/threads" in url and url.endswith("/threads"):
                return threads_resp
            if url.endswith("/insights"):
                return insights_resp
            if url.endswith("/replies"):
                return replies_resp
            # specific thread by ID
            return post_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)

    def test_returns_none_when_me_fails(self, analyzer):
        me_resp = _make_resp(ok=False, status_code=401)
        analyzer._session.get = MagicMock(return_value=me_resp)
        result = analyzer._fetch_threads_api("bad_token", "CODE123", "user", "https://t.net/u/post/CODE123")
        assert result is None

    def test_returns_none_when_me_has_no_id(self, analyzer):
        me_resp = _make_resp(json_data={"id": None})
        analyzer._session.get = MagicMock(return_value=me_resp)
        result = analyzer._fetch_threads_api("tok", "CODE", "user", "https://t.net/u/post/CODE")
        assert result is None

    def test_returns_none_when_thread_not_found(self, analyzer):
        self._setup_analyzer(
            analyzer,
            me_data={"id": "123"},
            threads_data={"data": [{"id": "t1", "shortcode": "OTHER"}]},
        )
        result = analyzer._fetch_threads_api("tok", "MISSING", "user", "https://t.net/u/post/MISSING")
        assert result is None

    def test_returns_post_with_correct_structure(self, analyzer):
        self._setup_analyzer(
            analyzer,
            me_data={"id": "U1"},
            threads_data={"data": [{"id": "T1", "shortcode": "CODE1", "permalink": ""}]},
            post_data={
                "text": "Post content here",
                "username": "realuser",
                "timestamp": "2024-01-01T12:00:00Z",
                "permalink": "https://threads.net/@realuser/post/CODE1",
            },
            insights_data={
                "data": [
                    {"name": "likes", "values": [{"value": 42}]},
                    {"name": "replies", "values": [{"value": 10}]},
                    {"name": "views", "values": [{"value": 500}]},
                ]
            },
            replies_data={
                "data": [
                    {"text": "Nice post!", "username": "commenter1", "timestamp": "2024-01-01T13:00:00Z"},
                    {"text": "  ", "username": "empty_user"},  # empty text should be skipped
                ]
            },
        )
        result = analyzer._fetch_threads_api("token", "CODE1", "user", "https://threads.net/@user/post/CODE1")
        assert result is not None
        assert result["type"] == "post"
        assert result["content"] == "Post content here"
        assert result["username"] == "realuser"
        assert result["like_count"] == 42
        assert result["reply_count"] == 10
        assert result["view_count"] == 500
        assert result["source"] == "threads_api"
        assert len(result["replies"]) == 1
        assert result["replies"][0]["text"] == "Nice post!"

    def test_exception_in_me_returns_none(self, analyzer):
        analyzer._session.get = MagicMock(side_effect=Exception("connection error"))
        result = analyzer._fetch_threads_api("token", "C1", "u", "https://t.net")
        assert result is None

    def test_permalink_match_fallback(self, analyzer):
        """Thread matched by permalink when shortcode not directly matching."""
        self._setup_analyzer(
            analyzer,
            me_data={"id": "U2"},
            threads_data={"data": [{"id": "T2", "shortcode": "", "permalink": "https://threads.net/@u/post/MYCODE"}]},
            post_data={"text": "Found via permalink", "username": "u"},
        )
        result = analyzer._fetch_threads_api("tok", "MYCODE", "u", "https://t.net/u/post/MYCODE")
        assert result is not None
        assert result["content"] == "Found via permalink"


# ── _fetch_threads_html ─────────────────────────────────────────


class TestFetchThreadsHtml:
    def test_html_with_og_meta_extracts_content(self, analyzer):
        html = """
        <html><head>
        <meta property="og:title" content="@testuser"/>
        <meta property="og:description" content="This is the post content"/>
        </head><body></body></html>
        """
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)

        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@testuser/post/C1",
            "testuser", "C1",
            "https://www.threads.net/@testuser/post/C1"
        )
        assert result["type"] == "post"
        assert result["content"] == "This is the post content"
        assert result["source"] == "html_scraping"

    def test_html_request_failure_returns_fallback_message(self, analyzer):
        analyzer._session.get = MagicMock(side_effect=Exception("timeout"))

        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@u/post/X",
            "u", "X", "https://www.threads.net/@u/post/X"
        )
        assert result["type"] == "post"
        assert "불러오지 못했습니다" in result["description"] or result["content"] == ""

    def test_oembed_fallback_when_no_content(self, analyzer):
        empty_html = "<html><body></body></html>"
        page_resp = _make_resp(ok=True, text=empty_html)
        oembed_resp = _make_resp(ok=True, json_data={"html": "<blockquote>Embedded post text</blockquote>"})

        def side_effect(url, **kwargs):
            if "oembed" in url:
                return oembed_resp
            return page_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)

        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@u/post/X",
            "u", "X", "https://www.threads.net/@u/post/X"
        )
        assert "Embedded post text" in result["content"]

    def test_html_with_application_json_script_tag(self, analyzer):
        json_data = {"text": "Post from JSON script", "username": "jsonuser", "like_count": 5}
        html = f"""
        <html><body>
        <script type="application/json">{json.dumps(json_data)}</script>
        </body></html>
        """
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)

        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@jsonuser/post/J1",
            "jsonuser", "J1",
            "https://www.threads.net/@jsonuser/post/J1"
        )
        assert result["type"] == "post"

    def test_ld_json_articleBody_extracted(self, analyzer):
        ld_json = {
            "@type": "SocialMediaPosting",
            "articleBody": "Content from LD+JSON",
            "author": {"name": "ld_author"},
            "interactionStatistic": [
                {"interactionType": "LikeAction", "userInteractionCount": 100},
                {"interactionType": "CommentAction", "userInteractionCount": 20},
            ]
        }
        html = f"""
        <html><body>
        <script type="application/ld+json">{json.dumps(ld_json)}</script>
        </body></html>
        """
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)

        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@ld_author/post/L1",
            "unknown", "L1",
            "https://www.threads.net/@ld_author/post/L1"
        )
        assert "Content from LD+JSON" in result["content"]

    def test_not_ok_page_falls_through(self, analyzer):
        page_resp = _make_resp(ok=False, status_code=404)
        oembed_resp = _make_resp(ok=False)
        analyzer._session.get = MagicMock(side_effect=[page_resp, oembed_resp])

        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@u/post/X",
            "u", "X", "https://www.threads.net/@u/post/X"
        )
        assert result["type"] == "post"

    def test_result_has_required_keys(self, analyzer):
        html = "<html><head><meta property='og:description' content='test'/></head></html>"
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)

        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@u/post/R",
            "u", "R",
            "https://www.threads.net/@u/post/R?tracking=abc"
        )
        for key in ("type", "username", "title", "description", "content", "url", "replies"):
            assert key in result
        # url should be stripped of query params
        assert "?" not in result["url"]


# ── _extract_threads_json_data ──────────────────────────────────


class TestExtractThreadsJsonData:
    def test_extracts_from_flat_dict(self, analyzer):
        data = {"text": "Hello world post", "username": "user1", "like_count": 10}
        result = analyzer._extract_threads_json_data(data)
        assert result is not None
        assert result["text"] == "Hello world post"
        assert result["username"] == "user1"
        # like_count stored when present (may be None if 'likes' dict format not used)
        assert "like_count" in result

    def test_returns_none_for_non_dict_non_list(self, analyzer):
        assert analyzer._extract_threads_json_data("just a string") is None
        assert analyzer._extract_threads_json_data(42) is None
        assert analyzer._extract_threads_json_data(None) is None

    def test_recurses_into_nested_dict(self, analyzer):
        data = {
            "meta": {"count": 1},
            "post": {"text": "Nested post text", "username": "nesteduser"},
        }
        result = analyzer._extract_threads_json_data(data)
        assert result is not None
        assert result["text"] == "Nested post text"

    def test_recurses_into_list(self, analyzer):
        data = [
            {"meta": "skip"},
            {"text": "List item post", "username": "listuser"},
        ]
        result = analyzer._extract_threads_json_data(data)
        assert result is not None
        assert result["text"] == "List item post"

    def test_skips_short_text(self, analyzer):
        data = {"text": "Hi", "username": "u"}  # text < 5 chars
        result = analyzer._extract_threads_json_data(data)
        assert result is None

    def test_extracts_replies_from_edges(self, analyzer):
        data = {
            "text": "Main post content here",
            "username": "poster",
            "replies": {
                "edges": [
                    {"node": {"text": "Reply 1", "username": "r1", "taken_at": "1234567"}},
                    {"node": {"text": "Reply 2", "username": "r2"}},
                ]
            }
        }
        result = analyzer._extract_threads_json_data(data)
        assert result is not None
        assert len(result.get("replies", [])) == 2
        assert result["replies"][0]["text"] == "Reply 1"

    def test_caption_field_used_as_text(self, analyzer):
        data = {"caption": "Caption as text content here", "username": "capuser"}
        result = analyzer._extract_threads_json_data(data)
        assert result is not None
        assert result["text"] == "Caption as text content here"

    def test_body_field_used_as_text(self, analyzer):
        data = {"body": "Body field content here!", "username": "bodyuser"}
        result = analyzer._extract_threads_json_data(data)
        assert result is not None
        assert result["text"] == "Body field content here!"

    def test_user_nested_username(self, analyzer):
        data = {
            "text": "Post with nested user object",
            "user": {"username": "nested_name"},
        }
        result = analyzer._extract_threads_json_data(data)
        assert result is not None
        assert result["username"] == "nested_name"

    def test_reply_count_from_replies_dict(self, analyzer):
        data = {
            "text": "Post with reply count info",
            "username": "poster",
            "replies": {"count": 7},
        }
        result = analyzer._extract_threads_json_data(data)
        assert result is not None

    def test_empty_list_returns_none(self, analyzer):
        result = analyzer._extract_threads_json_data([])
        assert result is None

    def test_empty_dict_returns_none(self, analyzer):
        result = analyzer._extract_threads_json_data({})
        assert result is None
