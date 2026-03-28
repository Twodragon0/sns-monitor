"""Targeted tests to boost coverage for app/api/members.py and app/api/dashboard.py.

Covers uncovered lines:
  members.py  : 119, 230, 287-300, 342-362, 389-408, 425-427, 434-441, 475-477, 490, 548-550
  dashboard.py: 78-83, 88, 103-106, 144
"""

import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, mock_open

import pytest


# ---------------------------------------------------------------------------
# dashboard.py — uncovered lines 78-83, 88, 103-106, 144
# ---------------------------------------------------------------------------

class TestDashboardRedisCache:
    """Lines 78-83: Redis cache hit returns cached data."""

    def test_stats_redis_cache_hit(self, client):
        """When Redis returns a cached value the route returns it immediately."""
        cached_stats = {
            'total_items': 42,
            'today_items': 7,
            'analyzed_items': 5,
            'total_comments': 100,
            'avg_sentiment': 'positive',
        }
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached_stats).encode()

        with patch('app.api.dashboard.get_redis', return_value=mock_redis):
            resp = client.get('/api/dashboard/stats')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_items'] == 42
        assert data['today_items'] == 7
        mock_redis.get.assert_called_once()

    def test_stats_redis_exception_falls_through(self, client):
        """When Redis.get raises an exception the route falls through to compute."""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("redis error")

        with patch('app.api.dashboard.get_redis', return_value=mock_redis), \
             patch('app.api.dashboard.load_metadata_files_local', return_value=[]):
            resp = client.get('/api/dashboard/stats')

        assert resp.status_code == 200

    def test_stats_redis_stores_result(self, client):
        """Lines 103-106: When Redis is available and no cache hit, result is stored."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # cache miss

        with patch('app.api.dashboard.get_redis', return_value=mock_redis), \
             patch('app.api.dashboard.load_metadata_files_local', return_value=[]):
            resp = client.get('/api/dashboard/stats')

        assert resp.status_code == 200
        mock_redis.setex.assert_called_once()

    def test_stats_redis_setex_exception_ignored(self, client):
        """Lines 103-106: Exception in Redis setex is silently caught."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.setex.side_effect = Exception("write error")

        with patch('app.api.dashboard.get_redis', return_value=mock_redis), \
             patch('app.api.dashboard.load_metadata_files_local', return_value=[]):
            resp = client.get('/api/dashboard/stats')

        assert resp.status_code == 200


class TestDashboardInMemoryCache:
    """Line 88: In-memory cache hit path."""

    def test_stats_in_memory_cache_hit(self, client):
        """When in-memory cache is valid the cached data is returned."""
        import app.api.dashboard as dash
        cached = {
            'total_items': 99,
            'today_items': 3,
            'analyzed_items': 1,
            'total_comments': 50,
            'avg_sentiment': 'neutral',
        }
        # Set in-memory cache to a future expiry
        dash._stats_cache = {'data': cached, 'expires': 9_999_999_999}

        with patch('app.api.dashboard.get_redis', return_value=None):
            resp = client.get('/api/dashboard/stats')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_items'] == 99

        # Reset for other tests
        dash._stats_cache = {'data': None, 'expires': 0}


class TestDashboardScansPlatformFilter:
    """Line 144: Platform filter path in scans."""

    @patch('app.api.dashboard.load_metadata_files_local')
    @patch('app.api.dashboard.convert_item_to_scan')
    def test_scans_platform_filter(self, mock_convert, mock_load, client):
        """When platform query param is set, items are filtered by platform."""
        mock_load.return_value = [
            {'timestamp': '2026-01-01T00:00:00', 'platform': 'youtube'},
            {'timestamp': '2026-01-02T00:00:00', 'platform': 'reddit'},
            {'timestamp': '2026-01-03T00:00:00', 'platform': 'youtube'},
        ]
        mock_convert.side_effect = lambda x: {'platform': x['platform']}

        resp = client.get('/api/scans?platform=youtube')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] == 2
        for scan in data['scans']:
            assert scan['platform'] == 'youtube'

    @patch('app.api.dashboard.load_metadata_files_local')
    @patch('app.api.dashboard.convert_item_to_scan')
    def test_scans_platform_filter_no_match(self, mock_convert, mock_load, client):
        """Platform filter returns empty list when no items match."""
        mock_load.return_value = [
            {'timestamp': '2026-01-01T00:00:00', 'platform': 'youtube'},
        ]
        mock_convert.side_effect = lambda x: x

        resp = client.get('/api/scans?platform=telegram')
        data = resp.get_json()
        assert data['total'] == 0
        assert data['scans'] == []


# ---------------------------------------------------------------------------
# members.py — uncovered lines
# ---------------------------------------------------------------------------

class TestProcessCommentsBcCutoffContinue:
    """Line 119: continue when comment is outside cutoff."""

    def test_old_comment_excluded_by_cutoff(self):
        """Comments older than cutoff are skipped (line 119 continue)."""
        from app.api.members import _process_comments_bc
        # cutoff is now; old comment is 30 days ago
        cutoff = datetime.now()
        old_pub = (datetime.now() - timedelta(days=30)).isoformat()
        recent_pub = (datetime.now() + timedelta(days=1)).isoformat()

        creator_data = {
            'comment_samples': [
                {'text': 'old comment', 'published_at': old_pub},
                {'text': 'recent comment', 'published_at': recent_pub},
            ]
        }
        result = _process_comments_bc(creator_data, cutoff)
        texts = [c['text'] for c in result]
        assert 'recent comment' in texts
        assert 'old comment' not in texts


class TestBuildCreatorsBcVideoLinks:
    """Line 230: video_links loop in _build_creators_bc."""

    def test_video_links_populated(self):
        """video_links from creator_data are appended to creator_info."""
        from app.api.members import _build_creators_bc
        data = {
            'creators': [{
                'name': 'Creator',
                'youtube_channel': '@creator',
                'total_comments': 0,
                'total_likes': 0,
                'comment_samples': [],
                'video_links': [
                    {'title': 'Video 1', 'url': 'https://yt.com/v1', 'channel': 'Creator', 'published_at': '2026-01-01'},
                    {'title': 'Video 2', 'url': 'https://yt.com/v2', 'channel': 'Creator', 'published_at': '2026-01-02'},
                ],
            }]
        }
        result = _build_creators_bc(data, '2026-01-01')
        assert len(result) == 1
        assert len(result[0]['video_links']) == 2
        assert result[0]['video_links'][0]['title'] == 'Video 1'
        assert result[0]['video_links'][1]['url'] == 'https://yt.com/v2'

    def test_video_links_channel_falls_back_to_name(self):
        """video_links channel falls back to creator name when missing."""
        from app.api.members import _build_creators_bc
        data = {
            'creators': [{
                'name': 'MyCreator',
                'total_comments': 0,
                'total_likes': 0,
                'comment_samples': [],
                'video_links': [
                    {'title': 'V1', 'url': 'https://yt.com/v1'},
                ],
            }]
        }
        result = _build_creators_bc(data, '')
        assert result[0]['video_links'][0]['channel'] == 'MyCreator'


class TestFindChannelFilesLocalBody:
    """Lines 287-300: body of _find_channel_files_local when directory exists."""

    def test_matching_channel_handle_found(self, tmp_path):
        """File with matching channel_handle is returned."""
        from app.api.members import _find_channel_files_local
        channel_data = {'channel_handle': '@testchannel', 'channel_title': 'Test'}
        (tmp_path / 'test_channel.json').write_text(json.dumps(channel_data))

        matches = _find_channel_files_local(str(tmp_path), '@testchannel')
        assert len(matches) == 1
        assert matches[0][2]['channel_handle'] == '@testchannel'

    def test_channel_handle_without_at_matches(self, tmp_path):
        """File matches when file handle has no @ but we search with @."""
        from app.api.members import _find_channel_files_local
        # ch='creator', handle='@creator' → ch == handle.lstrip('@').lower()
        channel_data = {'channel_handle': 'creator', 'channel_title': 'Creator'}
        (tmp_path / 'creator.json').write_text(json.dumps(channel_data))

        matches = _find_channel_files_local(str(tmp_path), '@creator')
        assert len(matches) == 1

    def test_non_matching_handle_excluded(self, tmp_path):
        """Files with different handle are not returned."""
        from app.api.members import _find_channel_files_local
        channel_data = {'channel_handle': '@other', 'channel_title': 'Other'}
        (tmp_path / 'other.json').write_text(json.dumps(channel_data))

        matches = _find_channel_files_local(str(tmp_path), '@nothere')
        assert matches == []

    def test_invalid_json_file_skipped(self, tmp_path):
        """Files with invalid JSON are silently skipped."""
        from app.api.members import _find_channel_files_local
        (tmp_path / 'bad.json').write_text('{not valid json}')

        matches = _find_channel_files_local(str(tmp_path), '@anything')
        assert matches == []

    def test_non_json_files_skipped(self, tmp_path):
        """Non-.json files are ignored."""
        from app.api.members import _find_channel_files_local
        (tmp_path / 'readme.txt').write_text('not a json file')
        (tmp_path / 'data.json').write_text(json.dumps({'channel_handle': '@ch'}))

        matches = _find_channel_files_local(str(tmp_path), '@ch')
        assert len(matches) == 1


class TestHandleChannelAllLocal:
    """Lines 342-362: _handle_channel_all_local with populated members_data."""

    def test_channels_built_from_members_data(self):
        """Channels list is built from members_data creators."""
        from app.api.members import _handle_channel_all_local
        members_data = {
            'updated_at': '2026-01-01',
            'creators': [
                {
                    'channel_handle': '@creator1',
                    'channel_title': 'Creator One',
                    'profile_image': 'http://img.url/1',
                    'subscriber_count': 1000,
                    'total_comments': 50,
                    'total_videos': 10,
                    'comment_samples': [{'text': 'hi'}],
                },
                {
                    'youtube_channel': '@creator2',
                    'name': 'Creator Two (alias)',
                    'subscriber_count': 2000,
                    'total_comments': 100,
                    'total_videos': 20,
                    'comment_samples': [],
                },
            ],
        }
        result = _handle_channel_all_local('group-b', members_data)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert len(body['channels']) == 2
        assert body['last_crawled'] == '2026-01-01'
        assert body['channels'][0]['channel_handle'] == '@creator1'
        assert body['channels'][1]['channel_handle'] == '@creator2'

    def test_channels_empty_when_no_members_data(self):
        """Returns empty channels list when members_data is None."""
        from app.api.members import _handle_channel_all_local
        result = _handle_channel_all_local('group-b', None)
        body = json.loads(result['body'])
        assert body['channels'] == []

    def test_last_crawled_falls_back_to_timestamp(self):
        """last_crawled uses timestamp field if updated_at is absent."""
        from app.api.members import _handle_channel_all_local
        members_data = {
            'timestamp': '2026-02-15',
            'creators': [],
        }
        result = _handle_channel_all_local('group-c', members_data)
        body = json.loads(result['body'])
        assert body['last_crawled'] == '2026-02-15'


class TestHandleChannelAllGroupALocal:
    """Lines 389-408: _handle_channel_all_group_a_local with existing file."""

    def test_missing_file_returns_empty_channels(self):
        """Returns empty channels when group-a-channel-members.json is absent."""
        from app.api.members import _handle_channel_all_group_a_local
        with patch('os.path.exists', return_value=False):
            result = _handle_channel_all_group_a_local()
        body = json.loads(result['body'])
        assert body['channels'] == []
        assert result['statusCode'] == 200

    def test_valid_file_builds_channels(self, tmp_path):
        """Valid group-a channel file is parsed and channels returned."""
        from app.api.members import _handle_channel_all_group_a_local
        channel_file = tmp_path / 'vuddy' / 'comprehensive_analysis'
        channel_file.mkdir(parents=True)
        data = {
            'updated_at': '2026-03-01',
            'creators': [
                {
                    'channel_handle': '@creator_a',
                    'channel_title': 'Creator A',
                    'profile_image': '',
                    'subscriber_count': 500,
                    'total_comments': 30,
                    'total_videos': 5,
                    'comment_samples': [],
                }
            ],
        }
        (channel_file / 'group-a-channel-members.json').write_text(json.dumps(data))

        with patch('app.api.members.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            result = _handle_channel_all_group_a_local()

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert len(body['channels']) == 1
        assert body['channels'][0]['channel_handle'] == '@creator_a'
        assert body['last_crawled'] == '2026-03-01'

    def test_invalid_json_file_returns_empty_channels(self, tmp_path):
        """Exception during file parse returns empty channels (lines 407-408)."""
        from app.api.members import _handle_channel_all_group_a_local
        channel_file = tmp_path / 'vuddy' / 'comprehensive_analysis'
        channel_file.mkdir(parents=True)
        (channel_file / 'group-a-channel-members.json').write_text('{bad json{')

        with patch('app.api.members.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            result = _handle_channel_all_group_a_local()

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['channels'] == []


class TestHandleChannelSpecificLocalDataFound:
    """Lines 425-427, 434-441: channel data found paths."""

    def test_group_a_triggers_crawler_when_no_data(self, client):
        """Lines 425-427: group-a triggers crawler when channel not found."""
        with patch('app.api.members._find_channel_files_local', return_value=[]), \
             patch('app.api.members._trigger_youtube_crawler') as mock_trigger:
            resp = client.get('/api/group-a/channel?channel_handle=@newchannel')
        assert resp.status_code == 200
        mock_trigger.assert_called_once_with('@newchannel')

    def test_channel_data_found_builds_response(self, tmp_path):
        """Lines 434-441: when matching channel file exists, result is built."""
        from app.api.members import _handle_channel_specific_local
        channel_data = {
            'channel_title': 'Test Channel',
            'channel_id': 'UC123',
            'channel_handle': '@testch',
            'timestamp': '2026-01-10',
            'statistics': {'subscriberCount': 1000},
            'videos': [
                {
                    'video': {'video_id': 'v1', 'title': 'Test Video', 'view_count': 500},
                    'comments': [{'text': 'good'}],
                    'vtuber_stats': {},
                }
            ],
        }
        import time
        matches = [(str(tmp_path / 'ch.json'), time.time(), channel_data)]

        with patch('app.api.members._find_channel_files_local', return_value=matches), \
             patch('app.api.members.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            # Need a request context for _handle_channel_specific_local
            from app import create_app
            app = create_app()
            with app.test_request_context('/api/group-b/channel?channel_handle=@testch'):
                result = _handle_channel_specific_local('group-b', '@testch')

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['channel_title'] == 'Test Channel'
        assert body['total_comments'] == 1

    def test_channel_data_not_found_returns_empty_result(self, tmp_path):
        """When no matching channel found, empty result is returned."""
        from app.api.members import _handle_channel_specific_local
        from app import create_app

        with patch('app.api.members._find_channel_files_local', return_value=[]):
            app = create_app()
            with app.test_request_context('/api/group-b/channel?channel_handle=@unknown'):
                result = _handle_channel_specific_local('group-b', '@unknown')

        body = json.loads(result['body'])
        assert body['channel_handle'] == '@unknown'
        assert body['videos'] == []
        assert body['total_comments'] == 0


class TestTriggerYoutubeCrawler:
    """Lines 475-477, 490: _trigger_youtube_crawler success path."""

    def test_trigger_success_logs_info(self):
        """Lines 475-490: successful POST to crawler endpoint."""
        from app.api.members import _trigger_youtube_crawler
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_requests.post.return_value = mock_response

        with patch.dict('sys.modules', {'requests': mock_requests}):
            # Re-import to pick up the mock
            import importlib
            import app.api.members as members_mod
            original = members_mod._trigger_youtube_crawler

            # Call with patched requests inside the function
            with patch('app.api.members.os.environ.get', return_value='http://test-crawler:5000/invoke'):
                # Patch requests inside the function's try block
                import sys
                real_requests = sys.modules.get('requests')
                mock_req = MagicMock()
                mock_req.post.return_value = MagicMock()
                sys.modules['requests'] = mock_req
                try:
                    _trigger_youtube_crawler('@testhandle')
                finally:
                    if real_requests is not None:
                        sys.modules['requests'] = real_requests
                    elif 'requests' in sys.modules:
                        del sys.modules['requests']

            mock_req.post.assert_called_once()
            call_kwargs = mock_req.post.call_args
            assert '@testhandle' in str(call_kwargs)

    def test_trigger_post_exception_logged(self):
        """Lines 492-493: exception from POST is caught and logged."""
        from app.api.members import _trigger_youtube_crawler
        import sys
        real_requests = sys.modules.get('requests')
        mock_req = MagicMock()
        mock_req.post.side_effect = Exception("connection refused")
        sys.modules['requests'] = mock_req
        try:
            # Should not raise
            _trigger_youtube_crawler('@badhandle')
        finally:
            if real_requests is not None:
                sys.modules['requests'] = real_requests
            elif 'requests' in sys.modules:
                del sys.modules['requests']

    def test_trigger_import_error_handled(self):
        """Lines 475-477: ImportError when requests not installed is handled."""
        import sys
        import builtins

        from app.api.members import _trigger_youtube_crawler

        # Remove requests from cache and block re-import to force ImportError path
        real_requests = sys.modules.pop('requests', None)
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'requests':
                raise ImportError("requests not available")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = mock_import
        try:
            # Should return silently without raising
            _trigger_youtube_crawler('@test')
        finally:
            builtins.__import__ = real_import
            if real_requests is not None:
                sys.modules['requests'] = real_requests


class TestMakeChannelViewExceptionHandler:
    """Lines 548-550: exception handler in _make_channel_view."""

    @patch('app.api.members._handle_channel_local')
    def test_channel_exception_returns_500(self, mock_handler, client):
        """Exception in _handle_channel_local returns 500 JSON error."""
        mock_handler.side_effect = RuntimeError("unexpected crash")
        resp = client.get('/api/group-b/channel')
        assert resp.status_code == 500
        data = resp.get_json()
        assert 'error' in data
