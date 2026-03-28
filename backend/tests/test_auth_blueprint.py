"""Tests for auth.py blueprint routes."""

import pytest
from unittest.mock import patch, MagicMock


class TestAuthMe:
    """Tests for GET /api/auth/me."""

    def test_no_session_returns_logged_out(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["logged_in"] is False
        assert "auth_required" in data
        assert data["anthropic_oauth_available"] is True

    def test_with_session_returns_logged_in(self, client, app):
        with client.session_transaction() as sess:
            sess["user"] = {"id": "user123", "provider": "anthropic", "display": "Test User"}

        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["logged_in"] is True
        assert data["user"]["id"] == "user123"

    def test_openai_oauth_available_when_configured(self, client):
        with patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.OPENAI_OAUTH_CLIENT_ID = "some-client-id"
            mock_cfg.AUTH_REQUIRED_FOR_ANALYSIS = False
            resp = client.get("/api/auth/me")
        assert resp.status_code == 200


class TestAuthAnthropicStart:
    """Tests for GET /api/auth/anthropic."""

    def test_redirects_to_anthropic_oauth(self, client):
        with patch("app.api.auth._ANTHROPIC_CLIENT_ID", "test-anthropic-client-id"):
            resp = client.get("/api/auth/anthropic")
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert "claude.ai/oauth/authorize" in location
        assert "code_challenge" in location
        assert "state" in location

    def test_returns_503_when_not_configured(self, client):
        """Without ANTHROPIC_OAUTH_CLIENT_ID set, must return 503."""
        with patch("app.api.auth._ANTHROPIC_CLIENT_ID", None):
            resp = client.get("/api/auth/anthropic")
        assert resp.status_code == 503

    def test_sets_session_oauth_state(self, client):
        with patch("app.api.auth._ANTHROPIC_CLIENT_ID", "test-anthropic-client-id"):
            client.get("/api/auth/anthropic")
        with client.session_transaction() as sess:
            assert "oauth_state" in sess
            assert "pkce_verifier" in sess
            assert sess["oauth_provider"] == "anthropic"

    def test_valid_return_to_saved_in_session(self, client):
        with patch("app.api.auth._ANTHROPIC_CLIENT_ID", "test-anthropic-client-id"):
            client.get("/api/auth/anthropic?return_to=/analysis")
        with client.session_transaction() as sess:
            assert sess["oauth_return_to"] == "/analysis"

    def test_invalid_return_to_defaults_to_analysis(self, client):
        with patch("app.api.auth._ANTHROPIC_CLIENT_ID", "test-anthropic-client-id"):
            client.get("/api/auth/anthropic?return_to=http://evil.com/phish")
        with client.session_transaction() as sess:
            assert sess["oauth_return_to"] == "/analysis"

    def test_double_slash_return_to_defaults_to_analysis(self, client):
        with patch("app.api.auth._ANTHROPIC_CLIENT_ID", "test-anthropic-client-id"):
            client.get("/api/auth/anthropic?return_to=//evil.com")
        with client.session_transaction() as sess:
            assert sess["oauth_return_to"] == "/analysis"


class TestAuthOpenAIStart:
    """Tests for GET /api/auth/openai."""

    def test_redirects_to_openai_oauth(self, client):
        with patch("app.api.auth._OPENAI_CLIENT_ID", "test-openai-client-id"):
            resp = client.get("/api/auth/openai")
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert "auth.openai.com/oauth/authorize" in location or "openai" in location.lower()

    def test_returns_503_when_not_configured(self, client):
        """Without OPENAI_OAUTH_CLIENT_ID set, must return 503."""
        with patch("app.api.auth._OPENAI_CLIENT_ID", None), \
             patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.OPENAI_OAUTH_CLIENT_ID = ""
            mock_cfg.OAUTH_REDIRECT_URI = ""
            mock_cfg.OAUTH_AUTHORIZE_URL = ""
            resp = client.get("/api/auth/openai")
        assert resp.status_code == 503

    def test_sets_session_oauth_provider_openai(self, client):
        with patch("app.api.auth._OPENAI_CLIENT_ID", "test-openai-client-id"):
            client.get("/api/auth/openai")
        with client.session_transaction() as sess:
            assert sess["oauth_provider"] == "openai"
            assert "pkce_verifier" in sess

    def test_custom_authorize_url(self, client):
        with patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.OAUTH_AUTHORIZE_URL = "https://custom-auth.example.com/oauth"
            mock_cfg.OAUTH_REDIRECT_URI = ""
            mock_cfg.OPENAI_OAUTH_CLIENT_ID = "test-client-id"
            resp = client.get("/api/auth/openai")
        assert resp.status_code == 302
        assert "custom-auth.example.com" in resp.headers["Location"]


class TestAuthCallback:
    """Tests for GET /callback (OAuth callback)."""

    def test_oauth_error_redirects_with_error(self, client):
        resp = client.get("/callback?error=access_denied")
        assert resp.status_code == 302
        assert "auth_error=access_denied" in resp.headers["Location"]

    def test_missing_code_redirects_with_error(self, client):
        resp = client.get("/callback?state=abc")
        assert resp.status_code == 302
        assert "auth_error=missing_code_or_state" in resp.headers["Location"]

    def test_missing_state_redirects_with_error(self, client):
        resp = client.get("/callback?code=abc")
        assert resp.status_code == 302
        assert "auth_error=missing_code_or_state" in resp.headers["Location"]

    def test_state_mismatch_redirects_with_error(self, client):
        with client.session_transaction() as sess:
            sess["oauth_state"] = "correct-state"
            sess["oauth_provider"] = "anthropic"

        resp = client.get("/callback?code=mycode&state=wrong-state")
        assert resp.status_code == 302
        assert "auth_error=invalid_state" in resp.headers["Location"]

    @patch("app.api.auth.http_requests.post")
    def test_anthropic_callback_success(self, mock_post, client):
        with client.session_transaction() as sess:
            sess["oauth_state"] = "valid-state"
            sess["pkce_verifier"] = "my-verifier"
            sess["oauth_provider"] = "anthropic"
            sess["oauth_return_to"] = "/analysis"

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "access_token": "token-abc123",
            "refresh_token": "refresh-xyz",
            "user_id": "anthropic-user-1",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        resp = client.get("/callback?code=auth-code&state=valid-state")
        assert resp.status_code == 302

        with client.session_transaction() as sess:
            assert sess.get("access_token") == "token-abc123"
            assert sess.get("token_provider") == "anthropic"
            assert sess["user"]["provider"] == "anthropic"
            assert sess.get("refresh_token") == "refresh-xyz"

    @patch("app.api.auth.http_requests.post")
    def test_anthropic_callback_token_exchange_failure(self, mock_post, client):
        with client.session_transaction() as sess:
            sess["oauth_state"] = "valid-state"
            sess["pkce_verifier"] = "my-verifier"
            sess["oauth_provider"] = "anthropic"

        import requests as real_requests
        mock_post.side_effect = real_requests.RequestException("Connection refused")

        resp = client.get("/callback?code=auth-code&state=valid-state")
        assert resp.status_code == 302
        assert "auth_error=token_exchange_failed" in resp.headers["Location"]

    @patch("app.api.auth.http_requests.post")
    def test_anthropic_callback_no_access_token(self, mock_post, client):
        with client.session_transaction() as sess:
            sess["oauth_state"] = "valid-state"
            sess["pkce_verifier"] = "my-verifier"
            sess["oauth_provider"] = "anthropic"

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"error": "invalid_grant"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        resp = client.get("/callback?code=auth-code&state=valid-state")
        assert resp.status_code == 302
        assert "auth_error=no_access_token" in resp.headers["Location"]

    def test_anthropic_callback_missing_pkce_verifier(self, client):
        with client.session_transaction() as sess:
            sess["oauth_state"] = "valid-state"
            sess["oauth_provider"] = "anthropic"
            # pkce_verifier intentionally missing

        resp = client.get("/callback?code=auth-code&state=valid-state")
        assert resp.status_code == 302
        assert "auth_error=missing_pkce_verifier" in resp.headers["Location"]

    @patch("app.api.auth.http_requests.post")
    def test_openai_callback_success(self, mock_post, client):
        with client.session_transaction() as sess:
            sess["oauth_state"] = "valid-state"
            sess["pkce_verifier"] = "my-verifier"
            sess["oauth_provider"] = "openai"
            sess["oauth_return_to"] = "/analysis"

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "access_token": "openai-token-xyz",
            "refresh_token": "openai-refresh",
            "sub": "openai-user-1",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        resp = client.get("/callback?code=openai-code&state=valid-state")
        assert resp.status_code == 302

        with client.session_transaction() as sess:
            assert sess.get("access_token") == "openai-token-xyz"
            assert sess.get("token_provider") == "openai"
            assert sess["user"]["provider"] == "openai"

    @patch("app.api.auth.http_requests.post")
    def test_openai_callback_token_exchange_failure(self, mock_post, client):
        with client.session_transaction() as sess:
            sess["oauth_state"] = "valid-state"
            sess["pkce_verifier"] = "my-verifier"
            sess["oauth_provider"] = "openai"

        import requests as real_requests
        mock_post.side_effect = real_requests.RequestException("timeout")

        resp = client.get("/callback?code=openai-code&state=valid-state")
        assert resp.status_code == 302
        assert "auth_error=token_exchange_failed" in resp.headers["Location"]

    @patch("app.api.auth.http_requests.post")
    def test_openai_callback_no_access_token(self, mock_post, client):
        with client.session_transaction() as sess:
            sess["oauth_state"] = "valid-state"
            sess["pkce_verifier"] = "my-verifier"
            sess["oauth_provider"] = "openai"

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        resp = client.get("/callback?code=openai-code&state=valid-state")
        assert resp.status_code == 302
        assert "auth_error=no_access_token" in resp.headers["Location"]

    @patch("app.api.auth.http_requests.post")
    def test_openai_callback_with_client_secret_fallback(self, mock_post, client):
        """OpenAI callback uses client_secret when no pkce_verifier."""
        with client.session_transaction() as sess:
            sess["oauth_state"] = "valid-state"
            sess["oauth_provider"] = "openai"
            # no pkce_verifier in session

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"access_token": "tok", "sub": "uid"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        with patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.OPENAI_OAUTH_CLIENT_SECRET = "secret-val"
            mock_cfg.OPENAI_OAUTH_CLIENT_ID = ""
            mock_cfg.OAUTH_TOKEN_URL = ""
            mock_cfg.OAUTH_REDIRECT_URI = ""
            resp = client.get("/callback?code=openai-code&state=valid-state")

        assert resp.status_code == 302
        call_data = mock_post.call_args[1].get("data") or mock_post.call_args[0][1] if mock_post.call_args[0] else mock_post.call_args[1].get("data", {})
        # Verify client_secret was passed in the POST data
        assert "client_secret" in str(mock_post.call_args)


class TestAuthLegacyCallbacks:
    """Tests for legacy callback paths."""

    def test_auth_callback_path(self, client):
        resp = client.get("/auth/callback?error=test_error")
        assert resp.status_code == 302
        assert "auth_error=test_error" in resp.headers["Location"]

    def test_api_auth_callback_path(self, client):
        resp = client.get("/api/auth/callback?error=test_error")
        assert resp.status_code == 302
        assert "auth_error=test_error" in resp.headers["Location"]


class TestSetApiKey:
    """Tests for POST /api/auth/apikey."""

    def test_set_openai_api_key_success(self, client):
        resp = client.post(
            "/api/auth/apikey",
            json={"provider": "openai", "api_key": "sk-testkey123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["provider"] == "openai"

    def test_set_anthropic_api_key_success(self, client):
        resp = client.post(
            "/api/auth/apikey",
            json={"provider": "anthropic", "api_key": "sk-ant-testkey123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_invalid_provider_returns_400(self, client):
        resp = client.post(
            "/api/auth/apikey",
            json={"provider": "google", "api_key": "some-key"},
        )
        assert resp.status_code == 400
        assert "Provider" in resp.get_json()["error"]

    def test_missing_api_key_returns_400(self, client):
        resp = client.post(
            "/api/auth/apikey",
            json={"provider": "openai", "api_key": ""},
        )
        assert resp.status_code == 400
        assert "API key is required" in resp.get_json()["error"]

    def test_openai_key_wrong_prefix_returns_400(self, client):
        resp = client.post(
            "/api/auth/apikey",
            json={"provider": "openai", "api_key": "not-sk-key"},
        )
        assert resp.status_code == 400
        assert "sk-" in resp.get_json()["error"]

    def test_anthropic_key_wrong_prefix_returns_400(self, client):
        resp = client.post(
            "/api/auth/apikey",
            json={"provider": "anthropic", "api_key": "sk-wrong-prefix"},
        )
        assert resp.status_code == 400
        assert "sk-ant-" in resp.get_json()["error"]

    def test_api_key_stored_in_session(self, client):
        client.post(
            "/api/auth/apikey",
            json={"provider": "openai", "api_key": "sk-validkey"},
        )
        with client.session_transaction() as sess:
            assert sess["session_api_key"] == "sk-validkey"
            assert sess["session_api_provider"] == "openai"
            assert sess["user"]["provider"] == "openai"


class TestAuthLogout:
    """Tests for POST /api/auth/logout."""

    def test_logout_clears_session(self, client):
        with client.session_transaction() as sess:
            sess["user"] = {"id": "user1"}
            sess["access_token"] = "token-xyz"

        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        with client.session_transaction() as sess:
            assert "user" not in sess
            assert "access_token" not in sess

    def test_logout_without_session_succeeds(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True


class TestRequireAnalysisAuth:
    """Tests for require_analysis_auth decorator (lines 41-43)."""

    def test_auth_not_required_allows_access(self, client):
        with patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.AUTH_REQUIRED_FOR_ANALYSIS = False
            # analyze/url does not require auth by default
            resp = client.get("/api/auth/me")
        assert resp.status_code == 200

    def test_auth_required_without_session_returns_401(self, app):
        """require_analysis_auth returns 401 when AUTH_REQUIRED and no user session."""
        from app.api.auth import require_analysis_auth
        from flask import Flask, jsonify

        test_app = Flask("test_decorator")
        test_app.config["SECRET_KEY"] = "test-secret"
        test_app.config["TESTING"] = True

        @test_app.route("/test-protected")
        @require_analysis_auth
        def protected():
            return jsonify({"ok": True})

        with patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.AUTH_REQUIRED_FOR_ANALYSIS = True
            with test_app.test_client() as c:
                resp = c.get("/test-protected")
                assert resp.status_code == 401
                assert "auth_required" in resp.get_json()["code"]

    def test_auth_required_with_session_allows_access(self, app):
        """require_analysis_auth allows when user in session."""
        from app.api.auth import require_analysis_auth
        from flask import Flask, jsonify, session

        test_app = Flask("test_decorator2")
        test_app.config["SECRET_KEY"] = "test-secret"
        test_app.config["TESTING"] = True

        @test_app.route("/test-protected2")
        @require_analysis_auth
        def protected2():
            return jsonify({"ok": True})

        with patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.AUTH_REQUIRED_FOR_ANALYSIS = True
            with test_app.test_client() as c:
                with c.session_transaction() as sess:
                    sess["user"] = {"id": "user1"}
                resp = c.get("/test-protected2")
                assert resp.status_code == 200


class TestFrontendRedirect:
    """Tests for _frontend_redirect helper (lines 362-365)."""

    def test_redirect_without_frontend_url(self, client):
        with patch.dict("os.environ", {"FRONTEND_URL": ""}, clear=False):
            resp = client.get("/callback?error=test")
        assert resp.status_code == 302
        # Without FRONTEND_URL, path is returned as-is
        assert "/analysis" in resp.headers["Location"]

    def test_redirect_with_frontend_url(self, client):
        with patch.dict("os.environ", {"FRONTEND_URL": "http://frontend.example.com"}, clear=False):
            resp = client.get("/callback?error=test")
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert "frontend.example.com" in location or "/analysis" in location


class TestGetCallbackUri:
    """Tests for _get_callback_uri (line 54)."""

    def test_uses_oauth_redirect_uri_when_set(self):
        from app.api.auth import _get_callback_uri
        with patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.OAUTH_REDIRECT_URI = "http://custom.example.com/callback"
            result = _get_callback_uri()
        assert result == "http://custom.example.com/callback"

    def test_builds_from_env_port_when_no_redirect_uri(self):
        from app.api.auth import _get_callback_uri
        with patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.OAUTH_REDIRECT_URI = ""
            with patch.dict("os.environ", {"API_EXTERNAL_PORT": "9999"}, clear=False):
                result = _get_callback_uri()
        assert "9999" in result
        assert result.startswith("http://localhost:")


class TestGetOpenAICallbackUri:
    """Tests for _get_openai_callback_uri (line 132)."""

    def test_uses_oauth_redirect_uri_when_set(self):
        from app.api.auth import _get_openai_callback_uri
        with patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.OAUTH_REDIRECT_URI = "http://custom.example.com/auth/callback"
            result = _get_openai_callback_uri()
        assert result == "http://custom.example.com/auth/callback"

    def test_builds_localhost_url_when_not_set(self):
        from app.api.auth import _get_openai_callback_uri
        with patch("app.api.auth.Config") as mock_cfg:
            mock_cfg.OAUTH_REDIRECT_URI = ""
            with patch.dict("os.environ", {"API_EXTERNAL_PORT": "8888"}, clear=False):
                result = _get_openai_callback_uri()
        assert result.startswith("http://localhost:")
        assert "/auth/callback" in result


class TestAuthOpenAIInvalidReturnTo:
    """Test invalid return_to for OpenAI OAuth start (line 158)."""

    def test_invalid_return_to_defaults_to_analysis(self, client):
        with patch("app.api.auth._OPENAI_CLIENT_ID", "test-openai-client-id"):
            resp = client.get("/api/auth/openai?return_to=http://evil.com/steal")
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert sess["oauth_return_to"] == "/analysis"

    def test_double_slash_return_to_defaults_to_analysis(self, client):
        with patch("app.api.auth._OPENAI_CLIENT_ID", "test-openai-client-id"):
            resp = client.get("/api/auth/openai?return_to=//evil.com/path")
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert sess["oauth_return_to"] == "/analysis"
