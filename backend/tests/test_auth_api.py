"""Tests for /api/auth/* endpoints."""

import pytest
from unittest.mock import patch, MagicMock


class TestAuthMe:
    """Tests for GET /api/auth/me."""

    def test_not_logged_in(self, client):
        resp = client.get('/api/auth/me')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['logged_in'] is False
        assert 'auth_required' in data

    def test_logged_in(self, client):
        with client.session_transaction() as sess:
            sess['user'] = {'id': 'test', 'provider': 'anthropic', 'display': 'Test'}
        resp = client.get('/api/auth/me')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['logged_in'] is True
        assert data['user']['id'] == 'test'


class TestAuthAnthropicStart:
    """Tests for GET /api/auth/anthropic."""

    def test_redirects_to_claude_oauth(self, client):
        resp = client.get('/api/auth/anthropic')
        assert resp.status_code == 302
        location = resp.headers['Location']
        assert 'claude.ai/oauth/authorize' in location
        assert 'code_challenge' in location
        assert 'state=' in location

    def test_stores_pkce_in_session(self, client):
        """Verify PKCE verifier and state are set in session before redirect."""
        # After the redirect, session should have pkce_verifier and oauth_provider
        client.get('/api/auth/anthropic')
        with client.session_transaction() as sess:
            assert 'pkce_verifier' in sess
            assert sess.get('oauth_provider') == 'anthropic'


class TestAuthOpenaiStart:
    """Tests for GET /api/auth/openai."""

    def test_redirects_to_openai_oauth(self, client):
        resp = client.get('/api/auth/openai')
        assert resp.status_code == 302
        location = resp.headers['Location']
        assert 'auth.openai.com' in location
        assert 'code_challenge' in location


class TestAuthCallback:
    """Tests for GET /callback."""

    def test_missing_code(self, client):
        resp = client.get('/callback?state=abc')
        assert resp.status_code == 302
        assert 'missing_code_or_state' in resp.headers['Location']

    def test_missing_state(self, client):
        resp = client.get('/callback?code=abc')
        assert resp.status_code == 302
        assert 'missing_code_or_state' in resp.headers['Location']

    def test_state_mismatch(self, client):
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'correct-state'
            sess['pkce_verifier'] = 'test-verifier'
            sess['oauth_provider'] = 'anthropic'
        resp = client.get('/callback?code=abc&state=wrong-state')
        assert resp.status_code == 302
        assert 'invalid_state' in resp.headers['Location']

    def test_oauth_error_parameter(self, client):
        resp = client.get('/callback?error=access_denied')
        assert resp.status_code == 302
        assert 'access_denied' in resp.headers['Location']


class TestSetApiKey:
    """Tests for POST /api/auth/apikey."""

    def test_invalid_provider(self, client):
        resp = client.post('/api/auth/apikey', json={'provider': 'invalid', 'api_key': 'sk-test'})
        assert resp.status_code == 400
        assert 'Provider must be' in resp.get_json()['error']

    def test_missing_api_key(self, client):
        resp = client.post('/api/auth/apikey', json={'provider': 'openai', 'api_key': ''})
        assert resp.status_code == 400
        assert 'API key is required' in resp.get_json()['error']

    def test_openai_key_prefix_validation(self, client):
        resp = client.post('/api/auth/apikey', json={'provider': 'openai', 'api_key': 'bad-prefix'})
        assert resp.status_code == 400
        assert "start with 'sk-'" in resp.get_json()['error']

    def test_anthropic_key_prefix_validation(self, client):
        resp = client.post('/api/auth/apikey', json={'provider': 'anthropic', 'api_key': 'sk-wrong'})
        assert resp.status_code == 400
        assert "start with 'sk-ant-'" in resp.get_json()['error']

    def test_valid_openai_key(self, client):
        resp = client.post('/api/auth/apikey', json={'provider': 'openai', 'api_key': 'sk-test123'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['provider'] == 'openai'

    def test_valid_anthropic_key(self, client):
        resp = client.post('/api/auth/apikey', json={'provider': 'anthropic', 'api_key': 'sk-ant-test123'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['provider'] == 'anthropic'


class TestRequireAnalysisAuth:
    """Tests for require_analysis_auth decorator."""

    def test_auth_not_required_passes(self, client):
        """When AUTH_REQUIRED_FOR_ANALYSIS is false, all requests pass."""
        resp = client.get('/api/auth/me')
        assert resp.status_code == 200

    def test_require_analysis_auth_decorator_logic(self, client):
        """Test the require_analysis_auth decorator function directly."""
        from app.api.auth import require_analysis_auth
        from unittest.mock import MagicMock

        @require_analysis_auth
        def dummy_view():
            return 'ok'

        # When AUTH_REQUIRED is False, should pass through
        with client.application.test_request_context():
            result = dummy_view()
            assert result == 'ok'


class TestAuthLogout:
    """Tests for POST /api/auth/logout."""

    def test_logout_clears_session(self, client):
        with client.session_transaction() as sess:
            sess['user'] = {'id': 'test'}
            sess['access_token'] = 'token123'
        resp = client.post('/api/auth/logout')
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True
        with client.session_transaction() as sess:
            assert 'user' not in sess
            assert 'access_token' not in sess
