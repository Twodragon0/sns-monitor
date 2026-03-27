"""Tests for Reddit subreddit and post analysis (reddit.py mixin)."""

import requests
from unittest.mock import MagicMock, patch

import pytest

from app.services.platform_analyzer import PlatformAnalyzer


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture()
def analyzer():
    """PlatformAnalyzer without Reddit credentials (public API path)."""
    with patch.dict(
        "os.environ",
        {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": "", "YOUTUBE_API_KEY": ""},
    ):
        pa = PlatformAnalyzer()
    return pa


@pytest.fixture()
def analyzer_oauth():
    """PlatformAnalyzer with Reddit OAuth credentials."""
    with patch.dict(
        "os.environ",
        {
            "REDDIT_CLIENT_ID": "fake_id",
            "REDDIT_CLIENT_SECRET": "fake_secret",
            "YOUTUBE_API_KEY": "",
        },
    ):
        pa = PlatformAnalyzer()
    return pa


def _make_resp(data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.ok = status < 400
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


def _make_req_exc(status=403):
    """Create a requests.RequestException with a .response attribute."""
    exc = requests.RequestException("blocked")
    exc.response = MagicMock()
    exc.response.status_code = status
    return exc


# ── _analyze_reddit URL dispatching ─────────────────────────────


class TestAnalyzeRedditDispatch:
    def test_dispatches_to_post_for_comments_url(self, analyzer):
        analyzer._analyze_reddit_post = MagicMock(return_value={"type": "post"})
        analyzer._reddit_get_token = MagicMock(return_value=None)

        result = analyzer._analyze_reddit(
            "https://www.reddit.com/r/python/comments/abc123/some_title/"
        )

        analyzer._analyze_reddit_post.assert_called_once()
        call_args = analyzer._analyze_reddit_post.call_args[0]
        assert call_args[0] == "python"
        assert call_args[1] == "abc123"
        assert result["type"] == "post"

    def test_dispatches_to_subreddit(self, analyzer):
        analyzer._analyze_reddit_subreddit = MagicMock(return_value={"type": "subreddit"})
        analyzer._reddit_get_token = MagicMock(return_value=None)

        result = analyzer._analyze_reddit("https://www.reddit.com/r/python/")

        analyzer._analyze_reddit_subreddit.assert_called_once()
        assert result["type"] == "subreddit"

    def test_raises_for_unrecognized_url(self, analyzer):
        analyzer._reddit_get_token = MagicMock(return_value=None)

        with pytest.raises(ValueError, match="Could not extract"):
            analyzer._analyze_reddit("https://www.reddit.com/")

    def test_oauth_headers_include_bearer_token(self, analyzer_oauth):
        """When credentials exist, Authorization header is set."""
        analyzer_oauth._reddit_get_token = MagicMock(return_value="tok_xyz")
        analyzer_oauth._analyze_reddit_subreddit = MagicMock(
            return_value={"type": "subreddit"}
        )

        analyzer_oauth._analyze_reddit("https://www.reddit.com/r/learnpython/")

        call_headers = analyzer_oauth._analyze_reddit_subreddit.call_args[0][1]
        assert call_headers.get("Authorization") == "Bearer tok_xyz"

    def test_no_auth_header_without_token(self, analyzer):
        """Without credentials, Authorization header is absent."""
        analyzer._analyze_reddit_subreddit = MagicMock(
            return_value={"type": "subreddit"}
        )

        analyzer._analyze_reddit("https://www.reddit.com/r/learnpython/")

        call_headers = analyzer._analyze_reddit_subreddit.call_args[0][1]
        assert "Authorization" not in call_headers


# ── _analyze_reddit_subreddit ────────────────────────────────────


class TestAnalyzeRedditSubreddit:
    def _subreddit_hot_data(self, posts=None):
        if posts is None:
            posts = [
                {
                    "data": {
                        "title": "Post 1",
                        "author": "user1",
                        "score": 100,
                        "num_comments": 10,
                        "created_utc": 1700000000,
                        "url": "https://reddit.com/r/test/p1",
                        "selftext": "Body text",
                        "permalink": "/r/test/comments/p1/post1/",
                        "stickied": False,
                    }
                }
            ]
        return {"data": {"children": posts}}

    def _about_data(self, subscribers=5000):
        return {
            "data": {
                "subscribers": subscribers,
                "accounts_active": 200,
                "public_description": "A test subreddit",
            }
        }

    def test_returns_subreddit_data(self, analyzer):
        hot_resp = _make_resp(self._subreddit_hot_data())
        # comment request for the post
        cmt_resp = _make_resp([
            {},
            {"data": {"children": [
                {
                    "kind": "t1",
                    "data": {
                        "body": "Nice post",
                        "author": "commenter1",
                        "score": 5,
                        "created_utc": 1700001000,
                    },
                }
            ]}},
        ])
        about_resp = _make_resp(self._about_data(subscribers=9999))
        analyzer._reddit_request = MagicMock(
            side_effect=[hot_resp, cmt_resp, about_resp]
        )

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        assert result["type"] == "subreddit"
        assert result["subreddit"] == "test"
        assert result["subscribers"] == 9999
        assert result["total_posts"] == 1
        assert len(result["posts"]) == 1

    def test_stickied_posts_are_filtered(self, analyzer):
        posts = [
            {
                "data": {
                    "title": "Sticky",
                    "author": "mod",
                    "score": 0,
                    "num_comments": 0,
                    "created_utc": 0,
                    "url": "",
                    "selftext": "",
                    "permalink": "/r/test/comments/s1/sticky/",
                    "stickied": True,
                }
            }
        ]
        hot_resp = _make_resp(self._subreddit_hot_data(posts))
        about_resp = _make_resp(self._about_data())
        analyzer._reddit_request = MagicMock(side_effect=[hot_resp, about_resp])

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        assert result["total_posts"] == 0
        assert result["posts"] == []

    def test_403_response_returns_blocked_result(self, analyzer):
        blocked_resp = _make_resp({}, status=403)
        analyzer._reddit_request = MagicMock(return_value=blocked_resp)

        result = analyzer._analyze_reddit_subreddit(
            "private", {"User-Agent": "test-agent"}
        )

        assert result["type"] == "subreddit"
        assert result["fetch_status"] == "blocked"
        assert result["fetch_reason"] == "reddit_api_403"
        assert result["total_posts"] == 0

    def test_403_requestexception_returns_blocked_result(self, analyzer):
        exc = _make_req_exc(403)
        analyzer._reddit_request = MagicMock(side_effect=exc)

        result = analyzer._analyze_reddit_subreddit(
            "private", {"User-Agent": "test-agent"}
        )

        assert result["fetch_status"] == "blocked"

    def test_generic_requestexception_returns_blocked_result(self, analyzer):
        exc = requests.RequestException("timeout")
        # No response attribute
        analyzer._reddit_request = MagicMock(side_effect=exc)

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        assert result["type"] == "subreddit"
        assert result["fetch_status"] == "blocked"

    def test_oauth_uses_oauth_base_url(self, analyzer_oauth):
        """When Authorization header present, uses oauth.reddit.com base."""
        analyzer_oauth._reddit_get_token = MagicMock(return_value="tok")
        hot_resp = _make_resp({"data": {"children": []}})
        about_resp = _make_resp({"data": {}})
        analyzer_oauth._reddit_request = MagicMock(
            side_effect=[hot_resp, about_resp]
        )

        analyzer_oauth._analyze_reddit_subreddit(
            "test", {"Authorization": "Bearer tok", "User-Agent": "app"}
        )

        first_call_url = analyzer_oauth._reddit_request.call_args_list[0][0][0]
        assert "oauth.reddit.com" in first_call_url

    def test_comment_fetch_single_post_with_permalink(self, analyzer):
        """A post with a valid permalink gets a comment fetch request."""
        posts = [
            {
                "data": {
                    "title": "Has permalink",
                    "author": "user",
                    "score": 10,
                    "num_comments": 2,
                    "created_utc": 0,
                    "url": "",
                    "selftext": "",
                    "permalink": "/r/test/comments/p1/post/",
                    "stickied": False,
                }
            }
        ]
        hot_resp = _make_resp(self._subreddit_hot_data(posts))
        cmt_resp = _make_resp([{}, {"data": {"children": [
            {"kind": "t1", "data": {"body": "Hello", "author": "u", "score": 1, "created_utc": 0}},
        ]}}])
        about_resp = _make_resp(self._about_data())
        analyzer._reddit_request = MagicMock(
            side_effect=[hot_resp, cmt_resp, about_resp]
        )

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        assert result["total_posts"] == 1
        assert result["posts"][0]["comments"][0]["text"] == "Hello"

    def test_comment_fetch_skips_non_ok_response(self, analyzer):
        """Non-OK comment response is silently skipped."""
        hot_resp = _make_resp(self._subreddit_hot_data())
        cmt_resp = _make_resp({}, status=404)
        about_resp = _make_resp(self._about_data())
        analyzer._reddit_request = MagicMock(
            side_effect=[hot_resp, cmt_resp, about_resp]
        )

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        assert result["total_posts"] == 1
        # Post exists but no "comments" key injected (skipped)
        post = result["posts"][0]
        assert "comments" not in post

    def test_comment_data_not_list_skipped(self, analyzer):
        """Comment response not a list with 2 elements is skipped."""
        hot_resp = _make_resp(self._subreddit_hot_data())
        # Returns dict instead of list
        cmt_resp = _make_resp({"error": "unexpected"})
        about_resp = _make_resp(self._about_data())
        analyzer._reddit_request = MagicMock(
            side_effect=[hot_resp, cmt_resp, about_resp]
        )

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        post = result["posts"][0]
        assert "comments" not in post

    def test_comment_non_t1_kind_skipped(self, analyzer):
        """Comment children with kind != 't1' are skipped."""
        hot_resp = _make_resp(self._subreddit_hot_data())
        cmt_resp = _make_resp([
            {},
            {"data": {"children": [
                {"kind": "more", "data": {}},
                {"kind": "t1", "data": {"body": "Real comment", "author": "u", "score": 1, "created_utc": 0}},
            ]}},
        ])
        about_resp = _make_resp(self._about_data())
        analyzer._reddit_request = MagicMock(
            side_effect=[hot_resp, cmt_resp, about_resp]
        )

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        assert len(result["posts"][0]["comments"]) == 1
        assert result["posts"][0]["comments"][0]["text"] == "Real comment"

    def test_comment_request_exception_is_caught(self, analyzer):
        """Exception from _reddit_request during comment fetch is caught (line 145-146)."""
        posts = [
            {
                "data": {
                    "title": "Post",
                    "author": "user",
                    "score": 10,
                    "num_comments": 2,
                    "created_utc": 0,
                    "url": "",
                    "selftext": "",
                    "permalink": "/r/test/comments/abc/post/",
                    "stickied": False,
                }
            }
        ]
        hot_resp = _make_resp(self._subreddit_hot_data(posts))
        about_resp = _make_resp(self._about_data())
        # comment request raises an Exception
        analyzer._reddit_request = MagicMock(
            side_effect=[hot_resp, Exception("connection error"), about_resp]
        )

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        assert result["total_posts"] == 1
        # Post exists but no comments appended
        assert "comments" not in result["posts"][0]

    def test_about_request_failure_uses_defaults(self, analyzer):
        hot_resp = _make_resp({"data": {"children": []}})
        analyzer._reddit_request = MagicMock(
            side_effect=[hot_resp, Exception("about failed")]
        )

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        assert result["subscribers"] == 0
        assert result["active_users"] == 0

    def test_data_as_list_format(self, analyzer):
        """Handle OAuth endpoint returning data as list format."""
        hot_resp = _make_resp([
            {
                "data": {
                    "children": [{
                        "data": {
                            "title": "List format post",
                            "author": "user1",
                            "score": 50,
                            "num_comments": 5,
                            "created_utc": 0,
                            "url": "",
                            "selftext": "",
                            "permalink": "",
                            "stickied": False,
                        }
                    }]
                }
            }
        ])
        about_resp = _make_resp(self._about_data())
        analyzer._reddit_request = MagicMock(side_effect=[hot_resp, about_resp])

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        assert result["total_posts"] == 1

    def test_data_unexpected_format_returns_empty(self, analyzer):
        """Unexpected data format falls back to empty dict."""
        hot_resp = _make_resp("unexpected string")
        about_resp = _make_resp(self._about_data())
        analyzer._reddit_request = MagicMock(side_effect=[hot_resp, about_resp])

        result = analyzer._analyze_reddit_subreddit(
            "test", {"User-Agent": "test-agent"}
        )

        assert result["total_posts"] == 0


# ── _reddit_blocked_subreddit_result ────────────────────────────


class TestRedditBlockedSubredditResult:
    def test_structure(self, analyzer):
        result = analyzer._reddit_blocked_subreddit_result("mySub", "blocked msg")

        assert result["type"] == "subreddit"
        assert result["subreddit"] == "mySub"
        assert result["subscribers"] == 0
        assert result["active_users"] == 0
        assert result["description"] == "blocked msg"
        assert result["total_posts"] == 0
        assert result["posts"] == []
        assert result["fetch_status"] == "blocked"
        assert result["fetch_reason"] == "reddit_api_403"


# ── _analyze_reddit_post ─────────────────────────────────────────


class TestAnalyzeRedditPost:
    def _post_resp(self, title="My Post", comments=None):
        if comments is None:
            comments = [
                {
                    "kind": "t1",
                    "data": {
                        "body": "First comment",
                        "author": "commenter",
                        "score": 10,
                        "created_utc": 1700000100,
                    },
                }
            ]
        return _make_resp([
            {
                "data": {
                    "children": [{
                        "data": {
                            "title": title,
                            "author": "poster",
                            "score": 500,
                            "upvote_ratio": 0.95,
                            "num_comments": 25,
                            "selftext": "Post body",
                            "created_utc": 1700000000,
                        }
                    }]
                }
            },
            {"data": {"children": comments}},
        ])

    def test_returns_post_data(self, analyzer):
        analyzer._reddit_request = MagicMock(return_value=self._post_resp())

        result = analyzer._analyze_reddit_post(
            "python", "abc123", {"User-Agent": "test"}
        )

        assert result["type"] == "post"
        assert result["subreddit"] == "python"
        assert result["title"] == "My Post"
        assert result["author"] == "poster"
        assert result["score"] == 500
        assert result["upvote_ratio"] == 0.95
        assert len(result["comments"]) == 1
        assert result["comments"][0]["text"] == "First comment"

    def test_403_response_returns_blocked_result(self, analyzer):
        blocked_resp = _make_resp({}, status=403)
        analyzer._reddit_request = MagicMock(return_value=blocked_resp)

        result = analyzer._analyze_reddit_post(
            "private", "xyz", {"User-Agent": "test"}
        )

        assert result["type"] == "post"
        assert result["fetch_status"] == "blocked"
        assert result["fetch_reason"] == "reddit_api_403"
        assert result["subreddit"] == "private"

    def test_403_requestexception_returns_blocked_result(self, analyzer):
        exc = _make_req_exc(403)
        analyzer._reddit_request = MagicMock(side_effect=exc)

        result = analyzer._analyze_reddit_post(
            "private", "xyz", {"User-Agent": "test"}
        )

        assert result["fetch_status"] == "blocked"

    def test_other_requestexception_raises(self, analyzer):
        exc = requests.RequestException("timeout")
        analyzer._reddit_request = MagicMock(side_effect=exc)

        with pytest.raises(requests.RequestException):
            analyzer._analyze_reddit_post(
                "test", "abc", {"User-Agent": "test"}
            )

    def test_invalid_response_format_raises(self, analyzer):
        """Response that is not a list with 2 elements raises ValueError."""
        analyzer._reddit_request = MagicMock(return_value=_make_resp({"error": "not found"}))

        with pytest.raises((ValueError, Exception)):
            analyzer._analyze_reddit_post("test", "bad_id", {"User-Agent": "test"})

    def test_non_t1_comments_skipped(self, analyzer):
        comments = [
            {"kind": "more", "data": {}},
            {"kind": "t1", "data": {"body": "Real", "author": "u", "score": 1, "created_utc": 0}},
        ]
        analyzer._reddit_request = MagicMock(
            return_value=self._post_resp(comments=comments)
        )

        result = analyzer._analyze_reddit_post(
            "test", "abc", {"User-Agent": "test"}
        )

        assert len(result["comments"]) == 1
        assert result["comments"][0]["text"] == "Real"

    def test_oauth_uses_oauth_base_url(self, analyzer_oauth):
        analyzer_oauth._reddit_get_token = MagicMock(return_value="tok")
        analyzer_oauth._reddit_request = MagicMock(
            return_value=self._post_resp()
        )

        analyzer_oauth._analyze_reddit_post(
            "test", "abc", {"Authorization": "Bearer tok", "User-Agent": "app"}
        )

        call_url = analyzer_oauth._reddit_request.call_args[0][0]
        assert "oauth.reddit.com" in call_url

    def test_selftext_truncated_to_1000_chars(self, analyzer):
        long_text = "X" * 2000
        resp = _make_resp([
            {
                "data": {
                    "children": [{
                        "data": {
                            "title": "Long Post",
                            "author": "user",
                            "score": 1,
                            "upvote_ratio": 0.5,
                            "num_comments": 0,
                            "selftext": long_text,
                            "created_utc": 0,
                        }
                    }]
                }
            },
            {"data": {"children": []}},
        ])
        analyzer._reddit_request = MagicMock(return_value=resp)

        result = analyzer._analyze_reddit_post("test", "abc", {"User-Agent": "test"})

        assert len(result["selftext"]) == 1000


# ── _reddit_blocked_post_result ──────────────────────────────────


class TestRedditBlockedPostResult:
    def test_structure(self, analyzer):
        result = analyzer._reddit_blocked_post_result("mySub", "post123", "msg")

        assert result["type"] == "post"
        assert result["subreddit"] == "mySub"
        assert result["title"] == "r/mySub (API 차단)"
        assert result["author"] == ""
        assert result["score"] == 0
        assert result["upvote_ratio"] == 0
        assert result["num_comments"] == 0
        assert result["selftext"] == ""
        assert result["created_utc"] == 0
        assert result["comments"] == []
        assert result["fetch_status"] == "blocked"
        assert result["fetch_reason"] == "reddit_api_403"
        assert result["description"] == "msg"
