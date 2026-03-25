"""Additional tests for /api/analysis/* to boost coverage from 25% to 50%+.

Covers: MiroFish proxy routes, transform success, compare, trend,
ai-summary, ai-chat, ai-url-analyze, ai-url-chat, local-summary success,
daily report, projects, _read_source_items, _transform helpers.
"""

import json
import pytest
import requests as req_lib
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# MiroFish proxy routes (graph/build, graph/task, graph/data, report/*)
# ---------------------------------------------------------------------------

class TestGraphBuild:
    @patch('app.api.analysis.requests.post')
    def test_success(self, mock_post, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'task_id': 'abc123'}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        resp = client.post('/api/analysis/graph/build', json={'project': 'test'})
        assert resp.status_code == 200
        assert resp.get_json()['task_id'] == 'abc123'

    @patch('app.api.analysis.requests.post')
    def test_connection_error(self, mock_post, client):
        mock_post.side_effect = req_lib.ConnectionError("refused")
        resp = client.post('/api/analysis/graph/build', json={})
        assert resp.status_code == 503


class TestGraphTask:
    @patch('app.api.analysis.requests.get')
    def test_success(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'status': 'completed'}
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        resp = client.get('/api/analysis/graph/task/task123')
        assert resp.status_code == 200

    def test_invalid_task_id(self, client):
        resp = client.get('/api/analysis/graph/task/bad%20id!')
        assert resp.status_code == 400

    @patch('app.api.analysis.requests.get')
    def test_connection_error(self, mock_get, client):
        mock_get.side_effect = req_lib.ConnectionError()
        resp = client.get('/api/analysis/graph/task/task123')
        assert resp.status_code == 503


class TestGraphData:
    @patch('app.api.analysis.requests.get')
    def test_success(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'nodes': [], 'edges': []}
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        resp = client.get('/api/analysis/graph/data/graph123')
        assert resp.status_code == 200

    def test_invalid_graph_id(self, client):
        resp = client.get('/api/analysis/graph/data/bad%20id!')
        assert resp.status_code == 400


class TestReportGenerate:
    @patch('app.api.analysis.requests.post')
    def test_success(self, mock_post, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'report_id': 'rpt1'}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        resp = client.post('/api/analysis/report/generate', json={'graph_id': 'g1'})
        assert resp.status_code == 200

    @patch('app.api.analysis.requests.post')
    def test_connection_error(self, mock_post, client):
        mock_post.side_effect = req_lib.ConnectionError()
        resp = client.post('/api/analysis/report/generate', json={})
        assert resp.status_code == 503


class TestReportGet:
    @patch('app.api.analysis.requests.get')
    def test_success(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'content': 'report text'}
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        resp = client.get('/api/analysis/report/rpt123')
        assert resp.status_code == 200

    def test_invalid_report_id(self, client):
        resp = client.get('/api/analysis/report/bad%20id!')
        assert resp.status_code == 400

    @patch('app.api.analysis.requests.get')
    def test_connection_error(self, mock_get, client):
        mock_get.side_effect = req_lib.ConnectionError()
        resp = client.get('/api/analysis/report/rpt123')
        assert resp.status_code == 503


class TestReportChat:
    @patch('app.api.analysis.requests.post')
    def test_success(self, mock_post, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'reply': 'hello'}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        resp = client.post('/api/analysis/report/chat', json={'message': 'hi'})
        assert resp.status_code == 200

    @patch('app.api.analysis.requests.post')
    def test_connection_error(self, mock_post, client):
        mock_post.side_effect = req_lib.ConnectionError()
        resp = client.post('/api/analysis/report/chat', json={})
        assert resp.status_code == 503


class TestProjects:
    @patch('app.api.analysis.requests.get')
    def test_success(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'projects': []}
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        resp = client.get('/api/analysis/projects')
        assert resp.status_code == 200

    @patch('app.api.analysis.requests.get')
    def test_connection_error(self, mock_get, client):
        mock_get.side_effect = req_lib.ConnectionError()
        resp = client.get('/api/analysis/projects')
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Transform endpoint (success path with mocked file data)
# ---------------------------------------------------------------------------

class TestTransformSuccess:
    @patch('app.api.analysis.requests.post')
    @patch('app.api.analysis._transform_youtube_to_document')
    def test_transform_youtube_success(self, mock_transform, mock_post, client):
        mock_transform.return_value = '# YouTube Analysis\nsome content'
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'task_id': 't1'}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        resp = client.post('/api/analysis/transform', json={
            'sources': [{'type': 'youtube', 'id': 'test-channel'}],
            'project_name': 'Test Project',
        })
        assert resp.status_code == 200

    @patch('app.api.analysis._transform_youtube_to_document')
    def test_transform_no_data(self, mock_transform, client):
        mock_transform.return_value = None
        resp = client.post('/api/analysis/transform', json={
            'sources': [{'type': 'youtube', 'id': 'empty-channel'}],
        })
        assert resp.status_code == 404

    def test_transform_invalid_source_id(self, client):
        resp = client.post('/api/analysis/transform', json={
            'sources': [{'type': 'youtube', 'id': '../../etc'}],
        })
        assert resp.status_code == 400

    def test_transform_unknown_type_skipped(self, client):
        resp = client.post('/api/analysis/transform', json={
            'sources': [{'type': 'unknown_platform', 'id': 'test'}],
        })
        assert resp.status_code == 404

    @patch('app.api.analysis._transform_youtube_to_document')
    @patch('app.api.analysis.requests.post')
    def test_transform_connection_error(self, mock_post, mock_transform, client):
        mock_transform.return_value = '# doc'
        mock_post.side_effect = req_lib.ConnectionError()
        resp = client.post('/api/analysis/transform', json={
            'sources': [{'type': 'youtube', 'id': 'test'}],
        })
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Local Summary (success path)
# ---------------------------------------------------------------------------

class TestLocalSummarySuccess:
    @patch('app.api.analysis._read_source_items')
    def test_success(self, mock_read, client):
        mock_read.return_value = (
            [{'text': 'great video!'}, {'text': 'nice content'}],
            {'channel_name': 'TestChannel'},
        )
        resp = client.post('/api/analysis/local-summary', json={
            'sources': [{'type': 'youtube', 'id': 'test-channel'}],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['mode'] == 'local'
        assert len(data['sources']) == 1
        assert data['total_items'] == 2

    @patch('app.api.analysis._read_source_items')
    def test_multiple_sources(self, mock_read, client):
        mock_read.side_effect = [
            ([{'text': 'yt comment'}], {'channel_name': 'YT'}),
            ([{'text': 'dc post'}], {'gallery_name': 'DC'}),
        ]
        resp = client.post('/api/analysis/local-summary', json={
            'sources': [
                {'type': 'youtube', 'id': 'yt1'},
                {'type': 'dcinside', 'id': 'dc1'},
            ],
        })
        assert resp.status_code == 200
        assert resp.get_json()['total_items'] == 2


# ---------------------------------------------------------------------------
# Sentiment Trend
# ---------------------------------------------------------------------------

class TestSentimentTrend:
    def test_valid_source_no_dir(self, client):
        resp = client.get('/api/analysis/trend?type=dcinside&id=nonexistent')
        assert resp.status_code in (200, 404)
        data = resp.get_json()
        if resp.status_code == 200:
            assert data['source_id'] == 'nonexistent'
            assert data['trend'] == [] or 'error' in data

    def test_non_dcinside_type(self, client):
        resp = client.get('/api/analysis/trend?type=youtube&id=test')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['trend'] == []


# ---------------------------------------------------------------------------
# Compare galleries
# ---------------------------------------------------------------------------

class TestGalleryCompare:
    def test_no_dcinside_dir(self, client):
        resp = client.get('/api/analysis/compare')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'galleries' in data


# ---------------------------------------------------------------------------
# AI Summary
# ---------------------------------------------------------------------------

class TestAiSummaryRoutes:
    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_youtube_to_document')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_ai_summary_success(self, mock_analyze, mock_transform, mock_provider, client):
        mock_transform.return_value = '# doc content'
        mock_analyze.return_value = {'success': True, 'analysis': 'looks good', 'provider': 'openai'}
        resp = client.post('/api/analysis/ai-summary', json={
            'sources': [{'type': 'youtube', 'id': 'test'}],
            'question': 'What is the sentiment?',
        })
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_youtube_to_document')
    def test_ai_summary_no_data(self, mock_transform, mock_provider, client):
        mock_transform.return_value = None
        resp = client.post('/api/analysis/ai-summary', json={
            'sources': [{'type': 'youtube', 'id': 'empty'}],
        })
        assert resp.status_code == 404

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_youtube_to_document')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_ai_summary_llm_error(self, mock_analyze, mock_transform, mock_provider, client):
        mock_transform.return_value = '# doc'
        mock_analyze.return_value = {'error': 'API error'}
        resp = client.post('/api/analysis/ai-summary', json={
            'sources': [{'type': 'youtube', 'id': 'test'}],
        })
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# AI Chat
# ---------------------------------------------------------------------------

class TestAiChat:
    @patch('app.services.llm_analyzer.get_available_provider', return_value=None)
    def test_no_provider(self, mock_provider, client):
        resp = client.post('/api/analysis/ai-chat', json={
            'sources': [{'type': 'youtube', 'id': 'test'}],
            'message': 'hi',
        })
        assert resp.status_code == 503

    def test_missing_message(self, client):
        resp = client.post('/api/analysis/ai-chat', json={
            'sources': [{'type': 'youtube', 'id': 'test'}],
        })
        # Either 400 (no message) or 503 (no provider, checked first)
        assert resp.status_code in (400, 503)

    @patch('app.services.llm_analyzer.get_available_provider', return_value='anthropic')
    def test_missing_sources(self, mock_provider, client):
        resp = client.post('/api/analysis/ai-chat', json={
            'message': 'hi',
        })
        assert resp.status_code == 400

    @patch('app.services.llm_analyzer.get_available_provider', return_value='anthropic')
    @patch('app.api.analysis._transform_youtube_to_document')
    @patch('app.services.llm_analyzer.chat_with_llm')
    def test_success(self, mock_chat, mock_transform, mock_provider, client):
        mock_transform.return_value = '# doc'
        mock_chat.return_value = {'success': True, 'reply': 'analysis result'}
        resp = client.post('/api/analysis/ai-chat', json={
            'sources': [{'type': 'youtube', 'id': 'test'}],
            'message': 'What is the trend?',
            'chat_history': [],
        })
        assert resp.status_code == 200

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_youtube_to_document')
    def test_no_data(self, mock_transform, mock_provider, client):
        mock_transform.return_value = None
        resp = client.post('/api/analysis/ai-chat', json={
            'sources': [{'type': 'youtube', 'id': 'empty'}],
            'message': 'hi',
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AI URL Analyze
# ---------------------------------------------------------------------------

class TestAiUrlAnalyze:
    @patch('app.services.llm_analyzer.get_available_provider', return_value=None)
    def test_no_provider(self, mock_provider, client):
        resp = client.post('/api/analysis/ai-url-analyze', json={
            'result': {'platform': 'youtube', 'title': 'test'},
        })
        assert resp.status_code == 503

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    def test_missing_result(self, mock_provider, client):
        resp = client.post('/api/analysis/ai-url-analyze', json={})
        assert resp.status_code == 400

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_success(self, mock_analyze, mock_provider, client):
        mock_analyze.return_value = {'success': True, 'analysis': 'positive'}
        resp = client.post('/api/analysis/ai-url-analyze', json={
            'result': {
                'platform': 'youtube',
                'title': 'Test Video',
                'description': 'A test',
                'content': 'Some content here',
                'view_count': 1000,
                'like_count': 50,
                'comments': [
                    {'text': 'great!', 'author': 'user1'},
                    {'text': 'nice', 'author': 'user2'},
                ],
                'analysis': {
                    'overall': 'positive',
                    'sentiment': {'positive': 5, 'neutral': 2, 'negative': 1},
                },
            },
            'question': 'deep analysis please',
        })
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


# ---------------------------------------------------------------------------
# AI URL Chat
# ---------------------------------------------------------------------------

class TestAiUrlChat:
    @patch('app.services.llm_analyzer.get_available_provider', return_value=None)
    def test_no_provider(self, mock_provider, client):
        resp = client.post('/api/analysis/ai-url-chat', json={
            'result': {'platform': 'youtube'},
            'message': 'hi',
        })
        assert resp.status_code == 503

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    def test_missing_message(self, mock_provider, client):
        resp = client.post('/api/analysis/ai-url-chat', json={
            'result': {'platform': 'youtube'},
        })
        assert resp.status_code == 400

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    def test_missing_result(self, mock_provider, client):
        resp = client.post('/api/analysis/ai-url-chat', json={
            'message': 'hi',
        })
        assert resp.status_code == 400

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.chat_with_llm')
    def test_success(self, mock_chat, mock_provider, client):
        mock_chat.return_value = {'success': True, 'reply': 'analysis'}
        resp = client.post('/api/analysis/ai-url-chat', json={
            'result': {
                'platform': 'youtube',
                'title': 'Test',
                'description': 'desc',
                'comments': [{'text': 'cool', 'author': 'u1'}],
            },
            'message': 'What do you think?',
            'chat_history': [],
        })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Daily report generation
# ---------------------------------------------------------------------------

class TestDailyReport:
    @patch('app.api.analysis._get_local_data_dir')
    def test_no_data_dir(self, mock_dir, client, tmp_path):
        # Create the dcinside dir but leave it empty
        dc_dir = tmp_path / 'dcinside'
        dc_dir.mkdir(parents=True)
        mock_dir.return_value = tmp_path
        resp = client.post('/api/analysis/report/generate-daily')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'date' in data or 'galleries' in data or 'error' in data


# ---------------------------------------------------------------------------
# _transform helpers
# ---------------------------------------------------------------------------

class TestTransformHelpers:
    @patch('app.api.analysis._get_local_data_dir')
    def test_youtube_transform_no_files(self, mock_dir, tmp_path):
        yt_dir = tmp_path / 'youtube' / 'channels'
        yt_dir.mkdir(parents=True)
        mock_dir.return_value = tmp_path

        from app.api.analysis import _transform_youtube_to_document
        result = _transform_youtube_to_document('nonexistent')
        assert result is None

    @patch('app.api.analysis._get_local_data_dir')
    def test_youtube_transform_with_data(self, mock_dir, tmp_path):
        yt_dir = tmp_path / 'youtube' / 'channels'
        yt_dir.mkdir(parents=True)
        data = {
            'channel_name': 'TestChannel',
            'recent_videos': [{
                'video': {'title': 'Video1', 'view_count': 100, 'like_count': 10, 'comment_count': 5},
                'comments': [{'text': 'nice!', 'likes': 3, 'sentiment': 'positive'}],
            }]
        }
        (yt_dir / 'test-channel_2026.json').write_text(json.dumps(data))
        mock_dir.return_value = tmp_path

        from app.api.analysis import _transform_youtube_to_document
        result = _transform_youtube_to_document('test-channel')
        assert result is not None
        assert 'TestChannel' in result
        assert 'Video1' in result
        assert 'nice!' in result

    @patch('app.api.analysis._get_local_data_dir')
    def test_dcinside_transform_no_files(self, mock_dir, tmp_path):
        dc_dir = tmp_path / 'dcinside' / 'test-gallery'
        dc_dir.mkdir(parents=True)
        mock_dir.return_value = tmp_path

        from app.api.analysis import _transform_dcinside_to_document
        result = _transform_dcinside_to_document('test-gallery')
        assert result is None  # empty dir

    @patch('app.api.analysis._get_local_data_dir')
    def test_dcinside_transform_with_data(self, mock_dir, tmp_path):
        dc_dir = tmp_path / 'dcinside' / 'testgallery'
        dc_dir.mkdir(parents=True)
        data = {
            'gallery_name': 'Test Gallery',
            'posts': [
                {'post': {'title': 'Post1', 'author': 'user1'}, 'content': 'content here',
                 'comments': [{'text': 'reply1', 'author': 'user2'}]},
            ]
        }
        (dc_dir / '2026-03-25.json').write_text(json.dumps(data))
        mock_dir.return_value = tmp_path

        from app.api.analysis import _transform_dcinside_to_document
        result = _transform_dcinside_to_document('testgallery')
        assert result is not None
        assert 'testgallery' in result or 'Test Gallery' in result


# ---------------------------------------------------------------------------
# _read_source_items
# ---------------------------------------------------------------------------

class TestReadSourceItems:
    @patch('app.api.analysis._get_local_data_dir')
    def test_youtube_items(self, mock_dir, tmp_path):
        yt_dir = tmp_path / 'youtube' / 'channels'
        yt_dir.mkdir(parents=True)
        data = {
            'channel_name': 'TestCh',
            'recent_videos': [{
                'video': {'title': 'V1'},
                'comments': [{'text': 'great', 'author': 'u1'}, {'text': 'bad', 'author': 'u2'}],
            }]
        }
        (yt_dir / 'testch_2026.json').write_text(json.dumps(data))
        mock_dir.return_value = tmp_path

        from app.api.analysis import _read_source_items
        items, stats = _read_source_items('youtube', 'testch')
        assert len(items) == 2
        assert stats['channel_name'] == 'TestCh'

    @patch('app.api.analysis._get_local_data_dir')
    def test_dcinside_items(self, mock_dir, tmp_path):
        dc_dir = tmp_path / 'dcinside' / 'testgal'
        dc_dir.mkdir(parents=True)
        data = {
            'gallery_name': 'TestGal',
            'posts': [
                {'post': {'title': 'P1', 'author': 'a1'}, 'comments': [{'text': 'c1'}]},
            ]
        }
        (dc_dir / 'data.json').write_text(json.dumps(data))
        mock_dir.return_value = tmp_path

        from app.api.analysis import _read_source_items
        items, stats = _read_source_items('dcinside', 'testgal')
        assert len(items) >= 1
        assert stats['gallery_name'] == 'TestGal'

    @patch('app.api.analysis._get_local_data_dir')
    def test_unknown_type(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path

        from app.api.analysis import _read_source_items
        items, stats = _read_source_items('unknown', 'test')
        assert items == []
        assert stats == {}
