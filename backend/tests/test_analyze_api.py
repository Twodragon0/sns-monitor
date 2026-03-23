"""Tests for /api/analyze/url and /api/analyze/summarize endpoints."""

import pytest
from unittest.mock import patch, MagicMock


class TestAnalyzeUrl:
    """Tests for POST /api/analyze/url."""

    def test_missing_body(self, client):
        resp = client.post('/api/analyze/url', content_type='application/json')
        assert resp.status_code == 400
        assert 'URL is required' in resp.get_json()['error']

    def test_missing_url_field(self, client):
        resp = client.post('/api/analyze/url', json={'foo': 'bar'})
        assert resp.status_code == 400
        assert 'URL is required' in resp.get_json()['error']

    def test_empty_url(self, client):
        resp = client.post('/api/analyze/url', json={'url': ''})
        assert resp.status_code == 400
        assert 'URL is required' in resp.get_json()['error']

    def test_whitespace_url(self, client):
        resp = client.post('/api/analyze/url', json={'url': '   '})
        assert resp.status_code == 400
        assert 'URL is required' in resp.get_json()['error']

    def test_too_long_url(self, client):
        long_url = 'https://example.com/' + 'a' * 2048
        resp = client.post('/api/analyze/url', json={'url': long_url})
        assert resp.status_code == 400
        assert 'too long' in resp.get_json()['error']

    def test_invalid_scheme_ftp(self, client):
        resp = client.post('/api/analyze/url', json={'url': 'ftp://example.com'})
        assert resp.status_code == 400
        assert 'Invalid URL format' in resp.get_json()['error']

    def test_invalid_scheme_javascript(self, client):
        resp = client.post('/api/analyze/url', json={'url': 'javascript:alert(1)'})
        assert resp.status_code == 400
        assert 'Invalid URL format' in resp.get_json()['error']

    @patch('app.api.analyze._get_analyzer')
    def test_successful_analysis(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = {
            'platform': 'youtube',
            'title': 'Test Video',
            'analyzed_at': '2025-01-01T00:00:00',
        }
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.post('/api/analyze/url', json={'url': 'https://youtube.com/watch?v=test'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['platform'] == 'youtube'
        assert data['title'] == 'Test Video'

    @patch('app.api.analyze._get_analyzer')
    def test_value_error_returns_400(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = ValueError("Unsupported platform")
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.post('/api/analyze/url', json={'url': 'https://example.com'})
        assert resp.status_code == 400
        assert 'Unsupported platform' in resp.get_json()['error']

    @patch('app.api.analyze._get_analyzer')
    def test_unexpected_error_returns_500(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = RuntimeError("Connection failed")
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.post('/api/analyze/url', json={'url': 'https://youtube.com/watch?v=test'})
        assert resp.status_code == 500
        assert resp.get_json()['error'] == 'Internal server error'


class TestSummarizeAnalysis:
    """Tests for POST /api/analyze/summarize."""

    def test_missing_result(self, client):
        resp = client.post('/api/analyze/summarize', json={})
        assert resp.status_code == 400
        assert 'Analysis result is required' in resp.get_json()['error']

    @patch('app.api.analyze.Config')
    def test_local_fallback_summary(self, mock_config, client):
        """When MiroFish and LLM are unavailable, should return local summary."""
        mock_config.MIROFISH_ENDPOINT = 'http://nonexistent:5001'
        mock_config.MIROFISH_SSL_VERIFY = False

        result = {
            'platform': 'youtube',
            'title': 'Test Video',
            'analyzed_at': '2025-01-01T00:00:00',
            'view_count': 1000,
            'comment_count': 50,
            'analysis': {
                'overall': 'positive',
                'total': 50,
                'sentiment': {'positive': 30, 'neutral': 15, 'negative': 5},
                'top_keywords': [{'word': 'good', 'count': 10}],
            },
        }

        resp = client.post('/api/analyze/summarize', json={'result': result})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'summary' in data
        assert data['source'] == 'local'
        assert 'Test Video' in data['summary']


class TestListPlatforms:
    """Tests for GET /api/platforms."""

    @patch('app.api.analyze._get_analyzer')
    def test_list_platforms(self, mock_get_analyzer, client):
        mock_analyzer = MagicMock()
        mock_analyzer.list_platforms.return_value = ['youtube', 'dcinside']
        mock_analyzer.get_api_usage.return_value = {'youtube': 10}
        mock_get_analyzer.return_value = mock_analyzer

        resp = client.get('/api/platforms')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'platforms' in data
        assert 'api_usage' in data
