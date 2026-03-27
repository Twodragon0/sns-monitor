"""Tests for app/services/platforms/twitter.py - TwitterMixin coverage."""

import os
from unittest.mock import MagicMock, patch, PropertyMock

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


# ── _analyze_twitter routing ────────────────────────────────────


class TestAnalyzeTwitterRouting:
    def test_routes_status_url_to_tweet(self, analyzer):
        analyzer._analyze_twitter_tweet = MagicMock(return_value={"type": "tweet"})
        result = analyzer._analyze_twitter("https://twitter.com/user/status/123456789")
        analyzer._analyze_twitter_tweet.assert_called_once_with("user", "123456789")
        assert result["type"] == "tweet"

    def test_routes_x_com_status_url(self, analyzer):
        analyzer._analyze_twitter_tweet = MagicMock(return_value={"type": "tweet"})
        analyzer._analyze_twitter("https://x.com/someone/status/9999")
        analyzer._analyze_twitter_tweet.assert_called_once_with("someone", "9999")

    def test_routes_profile_url(self, analyzer):
        analyzer._analyze_twitter_profile = MagicMock(return_value={"type": "profile"})
        result = analyzer._analyze_twitter("https://twitter.com/testuser")
        analyzer._analyze_twitter_profile.assert_called_once_with("testuser")
        assert result["type"] == "profile"

    def test_raises_if_no_username(self, analyzer):
        with pytest.raises(ValueError, match="Could not extract username"):
            analyzer._analyze_twitter("https://twitter.com/")

    def test_routes_x_com_profile(self, analyzer):
        analyzer._analyze_twitter_profile = MagicMock(return_value={"type": "profile"})
        analyzer._analyze_twitter("https://x.com/anotheruser")
        analyzer._analyze_twitter_profile.assert_called_once_with("anotheruser")


# ── _analyze_twitter_profile ────────────────────────────────────


class TestAnalyzeTwitterProfile:
    def test_fxtwitter_success_populates_profile(self, analyzer):
        fx_resp = _make_resp(json_data={
            "user": {
                "name": "Test User",
                "description": "A test bio",
                "avatar_url": "https://pbs.twimg.com/avatar.jpg",
                "followers": 1000,
                "following": 200,
                "tweets": 500,
                "banner_url": "https://pbs.twimg.com/banner.jpg",
            }
        })
        analyzer._session.get = MagicMock(return_value=fx_resp)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_profile("testuser")

        assert result["title"] == "Test User"
        assert result["description"] == "A test bio"
        assert result["thumbnail"] == "https://pbs.twimg.com/avatar.jpg"
        assert result["follower_count"] == 1000
        assert result["following_count"] == 200
        assert result["tweet_count"] == 500
        assert result["banner"] == "https://pbs.twimg.com/banner.jpg"
        assert result["type"] == "profile"
        assert result["username"] == "testuser"

    def test_fxtwitter_failure_continues_gracefully(self, analyzer):
        analyzer._session.get = MagicMock(side_effect=Exception("network error"))

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_profile("brokenuser")

        # Should return a partial result with defaults
        assert result["type"] == "profile"
        assert result["username"] == "brokenuser"
        assert result["title"] == "@brokenuser"

    def test_fxtwitter_not_ok_skips_user_data(self, analyzer):
        resp = _make_resp(ok=False, status_code=404)
        analyzer._session.get = MagicMock(return_value=resp)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_profile("nouser")

        assert result["title"] == "@nouser"

    def test_with_bearer_token_calls_timeline(self, analyzer):
        # FxTwitter returns empty user
        fx_resp = _make_resp(json_data={"user": {}})
        # Timeline API: user lookup
        user_resp = _make_resp(json_data={"data": {"id": "12345"}})
        # Timeline API: tweets
        tweets_resp = _make_resp(json_data={
            "data": [
                {"text": "Hello world", "public_metrics": {"like_count": 10, "retweet_count": 2, "reply_count": 1}, "created_at": "2024-01-01T00:00:00Z"}
            ]
        })

        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if "fxtwitter" in url:
                return fx_resp
            if "/users/by/username/" in url:
                return user_resp
            if "/tweets" in url:
                return tweets_resp
            return _make_resp(ok=False)

        analyzer._session.get = MagicMock(side_effect=side_effect)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "fake_token"}):
            result = analyzer._analyze_twitter_profile("tokenuser")

        assert len(result["posts"]) == 1
        assert result["posts"][0]["text"] == "Hello world"

    def test_syndication_fallback_when_no_posts(self, analyzer):
        from bs4 import BeautifulSoup

        fx_resp = _make_resp(ok=False)
        html_content = """
        <html><body>
        <div data-tweet-id="1234">
            <p class="timeline-Tweet-text">Test tweet from syndication</p>
        </div>
        </body></html>
        """
        synd_resp = _make_resp(ok=True, text=html_content)

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "syndication" in url:
                return synd_resp
            return _make_resp(ok=False)

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "TestAgent/1.0"}

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_profile("synduser")

        # If syndication found tweets, they'll be in posts
        assert result["type"] == "profile"

    def test_og_meta_fallback_for_description(self, analyzer):
        fx_resp = _make_resp(ok=True, json_data={"user": {"name": "Known Name"}})
        og_html = """
        <html><head>
        <meta property="og:title" content="Known Name (@testmeta)"/>
        <meta property="og:description" content="This is the bio"/>
        <meta property="og:image" content="https://example.com/pic.jpg"/>
        </head></html>
        """
        og_resp = _make_resp(ok=True, text=og_html)

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "x.com" in url:
                return og_resp
            return _make_resp(ok=False)

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "TestAgent/1.0"}

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_profile("testmeta")

        assert result["description"] == "This is the bio"
        assert result["total_posts"] == 0

    def test_total_posts_count(self, analyzer):
        fx_resp = _make_resp(json_data={
            "user": {"name": "User", "description": "bio"}
        })
        analyzer._session.get = MagicMock(return_value=fx_resp)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_profile("countuser")

        assert "total_posts" in result
        assert isinstance(result["total_posts"], int)


# ── _fetch_twitter_timeline_v2 ──────────────────────────────────


class TestFetchTwitterTimelineV2:
    def test_returns_posts_list(self, analyzer):
        user_resp = _make_resp(json_data={"data": {"id": "9999"}})
        tweets_resp = _make_resp(json_data={
            "data": [
                {
                    "text": "Tweet 1",
                    "public_metrics": {"like_count": 5, "retweet_count": 1, "reply_count": 2},
                    "created_at": "2024-01-15T10:00:00Z",
                }
            ]
        })

        def side_effect(url, **kwargs):
            if "/users/by/username/" in url:
                return user_resp
            return tweets_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)

        posts = analyzer._fetch_twitter_timeline_v2("testuser", "token123")
        assert len(posts) == 1
        assert posts[0]["text"] == "Tweet 1"
        assert posts[0]["like_count"] == 5
        assert posts[0]["author"] == "@testuser"

    def test_returns_empty_when_user_not_found(self, analyzer):
        user_resp = _make_resp(json_data={"data": {}})
        analyzer._session.get = MagicMock(return_value=user_resp)

        posts = analyzer._fetch_twitter_timeline_v2("ghost", "token")
        assert posts == []

    def test_raises_on_http_error(self, analyzer):
        resp = _make_resp(ok=False, status_code=401)
        resp.raise_for_status = MagicMock(side_effect=Exception("401 Unauthorized"))
        analyzer._session.get = MagicMock(return_value=resp)

        with pytest.raises(Exception):
            analyzer._fetch_twitter_timeline_v2("user", "bad_token")

    def test_empty_tweets_returns_empty_list(self, analyzer):
        user_resp = _make_resp(json_data={"data": {"id": "1234"}})
        tweets_resp = _make_resp(json_data={"data": []})

        def side_effect(url, **kwargs):
            if "/users/by/username/" in url:
                return user_resp
            return tweets_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)

        posts = analyzer._fetch_twitter_timeline_v2("emptyuser", "token")
        assert posts == []


# ── _analyze_twitter_tweet ──────────────────────────────────────


class TestAnalyzeTwitterTweet:
    def test_fxtwitter_success(self, analyzer):
        fx_resp = _make_resp(json_data={
            "tweet": {
                "text": "Hello from tweet",
                "author": {"screen_name": "tweetauthor", "name": "Tweet Author", "avatar_url": "https://example.com/ava.jpg"},
                "likes": 42,
                "retweets": 5,
                "replies": 3,
                "views": 1000,
                "created_at": "2024-01-01T00:00:00Z",
            }
        })
        replies_resp = _make_resp(json_data={"data": [], "includes": {"users": []}})

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "search/recent" in url:
                return replies_resp
            return _make_resp(ok=False)

        analyzer._session.get = MagicMock(side_effect=side_effect)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_tweet("tweetauthor", "111222333")

        assert result["type"] == "tweet"
        assert result["title"] == "Hello from tweet"[:100]
        assert result["description"] == "Hello from tweet"
        assert result["retweet_count"] == 5
        assert result["reply_count"] == 3
        assert result["view_count"] == 1000
        assert result["author_name"] == "Tweet Author"
        assert result["posts"][0]["like_count"] == 42

    def test_fxtwitter_failure_falls_through_to_twitter_api_v2(self, analyzer):
        fx_resp = _make_resp(ok=True, json_data={"tweet": {}})  # empty tweet data
        api_resp = _make_resp(ok=True, json_data={
            "data": {
                "text": "API v2 text",
                "public_metrics": {
                    "like_count": 10, "reply_count": 1,
                    "retweet_count": 2, "impression_count": 500,
                },
                "created_at": "2024-02-01",
                "author_id": "99",
            },
            "includes": {
                "users": [{"name": "API Author", "profile_image_url": "https://pic.com/a.jpg"}]
            }
        })

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "/tweets/" in url and "search" not in url:
                return api_resp
            return _make_resp(ok=False, json_data={"data": []})

        analyzer._session.get = MagicMock(side_effect=side_effect)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "token_abc"}):
            result = analyzer._analyze_twitter_tweet("user", "tweet999")

        assert result["posts"][0]["text"] == "API v2 text"
        assert result["author_name"] == "API Author"
        assert result["view_count"] == 500

    def test_og_meta_fallback(self, analyzer):
        fx_resp = _make_resp(ok=False)
        og_html = """
        <html><head>
        <meta property="og:title" content="Tweet Title"/>
        <meta property="og:description" content="Tweet Description Text"/>
        </head></html>
        """
        og_resp = _make_resp(ok=True, text=og_html)

        def side_effect(url, **kwargs):
            if "fxtwitter" in url:
                return fx_resp
            if "x.com" in url and "search" not in url:
                return og_resp
            return _make_resp(ok=False, json_data={"data": []})

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._session.headers = {"User-Agent": "TestAgent/1.0"}

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_tweet("fallback_user", "tweet42")

        assert result["type"] == "tweet"
        assert result["description"] == "Tweet Description Text"
        assert len(result["posts"]) == 1

    def test_always_calls_fetch_replies(self, analyzer):
        fx_resp = _make_resp(ok=True, json_data={"tweet": {"text": "x"}})
        analyzer._fetch_twitter_replies = MagicMock(return_value=[{"text": "reply1", "author": "@r"}])
        analyzer._session.get = MagicMock(return_value=fx_resp)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_tweet("u", "t1")

        analyzer._fetch_twitter_replies.assert_called_once()
        assert result["comments"] == [{"text": "reply1", "author": "@r"}]

    def test_total_posts_in_result(self, analyzer):
        fx_resp = _make_resp(ok=True, json_data={
            "tweet": {"text": "Some tweet", "author": {"screen_name": "u"}}
        })
        analyzer._session.get = MagicMock(return_value=fx_resp)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._analyze_twitter_tweet("u", "t")

        assert "total_posts" in result


# ── _fetch_twitter_replies ──────────────────────────────────────


class TestFetchTwitterReplies:
    def test_returns_empty_without_bearer_token(self, analyzer):
        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            result = analyzer._fetch_twitter_replies("12345", "user")
        assert result == []

    def test_returns_comments_with_bearer_token(self, analyzer):
        resp = _make_resp(json_data={
            "data": [
                {
                    "text": "A reply",
                    "public_metrics": {"like_count": 1},
                    "author_id": "u1",
                    "created_at": "2024-01-01",
                }
            ],
            "includes": {
                "users": [{"id": "u1", "username": "replier", "name": "Replier"}]
            }
        })
        analyzer._session.get = MagicMock(return_value=resp)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "tok123"}):
            comments = analyzer._fetch_twitter_replies("tweet_id_456", "origuser")

        assert len(comments) == 1
        assert comments[0]["text"] == "A reply"
        assert comments[0]["author"] == "@replier"
        assert comments[0]["like_count"] == 1

    def test_non_ok_response_returns_empty(self, analyzer):
        resp = _make_resp(ok=False, status_code=429, text="rate limit")
        analyzer._session.get = MagicMock(return_value=resp)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "token"}):
            result = analyzer._fetch_twitter_replies("twid", "usr")

        assert result == []

    def test_exception_returns_empty(self, analyzer):
        analyzer._session.get = MagicMock(side_effect=Exception("timeout"))

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "token"}):
            result = analyzer._fetch_twitter_replies("twid", "usr")

        assert result == []

    def test_author_without_username_in_map(self, analyzer):
        resp = _make_resp(json_data={
            "data": [
                {
                    "text": "Another reply",
                    "public_metrics": {"like_count": 0},
                    "author_id": "unknown_id",
                    "created_at": "2024-01-02",
                }
            ],
            "includes": {"users": []}
        })
        analyzer._session.get = MagicMock(return_value=resp)

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "tok"}):
            comments = analyzer._fetch_twitter_replies("t1", "u1")

        assert len(comments) == 1
        assert comments[0]["author"] == ""
