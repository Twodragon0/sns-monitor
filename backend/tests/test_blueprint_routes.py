"""Tests for new Blueprint route modules (dashboard, dcinside, data)."""

import pytest
from unittest.mock import patch, MagicMock


DASH_H = 'app.api.dashboard.get_handlers'
DC_H = 'app.api.dcinside.get_handlers'
DATA_H = 'app.api.data.get_handlers'


def _mock_result(body='{"ok": true}', status=200):
    return {'statusCode': status, 'body': body}


class TestDashboardBlueprint:
    """Tests for dashboard.py routes."""

    def test_dashboard_stats(self, client):
        """dashboard_stats is now a direct implementation (no legacy wrapper)."""
        resp = client.get('/api/dashboard/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total_items' in data
        assert 'today_items' in data

    @patch(DASH_H)
    def test_scans(self, mock_gh, client):
        mock_gh.return_value._handle_scans.return_value = _mock_result()
        resp = client.get('/api/scans')
        assert resp.status_code == 200

    def test_channels(self, client):
        """channels is now a direct implementation."""
        resp = client.get('/api/channels')
        assert resp.status_code == 200
        assert 'channels' in resp.get_json()

    @patch(DASH_H)
    def test_vuddy_creators(self, mock_gh, client):
        mock_gh.return_value._handle_vuddy_creators.return_value = _mock_result()
        resp = client.get('/api/vuddy/creators')
        assert resp.status_code == 200

    @patch(DASH_H)
    def test_group_a_members(self, mock_gh, client):
        mock_gh.return_value._handle_group_a_members.return_value = _mock_result()
        resp = client.get('/api/group-a/members')
        assert resp.status_code == 200

    @patch(DASH_H)
    def test_group_b_members(self, mock_gh, client):
        mock_gh.return_value._handle_group_b_members.return_value = _mock_result()
        resp = client.get('/api/group-b/members')
        assert resp.status_code == 200

    @patch(DASH_H)
    def test_group_c_members(self, mock_gh, client):
        mock_gh.return_value._handle_group_c_members.return_value = _mock_result()
        resp = client.get('/api/group-c/members')
        assert resp.status_code == 200

    @patch(DASH_H)
    def test_group_a_channel(self, mock_gh, client):
        mock_gh.return_value._handle_group_a_channel.return_value = _mock_result()
        resp = client.get('/api/group-a/channel?id=test')
        assert resp.status_code == 200

    @patch(DASH_H)
    def test_group_b_channel(self, mock_gh, client):
        mock_gh.return_value._handle_group_b_channel.return_value = _mock_result()
        resp = client.get('/api/group-b/channel')
        assert resp.status_code == 200

    @patch(DASH_H)
    def test_group_c_channel(self, mock_gh, client):
        mock_gh.return_value._handle_group_c_channel.return_value = _mock_result()
        resp = client.get('/api/group-c/channel')
        assert resp.status_code == 200


class TestDCInsideBlueprint:
    """Tests for dcinside.py routes."""

    @patch(DC_H)
    def test_galleries(self, mock_gh, client):
        mock_gh.return_value._handle_dcinside_galleries.return_value = _mock_result()
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 200

    @patch(DC_H)
    def test_gallery_posts(self, mock_gh, client):
        mock_gh.return_value._handle_dcinside_gallery_posts.return_value = _mock_result()
        resp = client.get('/api/dcinside/gallery/test_gallery/posts')
        assert resp.status_code == 200


class TestDataBlueprint:
    """Tests for data.py routes."""

    @patch(DATA_H)
    def test_get_data(self, mock_gh, client):
        mock_gh.return_value._handle_data_s3_key.return_value = _mock_result()
        resp = client.get('/api/data/some/path.json')
        assert resp.status_code == 200

    @patch(DATA_H)
    def test_crawler_results(self, mock_gh, client):
        mock_gh.return_value._handle_crawler_results.return_value = _mock_result()
        resp = client.post('/api/crawler/results', json={'data': 'test'})
        assert resp.status_code == 200

    @patch(DATA_H)
    def test_twitter_search(self, mock_gh, client):
        mock_gh.return_value._handle_twitter_search.return_value = _mock_result()
        resp = client.post('/api/twitter/search', json={'query': 'test'})
        assert resp.status_code == 200


class TestSafeLegacyCall:
    """Tests for error handling decorator on blueprint routes."""

    @patch('app.api.dashboard.load_metadata_files_local')
    def test_dashboard_error_graceful(self, mock_load, client):
        """dashboard_stats handles errors internally, returns empty stats."""
        mock_load.side_effect = RuntimeError("db crash")
        resp = client.get('/api/dashboard/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_items'] == 0
        assert 'db crash' not in resp.get_data(as_text=True)

    @patch(DC_H)
    def test_dcinside_error_returns_500(self, mock_gh, client):
        mock_gh.return_value._handle_dcinside_galleries.side_effect = Exception("oops")
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 500
        assert resp.get_json()['error'] == 'Internal server error'

    @patch(DATA_H)
    def test_data_error_returns_500(self, mock_gh, client):
        mock_gh.return_value._handle_data_s3_key.side_effect = ValueError("bad key")
        resp = client.get('/api/data/some/key.json')
        assert resp.status_code == 500
        assert resp.get_json()['error'] == 'Internal server error'


class TestLegacyHelpers:
    """Tests for shared legacy_helpers module."""

    def test_legacy_response_defaults(self):
        from app.api.legacy_helpers import legacy_response
        resp = legacy_response({})
        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == '{}'

    def test_legacy_response_custom_status(self):
        from app.api.legacy_helpers import legacy_response
        resp = legacy_response({'statusCode': 404, 'body': '{"error":"nope"}'})
        assert resp.status_code == 404

    def test_build_event(self, client):
        from app.api.legacy_helpers import build_event
        with client.application.test_request_context('/api/test?foo=bar', method='GET'):
            event = build_event()
            assert event['httpMethod'] == 'GET'
            assert event['path'] == '/api/test'
            assert event['queryStringParameters'] == {'foo': 'bar'}
