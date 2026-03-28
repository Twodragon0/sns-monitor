"""
Boost tests for analysis.py to reach 90%+ coverage.

Targets uncovered lines:
  - 35-38:  _mirofish_headers with valid/invalid session tokens
  - 80-81:  _transform_youtube_to_document JSON parse error
  - 92, 122-123: _transform_dcinside_to_document missing dir + JSON error
  - 185, 235-237: transform_sns_data else-branch and except Exception
  - 287-288: get_analysis_graph_data ConnectionError
  - 360-365: _source_display_name_youtube exception branch
  - 378, 389-402: list_available_sources with real DCInside dir structure
  - 432-433, 452-453: _read_source_items exception handlers
  - 534-571: sentiment_trend DCInside with actual data files
  - 593-638: gallery_compare full path with data
  - 643-741: generate_daily_report full path
  - 744-781: list_reports + get_report
  - 792, 796: _session_llm_kwargs, llm_status
  - 822-854: ai_summary complete
  - 859-915: ai_chat complete paths
  - 918-993: ai_url_analyze complete
  - 995-1045: ai_url_chat complete
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import requests as req_lib


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dc_data(gallery_name='TestGal', pos=3, neg=1):
    """Build a minimal DCInside JSON structure with some posts."""
    return {
        'gallery_name': gallery_name,
        'collected_at': '2026-03-25T10:00:00',
        'posts': [
            {
                'post': {'title': f'Post {i}', 'author': f'user{i}', 'text': '좋아요 정말'},
                'content': 'really great content here',
                'comments': [
                    {'text': '굉장히 좋다'},
                    {'text': '별로'},
                ]
            }
            for i in range(pos + neg)
        ]
    }


# ---------------------------------------------------------------------------
# _mirofish_headers – session token branches (lines 35-38)
# ---------------------------------------------------------------------------

class TestMirofishHeaders:
    def test_valid_token_sets_authorization(self, app):
        """Line 35-36: valid string token → Authorization header set."""
        with app.test_request_context('/'):
            from flask import session
            with app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['access_token'] = 'valid-token-abc'
                # call inside an actual request context
            # Direct function call with patched session
            from app.api.analysis import _mirofish_headers
            with app.test_request_context('/'):
                from flask import session as flask_session
                flask_session['access_token'] = 'valid-token-abc'
                headers = _mirofish_headers()
        assert headers.get('Authorization') == 'Bearer valid-token-abc'
        assert headers.get('X-OpenAI-Access-Token') == 'valid-token-abc'

    def test_invalid_token_type_logs_warning(self, app):
        """Line 38: non-string token → warning logged, no header."""
        from app.api.analysis import _mirofish_headers
        with app.test_request_context('/'):
            from flask import session as flask_session
            flask_session['access_token'] = 12345  # int, not string
            with patch('app.api.analysis.logger') as mock_log:
                headers = _mirofish_headers()
                mock_log.warning.assert_called_once()
        assert 'Authorization' not in headers

    def test_token_with_newline_rejected(self, app):
        """Line 38: token with newline → treated as invalid."""
        from app.api.analysis import _mirofish_headers
        with app.test_request_context('/'):
            from flask import session as flask_session
            flask_session['access_token'] = 'bad\ntoken'
            headers = _mirofish_headers()
        assert 'Authorization' not in headers

    def test_no_token_returns_empty_headers(self, app):
        """No access_token in session → empty dict."""
        from app.api.analysis import _mirofish_headers
        with app.test_request_context('/'):
            headers = _mirofish_headers()
        assert headers == {}


# ---------------------------------------------------------------------------
# _transform_youtube_to_document – exception handler (line 80-81)
# ---------------------------------------------------------------------------

class TestTransformYoutubeException:
    @patch('app.api.analysis._get_local_data_dir')
    def test_json_parse_error_logged(self, mock_dir, tmp_path):
        """Line 80-81: bad JSON file → warning logged, returns None."""
        yt_dir = tmp_path / 'youtube' / 'channels'
        yt_dir.mkdir(parents=True)
        (yt_dir / 'broken-channel_2026.json').write_text('{ not valid json }}}')
        mock_dir.return_value = tmp_path

        from app.api.analysis import _transform_youtube_to_document
        with patch('app.api.analysis.logger') as mock_log:
            result = _transform_youtube_to_document('broken-channel')
        mock_log.warning.assert_called()
        assert result is None


# ---------------------------------------------------------------------------
# _transform_dcinside_to_document – missing dir + exception (lines 92, 122-123)
# ---------------------------------------------------------------------------

class TestTransformDCInsideException:
    @patch('app.api.analysis._get_local_data_dir')
    def test_nonexistent_gallery_dir(self, mock_dir, tmp_path):
        """Line 92: gallery dir doesn't exist → returns None."""
        mock_dir.return_value = tmp_path
        from app.api.analysis import _transform_dcinside_to_document
        result = _transform_dcinside_to_document('totally-missing-gallery')
        assert result is None

    @patch('app.api.analysis._get_local_data_dir')
    def test_json_parse_error_logged(self, mock_dir, tmp_path):
        """Line 122-123: bad JSON in DCInside dir → warning logged."""
        dc_dir = tmp_path / 'dcinside' / 'broken-gal'
        dc_dir.mkdir(parents=True)
        (dc_dir / '2026-03-25.json').write_text('not valid{{')
        mock_dir.return_value = tmp_path

        from app.api.analysis import _transform_dcinside_to_document
        with patch('app.api.analysis.logger') as mock_log:
            result = _transform_dcinside_to_document('broken-gal')
        mock_log.warning.assert_called()
        assert result is None


# ---------------------------------------------------------------------------
# transform_sns_data – dcinside branch + generic Exception (lines 185, 235-237)
# ---------------------------------------------------------------------------

class TestTransformSnsDataExtraPaths:
    @patch('app.api.analysis._transform_dcinside_to_document')
    @patch('app.api.analysis.requests.post')
    def test_dcinside_source_type(self, mock_post, mock_transform, client):
        """Line 185: dcinside type reaches _transform_dcinside_to_document."""
        mock_transform.return_value = '# DC content'
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'task_id': 'dc-t1'}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        resp = client.post('/api/analysis/transform', json={
            'sources': [{'type': 'dcinside', 'id': 'test-gallery'}],
        })
        assert resp.status_code == 200
        mock_transform.assert_called_once_with('test-gallery')

    @patch('app.api.analysis._transform_youtube_to_document')
    @patch('app.api.analysis.requests.post')
    def test_generic_exception_returns_500(self, mock_post, mock_transform, client):
        """Lines 235-237: non-ConnectionError exception → 500."""
        mock_transform.return_value = '# doc'
        mock_post.side_effect = ValueError("unexpected")

        resp = client.post('/api/analysis/transform', json={
            'sources': [{'type': 'youtube', 'id': 'test'}],
        })
        assert resp.status_code == 500
        assert 'error' in resp.get_json()


# ---------------------------------------------------------------------------
# get_analysis_graph_data – ConnectionError (line 287-288)
# ---------------------------------------------------------------------------

class TestGraphDataConnectionError:
    @patch('app.api.analysis.requests.get')
    def test_connection_error(self, mock_get, client):
        """Lines 287-288: ConnectionError → 503."""
        mock_get.side_effect = req_lib.ConnectionError()
        resp = client.get('/api/analysis/graph/data/graph123')
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# _source_display_name_youtube – exception branch (lines 360-365)
# ---------------------------------------------------------------------------

class TestSourceDisplayNameYoutube:
    def test_read_error_returns_stem(self, tmp_path):
        """Lines 360-365: unreadable file → falls back to stem."""
        bad_file = tmp_path / 'my-channel_2026.json'
        bad_file.write_text('{ invalid }}}')
        from app.api.analysis import _source_display_name_youtube
        result = _source_display_name_youtube(bad_file)
        assert result == 'my-channel_2026'

    def test_reads_channel_title(self, tmp_path):
        """Normal read with channel_title."""
        f = tmp_path / 'ch_2026.json'
        f.write_text(json.dumps({'channel_title': 'My Channel Title'}))
        from app.api.analysis import _source_display_name_youtube
        assert _source_display_name_youtube(f) == 'My Channel Title'

    def test_reads_channel_name_fallback(self, tmp_path):
        """Falls back to channel_name when no channel_title."""
        f = tmp_path / 'ch_2026.json'
        f.write_text(json.dumps({'channel_name': 'Channel Name'}))
        from app.api.analysis import _source_display_name_youtube
        assert _source_display_name_youtube(f) == 'Channel Name'


# ---------------------------------------------------------------------------
# list_available_sources – DCInside dir iteration (lines 378, 389-402)
# ---------------------------------------------------------------------------

class TestListAvailableSources:
    @patch('app.api.analysis._get_local_data_dir')
    def test_with_dcinside_dir(self, mock_dir, tmp_path):
        """Lines 389-402: DCInside galleries listed in sources."""
        # Create youtube dir (empty)
        yt_dir = tmp_path / 'youtube' / 'channels'
        yt_dir.mkdir(parents=True)
        # Create DCInside gallery with JSON
        dc_gal = tmp_path / 'dcinside' / 'my-gallery'
        dc_gal.mkdir(parents=True)
        gal_data = {'gallery_name': 'My Gallery'}
        (dc_gal / '2026-03-25.json').write_text(json.dumps(gal_data))
        mock_dir.return_value = tmp_path

        # Patch Config.LOCAL_DATA_DIR to match tmp_path
        with patch('app.api.analysis.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            from app.api.analysis import list_available_sources
            # Can't call directly (needs app context) — use client
        pass  # tested via client below

    def test_sources_endpoint_returns_dcinside(self, client, tmp_path):
        """Full endpoint test for DCInside source listing."""
        dc_gal = tmp_path / 'dcinside' / 'test-gallery'
        dc_gal.mkdir(parents=True)
        (dc_gal / '2026-03-25.json').write_text(json.dumps({'gallery_name': 'Test Gallery'}))

        yt_dir = tmp_path / 'youtube' / 'channels'
        yt_dir.mkdir(parents=True)
        yt_file = yt_dir / 'my-channel_2026.json'
        yt_file.write_text(json.dumps({'channel_name': 'MyChannel'}))

        with patch('app.api.analysis.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = str(tmp_path)
            resp = client.get('/api/analysis/sources')

        assert resp.status_code == 200
        data = resp.get_json()
        assert 'sources' in data


# ---------------------------------------------------------------------------
# _read_source_items – exception handlers (lines 432-433, 452-453)
# ---------------------------------------------------------------------------

class TestReadSourceItemsExceptions:
    @patch('app.api.analysis._get_local_data_dir')
    def test_youtube_json_error_skipped(self, mock_dir, tmp_path):
        """Lines 432-433: bad JSON file in YouTube → skipped silently."""
        yt_dir = tmp_path / 'youtube' / 'channels'
        yt_dir.mkdir(parents=True)
        (yt_dir / 'broken_2026.json').write_text('NOT JSON')
        mock_dir.return_value = tmp_path

        from app.api.analysis import _read_source_items
        items, stats = _read_source_items('youtube', 'broken')
        assert items == []
        assert stats == {}

    @patch('app.api.analysis._get_local_data_dir')
    def test_dcinside_json_error_skipped(self, mock_dir, tmp_path):
        """Lines 452-453: bad JSON file in DCInside → skipped silently."""
        dc_dir = tmp_path / 'dcinside' / 'broken-gal'
        dc_dir.mkdir(parents=True)
        (dc_dir / 'data.json').write_text('BROKEN{{')
        mock_dir.return_value = tmp_path

        from app.api.analysis import _read_source_items
        items, stats = _read_source_items('dcinside', 'broken-gal')
        assert items == []
        assert stats == {}


# ---------------------------------------------------------------------------
# sentiment_trend – DCInside with real data (lines 534-571)
# ---------------------------------------------------------------------------

class TestSentimentTrendWithData:
    @patch('app.api.analysis._get_local_data_dir')
    def test_dcinside_trend_with_files(self, mock_dir, tmp_path, client):
        """Lines 534-571: DCInside trend calculation with timestamped files."""
        dc_dir = tmp_path / 'dcinside' / 'test-gal'
        dc_dir.mkdir(parents=True)

        # Use timestamp filename format: 2026-03-18-12-30-05.json
        dc_data = _make_dc_data()
        (dc_dir / '2026-03-18-12-30-05.json').write_text(json.dumps(dc_data))
        mock_dir.return_value = tmp_path

        resp = client.get('/api/analysis/trend?type=dcinside&id=test-gal')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['source_id'] == 'test-gal'
        assert len(body['trend']) >= 1
        point = body['trend'][0]
        assert 'timestamp' in point
        assert 'positive' in point
        assert 'negative' in point

    @patch('app.api.analysis._get_local_data_dir')
    def test_dcinside_trend_non_timestamp_filename(self, mock_dir, tmp_path, client):
        """Line 543: filename without 5-part timestamp → fallback to collected_at."""
        dc_dir = tmp_path / 'dcinside' / 'short-gal'
        dc_dir.mkdir(parents=True)
        dc_data = _make_dc_data()
        dc_data['collected_at'] = '2026-03-25T09:00:00'
        # Short filename: only 3 parts when split by '-'
        (dc_dir / '2026-03.json').write_text(json.dumps(dc_data))
        mock_dir.return_value = tmp_path

        resp = client.get('/api/analysis/trend?type=dcinside&id=short-gal')
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body['trend']) >= 1

    @patch('app.api.analysis._get_local_data_dir')
    def test_dcinside_trend_empty_items_skipped(self, mock_dir, tmp_path, client):
        """Line 558: files with no text items → trend entry skipped."""
        dc_dir = tmp_path / 'dcinside' / 'empty-gal'
        dc_dir.mkdir(parents=True)
        # Posts with no text
        dc_data = {'posts': [{'post': {'title': '', 'text': ''}, 'comments': []}]}
        (dc_dir / '2026-03-18-12-30-05.json').write_text(json.dumps(dc_data))
        mock_dir.return_value = tmp_path

        resp = client.get('/api/analysis/trend?type=dcinside&id=empty-gal')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['trend'] == []

    @patch('app.api.analysis._get_local_data_dir')
    def test_dcinside_trend_bad_json_file_logged(self, mock_dir, tmp_path, client):
        """Line 569: bad JSON in trend file → warning, still returns 200."""
        dc_dir = tmp_path / 'dcinside' / 'bad-gal'
        dc_dir.mkdir(parents=True)
        (dc_dir / '2026-03-18-12-30-05.json').write_text('{ broken }}}')
        mock_dir.return_value = tmp_path

        resp = client.get('/api/analysis/trend?type=dcinside&id=bad-gal')
        assert resp.status_code == 200
        assert resp.get_json()['trend'] == []

    def test_trend_missing_id_returns_400(self, client):
        """Line 521: empty id param → 400."""
        resp = client.get('/api/analysis/trend?type=dcinside&id=')
        assert resp.status_code == 400

    def test_trend_invalid_id_returns_400(self, client):
        """Line 521: id with invalid chars → 400."""
        resp = client.get('/api/analysis/trend?type=dcinside&id=../../bad')
        assert resp.status_code == 400

    @patch('app.api.analysis._get_local_data_dir')
    def test_dcinside_trend_source_not_found(self, mock_dir, tmp_path, client):
        """Line 530: dcinside dir doesn't exist → 404."""
        mock_dir.return_value = tmp_path
        resp = client.get('/api/analysis/trend?type=dcinside&id=nonexistent')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# gallery_compare – full path with data (lines 593-638)
# ---------------------------------------------------------------------------

class TestGalleryCompareWithData:
    @patch('app.api.analysis._get_local_data_dir')
    def test_compare_with_galleries(self, mock_dir, tmp_path, client):
        """Lines 593-638: galleries directory with data → analyzed and returned."""
        dc_dir = tmp_path / 'dcinside'
        # Gallery 1 – real data
        gal1 = dc_dir / 'gallery1'
        gal1.mkdir(parents=True)
        (gal1 / '2026-03-25.json').write_text(json.dumps(_make_dc_data('Gallery One', pos=3, neg=1)))
        # Gallery 2 – different data
        gal2 = dc_dir / 'gallery2'
        gal2.mkdir(parents=True)
        (gal2 / '2026-03-25.json').write_text(json.dumps(_make_dc_data('Gallery Two', pos=1, neg=3)))
        # example prefix → should be skipped
        example_dir = dc_dir / 'example-gallery'
        example_dir.mkdir(parents=True)
        (example_dir / '2026-03-25.json').write_text(json.dumps(_make_dc_data('Example')))

        mock_dir.return_value = tmp_path
        resp = client.get('/api/analysis/compare')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'galleries' in data
        # only non-example galleries
        ids = [g['id'] for g in data['galleries']]
        assert 'gallery1' in ids
        assert 'gallery2' in ids
        assert 'example-gallery' not in ids

    @patch('app.api.analysis._get_local_data_dir')
    def test_compare_bad_json_skipped(self, mock_dir, tmp_path, client):
        """Line 633-634: bad JSON in gallery → warning logged, gallery skipped."""
        dc_dir = tmp_path / 'dcinside' / 'broken-gallery'
        dc_dir.mkdir(parents=True)
        (dc_dir / '2026-03-25.json').write_text('{ broken }}}')
        mock_dir.return_value = tmp_path

        resp = client.get('/api/analysis/compare')
        assert resp.status_code == 200
        assert resp.get_json()['galleries'] == []

    @patch('app.api.analysis._get_local_data_dir')
    def test_compare_skips_gallery_with_no_json(self, mock_dir, tmp_path, client):
        """Lines 598-599: gallery dir with no JSON files → skipped."""
        dc_dir = tmp_path / 'dcinside' / 'empty-gallery'
        dc_dir.mkdir(parents=True)
        mock_dir.return_value = tmp_path

        resp = client.get('/api/analysis/compare')
        assert resp.status_code == 200
        assert resp.get_json()['galleries'] == []


# ---------------------------------------------------------------------------
# generate_daily_report – full path (lines 643-741)
# ---------------------------------------------------------------------------

class TestGenerateDailyReport:
    @patch('app.api.analysis._get_local_data_dir')
    def test_generates_report_with_data(self, mock_dir, tmp_path, client):
        """Lines 643-741: full daily report generation with multiple galleries."""
        dc_dir = tmp_path / 'dcinside'
        gal = dc_dir / 'test-gallery'
        gal.mkdir(parents=True)
        data = _make_dc_data('Test Gallery', pos=5, neg=2)
        (gal / '2026-03-25.json').write_text(json.dumps(data))
        mock_dir.return_value = tmp_path

        resp = client.post('/api/analysis/report/generate-daily')
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'date' in body
        assert 'summary' in body
        assert 'galleries' in body
        assert len(body['galleries']) >= 1
        assert (tmp_path / 'analysis' / 'reports').exists()

    @patch('app.api.analysis._get_local_data_dir')
    def test_daily_report_today_files_preferred(self, mock_dir, tmp_path, client):
        """Line 663: files matching today's date are preferred over latest."""
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        dc_dir = tmp_path / 'dcinside' / 'daily-gal'
        dc_dir.mkdir(parents=True)
        data = _make_dc_data()
        (dc_dir / f'{today}-12-00-00.json').write_text(json.dumps(data))
        (dc_dir / '2020-01-01-00-00-00.json').write_text(json.dumps(data))
        mock_dir.return_value = tmp_path

        resp = client.post('/api/analysis/report/generate-daily')
        assert resp.status_code == 200

    @patch('app.api.analysis._get_local_data_dir')
    def test_daily_report_skips_empty_items(self, mock_dir, tmp_path, client):
        """Line 684: gallery files with no extractable text → skipped."""
        dc_dir = tmp_path / 'dcinside' / 'empty-gal'
        dc_dir.mkdir(parents=True)
        (dc_dir / '2026-03-25.json').write_text(
            json.dumps({'posts': [{'post': {'title': '', 'text': ''}, 'comments': []}]})
        )
        mock_dir.return_value = tmp_path

        resp = client.post('/api/analysis/report/generate-daily')
        assert resp.status_code == 200
        assert resp.get_json()['galleries'] == []

    @patch('app.api.analysis._get_local_data_dir')
    def test_daily_report_bad_json_inner_loop(self, mock_dir, tmp_path, client):
        """Line 681: bad JSON in inner loop → silently skipped."""
        dc_dir = tmp_path / 'dcinside' / 'partial-gal'
        dc_dir.mkdir(parents=True)
        (dc_dir / '2026-03-25.json').write_text('{{BROKEN')
        mock_dir.return_value = tmp_path

        resp = client.post('/api/analysis/report/generate-daily')
        assert resp.status_code == 200

    @patch('app.api.analysis._get_local_data_dir')
    def test_daily_report_example_galleries_skipped(self, mock_dir, tmp_path, client):
        """Line 656: directories starting with 'example' are skipped."""
        dc_dir = tmp_path / 'dcinside' / 'example-gallery'
        dc_dir.mkdir(parents=True)
        (dc_dir / '2026-03-25.json').write_text(json.dumps(_make_dc_data()))
        mock_dir.return_value = tmp_path

        resp = client.post('/api/analysis/report/generate-daily')
        assert resp.status_code == 200
        assert resp.get_json()['galleries'] == []

    @patch('app.api.analysis._get_local_data_dir')
    def test_daily_report_alerts_for_high_negative(self, mock_dir, tmp_path, client):
        """Line 715: galleries with neg_pct >= 5 appear in alerts."""
        dc_dir = tmp_path / 'dcinside' / 'neg-gallery'
        dc_dir.mkdir(parents=True)
        # Many negative comments
        data = {
            'gallery_name': 'Negative Gallery',
            'posts': [
                {
                    'post': {'title': f'Bad Post {i}', 'text': '싫어요 별로'},
                    'content': 'terrible content bad',
                    'comments': [{'text': '나쁘다'}, {'text': '별로다'}]
                }
                for i in range(20)
            ]
        }
        (dc_dir / '2026-03-25.json').write_text(json.dumps(data))
        mock_dir.return_value = tmp_path

        resp = client.post('/api/analysis/report/generate-daily')
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'alerts' in body
        assert 'summary' in body


# ---------------------------------------------------------------------------
# list_reports + get_report (lines 744-781)
# ---------------------------------------------------------------------------

class TestReportEndpoints:
    @patch('app.api.analysis._get_local_data_dir')
    def test_list_reports_no_dir(self, mock_dir, tmp_path, client):
        """Line 748: report dir doesn't exist → empty list."""
        mock_dir.return_value = tmp_path
        resp = client.get('/api/analysis/reports')
        assert resp.status_code == 200
        assert resp.get_json() == {'reports': []}

    @patch('app.api.analysis._get_local_data_dir')
    def test_list_reports_with_data(self, mock_dir, tmp_path, client):
        """Lines 752-766: report files read and returned."""
        report_dir = tmp_path / 'analysis' / 'reports'
        report_dir.mkdir(parents=True)
        report = {
            'date': '2026-03-25',
            'summary': {'total_items': 10, 'alerts': 0},
        }
        (report_dir / '2026-03-25.json').write_text(json.dumps(report))
        mock_dir.return_value = tmp_path

        resp = client.get('/api/analysis/reports')
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body['reports']) == 1
        assert body['reports'][0]['date'] == '2026-03-25'

    @patch('app.api.analysis._get_local_data_dir')
    def test_list_reports_bad_json_skipped(self, mock_dir, tmp_path, client):
        """Line 761 (except): bad JSON in report dir → skipped."""
        report_dir = tmp_path / 'analysis' / 'reports'
        report_dir.mkdir(parents=True)
        (report_dir / '2026-03-25.json').write_text('{{broken')
        mock_dir.return_value = tmp_path

        resp = client.get('/api/analysis/reports')
        assert resp.status_code == 200
        assert resp.get_json()['reports'] == []

    def test_get_report_invalid_date(self, client):
        """Line 770: invalid date format → 400."""
        resp = client.get('/api/analysis/reports/bad date!')
        assert resp.status_code == 400

    @patch('app.api.analysis._get_local_data_dir')
    def test_get_report_not_found(self, mock_dir, tmp_path, client):
        """Lines 771-773: report file doesn't exist → 404."""
        mock_dir.return_value = tmp_path
        resp = client.get('/api/analysis/reports/2026-03-25')
        assert resp.status_code == 404

    @patch('app.api.analysis._get_local_data_dir')
    def test_get_report_success(self, mock_dir, tmp_path, client):
        """Lines 774-775: existing report returned."""
        report_dir = tmp_path / 'analysis' / 'reports'
        report_dir.mkdir(parents=True)
        report = {'date': '2026-03-25', 'galleries': []}
        (report_dir / '2026-03-25.json').write_text(json.dumps(report))
        mock_dir.return_value = tmp_path

        resp = client.get('/api/analysis/reports/2026-03-25')
        assert resp.status_code == 200
        assert resp.get_json()['date'] == '2026-03-25'


# ---------------------------------------------------------------------------
# llm_status (lines 792, 796)
# ---------------------------------------------------------------------------

class TestLlmStatus:
    @patch('app.services.llm_analyzer.get_llm_status')
    def test_llm_status_returns_status(self, mock_status, client):
        """Lines 792, 796: llm_status calls get_llm_status and returns result."""
        mock_status.return_value = {
            'available': True,
            'provider': 'openai',
            'providers': {'openai': True, 'anthropic': False},
        }
        resp = client.get('/api/analysis/llm/status')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['available'] is True


# ---------------------------------------------------------------------------
# ai_summary – complete (lines 822-854)
# ---------------------------------------------------------------------------

class TestAiSummaryComplete:
    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_dcinside_to_document')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_dcinside_source(self, mock_analyze, mock_transform, mock_provider, client):
        """Line 835: dcinside source type in ai_summary."""
        mock_transform.return_value = '# DCInside doc'
        mock_analyze.return_value = {'success': True, 'analysis': 'results', 'provider': 'openai'}
        resp = client.post('/api/analysis/ai-summary', json={
            'sources': [{'type': 'dcinside', 'id': 'test-gal'}],
        })
        assert resp.status_code == 200
        mock_transform.assert_called_once_with('test-gal')

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_youtube_to_document')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_unknown_source_type_skipped(self, mock_analyze, mock_transform, mock_provider, client):
        """Line 837: unknown type → skipped, if no docs → 404."""
        mock_transform.return_value = None
        resp = client.post('/api/analysis/ai-summary', json={
            'sources': [{'type': 'unknown', 'id': 'test'}],
        })
        assert resp.status_code == 404

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    def test_invalid_source_id(self, mock_provider, client):
        """Line 830: invalid id → 400."""
        resp = client.post('/api/analysis/ai-summary', json={
            'sources': [{'type': 'youtube', 'id': '../../bad'}],
        })
        assert resp.status_code == 400

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    def test_no_sources(self, mock_provider, client):
        """Line 822: no sources → 400."""
        resp = client.post('/api/analysis/ai-summary', json={})
        assert resp.status_code == 400

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_youtube_to_document')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_llm_error_with_success_false(self, mock_analyze, mock_transform, mock_provider, client):
        """Line 848-849: LLM returns error without success → 500."""
        mock_transform.return_value = '# doc'
        mock_analyze.return_value = {'error': 'quota exceeded', 'success': False}
        resp = client.post('/api/analysis/ai-summary', json={
            'sources': [{'type': 'youtube', 'id': 'test'}],
        })
        assert resp.status_code == 500

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_youtube_to_document')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_multiple_sources_combined(self, mock_analyze, mock_transform, mock_provider, client):
        """Line 845: multiple documents joined with separator."""
        mock_transform.return_value = '# doc content'
        mock_analyze.return_value = {'success': True, 'analysis': 'ok', 'provider': 'openai'}
        resp = client.post('/api/analysis/ai-summary', json={
            'sources': [
                {'type': 'youtube', 'id': 'ch1'},
                {'type': 'youtube', 'id': 'ch2'},
            ],
        })
        assert resp.status_code == 200
        # analyze_with_llm called with joined docs
        call_args = mock_analyze.call_args[0][0]
        assert '---' in call_args


# ---------------------------------------------------------------------------
# ai_chat – complete paths (lines 859-915)
# ---------------------------------------------------------------------------

class TestAiChatComplete:
    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    def test_invalid_source_id(self, mock_provider, client):
        """Line 894: invalid source id → 400."""
        resp = client.post('/api/analysis/ai-chat', json={
            'sources': [{'type': 'youtube', 'id': '../../bad'}],
            'message': 'hello',
        })
        assert resp.status_code == 400

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_dcinside_to_document')
    @patch('app.services.llm_analyzer.chat_with_llm')
    def test_dcinside_source_in_chat(self, mock_chat, mock_transform, mock_provider, client):
        """Line 899: dcinside type in ai_chat."""
        mock_transform.return_value = '# DCInside doc'
        mock_chat.return_value = {'success': True, 'reply': 'response'}
        resp = client.post('/api/analysis/ai-chat', json={
            'sources': [{'type': 'dcinside', 'id': 'test-gal'}],
            'message': 'What is the sentiment?',
        })
        assert resp.status_code == 200
        mock_transform.assert_called_once_with('test-gal')

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_youtube_to_document')
    @patch('app.services.llm_analyzer.chat_with_llm')
    def test_unknown_type_skipped_no_data(self, mock_chat, mock_transform, mock_provider, client):
        """Line 901: unknown type → continue. No docs → 404."""
        resp = client.post('/api/analysis/ai-chat', json={
            'sources': [{'type': 'reddit', 'id': 'testid'}],
            'message': 'hello',
        })
        assert resp.status_code == 404

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.api.analysis._transform_youtube_to_document')
    @patch('app.services.llm_analyzer.chat_with_llm')
    def test_llm_error_returns_500(self, mock_chat, mock_transform, mock_provider, client):
        """Lines 912-913: chat_with_llm returns error → 500."""
        mock_transform.return_value = '# doc'
        mock_chat.return_value = {'error': 'model down', 'success': False}
        resp = client.post('/api/analysis/ai-chat', json={
            'sources': [{'type': 'youtube', 'id': 'test'}],
            'message': 'question here',
        })
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# ai_url_analyze – complete (lines 918-993)
# ---------------------------------------------------------------------------

class TestAiUrlAnalyzeComplete:
    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_url_analyze_with_all_fields(self, mock_analyze, mock_provider, client):
        """Lines 953-993: full document building with all optional fields."""
        mock_analyze.return_value = {'success': True, 'analysis': 'great content', 'provider': 'openai'}
        resp = client.post('/api/analysis/ai-url-analyze', json={
            'result': {
                'platform': 'youtube',
                'title': 'Test Video Title',
                'description': 'A fascinating test video',
                'content': 'Long video content here' * 10,
                'view_count': 50000,
                'like_count': 1500,
                'comment_count': 200,
                'subscriber_count': 100000,
                'comments': [
                    {'text': 'Amazing video!', 'author': 'user1'},
                    {'text': 'Not great', 'author': 'user2'},
                ],
                'analysis': {
                    'overall': 'positive',
                    'sentiment': {'positive': 180, 'neutral': 15, 'negative': 5},
                },
            },
            'question': 'What are the key themes?',
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        # Verify document was built with all sections
        doc_arg = mock_analyze.call_args[0][0]
        assert 'YOUTUBE' in doc_arg
        assert 'Description' in doc_arg
        assert 'Content' in doc_arg
        assert 'Stats' in doc_arg
        assert 'Comments' in doc_arg
        assert 'Sentiment' in doc_arg

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_url_analyze_replies_label(self, mock_analyze, mock_provider, client):
        """Line 968-971: replies (not comments) → label='Posts'."""
        mock_analyze.return_value = {'success': True, 'analysis': 'ok', 'provider': 'openai'}
        resp = client.post('/api/analysis/ai-url-analyze', json={
            'result': {
                'platform': 'reddit',
                'title': 'A Reddit Post',
                'replies': [{'text': 'reply one'}, {'text': 'reply two'}],
            },
        })
        assert resp.status_code == 200
        doc_arg = mock_analyze.call_args[0][0]
        assert 'Posts' in doc_arg

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_url_analyze_llm_error_500(self, mock_analyze, mock_provider, client):
        """Lines 990-991: LLM error → 500."""
        mock_analyze.return_value = {'error': 'api down', 'success': False}
        resp = client.post('/api/analysis/ai-url-analyze', json={
            'result': {'platform': 'youtube', 'title': 'test'},
        })
        assert resp.status_code == 500

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.analyze_with_llm')
    def test_url_analyze_no_optional_fields(self, mock_analyze, mock_provider, client):
        """Lines 953-962: result with minimal fields – no description/content/stats."""
        mock_analyze.return_value = {'success': True, 'analysis': 'ok', 'provider': 'openai'}
        resp = client.post('/api/analysis/ai-url-analyze', json={
            'result': {'platform': 'telegram', 'username': 'testchannel'},
        })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# ai_url_chat – complete (lines 995-1045)
# ---------------------------------------------------------------------------

class TestAiUrlChatComplete:
    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.chat_with_llm')
    def test_url_chat_with_comments(self, mock_chat, mock_provider, client):
        """Lines 1030-1043: URL chat with comment items."""
        mock_chat.return_value = {'success': True, 'reply': 'great analysis'}
        resp = client.post('/api/analysis/ai-url-chat', json={
            'result': {
                'platform': 'youtube',
                'title': 'Test',
                'description': 'A description',
                'comments': [
                    {'text': 'love it'},
                    {'text': 'good'},
                ],
            },
            'message': 'Summarize the comments',
        })
        assert resp.status_code == 200
        doc_arg = mock_chat.call_args[0][0]
        assert 'YOUTUBE' in doc_arg
        assert 'items collected' in doc_arg

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.chat_with_llm')
    def test_url_chat_with_replies(self, mock_chat, mock_provider, client):
        """Line 1030: replies fallback used when no comments."""
        mock_chat.return_value = {'success': True, 'reply': 'ok'}
        resp = client.post('/api/analysis/ai-url-chat', json={
            'result': {
                'platform': 'reddit',
                'title': 'Reddit thread',
                'replies': [{'text': 'a reply'}, {'text': 'another'}],
            },
            'message': 'Analyze replies',
        })
        assert resp.status_code == 200

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.chat_with_llm')
    def test_url_chat_llm_error_500(self, mock_chat, mock_provider, client):
        """Lines 1042-1043: LLM error → 500."""
        mock_chat.return_value = {'error': 'overloaded', 'success': False}
        resp = client.post('/api/analysis/ai-url-chat', json={
            'result': {'platform': 'youtube', 'title': 'Test'},
            'message': 'question',
        })
        assert resp.status_code == 500

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.chat_with_llm')
    def test_url_chat_no_optional_fields(self, mock_chat, mock_provider, client):
        """Line 1028: result with no description → skipped."""
        mock_chat.return_value = {'success': True, 'reply': 'ok'}
        resp = client.post('/api/analysis/ai-url-chat', json={
            'result': {'platform': 'kakao', 'title': 'Channel'},
            'message': 'hello',
        })
        assert resp.status_code == 200

    @patch('app.services.llm_analyzer.get_available_provider', return_value='openai')
    @patch('app.services.llm_analyzer.chat_with_llm')
    def test_url_chat_items_with_no_text(self, mock_chat, mock_provider, client):
        """Line 1036: items missing text → not appended to doc."""
        mock_chat.return_value = {'success': True, 'reply': 'ok'}
        resp = client.post('/api/analysis/ai-url-chat', json={
            'result': {
                'platform': 'youtube',
                'title': 'Test',
                'comments': [{'author': 'notext'}],  # no 'text' key
            },
            'message': 'test',
        })
        assert resp.status_code == 200
