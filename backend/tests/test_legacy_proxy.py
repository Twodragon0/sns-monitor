"""Tests for legacy API proxy (app/api/legacy.py)."""

import pytest
from unittest.mock import patch, MagicMock


class TestLegacyProxy:
    """Tests for legacy API proxy routes."""

    @patch('app.api.legacy._get_handlers')
    def test_proxies_to_lambda_handler(self, mock_handlers, client):
        """Legacy proxy handles routes not claimed by new Blueprints."""
        mock_module = MagicMock()
        mock_module.lambda_handler.return_value = {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': '{"status": "ok"}'
        }
        mock_handlers.return_value = mock_module

        # Use a route that still goes through legacy (not migrated to Blueprint)
        resp = client.get('/api/some-legacy-route')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'ok'

    @patch('app.api.legacy._get_handlers')
    def test_cors_headers_not_forwarded(self, mock_handlers, client):
        """CORS headers from lambda_handler should be filtered out."""
        mock_module = MagicMock()
        mock_module.lambda_handler.return_value = {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,POST',
            },
            'body': '{"ok": true}'
        }
        mock_handlers.return_value = mock_module

        resp = client.get('/api/some-legacy-route')
        assert resp.status_code == 200
        assert 'Access-Control-Allow-Methods' not in resp.headers

    @patch('app.api.legacy._get_handlers')
    def test_error_returns_generic_message(self, mock_handlers, client):
        """Exception in handler should return generic error, not str(e)."""
        mock_module = MagicMock()
        mock_module.lambda_handler.side_effect = RuntimeError("secret database error")
        mock_handlers.return_value = mock_module

        resp = client.get('/api/some-legacy-route')
        assert resp.status_code == 500
        data = resp.get_json()
        assert data['error'] == 'Internal server error'
        assert 'secret database error' not in str(data)

    def test_analyze_url_skipped_by_proxy(self, client):
        """Routes handled by analyze blueprint should not go through legacy proxy."""
        # POST /api/analyze/url goes to analyze_bp, not legacy
        resp = client.post('/api/analyze/url', json={'url': ''})
        assert resp.status_code == 400
        assert 'URL is required' in resp.get_json()['error']

    @patch('app.api.legacy._get_handlers')
    def test_404_for_unknown_route(self, mock_handlers, client):
        mock_module = MagicMock()
        mock_module.lambda_handler.return_value = {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': '{"error": "Not found"}'
        }
        mock_handlers.return_value = mock_module

        resp = client.get('/api/nonexistent/route')
        assert resp.status_code == 404
