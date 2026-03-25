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


class TestLocalSummary:
    """Tests for POST /api/analysis/local-summary."""

    def test_missing_sources(self, client):
        resp = client.post('/api/analysis/local-summary', json={})
        assert resp.status_code == 400
        assert 'No data sources' in resp.get_json()['error']

    def test_empty_sources(self, client):
        resp = client.post('/api/analysis/local-summary', json={'sources': []})
        assert resp.status_code == 400

    def test_invalid_source_id(self, client):
        resp = client.post('/api/analysis/local-summary', json={
            'sources': [{'type': 'youtube', 'id': '../../../etc'}]
        })
        assert resp.status_code == 400
        assert 'Invalid source id' in resp.get_json()['error']

    @patch('app.api.analysis._read_source_items')
    def test_no_data_found(self, mock_read, client):
        mock_read.return_value = ([], {})
        resp = client.post('/api/analysis/local-summary', json={
            'sources': [{'type': 'youtube', 'id': 'test-channel'}]
        })
        assert resp.status_code == 404


class TestSentimentTrend:
    """Tests for GET /api/analysis/trend."""

    def test_missing_type_param(self, client):
        resp = client.get('/api/analysis/trend')
        assert resp.status_code in (400, 200)

    def test_missing_id_param(self, client):
        resp = client.get('/api/analysis/trend?type=dcinside')
        assert resp.status_code in (400, 200)

    def test_invalid_id_rejected(self, client):
        resp = client.get('/api/analysis/trend?type=dcinside&id=../../../etc')
        assert resp.status_code == 400


class TestAiSummary:
    """Tests for POST /api/analysis/ai-summary."""

    def test_no_sources(self, client):
        resp = client.post('/api/analysis/ai-summary', json={})
        # Either 400 (no sources) or 503 (no LLM provider)
        assert resp.status_code in (400, 503)

    @patch('app.services.llm_analyzer.get_available_provider', return_value=None)
    def test_no_llm_provider(self, mock_provider, client):
        resp = client.post('/api/analysis/ai-summary', json={
            'sources': [{'type': 'youtube', 'id': 'test'}]
        })
        assert resp.status_code == 503

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    def test_invalid_source_id(self, mock_provider, client):
        resp = client.post('/api/analysis/ai-summary', json={
            'sources': [{'type': 'youtube', 'id': '../../etc'}]
        })
        assert resp.status_code == 400


class TestAnalysisReports:
    """Tests for GET /api/analysis/reports."""

    def test_list_reports(self, client):
        resp = client.get('/api/analysis/reports')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'reports' in data

    def test_report_by_date_not_found(self, client):
        resp = client.get('/api/analysis/reports/2099-01-01')
        assert resp.status_code in (200, 404)
