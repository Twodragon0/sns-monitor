"""Tests for Reddit OAuth2 token management and auto-retry on 401."""

import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.platform_analyzer import PlatformAnalyzer


@pytest.fixture()
def analyzer():
    """Create a PlatformAnalyzer with fake Reddit credentials."""
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


def _mock_token_response(token="tok_abc", expires_in=3600):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"access_token": token, "expires_in": expires_in}
    return resp


# ── _reddit_get_token ──────────────────────────────────────────


class TestRedditGetToken:
    def test_returns_none_without_credentials(self):
        with patch.dict("os.environ", {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": "", "YOUTUBE_API_KEY": ""}):
            pa = PlatformAnalyzer()
        assert pa._reddit_get_token() is None

    def test_fetches_new_token(self, analyzer):
        analyzer._session.post = MagicMock(return_value=_mock_token_response("new_tok"))

        token = analyzer._reddit_get_token()

        assert token == "new_tok"
        assert analyzer._reddit_token == "new_tok"
        assert analyzer._reddit_token_expiry > time.time()

    def test_returns_cached_token_when_valid(self, analyzer):
        analyzer._reddit_token = "cached"
        analyzer._reddit_token_expiry = time.time() + 600
        analyzer._session.post = MagicMock(side_effect=AssertionError("should not be called"))

        token = analyzer._reddit_get_token()

        assert token == "cached"

    def test_refreshes_expired_token(self, analyzer):
        analyzer._reddit_token = "old"
        analyzer._reddit_token_expiry = time.time() - 10  # expired
        analyzer._session.post = MagicMock(return_value=_mock_token_response("fresh"))

        token = analyzer._reddit_get_token()

        assert token == "fresh"

    def test_force_refresh_ignores_cache(self, analyzer):
        analyzer._reddit_token = "cached"
        analyzer._reddit_token_expiry = time.time() + 600
        analyzer._session.post = MagicMock(return_value=_mock_token_response("forced"))

        token = analyzer._reddit_get_token(force_refresh=True)

        assert token == "forced"
        analyzer._session.post.assert_called_once()

    def test_returns_none_on_exception(self, analyzer):
        analyzer._session.post = MagicMock(side_effect=Exception("network error"))

        token = analyzer._reddit_get_token()

        assert token is None
        assert analyzer._reddit_token is None
        assert analyzer._reddit_token_expiry == 0


# ── _reddit_request ────────────────────────────────────────────


class TestRedditRequest:
    def _ok_response(self, status=200):
        resp = MagicMock()
        resp.status_code = status
        resp.ok = status < 400
        return resp

    def test_returns_response_on_success(self, analyzer):
        ok = self._ok_response(200)
        analyzer._session.get = MagicMock(return_value=ok)

        result = analyzer._reddit_request(
            "https://oauth.reddit.com/r/test/hot",
            headers={"Authorization": "Bearer tok"},
        )

        assert result.status_code == 200
        analyzer._session.get.assert_called_once()

    def test_retries_on_401(self, analyzer):
        unauthorized = self._ok_response(401)
        ok = self._ok_response(200)
        analyzer._session.get = MagicMock(side_effect=[unauthorized, ok])
        analyzer._session.post = MagicMock(return_value=_mock_token_response("new_tok"))

        result = analyzer._reddit_request(
            "https://oauth.reddit.com/r/test/hot",
            headers={"Authorization": "Bearer expired_tok"},
        )

        assert result.status_code == 200
        assert analyzer._session.get.call_count == 2
        # Verify second call used the new token
        second_call_headers = analyzer._session.get.call_args_list[1].kwargs.get(
            "headers"
        ) or analyzer._session.get.call_args_list[1][1].get("headers")
        assert second_call_headers["Authorization"] == "Bearer new_tok"

    def test_no_retry_without_auth_header(self, analyzer):
        unauthorized = self._ok_response(401)
        analyzer._session.get = MagicMock(return_value=unauthorized)

        result = analyzer._reddit_request(
            "https://www.reddit.com/r/test/hot",
            headers={"User-Agent": "test"},
        )

        assert result.status_code == 401
        analyzer._session.get.assert_called_once()

    def test_returns_401_when_refresh_fails(self, analyzer):
        unauthorized = self._ok_response(401)
        analyzer._session.get = MagicMock(return_value=unauthorized)
        analyzer._session.post = MagicMock(side_effect=Exception("refresh failed"))

        result = analyzer._reddit_request(
            "https://oauth.reddit.com/r/test/hot",
            headers={"Authorization": "Bearer bad_tok"},
        )

        assert result.status_code == 401
        # Only 1 GET call — no retry since refresh failed
        analyzer._session.get.assert_called_once()
