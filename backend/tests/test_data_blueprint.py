"""Tests for data.py Blueprint - crawler results and twitter search routes."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


class TestSaveYoutubeResult:
    def test_missing_channel_returns_false(self):
        from app.api.data import _save_youtube_result
        ok, handle = _save_youtube_result({}, '2024-01-01')
        assert ok is False
        assert handle is None

    def test_invalid_channel_handle_rejected(self):
        from app.api.data import _save_youtube_result
        result = {'channel': '../../../etc/passwd'}
        ok, handle = _save_youtube_result(result, '2024-01-01')
        assert ok is False

    def test_valid_channel_saves_file(self):
        from app.api.data import _save_youtube_result
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('app.api.data.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                result = {'channel': '@testchannel', 'data': 'some content'}
                ok, handle = _save_youtube_result(result, '2024-01-01-00-00-00')
                assert ok is True
                assert handle == '@testchannel'
                saved_path = os.path.join(tmpdir, 'youtube', 'testchannel', '2024-01-01-00-00-00.json')
                assert os.path.exists(saved_path)

    def test_channel_strip_at_sign(self):
        from app.api.data import _save_youtube_result
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('app.api.data.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                result = {'channel': '@MyChannel'}
                ok, handle = _save_youtube_result(result, 'ts')
                assert ok is True
                # directory uses lowercase without @
                channel_dir = os.path.join(tmpdir, 'youtube', 'mychannel')
                assert os.path.exists(channel_dir)


class TestSaveDcinsideResult:
    def test_missing_gallery_id_returns_false(self):
        from app.api.data import _save_dcinside_result
        assert _save_dcinside_result({}, '2024-01-01') is False

    def test_invalid_gallery_id_rejected(self):
        from app.api.data import _save_dcinside_result
        result = {'gallery_id': '../../../evil'}
        assert _save_dcinside_result(result, '2024-01-01') is False

    def test_valid_gallery_id_saves_file(self):
        from app.api.data import _save_dcinside_result
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('app.api.data.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                result = {'gallery_id': 'test-gallery', 'posts': []}
                ok = _save_dcinside_result(result, '2024-01-01-00-00-00')
                assert ok is True
                saved_path = os.path.join(tmpdir, 'dcinside', 'test-gallery', '2024-01-01-00-00-00.json')
                assert os.path.exists(saved_path)


class TestLoadTweetsFromLocalFiles:
    def test_missing_twitter_dir_returns_empty(self):
        from app.api.data import _load_tweets_from_local_files
        with patch('app.api.data.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = '/nonexistent/dir'
            tweets, replies = _load_tweets_from_local_files('test')
            assert tweets == []
            assert replies == []

    def test_loads_tweets_from_matching_file(self):
        from app.api.data import _load_tweets_from_local_files
        with tempfile.TemporaryDirectory() as tmpdir:
            twitter_dir = os.path.join(tmpdir, 'twitter')
            os.makedirs(twitter_dir)
            data = {'tweets': [{'text': 'hello keyword world'}]}
            with open(os.path.join(twitter_dir, 'test.json'), 'w') as f:
                json.dump(data, f)
            with patch('app.api.data.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                tweets, replies = _load_tweets_from_local_files('keyword')
                assert len(tweets) == 1

    def test_skips_non_matching_files(self):
        from app.api.data import _load_tweets_from_local_files
        with tempfile.TemporaryDirectory() as tmpdir:
            twitter_dir = os.path.join(tmpdir, 'twitter')
            os.makedirs(twitter_dir)
            data = {'tweets': [{'text': 'unrelated content'}]}
            with open(os.path.join(twitter_dir, 'test.json'), 'w') as f:
                json.dump(data, f)
            with patch('app.api.data.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                tweets, replies = _load_tweets_from_local_files('keyword_not_present')
                assert tweets == []

    def test_loads_data_array_format(self):
        from app.api.data import _load_tweets_from_local_files
        with tempfile.TemporaryDirectory() as tmpdir:
            twitter_dir = os.path.join(tmpdir, 'twitter')
            os.makedirs(twitter_dir)
            data = {
                'data': [
                    {'tweet': {'text': 'keyword tweet'}, 'replies': [{'text': 'reply1'}]},
                ]
            }
            with open(os.path.join(twitter_dir, 'test.json'), 'w') as f:
                json.dump(data, f)
            with patch('app.api.data.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                tweets, replies = _load_tweets_from_local_files('keyword')
                assert len(tweets) == 1
                assert len(replies) == 1


class TestGetDataRoute:
    def test_get_data_returns_501(self, client):
        resp = client.get('/api/data/some/path.json')
        assert resp.status_code == 501
        assert 'error' in resp.get_json()

    def test_get_data_any_path_returns_501(self, client):
        resp = client.get('/api/data/nested/deep/path.json')
        assert resp.status_code == 501


class TestCrawlerResultsRoute:
    _TOKEN_HEADER = {'X-Crawler-Token': 'test-crawler-token'}

    def test_local_mode_empty_results_saved(self, client):
        resp = client.post('/api/crawler/results', json={'results': []}, headers=self._TOKEN_HEADER)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['saved_count'] == 0

    def test_local_mode_with_youtube_result(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('app.api.data.Config') as mock_cfg:
                mock_cfg.LOCAL_MODE = True
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                resp = client.post('/api/crawler/results', json={
                    'results': [{'channel': '@testch', 'videos': []}]
                }, headers=self._TOKEN_HEADER)
                assert resp.status_code == 200
                data = resp.get_json()
                assert data['saved_count'] == 1

    @patch('app.api.data.Config')
    def test_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.post('/api/crawler/results', json={'results': []}, headers=self._TOKEN_HEADER)
        assert resp.status_code == 501

    def test_no_json_body_returns_200_with_zero(self, client):
        resp = client.post('/api/crawler/results', data='not json', content_type='text/plain', headers=self._TOKEN_HEADER)
        assert resp.status_code == 200
        assert resp.get_json()['saved_count'] == 0

    def test_response_includes_youtube_channels(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('app.api.data.Config') as mock_cfg:
                mock_cfg.LOCAL_MODE = True
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                resp = client.post('/api/crawler/results', json={
                    'results': [{'channel': '@chan1'}, {'channel': '@chan2'}]
                }, headers=self._TOKEN_HEADER)
                data = resp.get_json()
                assert 'youtube_channels' in data
                assert len(data['youtube_channels']) == 2

    def test_missing_token_returns_401(self, client):
        resp = client.post('/api/crawler/results', json={'results': []})
        assert resp.status_code == 401

    def test_unconfigured_token_returns_503(self, client):
        with patch.dict(os.environ, {'CRAWLER_INTERNAL_TOKEN': ''}):
            resp = client.post('/api/crawler/results', json={'results': []})
            assert resp.status_code == 503


class TestTwitterSearchRoute:
    @patch('app.api.data.Config')
    def test_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.post('/api/twitter/search', json={'action': 'search'})
        assert resp.status_code == 501

    def test_invalid_action_returns_400(self, client):
        resp = client.post('/api/twitter/search', json={'action': 'invalid_action'})
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_search_without_keyword_returns_400(self, client):
        resp = client.post('/api/twitter/search', json={'action': 'search', 'keyword': ''})
        assert resp.status_code == 400

    @patch('app.api.data._fetch_tweets_from_crawler', return_value=([], []))
    @patch('app.api.data._load_tweets_from_local_files', return_value=([], []))
    def test_search_with_keyword_returns_200(self, mock_local, mock_crawler, client):
        resp = client.post('/api/twitter/search', json={'action': 'search', 'keyword': 'test'})
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'tweets' in data
        assert data['keyword'] == 'test'

    @patch('app.api.data._fetch_tweets_from_crawler', return_value=([{'text': 'tweet1'}], []))
    @patch('app.api.data._load_tweets_from_local_files', return_value=([], []))
    def test_search_returns_tweet_count(self, mock_local, mock_crawler, client):
        resp = client.post('/api/twitter/search', json={'action': 'search', 'keyword': 'test'})
        data = json.loads(resp.data)
        assert data['total_tweets'] == 1

    @patch('app.api.data._fetch_tweets_from_crawler', return_value=([], []))
    @patch('app.api.data._load_tweets_from_local_files', return_value=([], []))
    def test_bulk_search_returns_results_dict(self, mock_local, mock_crawler, client):
        resp = client.post('/api/twitter/search', json={
            'action': 'bulk_search',
            'keywords': ['kw1', 'kw2'],
        })
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'results' in data
        assert 'kw1' in data['results']
        assert 'kw2' in data['results']

    @patch('app.api.data._fetch_tweets_from_crawler', return_value=([], []))
    @patch('app.api.data._load_tweets_from_local_files', return_value=([], []))
    def test_bulk_search_empty_keywords(self, mock_local, mock_crawler, client):
        resp = client.post('/api/twitter/search', json={
            'action': 'bulk_search',
            'keywords': [],
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data


class TestFetchTweetsFromCrawler:
    @patch('requests.post')
    def test_successful_response(self, mock_post):
        from app.api.data import _fetch_tweets_from_crawler
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': [{'tweets': [{'text': 'hi'}], 'replies': []}]
        }
        mock_post.return_value = mock_response
        tweets, replies = _fetch_tweets_from_crawler('http://crawler:5000', 'keyword')
        assert len(tweets) == 1

    @patch('requests.post', side_effect=Exception('connection refused'))
    def test_exception_returns_empty(self, mock_post):
        from app.api.data import _fetch_tweets_from_crawler
        tweets, replies = _fetch_tweets_from_crawler('http://crawler:5000', 'keyword')
        assert tweets == []
        assert replies == []

    @patch('requests.post')
    def test_non_200_response_returns_empty(self, mock_post):
        from app.api.data import _fetch_tweets_from_crawler
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        tweets, replies = _fetch_tweets_from_crawler('http://crawler:5000', 'keyword')
        assert tweets == []
        assert replies == []

    @patch('requests.post')
    def test_empty_results_array_returns_empty(self, mock_post):
        from app.api.data import _fetch_tweets_from_crawler
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'results': []}
        mock_post.return_value = mock_response
        tweets, replies = _fetch_tweets_from_crawler('http://crawler:5000', 'keyword')
        assert tweets == []
        assert replies == []


class TestLoadTweetsFileException:
    def test_bad_json_file_skipped(self, tmp_path):
        from app.api.data import _load_tweets_from_local_files
        twitter_dir = tmp_path / 'twitter'
        twitter_dir.mkdir()
        (twitter_dir / 'bad.json').write_text('not valid json{{{')
        with patch('app.api.data.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            tweets, replies = _load_tweets_from_local_files('keyword')
        assert tweets == []
        assert replies == []


class TestSaveDcinsideResultException:
    def test_write_error_raises(self, tmp_path):
        from app.api.data import _save_dcinside_result
        with patch('app.api.data.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            with patch('builtins.open', side_effect=OSError('disk full')):
                with pytest.raises(OSError):
                    _save_dcinside_result({'gallery_id': 'test-gallery'}, '2026-03-27')


class TestCrawlerResultsException:
    _TOKEN_HEADER = {'X-Crawler-Token': 'test-crawler-token'}

    def test_unexpected_exception_returns_500(self, client):
        with patch('app.api.data._save_youtube_result', side_effect=RuntimeError('boom')):
            resp = client.post('/api/crawler/results', json={
                'results': [{'channel': '@chan'}]
            }, headers=self._TOKEN_HEADER)
            assert resp.status_code == 500
            assert 'error' in resp.get_json()


class TestTwitterSearchExceptions:
    @patch('app.api.data._fetch_tweets_from_crawler', side_effect=RuntimeError('network down'))
    @patch('app.api.data._load_tweets_from_local_files', return_value=([], []))
    def test_bulk_search_per_keyword_error_graceful(self, mock_local, mock_crawler, client):
        resp = client.post('/api/twitter/search', json={
            'action': 'bulk_search',
            'keywords': ['kw1'],
        })
        assert resp.status_code == 200
        import json as _json
        data = _json.loads(resp.data)
        assert 'kw1' in data['results']
        assert 'error' in data['results']['kw1']

    @patch('app.api.data._load_tweets_from_local_files', side_effect=RuntimeError('crash'))
    @patch('app.api.data._fetch_tweets_from_crawler', return_value=([], []))
    def test_search_outer_exception_returns_500(self, mock_crawler, mock_local, client):
        # _load_tweets_from_local_files raising triggers the outer except block
        resp = client.post('/api/twitter/search', json={
            'action': 'search',
            'keyword': 'test',
        })
        assert resp.status_code == 500
        assert 'error' in resp.get_json()
