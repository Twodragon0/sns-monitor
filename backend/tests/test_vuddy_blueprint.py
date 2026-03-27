"""Tests for vuddy.py Blueprint - internal helpers and routes."""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestProcessCountryStats:
    def test_normalizes_comment_count(self):
        from app.api.vuddy import _process_country_stats
        raw = {'KR': {'comment_count': 10, 'total_likes': 5}}
        result = _process_country_stats(raw)
        assert result['KR']['comments'] == 10
        assert result['KR']['likes'] == 5

    def test_falls_back_to_comments_key(self):
        from app.api.vuddy import _process_country_stats
        raw = {'US': {'comments': 20, 'likes': 3}}
        result = _process_country_stats(raw)
        assert result['US']['comments'] == 20
        assert result['US']['likes'] == 3

    def test_empty_dict(self):
        from app.api.vuddy import _process_country_stats
        assert _process_country_stats({}) == {}

    def test_multiple_countries(self):
        from app.api.vuddy import _process_country_stats
        raw = {
            'KR': {'comment_count': 5, 'total_likes': 2},
            'JP': {'comment_count': 3, 'total_likes': 1},
        }
        result = _process_country_stats(raw)
        assert 'KR' in result
        assert 'JP' in result


class TestGenerateSummaryAndKeywords:
    def test_empty_samples_returns_empty(self):
        from app.api.vuddy import _generate_summary_and_keywords
        summary, keywords = _generate_summary_and_keywords([], [])
        assert summary == ''
        assert keywords == []

    def test_generates_summary_with_sentiment(self):
        from app.api.vuddy import _generate_summary_and_keywords
        samples = [
            {'text': 'great video', 'sentiment': 'positive'},
            {'text': 'bad quality', 'sentiment': 'negative'},
            {'text': 'ok content', 'sentiment': 'neutral'},
        ]
        summary, keywords = _generate_summary_and_keywords(samples, [])
        assert '3' in summary
        assert '긍정' in summary or 'positive' in summary.lower() or '%' in summary

    def test_includes_video_count_when_links_present(self):
        from app.api.vuddy import _generate_summary_and_keywords
        samples = [{'text': 'nice', 'sentiment': 'positive'}]
        video_links = [{'url': 'https://yt.com/v1'}, {'url': 'https://yt.com/v2'}]
        summary, _ = _generate_summary_and_keywords(samples, video_links)
        assert '2' in summary

    def test_extracts_frequent_keywords(self):
        from app.api.vuddy import _generate_summary_and_keywords
        samples = [
            {'text': 'hello world', 'sentiment': 'neutral'},
            {'text': 'hello there', 'sentiment': 'neutral'},
        ]
        _, keywords = _generate_summary_and_keywords(samples, [])
        assert 'hello' in keywords


class TestGenerateGoogleSummary:
    def test_empty_returns_empty_string(self):
        from app.api.vuddy import _generate_google_summary
        assert _generate_google_summary([]) == ''
        assert _generate_google_summary(None) == ''

    def test_returns_count_in_summary(self):
        from app.api.vuddy import _generate_google_summary
        links = [{'snippet': 'test snippet'}]
        result = _generate_google_summary(links)
        assert '1' in result

    def test_includes_keywords_from_snippets(self):
        from app.api.vuddy import _generate_google_summary
        links = [
            {'snippet': 'python programming python'},
            {'snippet': 'python development'},
        ]
        result = _generate_google_summary(links)
        assert 'python' in result.lower() or 'Google' in result


class TestBuildAnalysisInfo:
    def test_no_analysis_no_samples_returns_defaults(self):
        from app.api.vuddy import _build_analysis_info
        result = _build_analysis_info(None, [], '', [], '')
        assert result['sentiment'] == 'neutral'
        assert result['overall_score'] == 50
        assert result['sentiment_distribution'] == {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}

    def test_with_comment_samples_uses_calculated_sentiment(self):
        from app.api.vuddy import _build_analysis_info
        samples = [
            {'sentiment': 'positive'},
            {'sentiment': 'positive'},
            {'sentiment': 'negative'},
        ]
        result = _build_analysis_info(None, samples, 'test summary', ['kw1'], '')
        assert result['sentiment'] == 'positive'
        assert result['summary'] == 'test summary'
        assert 'kw1' in result['keywords']

    def test_with_analysis_result_uses_it(self):
        from app.api.vuddy import _build_analysis_info
        analysis_result = {
            'sentiment_analysis': {
                'overall_sentiment': 'positive',
                'sentiment_distribution': {'positive': 0.8, 'negative': 0.1, 'neutral': 0.1},
            },
            'keyword_analysis': {
                'summary': 'LLM summary',
                'keywords': ['kw_llm'],
                'trends': ['trend1'],
            },
            'insights': {'overall_score': 85, 'key_insights': ['insight1']},
            'analyzed_at': '2024-01-01',
        }
        result = _build_analysis_info(analysis_result, [], '', [], '')
        assert result['sentiment'] == 'positive'
        assert result['summary'] == 'LLM summary'
        assert result['overall_score'] == 85
        assert 'kw_llm' in result['keywords']

    def test_google_summary_appended_to_summary(self):
        from app.api.vuddy import _build_analysis_info
        samples = [{'sentiment': 'neutral'}]
        result = _build_analysis_info(None, samples, 'base summary', [], 'google info')
        assert 'google info' in result['summary']

    def test_analysis_result_no_sentiment_dist_uses_samples(self):
        from app.api.vuddy import _build_analysis_info
        # sentiment_dist is empty → falls back to _calculate_sentiment_from_samples (line 149)
        analysis_result = {
            'sentiment_analysis': {
                'overall_sentiment': 'positive',
                'sentiment_distribution': {},
            },
            'keyword_analysis': {'summary': '', 'keywords': [], 'trends': []},
            'insights': {'overall_score': 60, 'key_insights': []},
        }
        samples = [{'sentiment': 'positive'}, {'sentiment': 'positive'}]
        result = _build_analysis_info(analysis_result, samples, '', [], '')
        assert result['sentiment'] == 'positive'

    def test_analysis_result_decimal_overall_score(self):
        from decimal import Decimal
        from app.api.vuddy import _build_analysis_info
        # overall_score is Decimal → triggers isinstance check (line 152-153)
        analysis_result = {
            'sentiment_analysis': {
                'overall_sentiment': 'neutral',
                'sentiment_distribution': {'positive': 0.5, 'negative': 0.2, 'neutral': 0.3},
            },
            'keyword_analysis': {'summary': '', 'keywords': [], 'trends': []},
            'insights': {'overall_score': Decimal('75'), 'key_insights': []},
        }
        result = _build_analysis_info(analysis_result, [], '', [], '')
        assert result['overall_score'] == 75

    def test_analysis_result_google_summary_appended(self):
        from app.api.vuddy import _build_analysis_info
        # google_summary_text triggers line 157-158 inside analysis_result branch
        analysis_result = {
            'sentiment_analysis': {
                'overall_sentiment': 'neutral',
                'sentiment_distribution': {'positive': 0.5, 'negative': 0.2, 'neutral': 0.3},
            },
            'keyword_analysis': {'summary': 'LLM summary', 'keywords': [], 'trends': []},
            'insights': {'overall_score': 50, 'key_insights': []},
        }
        result = _build_analysis_info(analysis_result, [], '', [], 'extra google info')
        assert 'extra google info' in result['summary']


class TestProcessCreatorsFromData:
    def test_empty_list(self):
        from app.api.vuddy import _process_creators_from_data
        assert _process_creators_from_data([]) == []

    def test_builds_creator_info(self):
        from app.api.vuddy import _process_creators_from_data
        creators_data = [{
            'name': 'TestCreator',
            'youtube_channel': '@test',
            'vuddy_channel': 'test_vuddy',
            'total_comments': 100,
            'total_likes': 500,
            'country_stats': {},
            'comment_samples': [],
            'video_links': [],
            'sentiment_distribution': {'positive': 0.6, 'negative': 0.1, 'neutral': 0.3},
            'overall_score': 60,
        }]
        result = _process_creators_from_data(creators_data)
        assert len(result) == 1
        creator = result[0]
        assert creator['name'] == 'TestCreator'
        assert creator['total_comments'] == 100
        assert creator['analysis']['overall_score'] == 60

    def test_filters_timestamp_comments(self):
        from app.api.vuddy import _process_creators_from_data
        # is_timestamp_comment requires 3+ timestamps in the text
        timestamp_text = '0:00 intro\n0:01:23 part1\n0:05:00 part2\n0:10:00 outro'
        creators_data = [{
            'name': 'Creator',
            'comment_samples': [
                {'text': timestamp_text},
                {'text': 'Normal comment here'},
            ],
        }]
        result = _process_creators_from_data(creators_data)
        texts = [c['text'] for c in result[0]['comment_samples']]
        assert 'Normal comment here' in texts
        assert timestamp_text not in texts

    def test_video_url_filled_from_video_id(self):
        from app.api.vuddy import _process_creators_from_data
        creators_data = [{
            'name': 'Creator',
            'comment_samples': [
                {'text': 'Nice', 'video_id': 'abc123', 'video_url': ''},
            ],
        }]
        result = _process_creators_from_data(creators_data)
        assert result[0]['comment_samples'][0]['video_url'] == 'https://www.youtube.com/watch?v=abc123'

    def test_country_stats_processed(self):
        from app.api.vuddy import _process_creators_from_data
        creators_data = [{
            'name': 'Creator',
            'country_stats': {'KR': {'comment_count': 10, 'total_likes': 3}},
        }]
        result = _process_creators_from_data(creators_data)
        assert result[0]['country_stats']['KR']['comments'] == 10

    def test_video_links_processed(self):
        from app.api.vuddy import _process_creators_from_data
        # Exercises line 258 - video_links loop
        creators_data = [{
            'name': 'Creator',
            'video_links': [
                {'title': 'Video 1', 'url': 'https://yt.com/v1', 'published_at': '2026-01-01'},
                {'title': 'Video 2', 'url': 'https://yt.com/v2'},
            ],
        }]
        result = _process_creators_from_data(creators_data)
        assert len(result[0]['video_links']) == 2
        assert result[0]['video_links'][0]['title'] == 'Video 1'


class TestHandleVuddyCreatorsLocal:
    @patch('os.path.exists', return_value=False)
    def test_missing_file_returns_empty(self, mock_exists):
        from app.api.vuddy import _handle_vuddy_creators_local
        result = _handle_vuddy_creators_local()
        assert result == []

    @patch('builtins.open')
    @patch('os.path.exists', return_value=True)
    def test_valid_creators_format(self, mock_exists, mock_open):
        from app.api.vuddy import _handle_vuddy_creators_local
        import io
        data = {
            'creators': [{
                'name': 'TestCreator',
                'comment_samples': [],
                'video_links': [],
            }]
        }
        mock_open.return_value.__enter__ = lambda s: io.StringIO(json.dumps(data))
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        result = _handle_vuddy_creators_local()
        assert len(result) == 1

    @patch('builtins.open')
    @patch('os.path.exists', return_value=True)
    def test_comprehensive_analysis_format_returns_empty(self, mock_exists, mock_open):
        from app.api.vuddy import _handle_vuddy_creators_local
        import io
        data = {'comprehensive_analysis': {}}
        mock_open.return_value.__enter__ = lambda s: io.StringIO(json.dumps(data))
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        result = _handle_vuddy_creators_local()
        assert result == []

    @patch('builtins.open', side_effect=ValueError('bad json'))
    @patch('os.path.exists', return_value=True)
    def test_json_error_returns_empty(self, mock_exists, mock_open):
        from app.api.vuddy import _handle_vuddy_creators_local
        result = _handle_vuddy_creators_local()
        assert result == []


class TestVuddyRoutes:
    def test_vuddy_creators_local_mode_ok(self, client):
        resp = client.get('/api/vuddy/creators')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'creators' in data

    @patch('app.api.vuddy.Config')
    def test_vuddy_creators_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/vuddy/creators')
        assert resp.status_code == 501
        assert 'error' in resp.get_json()

    @patch('app.api.vuddy._handle_vuddy_creators_local', return_value=[])
    def test_vuddy_creators_returns_empty_list(self, mock_handle, client):
        resp = client.get('/api/vuddy/creators')
        assert resp.status_code == 200
        assert resp.get_json()['creators'] == []

    @patch('app.api.vuddy._handle_vuddy_creators_local', side_effect=RuntimeError('crash'))
    def test_vuddy_creators_exception_returns_empty(self, mock_handle, client):
        resp = client.get('/api/vuddy/creators')
        assert resp.status_code == 200
        assert resp.get_json()['creators'] == []


class TestLoadLatestMetadataLocal:
    @patch('os.path.exists', return_value=False)
    def test_missing_dir_returns_none(self, mock_exists):
        from app.api.vuddy import _load_latest_metadata_local
        result = _load_latest_metadata_local('vuddy', 'creator1')
        assert result is None

    @patch('os.listdir', return_value=[])
    @patch('os.path.exists', return_value=True)
    def test_empty_dir_returns_none(self, mock_exists, mock_listdir):
        from app.api.vuddy import _load_latest_metadata_local
        result = _load_latest_metadata_local('vuddy')
        assert result is None

    def test_loads_metadata_from_real_file(self, tmp_path):
        from app.api.vuddy import _load_latest_metadata_local
        import json
        meta_dir = tmp_path / 'metadata' / 'vuddy'
        meta_dir.mkdir(parents=True)
        data = {'keyword': 'creator1', 'timestamp': '2026-03-27T00:00:00', 'score': 80}
        (meta_dir / 'item.json').write_text(json.dumps(data))
        with patch('app.api.vuddy.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            result = _load_latest_metadata_local('vuddy', 'creator1')
        assert result is not None
        assert result['score'] == 80

    def test_keyword_filter_no_match_returns_none(self, tmp_path):
        from app.api.vuddy import _load_latest_metadata_local
        import json
        meta_dir = tmp_path / 'metadata' / 'vuddy'
        meta_dir.mkdir(parents=True)
        data = {'keyword': 'other_creator', 'timestamp': '2026-03-27T00:00:00'}
        (meta_dir / 'item.json').write_text(json.dumps(data))
        with patch('app.api.vuddy.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            result = _load_latest_metadata_local('vuddy', 'creator1')
        assert result is None

    def test_invalid_json_file_skipped(self, tmp_path):
        from app.api.vuddy import _load_latest_metadata_local
        meta_dir = tmp_path / 'metadata' / 'vuddy'
        meta_dir.mkdir(parents=True)
        (meta_dir / 'bad.json').write_text('not valid json{{')
        with patch('app.api.vuddy.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            result = _load_latest_metadata_local('vuddy')
        assert result is None

    def test_non_json_files_skipped(self, tmp_path):
        from app.api.vuddy import _load_latest_metadata_local
        import json
        meta_dir = tmp_path / 'metadata' / 'vuddy'
        meta_dir.mkdir(parents=True)
        (meta_dir / 'readme.txt').write_text('ignore me')
        data = {'keyword': 'test', 'timestamp': '2026-03-27T00:00:00'}
        (meta_dir / 'data.json').write_text(json.dumps(data))
        with patch('app.api.vuddy.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            result = _load_latest_metadata_local('vuddy')
        assert result is not None

    def test_returns_most_recent_by_timestamp(self, tmp_path):
        from app.api.vuddy import _load_latest_metadata_local
        import json
        meta_dir = tmp_path / 'metadata' / 'vuddy'
        meta_dir.mkdir(parents=True)
        (meta_dir / 'old.json').write_text(json.dumps({'keyword': 'k', 'timestamp': '2026-01-01', 'val': 1}))
        (meta_dir / 'new.json').write_text(json.dumps({'keyword': 'k', 'timestamp': '2026-03-27', 'val': 2}))
        with patch('app.api.vuddy.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            result = _load_latest_metadata_local('vuddy', 'k')
        assert result['val'] == 2


class TestGetAnalysisResultLocal:
    def test_returns_metadata_when_found(self, tmp_path):
        import json
        from app.api.vuddy import _get_analysis_result_local
        meta_dir = tmp_path / 'metadata' / 'vuddy'
        meta_dir.mkdir(parents=True)
        data = {'keyword': 'creator1', 'timestamp': '2026-03-27T00:00:00', 'score': 90}
        (meta_dir / 'item.json').write_text(json.dumps(data))
        with patch('app.api.vuddy.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            result = _get_analysis_result_local('creator1')
        assert result['score'] == 90

    def test_returns_none_when_not_found(self, tmp_path):
        from app.api.vuddy import _get_analysis_result_local
        with patch('app.api.vuddy.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            result = _get_analysis_result_local('nonexistent')
        assert result is None

    def test_exception_returns_none(self):
        from app.api.vuddy import _get_analysis_result_local
        with patch('app.api.vuddy._load_latest_metadata_local', side_effect=RuntimeError('disk error')):
            result = _get_analysis_result_local('creator1')
        assert result is None
