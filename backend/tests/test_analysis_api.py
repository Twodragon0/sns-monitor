"""Tests for /api/analysis/* endpoints."""

import pytest
from unittest.mock import patch, MagicMock


class TestAnalysisStatus:
    """Tests for GET /api/analysis/status."""

    @patch('app.api.analysis.requests.get')
    def test_mirofish_available(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        resp = client.get('/api/analysis/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['mirofish_available'] is True

    @patch('app.api.analysis.requests.get')
    def test_mirofish_unavailable(self, mock_get, client):
        mock_get.side_effect = ConnectionError("refused")

        resp = client.get('/api/analysis/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['mirofish_available'] is False

    @patch('app.api.analysis.requests.get')
    def test_mirofish_500(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        resp = client.get('/api/analysis/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['mirofish_available'] is False


class TestAnalysisSources:
    """Tests for GET /api/analysis/sources."""

    @patch('app.api.analysis.Path')
    def test_empty_data_dir(self, mock_path, client):
        mock_dir = MagicMock()
        mock_path.return_value = mock_dir
        # YouTube dir doesn't exist
        yt_dir = MagicMock()
        yt_dir.exists.return_value = False
        # DCInside dir doesn't exist
        dc_dir = MagicMock()
        dc_dir.exists.return_value = False
        mock_dir.__truediv__ = lambda self, key: yt_dir if 'youtube' in str(key) else dc_dir

        resp = client.get('/api/analysis/sources')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'sources' in data


class TestTransformSnsData:
    """Tests for POST /api/analysis/transform."""

    def test_missing_sources(self, client):
        resp = client.post('/api/analysis/transform', json={})
        assert resp.status_code == 400
        assert 'No data sources' in resp.get_json()['error']

    def test_empty_sources_list(self, client):
        resp = client.post('/api/analysis/transform', json={'sources': []})
        assert resp.status_code == 400


class TestAnalysisLlmStatus:
    """Tests for GET /api/analysis/llm/status."""

    def test_llm_status(self, client):
        resp = client.get('/api/analysis/llm/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'available' in data
