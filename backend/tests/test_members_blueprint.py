"""Tests for members.py Blueprint internal helpers and routes."""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


class TestInternalHelpers:
    """Test internal helper functions in members.py."""

    def test_is_comment_within_cutoff_true(self):
        from app.api.members import _is_comment_within_cutoff
        future = (datetime.now() + timedelta(days=1)).isoformat()
        assert _is_comment_within_cutoff(future, datetime.now()) is True

    def test_is_comment_within_cutoff_false(self):
        from app.api.members import _is_comment_within_cutoff
        old = (datetime.now() - timedelta(days=30)).isoformat()
        assert _is_comment_within_cutoff(old, datetime.now()) is False

    def test_is_comment_within_cutoff_empty_string_returns_true(self):
        from app.api.members import _is_comment_within_cutoff
        assert _is_comment_within_cutoff('', datetime.now()) is True

    def test_is_comment_within_cutoff_invalid_format_returns_true(self):
        from app.api.members import _is_comment_within_cutoff
        assert _is_comment_within_cutoff('not-a-date', datetime.now()) is True

    def test_is_comment_within_cutoff_z_suffix(self):
        from app.api.members import _is_comment_within_cutoff
        recent = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        assert _is_comment_within_cutoff(recent, datetime.now() - timedelta(days=2)) is True

    def test_build_comment_sample_bc_fills_video_url(self):
        from app.api.members import _build_comment_sample_bc
        comment = {
            'text': 'hello',
            'author': 'user1',
            'like_count': 5,
            'video_title': 'Test Video',
            'video_id': 'abc123',
            'sentiment': 'positive',
            'published_at': '2024-01-01',
        }
        result = _build_comment_sample_bc(comment)
        assert result['video_url'] == 'https://www.youtube.com/watch?v=abc123'
        assert result['text'] == 'hello'
        assert result['sentiment'] == 'positive'

    def test_build_comment_sample_bc_preserves_existing_url(self):
        from app.api.members import _build_comment_sample_bc
        comment = {
            'video_id': 'abc123',
            'video_url': 'https://custom.url/video',
        }
        result = _build_comment_sample_bc(comment)
        assert result['video_url'] == 'https://custom.url/video'

    def test_normalize_video_id_url_adds_url(self):
        from app.api.members import _normalize_video_id_url
        vid_id, vid_url = _normalize_video_id_url('abc123', '')
        assert vid_url == 'https://www.youtube.com/watch?v=abc123'

    def test_normalize_video_id_url_keeps_existing(self):
        from app.api.members import _normalize_video_id_url
        vid_id, vid_url = _normalize_video_id_url('abc123', 'https://existing.url')
        assert vid_url == 'https://existing.url'

    def test_calculate_sentiment_dist_normalizes(self):
        from app.api.members import _calculate_sentiment_dist
        result = _calculate_sentiment_dist({'positive': 3, 'negative': 1, 'neutral': 0})
        assert result['positive'] == 0.75
        assert result['negative'] == 0.25

    def test_calculate_sentiment_dist_zero_total(self):
        from app.api.members import _calculate_sentiment_dist
        result = _calculate_sentiment_dist({})
        assert result == {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}

    def test_overall_sentiment_returns_max(self):
        from app.api.members import _overall_sentiment
        result = _overall_sentiment({'positive': 0.1, 'negative': 0.8, 'neutral': 0.1})
        assert result == 'negative'

    def test_overall_sentiment_empty_returns_neutral(self):
        from app.api.members import _overall_sentiment
        assert _overall_sentiment({}) == 'neutral'
        assert _overall_sentiment(None) == 'neutral'

    def test_extract_channel_title_from_channel_title(self):
        from app.api.members import _extract_channel_title
        creator = {'channel_title': 'My Channel'}
        assert _extract_channel_title(creator) == 'My Channel'

    def test_extract_channel_title_from_name(self):
        from app.api.members import _extract_channel_title
        creator = {'name': 'Creator Name (alias)'}
        assert _extract_channel_title(creator) == 'Creator Name'

    def test_extract_channel_title_plain_name(self):
        from app.api.members import _extract_channel_title
        creator = {'name': 'Simple Name'}
        assert _extract_channel_title(creator) == 'Simple Name'

    def test_process_country_stats_local_passthrough(self):
        from app.api.members import _process_country_stats_local
        raw = {'KR': 10, 'US': 5}
        result = _process_country_stats_local(raw)
        assert result == {'KR': 10, 'US': 5}

    def test_process_country_stats_local_empty(self):
        from app.api.members import _process_country_stats_local
        assert _process_country_stats_local(None) == {}
        assert _process_country_stats_local({}) == {}


class TestBuildCreatorsGroupA:
    """Test _build_creators_group_a."""

    def test_empty_creators(self):
        from app.api.members import _build_creators_group_a
        data = {'creators': []}
        result = _build_creators_group_a(data, '2024-01-01')
        assert result == []

    def test_builds_creator_info(self):
        from app.api.members import _build_creators_group_a
        data = {
            'creators': [{
                'name': 'TestCreator',
                'channel_handle': '@test',
                'channel_title': 'Test Title',
                'total_comments': 100,
                'subscriber_count': 5000,
                'comment_samples': [],
            }]
        }
        result = _build_creators_group_a(data, '2024-01-01')
        assert len(result) == 1
        creator = result[0]
        assert creator['name'] == 'TestCreator'
        assert creator['total_comments'] == 100
        assert creator['statistics']['subscriberCount'] == 5000
        assert creator['last_crawled'] == '2024-01-01'

    def test_comment_samples_video_url_filled(self):
        from app.api.members import _build_creators_group_a
        data = {
            'creators': [{
                'name': 'Creator',
                'comment_samples': [{
                    'text': 'Nice video',
                    'video_id': 'vid001',
                    'video_url': '',
                    'sentiment': 'positive',
                }],
            }]
        }
        result = _build_creators_group_a(data, '')
        assert result[0]['comment_samples'][0]['video_url'] == 'https://www.youtube.com/watch?v=vid001'


class TestBuildCreatorsBc:
    """Test _build_creators_bc."""

    def test_empty_creators(self):
        from app.api.members import _build_creators_bc
        result = _build_creators_bc({'creators': []}, '')
        assert result == []

    def test_builds_creator_info(self):
        from app.api.members import _build_creators_bc
        data = {
            'creators': [{
                'name': 'BCCreator',
                'youtube_channel': '@bc',
                'total_comments': 50,
                'total_likes': 200,
                'sentiment_distribution': {'positive': 3, 'negative': 1, 'neutral': 1},
                'overall_score': 60,
                'comment_samples': [],
                'video_links': [],
            }]
        }
        result = _build_creators_bc(data, '2024-06-01')
        assert len(result) == 1
        creator = result[0]
        assert creator['name'] == 'BCCreator'
        assert creator['last_crawled'] == '2024-06-01'
        assert creator['analysis']['overall_score'] == 60

    def test_filters_timestamp_comments(self):
        from app.api.members import _build_creators_bc
        future = (datetime.now() + timedelta(days=1)).isoformat()
        # is_timestamp_comment filters when 3+ timestamps exist in the text
        timestamp_text = '0:00 intro\n0:01:23 part1\n0:05:00 part2\n0:10:00 outro'
        data = {
            'creators': [{
                'name': 'Creator',
                'comment_samples': [
                    {'text': timestamp_text, 'published_at': future},
                    {'text': 'Normal comment', 'published_at': future},
                ],
            }]
        }
        result = _build_creators_bc(data, '')
        texts = [c['text'] for c in result[0]['comment_samples']]
        assert 'Normal comment' in texts
        assert timestamp_text not in texts


class TestHandleMembersLocal:
    """Test _handle_members_local with mocked file I/O."""

    @patch('app.api.members._load_members_json')
    def test_no_data_returns_empty_creators(self, mock_load):
        from app.api.members import _handle_members_local
        mock_load.return_value = (None, '')
        result = _handle_members_local('group-a')
        body = json.loads(result['body'])
        assert body['creators'] == []
        assert result['statusCode'] == 200

    @patch('app.api.members._load_members_json')
    def test_group_a_uses_a_style(self, mock_load):
        from app.api.members import _handle_members_local
        mock_load.return_value = ({
            'creators': [{'name': 'A', 'channel_handle': '@a'}],
            'updated_at': '2024-01-01',
        }, '2024-01-01')
        result = _handle_members_local('group-a')
        body = json.loads(result['body'])
        assert len(body['creators']) == 1

    @patch('app.api.members._load_members_json')
    def test_group_b_uses_bc_style(self, mock_load):
        from app.api.members import _handle_members_local
        mock_load.return_value = ({
            'creators': [{'name': 'B', 'youtube_channel': '@b', 'comment_samples': [], 'video_links': []}],
            'timestamp': '2024-02-01',
        }, '2024-02-01')
        result = _handle_members_local('group-b')
        body = json.loads(result['body'])
        assert len(body['creators']) == 1


class TestMembersRoutes:
    """Test Blueprint HTTP routes."""

    def test_group_a_members_local_mode_ok(self, client):
        resp = client.get('/api/group-a/members')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'creators' in data

    def test_group_b_members_local_mode_ok(self, client):
        resp = client.get('/api/group-b/members')
        assert resp.status_code == 200

    def test_group_c_members_local_mode_ok(self, client):
        resp = client.get('/api/group-c/members')
        assert resp.status_code == 200

    @patch('app.api.members.Config')
    def test_members_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/group-a/members')
        assert resp.status_code == 501

    def test_group_a_channel_local_mode_ok(self, client):
        resp = client.get('/api/group-a/channel')
        assert resp.status_code == 200

    def test_group_b_channel_local_mode_ok(self, client):
        resp = client.get('/api/group-b/channel')
        assert resp.status_code == 200

    def test_group_c_channel_local_mode_ok(self, client):
        resp = client.get('/api/group-c/channel')
        assert resp.status_code == 200

    @patch('app.api.members.Config')
    def test_channel_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/group-a/channel')
        assert resp.status_code == 501

    @patch('app.api.members._load_members_json')
    def test_members_internal_exception_returns_500(self, mock_load, client):
        mock_load.side_effect = RuntimeError('DB crash')
        resp = client.get('/api/group-a/members')
        assert resp.status_code == 500

    def test_channel_with_handle_query_param(self, client):
        resp = client.get('/api/group-a/channel?channel_handle=@testchannel')
        assert resp.status_code == 200

    def test_channel_handle_without_at_sign(self, client):
        resp = client.get('/api/group-b/channel?channel=testchannel')
        assert resp.status_code == 200


class TestLoadMembersJson:
    """Test _load_members_json file loading."""

    @patch('os.path.exists', return_value=False)
    def test_missing_file_returns_none(self, mock_exists):
        from app.api.members import _load_members_json
        data, last_crawled = _load_members_json('group-a')
        assert data is None
        assert last_crawled == ''

    @patch('builtins.open')
    @patch('os.path.exists', return_value=True)
    def test_json_parse_error_returns_none(self, mock_exists, mock_open):
        from app.api.members import _load_members_json
        mock_open.side_effect = ValueError('bad json')
        data, last_crawled = _load_members_json('group-b')
        assert data is None

    @patch('builtins.open')
    @patch('os.path.exists', return_value=True)
    def test_valid_json_returns_data(self, mock_exists, mock_open):
        from app.api.members import _load_members_json
        import io
        fake_data = {'creators': [], 'timestamp': '2024-01-01'}
        mock_open.return_value.__enter__ = lambda s: io.StringIO(json.dumps(fake_data))
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        data, last_crawled = _load_members_json('group-b')
        assert data is not None


class TestFindChannelFilesLocal:
    """Test _find_channel_files_local."""

    @patch('os.path.exists', return_value=False)
    def test_missing_dir_returns_empty(self, mock_exists):
        from app.api.members import _find_channel_files_local
        result = _find_channel_files_local('/nonexistent', '@test')
        assert result == []


class TestProcessChannelVideos:
    """Test _process_channel_videos."""

    def test_empty_list(self):
        from app.api.members import _process_channel_videos
        videos, total, vtuber, likes = _process_channel_videos([])
        assert videos == []
        assert total == 0

    def test_none_list(self):
        from app.api.members import _process_channel_videos
        videos, total, vtuber, likes = _process_channel_videos(None)
        assert videos == []

    def test_processes_video_entry(self):
        from app.api.members import _process_channel_videos
        entries = [{
            'video': {'video_id': 'v1', 'title': 'Test', 'view_count': 100},
            'comments': [{'text': 'hi'}, {'text': 'there'}],
            'vtuber_stats': {'total_vtuber_comments': 5, 'vtuber_total_likes': 10},
        }]
        videos, total, vtuber_c, vtuber_l = _process_channel_videos(entries)
        assert len(videos) == 1
        assert videos[0]['video_id'] == 'v1'
        assert total == 2
        assert vtuber_c == 5
        assert vtuber_l == 10

    def test_skips_non_dict_entries(self):
        from app.api.members import _process_channel_videos
        videos, total, _, _ = _process_channel_videos(['not a dict', None])
        assert videos == []
        assert total == 0
