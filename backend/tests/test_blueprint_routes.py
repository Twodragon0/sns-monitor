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


class TestDashboardStats:
    """Tests for dashboard.py stats route uncovered paths (lines 51-62)."""

    @patch('app.api.dashboard.load_metadata_files_local')
    def test_stats_with_items_today(self, mock_load, client):
        """Stats route counts today items and analyzed items."""
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        mock_load.return_value = [
            {
                'timestamp': now_iso,
                'total_comments': 10,
                'sentiment_analysis': {'overall': 'positive'},
            },
            {
                'timestamp': now_iso,
                'total_comments': 5,
                'insights': {'score': 80},
            },
            {
                'timestamp': '2020-01-01T00:00:00',
                'total_comments': 0,
            },
        ]
        resp = client.get('/api/dashboard/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_items'] == 3
        assert data['today_items'] == 2
        assert data['analyzed_items'] == 2
        assert data['total_comments'] == 15

    @patch('app.api.dashboard.load_metadata_files_local')
    def test_stats_analyzed_via_synthesized_result(self, mock_load, client):
        """analyzed_items counts items with synthesized_result."""
        from datetime import datetime, timezone
        mock_load.return_value = [
            {'synthesized_result': 'some result', 'timestamp': '', 'total_comments': 0},
            {'sentiment': 'positive', 'timestamp': '', 'total_comments': 0},
        ]
        resp = client.get('/api/dashboard/stats')
        data = resp.get_json()
        assert data['analyzed_items'] == 2

    @patch('app.api.dashboard.load_channels_from_local')
    def test_channels_error_returns_empty(self, mock_load, client):
        """channels route returns empty list on error."""
        mock_load.side_effect = RuntimeError("disk error")
        resp = client.get('/api/channels')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['channels'] == []

    @patch('app.api.dashboard.load_metadata_files_local')
    @patch('app.api.dashboard.convert_item_to_scan')
    def test_scans_with_items(self, mock_convert, mock_load, client):
        """scans route converts items and returns sorted list."""
        mock_load.return_value = [
            {'timestamp': '2026-03-27T10:00:00'},
            {'timestamp': '2026-03-26T10:00:00'},
        ]
        mock_convert.side_effect = lambda x: {'timestamp': x['timestamp'], 'id': 'scan'}
        resp = client.get('/api/scans')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['scans']) == 2

    @patch('app.api.dashboard.load_metadata_files_local')
    def test_scans_error_returns_empty(self, mock_load, client):
        """scans route returns empty list on error."""
        mock_load.side_effect = RuntimeError("crash")
        resp = client.get('/api/scans')
        assert resp.status_code == 200
        assert resp.get_json()['scans'] == []


class TestDCInsideBlueprintExtra:
    """Extra coverage for dcinside.py uncovered paths."""

    @patch('app.api.dcinside._discover_gallery_ids', return_value=['test-gallery'])
    @patch('app.api.dcinside._load_gallery_data_local')
    def test_galleries_with_data(self, mock_load, mock_discover, client):
        """galleries route processes posts with comments."""
        mock_load.return_value = (
            [
                {
                    'post': {
                        'post_id': 'p1',
                        'title': 'Test Post',
                        'author': 'user1',
                        'date': '2026-03-27',
                        'view_count': 100,
                        'recommend_count': 10,
                        'url': 'http://example.com',
                        'comment_count': 5,
                    },
                    'comments': [{'text': 'hello'}],
                    'content': 'post content',
                }
            ],
            '2026-03-27T00:00:00',
            ['keyword1'],
            20,
            15,
            5,
        )
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['galleries']) > 0

    @patch('app.api.dcinside._load_gallery_data_local')
    def test_galleries_redistribute_comments(self, mock_load, client):
        """galleries route redistributes total_comments when posts have none."""
        mock_load.return_value = (
            [
                {
                    'post': {
                        'post_id': 'p1',
                        'title': 'Post 1',
                        'author': 'anon',
                        'date': '',
                        'view_count': 0,
                        'recommend_count': 0,
                        'url': '',
                        'comment_count': 0,
                    },
                    'comments': [],
                    'content': '',
                },
                {
                    'post': {
                        'post_id': 'p2',
                        'title': 'Post 2',
                        'author': 'anon',
                        'date': '',
                        'view_count': 0,
                        'recommend_count': 0,
                        'url': '',
                        'comment_count': 0,
                    },
                    'comments': [],
                    'content': '',
                },
            ],
            '',
            [],
            10,
            0,
            0,
        )
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 200

    @patch('app.api.dcinside._load_gallery_data_local')
    def test_gallery_posts_with_data(self, mock_load, client):
        """gallery_posts returns paginated posts."""
        mock_load.return_value = (
            [
                {
                    'post': {
                        'post_id': f'p{i}',
                        'title': f'Post {i}',
                        'author': 'user',
                        'date': '2026-03-27',
                        'view_count': i * 10,
                        'recommend_count': i,
                        'url': '',
                        'comment_count': 0,
                    },
                    'comments': [],
                    'content': f'content {i}',
                }
                for i in range(5)
            ],
            '2026-03-27',
            [],
            0,
            0,
            0,
        )
        resp = client.get('/api/dcinside/gallery/example-gallery-1/posts?page=1&limit=3')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['posts']) == 3
        assert data['pagination']['total_posts'] == 5
        assert data['pagination']['has_more'] is True

    @patch('app.api.dcinside._load_gallery_data_local')
    def test_gallery_posts_exception_returns_500(self, mock_load, client):
        """gallery_posts returns 500 on unexpected error."""
        mock_load.side_effect = RuntimeError("unexpected error")
        resp = client.get('/api/dcinside/gallery/valid_gallery/posts')
        assert resp.status_code == 500
        data = resp.get_json()
        assert 'error' in data

    def test_gallery_posts_invalid_id_special_chars(self, client):
        """gallery_posts returns 400 for gallery_id with special chars."""
        resp = client.get('/api/dcinside/gallery/bad%20id/posts')
        assert resp.status_code in (400, 404)


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


class TestCrawlerResultsDCInside:
    """Tests for data.py crawler_results dcinside save path (lines 143-144)."""

    @patch('app.api.data._save_youtube_result', return_value=(False, None))
    @patch('app.api.data._save_dcinside_result', return_value=True)
    def test_dcinside_result_saved(self, mock_dc, mock_yt, client):
        """When youtube save returns False, dcinside save path is tried (line 143-144)."""
        resp = client.post('/api/crawler/results', json={
            'results': [{'gallery_id': 'test_gallery', 'data': []}]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['saved_count'] == 1
        mock_dc.assert_called_once()

    @patch('app.api.data._save_youtube_result', return_value=(False, None))
    @patch('app.api.data._save_dcinside_result', return_value=False)
    def test_dcinside_result_not_saved(self, mock_dc, mock_yt, client):
        """When both saves fail, saved_count stays 0."""
        resp = client.post('/api/crawler/results', json={
            'results': [{'gallery_id': 'unknown', 'data': []}]
        })
        assert resp.status_code == 200
        assert resp.get_json()['saved_count'] == 0


class TestDCInsideBlueprintErrorPaths:
    """Extra coverage for dcinside.py gallery error path (lines 189-195, 210-212)."""

    @patch('app.api.dcinside._load_gallery_data_local')
    def test_galleries_exception_continues(self, mock_load, client):
        """galleries route logs error and continues on exception (lines 210-212)."""
        mock_load.side_effect = Exception("disk read error")
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'galleries' in data

    def test_load_gallery_data_local_invalid_filename(self, tmp_path):
        """lines 93-94: files with non-date filenames fall back to include."""
        import json as _json
        from app.api.dcinside import _load_gallery_data_local
        from unittest.mock import patch as _patch

        gallery_dir = tmp_path / "dcinside" / "testgal"
        gallery_dir.mkdir(parents=True)
        # File with non-date name → ValueError → appended anyway (line 94)
        data = {"data": [], "total_comments": 0, "positive_count": 0, "negative_count": 0}
        (gallery_dir / "notadate.json").write_text(_json.dumps(data))

        with _patch("app.api.dcinside.Config") as mc:
            mc.LOCAL_DATA_DIR = str(tmp_path)
            result = _load_gallery_data_local("testgal")
        assert isinstance(result, tuple)

    def test_load_gallery_data_local_invalid_json(self, tmp_path):
        """lines 122-124: invalid JSON in file is caught and skipped."""
        from app.api.dcinside import _load_gallery_data_local
        from unittest.mock import patch as _patch

        gallery_dir = tmp_path / "dcinside" / "testgal2"
        gallery_dir.mkdir(parents=True)
        (gallery_dir / "2026-01-01_data.json").write_text("{bad json{{")

        with _patch("app.api.dcinside.Config") as mc:
            mc.LOCAL_DATA_DIR = str(tmp_path)
            result = _load_gallery_data_local("testgal2")
        assert result[0] == []  # no posts loaded

    @patch('app.api.dcinside._discover_gallery_ids', return_value=['test-gallery'])
    @patch('app.api.dcinside._load_gallery_data_local')
    def test_galleries_with_total_comments_redistribution(self, mock_load, mock_discover, client):
        """galleries redistributes avg comments when posts have no comments (lines 189-195)."""
        mock_load.return_value = (
            [
                {
                    'post': {
                        'post_id': 'p1', 'title': 'Post 1', 'author': 'a',
                        'date': '', 'view_count': 10, 'recommend_count': 0,
                        'url': '', 'comment_count': 0,
                    },
                    'comments': [],
                    'content': '',
                },
                {
                    'post': {
                        'post_id': 'p2', 'title': 'Post 2', 'author': 'b',
                        'date': '', 'view_count': 5, 'recommend_count': 0,
                        'url': '', 'comment_count': 0,
                    },
                    'comments': [],
                    'content': '',
                },
            ],
            '2026-01-01',
            [],
            20,   # total_comments > 0 triggers redistribution
            0,
            0,
        )
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['galleries']) > 0
