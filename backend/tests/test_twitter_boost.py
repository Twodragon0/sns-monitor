"""Boost tests targeting uncovered lines in twitter.py:
- Lines 76-77: timeline v2 exception handler in _analyze_twitter_profile
- Lines 132-133: og:title assignment when title is still default
- Lines 146-147: og:image thumbnail assignment when thumbnail not yet set
- Lines 253-254: FxTwitter exception handler in _analyze_twitter_tweet
- Lines 296-297: Twitter API v2 exception handler in _analyze_twitter_tweet
- Lines 340-341: og:meta exception handler in _analyze_twitter_tweet
"""

import os
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


# ── Lines 76-77: timeline v2 exception in _analyze_twitter_profile ──

class TestTimelineV2ExceptionHandler:
    def test_timeline_v2_exception_is_caught_gracefully(self, analyzer):
        """Cover lines 76-77: _fetch_twitter_timeline_v2 raises, profile still returns."""
        fx_resp = _make_resp(ok=True, json_data={"user": {"name": "ExUser", "description": "bio"}})

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            # All other calls (syndication, x.com) fail
            raise Exception("connection refused")

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "Test/1.0"}

        # _fetch_twitter_timeline_v2 internally calls session.get which raises
        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "some_token"}):
            result = analyzer._analyze_twitter_profile("exuser")

        # Despite timeline failure, profile info is returned
        assert result["type"] == "profile"
        assert result["title"] == "ExUser"


# ── Lines 132-133: og:title applied when title is still default ──

class TestOgTitleAppliedWhenDefault:
    def test_og_title_updates_default_title(self, analyzer):
        """Cover lines 132-133: og:title replaces default '@username' title.

        Method 4 (og:meta) runs when profile_info has no 'description'.
        FxTwitter must return no name AND no description for both conditions to hold.
        """
        # FxTwitter returns empty user dict -> no name, no description set
        fx_resp = _make_resp(ok=True, json_data={"user": {}})
        og_html = """
        <html><head>
        <meta property="og:title" content="Real Display Name"/>
        <meta property="og:description" content="og desc"/>
        </head></html>
        """
        og_resp = _make_resp(ok=True, text=og_html)

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "syndication" in url:
                return _make_resp(ok=False)
            if "x.com" in url:
                return og_resp
            return _make_resp(ok=False)

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "Test/1.0"}

        # No description from FxTwitter -> Method 4 runs
        # Title is still "@titletest" (default) -> lines 132-133 execute
        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_profile("titletest")

        # og:title should replace the default "@titletest" title
        assert result["title"] == "Real Display Name"

    def test_og_title_not_applied_when_title_already_set(self, analyzer):
        """og:title is skipped when FxTwitter already set a non-default title."""
        fx_resp = _make_resp(ok=True, json_data={
            "user": {"name": "FxTwitter Name"}
            # No description, so Method 4 runs
        })
        og_html = """
        <html><head>
        <meta property="og:title" content="OG Title Should Be Ignored"/>
        <meta property="og:description" content="og desc"/>
        </head></html>
        """
        og_resp = _make_resp(ok=True, text=og_html)

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "syndication" in url:
                return _make_resp(ok=False)
            if "x.com" in url:
                return og_resp
            return _make_resp(ok=False)

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "Test/1.0"}

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_profile("titletest2")

        # title was already set by FxTwitter, og:title should not override
        assert result["title"] == "FxTwitter Name"


# ── Lines 146-147: og:image thumbnail when thumbnail not yet in profile ──

class TestOgImageThumbnailWhenNotSet:
    def test_og_image_sets_thumbnail_when_absent(self, analyzer):
        """Cover lines 146-147: og:image fills thumbnail when not already set.

        Thumbnail is only added to profile_info if FxTwitter user_data is truthy
        (line 57: if user_data). If user_data is empty, thumbnail key is never set.
        """
        # FxTwitter returns empty user_data -> thumbnail key never set in profile_info
        fx_resp = _make_resp(ok=True, json_data={"user": {}})
        og_html = """
        <html><head>
        <meta property="og:title" content="NoAvatarUser"/>
        <meta property="og:description" content="desc here"/>
        <meta property="og:image" content="https://cdn.example.com/img.jpg"/>
        </head></html>
        """
        og_resp = _make_resp(ok=True, text=og_html)

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "syndication" in url:
                return _make_resp(ok=False)
            if "x.com" in url:
                return og_resp
            return _make_resp(ok=False)

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "Test/1.0"}

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_profile("noavatar")

        assert result.get("thumbnail") == "https://cdn.example.com/img.jpg"

    def test_og_image_not_applied_when_thumbnail_already_set(self, analyzer):
        """og:image is skipped when FxTwitter already set thumbnail."""
        fx_resp = _make_resp(ok=True, json_data={
            "user": {
                "name": "AvatarUser",
                "avatar_url": "https://existing-avatar.com/a.jpg",
            }
            # Has avatar -> thumbnail already set, Method 4 won't overwrite
        })
        og_html = """
        <html><head>
        <meta property="og:description" content="desc"/>
        <meta property="og:image" content="https://og-image.com/b.jpg"/>
        </head></html>
        """
        og_resp = _make_resp(ok=True, text=og_html)

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "syndication" in url:
                return _make_resp(ok=False)
            if "x.com" in url:
                return og_resp
            return _make_resp(ok=False)

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "Test/1.0"}

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_profile("avataruser")

        # Thumbnail should remain the one from FxTwitter
        assert result.get("thumbnail") == "https://existing-avatar.com/a.jpg"


# ── Lines 253-254: FxTwitter exception handler in _analyze_twitter_tweet ──

class TestFxTwitterTweetExceptionHandler:
    def test_fxtwitter_exception_caught_falls_to_og_meta(self, analyzer):
        """Cover lines 253-254: FxTwitter call raises exception, falls through gracefully."""
        og_html = """
        <html><head>
        <meta property="og:title" content="Tweet Title From OG"/>
        <meta property="og:description" content="Tweet text from og:meta"/>
        </head></html>
        """
        og_resp = _make_resp(ok=True, text=og_html)

        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if "fxtwitter" in url:
                raise Exception("FxTwitter network error")
            if "x.com" in url:
                return og_resp
            return _make_resp(ok=False, json_data={"data": []})

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "Test/1.0"}

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_tweet("someuser", "tweet123")

        assert result["type"] == "tweet"
        # After FxTwitter exception, og:meta fallback fills in description
        assert result["description"] == "Tweet text from og:meta"


# ── Lines 296-297: Twitter API v2 exception in _analyze_twitter_tweet ──

class TestTwitterApiV2TweetExceptionHandler:
    def test_api_v2_exception_caught_falls_to_og_meta(self, analyzer):
        """Cover lines 296-297: Twitter API v2 tweet lookup raises, falls to og:meta."""
        fx_resp = _make_resp(ok=True, json_data={"tweet": {}})  # empty tweet -> posts empty
        og_html = """
        <html><head>
        <meta property="og:title" content="Fallback Title"/>
        <meta property="og:description" content="Fallback description text"/>
        </head></html>
        """
        og_resp = _make_resp(ok=True, text=og_html)

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "/2/tweets/" in url:
                raise Exception("API v2 error")
            if "x.com" in url:
                return og_resp
            return _make_resp(ok=False, json_data={"data": []})

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "Test/1.0"}

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "valid_token"}):
            result = analyzer._analyze_twitter_tweet("apiuser", "tweetabc")

        assert result["type"] == "tweet"
        assert result["description"] == "Fallback description text"


# ── Lines 340-341: og:meta exception handler in _analyze_twitter_tweet ──

class TestOgMetaTweetExceptionHandler:
    def test_og_meta_exception_caught_returns_partial_result(self, analyzer):
        """Cover lines 340-341: og:meta page fetch raises, result still returned."""
        fx_resp = _make_resp(ok=True, json_data={"tweet": {}})  # empty -> posts empty

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "x.com" in url:
                raise Exception("og:meta connection error")
            return _make_resp(ok=False, json_data={"data": []})

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "Test/1.0"}

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_tweet("exuser2", "tweetxyz")

        # Exception is caught; result still has required structure
        assert result["type"] == "tweet"
        assert "total_posts" in result
        assert result["posts"] == []
