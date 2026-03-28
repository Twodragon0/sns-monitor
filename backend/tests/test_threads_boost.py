"""Targeted coverage boost for app/services/platforms/threads.py.

Missing lines: 111-112, 138-139, 164-165, 188-189, 246, 255, 257, 259, 264-265, 288-289
"""

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


# ── lines 111-112: exception in user threads search ────────────────────────
class TestFetchThreadsApiExceptions:
    def test_exception_in_threads_search_returns_none(self, analyzer):
        """Lines 111-112: exception inside user threads search (try/except block)."""
        me_resp = _make_resp(json_data={"id": "U1"})

        call_count = [0]
        def side_effect(url, **kwargs):
            call_count[0] += 1
            if url.endswith("/me"):
                return me_resp
            # The /threads endpoint raises
            raise Exception("network error in threads search")

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._fetch_threads_api("tok", "SHORTCODE", "user", "https://t.net/u/post/SC")
        # thread_id stays None → returns None
        assert result is None

    def test_exception_in_post_fetch_uses_defaults(self, analyzer):
        """Lines 138-139: exception in post details fetch falls through with defaults."""
        me_resp = _make_resp(json_data={"id": "U1"})
        threads_resp = _make_resp(json_data={"data": [{"id": "T1", "shortcode": "SC1", "permalink": ""}]})
        insights_resp = _make_resp(json_data={"data": []})
        replies_resp = _make_resp(json_data={"data": []})

        def side_effect(url, **kwargs):
            if url.endswith("/me"):
                return me_resp
            if url.endswith("/threads"):
                return threads_resp
            if url.endswith("/insights"):
                return insights_resp
            if url.endswith("/replies"):
                return replies_resp
            # post detail fetch raises
            raise Exception("post fetch error")

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._fetch_threads_api("tok", "SC1", "user", "https://t.net/u/post/SC1")
        assert result is not None
        assert result["type"] == "post"
        assert result["content"] == ""  # default empty string

    def test_exception_in_insights_fetch_uses_zero_counts(self, analyzer):
        """Lines 164-165: exception in insights fetch uses zero counts."""
        me_resp = _make_resp(json_data={"id": "U1"})
        threads_resp = _make_resp(json_data={"data": [{"id": "T2", "shortcode": "SC2", "permalink": ""}]})
        post_resp = _make_resp(json_data={"text": "Some content", "username": "poster"})
        replies_resp = _make_resp(json_data={"data": []})

        def side_effect(url, **kwargs):
            if url.endswith("/me"):
                return me_resp
            if url.endswith("/threads"):
                return threads_resp
            if url.endswith("/insights"):
                raise Exception("insights error")
            if url.endswith("/replies"):
                return replies_resp
            return post_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._fetch_threads_api("tok", "SC2", "user", "https://t.net/u/post/SC2")
        assert result is not None
        assert result["like_count"] == 0
        assert result["reply_count"] == 0
        assert result["view_count"] == 0

    def test_exception_in_replies_fetch_uses_empty_replies(self, analyzer):
        """Lines 188-189: exception in replies fetch returns empty replies list."""
        me_resp = _make_resp(json_data={"id": "U1"})
        threads_resp = _make_resp(json_data={"data": [{"id": "T3", "shortcode": "SC3", "permalink": ""}]})
        post_resp = _make_resp(json_data={"text": "Post here", "username": "poster"})
        insights_resp = _make_resp(json_data={"data": []})

        def side_effect(url, **kwargs):
            if url.endswith("/me"):
                return me_resp
            if url.endswith("/threads"):
                return threads_resp
            if url.endswith("/insights"):
                return insights_resp
            if url.endswith("/replies"):
                raise Exception("replies error")
            return post_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._fetch_threads_api("tok", "SC3", "user", "https://t.net/u/post/SC3")
        assert result is not None
        assert result["replies"] == []


# ── lines 246, 255, 257, 259, 264-265: _fetch_threads_html script parsing ──
class TestFetchThreadsHtmlScriptParsing:
    def test_short_script_content_skipped(self, analyzer):
        """Line 246: script text too short (< 50 chars) is skipped."""
        html = """
        <html><head><meta property="og:description" content="fallback content"/></head>
        <body>
        <script type="application/json">{"x":1}</script>
        </body></html>
        """
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@u/post/X", "u", "X",
            "https://www.threads.net/@u/post/X"
        )
        assert result["content"] == "fallback content"

    def test_script_with_no_string_content_skipped(self, analyzer):
        """Line 246: script tag with None string attribute is skipped."""
        html = """
        <html><head><meta property="og:description" content="og content"/></head>
        <body>
        <script type="application/json"></script>
        </body></html>
        """
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@u/post/X", "u", "X",
            "https://www.threads.net/@u/post/X"
        )
        assert result["content"] == "og content"

    def test_json_script_with_extracted_like_count(self, analyzer):
        """Lines 254-255: if extracted.get('like_count') is not None branch is executed."""
        # like_count from extract returns non-None only when likes is a dict with count
        json_data = {
            "text": "Post with like count in json data here!",
            "username": "user_likes",
            "likes": {"count": 99}
        }
        html = f"""
        <html><body>
        <script type="application/json">{json.dumps(json_data)}</script>
        </body></html>
        """
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@user_likes/post/X",
            "user_likes", "X",
            "https://www.threads.net/@user_likes/post/X"
        )
        assert result["type"] == "post"
        # like_count branch executed: result should have like_count key
        assert "like_count" in result

    def test_json_script_with_extracted_reply_count(self, analyzer):
        """Lines 256-257: if extracted.get('reply_count') is not None branch executed."""
        # reply_count from extract returns non-None when replies is a dict with count
        json_data = {
            "text": "Post with reply count in json data here!",
            "username": "user_replies",
            "replies": {"count": 15}
        }
        html = f"""
        <html><body>
        <script type="application/json">{json.dumps(json_data)}</script>
        </body></html>
        """
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@user_replies/post/X",
            "user_replies", "X",
            "https://www.threads.net/@user_replies/post/X"
        )
        assert "reply_count" in result

    def test_json_script_with_extracted_replies_list(self, analyzer):
        """Lines 259: extracted replies list from JSON data is used."""
        json_data = {
            "text": "Post with embedded replies in json data here!",
            "username": "poster_w_replies",
            "replies": {
                "edges": [
                    {"node": {"text": "Reply from user one", "username": "r1"}},
                ]
            }
        }
        html = f"""
        <html><body>
        <script type="application/json">{json.dumps(json_data)}</script>
        </body></html>
        """
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@poster_w_replies/post/X",
            "poster_w_replies", "X",
            "https://www.threads.net/@poster_w_replies/post/X"
        )
        assert len(result["replies"]) >= 1

    def test_json_script_username_update(self, analyzer):
        """Lines 261-262: username update from extracted JSON data."""
        json_data = {
            "text": "Post where username differs from URL username!",
            "username": "realusername123"
        }
        html = f"""
        <html><body>
        <script type="application/json">{json.dumps(json_data)}</script>
        </body></html>
        """
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@unknown/post/X",
            "unknown", "X",
            "https://www.threads.net/@unknown/post/X"
        )
        assert result["username"] == "realusername123"
        assert result["title"] == "@realusername123"

    def test_invalid_json_in_script_skipped(self, analyzer):
        """Lines 264-265: invalid JSON in script tag is skipped (json.JSONDecodeError)."""
        html = """
        <html><head><meta property="og:description" content="fallback desc"/></head>
        <body>
        <script type="application/json">{"bad json: </script>
        </body></html>
        """
        resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._fetch_threads_html(
            "https://www.threads.net/@u/post/X", "u", "X",
            "https://www.threads.net/@u/post/X"
        )
        # Falls through to og:description
        assert result["content"] == "fallback desc"

    def test_ld_json_reply_count_for_reply_interaction(self, analyzer):
        """Lines 288-289: ld+json interactionStatistic with Reply in type."""
        ld_json = {
            "@type": "SocialMediaPosting",
            "articleBody": "Content with reply stat here",
            "interactionStatistic": [
                {"interactionType": "ReplyAction", "userInteractionCount": 30},
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
            "https://www.threads.net/@u/post/X", "unknown", "X",
            "https://www.threads.net/@u/post/X"
        )
        assert result.get("reply_count") == 30
