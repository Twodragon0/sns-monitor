"""Tests for Blueprint route modules (dashboard, dcinside, data, vuddy, members)."""

import pytest
from unittest.mock import patch


class TestDashboardBlueprint:
    """Tests for dashboard.py routes."""

    def test_dashboard_stats(self, client):
        """dashboard_stats is a direct implementation (no legacy wrapper)."""
        resp = client.get('/api/dashboard/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total_items' in data
        assert 'today_items' in data

    @patch('app.api.dashboard.load_metadata_files_local', return_value=[])
    def test_scans(self, mock_load, client):
        """scans is a direct implementation (no legacy wrapper)."""
        resp = client.get('/api/scans')
        assert resp.status_code == 200
        assert 'scans' in resp.get_json()

    def test_channels(self, client):
        """channels is a direct implementation."""
        resp = client.get('/api/channels')
        assert resp.status_code == 200
        assert 'channels' in resp.get_json()

    def test_vuddy_creators_local_mode(self, client):
        """vuddy_creators returns 200 in LOCAL_MODE."""
        resp = client.get('/api/vuddy/creators')
        assert resp.status_code == 200
        assert 'creators' in resp.get_json()

    @patch('app.api.vuddy.Config')
    def test_vuddy_creators_s3_mode_returns_501(self, mock_cfg, client):
        """vuddy_creators returns 501 when LOCAL_MODE=False."""
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/vuddy/creators')
        assert resp.status_code == 501
        assert 'error' in resp.get_json()

    def test_group_a_members_local_mode(self, client):
        """group-a/members returns 200 in LOCAL_MODE (empty creators OK)."""
        resp = client.get('/api/group-a/members')
        assert resp.status_code == 200

    def test_group_b_members_local_mode(self, client):
        resp = client.get('/api/group-b/members')
        assert resp.status_code == 200

    def test_group_c_members_local_mode(self, client):
        resp = client.get('/api/group-c/members')
        assert resp.status_code == 200

    @patch('app.api.members.Config')
    def test_group_a_members_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/group-a/members')
        assert resp.status_code == 501
        assert 'error' in resp.get_json()

    def test_group_a_channel_local_mode(self, client):
        resp = client.get('/api/group-a/channel')
        assert resp.status_code == 200

    def test_group_b_channel_local_mode(self, client):
        resp = client.get('/api/group-b/channel')
        assert resp.status_code == 200

    def test_group_c_channel_local_mode(self, client):
        resp = client.get('/api/group-c/channel')
        assert resp.status_code == 200

    @patch('app.api.members.Config')
    def test_group_a_channel_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/group-a/channel')
        assert resp.status_code == 501
        assert 'error' in resp.get_json()


class TestDCInsideBlueprint:
    """Tests for dcinside.py routes."""

    def test_galleries_local_mode(self, client):
        """galleries returns 200 in LOCAL_MODE."""
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 200
        assert 'galleries' in resp.get_json()

    @patch('app.api.dcinside.Config')
    def test_galleries_s3_mode_returns_501(self, mock_cfg, client):
        """galleries returns 501 when LOCAL_MODE=False."""
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 501
        assert 'error' in resp.get_json()

    def test_gallery_posts_local_mode(self, client):
        """gallery_posts returns 200 in LOCAL_MODE (empty posts OK)."""
        resp = client.get('/api/dcinside/gallery/test_gallery/posts')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'posts' in data
        assert 'pagination' in data

    @patch('app.api.dcinside.Config')
    def test_gallery_posts_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/dcinside/gallery/test_gallery/posts')
        assert resp.status_code == 501
        assert 'error' in resp.get_json()

    def test_gallery_posts_invalid_id(self, client):
        """gallery_posts returns 400 for invalid gallery_id."""
        resp = client.get('/api/dcinside/gallery/../posts')
        assert resp.status_code in (400, 404)


class TestDataBlueprint:
    """Tests for data.py routes."""

    def test_get_data_returns_501(self, client):
        """get_data always returns 501 (S3 route removed)."""
        resp = client.get('/api/data/some/path.json')
        assert resp.status_code == 501
        assert 'error' in resp.get_json()

    def test_crawler_results_local_mode(self, client):
        """crawler_results saves in LOCAL_MODE."""
        resp = client.post('/api/crawler/results', json={'results': []})
        assert resp.status_code == 200
        assert 'saved_count' in resp.get_json()

    @patch('app.api.data.Config')
    def test_crawler_results_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.post('/api/crawler/results', json={'results': []})
        assert resp.status_code == 501
        assert 'error' in resp.get_json()

    def test_twitter_search_local_mode(self, client):
        """twitter_search handles LOCAL_MODE requests."""
        resp = client.post('/api/twitter/search', json={'action': 'search', 'keywords': ['test']})
        assert resp.status_code in (200, 400, 500)

    @patch('app.api.data.Config')
    def test_twitter_search_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.post('/api/twitter/search', json={'action': 'search'})
        assert resp.status_code == 501
        assert 'error' in resp.get_json()


class TestErrorHandling:
    """Tests for error handling on blueprint routes."""

    @patch('app.api.dashboard.load_metadata_files_local')
    def test_dashboard_error_graceful(self, mock_load, client):
        """dashboard_stats handles errors internally, returns empty stats."""
        mock_load.side_effect = RuntimeError("db crash")
        resp = client.get('/api/dashboard/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_items'] == 0
        assert 'db crash' not in resp.get_data(as_text=True)

    @patch('app.api.dcinside.Config')
    def test_dcinside_s3_mode_returns_501(self, mock_cfg, client):
        """dcinside returns 501 in S3 mode (not 500)."""
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 501

    @patch('app.api.data.Config')
    def test_data_s3_mode_returns_501(self, mock_cfg, client):
        """data routes return 501 in S3 mode."""
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/data/some/key.json')
        assert resp.status_code == 501
