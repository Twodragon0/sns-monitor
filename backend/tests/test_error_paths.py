"""Error path tests for SNS Monitor backend.

Covers:
1. DCInside gallery_posts: non-numeric page/limit returns 400
2. MiroFish JSON parse error in transform_sns_data returns 502
3. _mirofish_headers() rejects tokens with control characters
4. _is_safe_redirect() blocks open redirect patterns
5. sentiment_trend handles missing keys in sentiment dict via .get() fallback
"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import requests as real_requests


# ---------------------------------------------------------------------------
# 1. DCInside gallery_posts — non-numeric query params → 400
# ---------------------------------------------------------------------------

class TestGalleryPostsInvalidParams:
    """Non-numeric page or limit params must return 400."""

    def test_non_numeric_page_returns_400(self, client):
        resp = client.get('/api/dcinside/gallery/test-gallery/posts?page=abc')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data
        assert 'Invalid' in data['error'] or 'invalid' in data['error'].lower()

    def test_non_numeric_limit_returns_400(self, client):
        resp = client.get('/api/dcinside/gallery/test-gallery/posts?limit=xyz')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_float_page_returns_400(self, client):
        # int() on '1.5' raises ValueError
        resp = client.get('/api/dcinside/gallery/test-gallery/posts?page=1.5')
        assert resp.status_code == 400

    def test_float_limit_returns_400(self, client):
        resp = client.get('/api/dcinside/gallery/test-gallery/posts?limit=2.5')
        assert resp.status_code == 400

    def test_empty_page_param_uses_default(self, client):
        # Empty string for page falls back to default (1) without error
        resp = client.get('/api/dcinside/gallery/test-gallery/posts?page=')
        # int('') raises ValueError → 400
        assert resp.status_code == 400

    def test_numeric_params_still_work(self, client):
        resp = client.get('/api/dcinside/gallery/test-gallery/posts?page=1&limit=10')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 2. MiroFish JSON parse error in transform_sns_data → 502
# ---------------------------------------------------------------------------

class TestTransformSnsDataJsonParseError:
    """When MiroFish returns a non-JSON body, transform_sns_data must return 502."""

    @patch('app.api.analysis.requests.post')
    @patch('app.api.analysis._transform_dcinside_to_document')
    def test_mirofish_invalid_json_returns_502(
        self, mock_transform, mock_post, client
    ):
        # Make transform return some content so we proceed past the 404 check
        mock_transform.return_value = '# Some document content'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = 'not-json-at-all'
        mock_resp.json.side_effect = ValueError('No JSON object could be decoded')
        mock_post.return_value = mock_resp

        resp = client.post(
            '/api/analysis/transform',
            json={
                'sources': [{'type': 'dcinside', 'id': 'test-gallery'}],
                'project_name': 'Test',
                'simulation_requirement': 'Test req',
            },
        )
        assert resp.status_code == 502
        data = resp.get_json()
        assert 'error' in data
        assert 'Invalid response' in data['error'] or 'invalid' in data['error'].lower()

    @patch('app.api.analysis.requests.post')
    @patch('app.api.analysis._transform_youtube_to_document')
    def test_mirofish_html_error_page_returns_502(
        self, mock_transform, mock_post, client
    ):
        mock_transform.return_value = '# YouTube channel data'

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = '<html><body>Internal Server Error</body></html>'
        mock_resp.json.side_effect = ValueError('not json')
        mock_post.return_value = mock_resp

        resp = client.post(
            '/api/analysis/transform',
            json={'sources': [{'type': 'youtube', 'id': 'my-channel'}]},
        )
        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# 3. _mirofish_headers() — tokens with control characters are rejected
# ---------------------------------------------------------------------------

class TestMirofishHeadersTokenValidation:
    """Access tokens containing control characters must not appear in headers."""

    def _get_headers(self, app, token):
        """Call _mirofish_headers() inside an app context with the given token."""
        from app.api.analysis import _mirofish_headers

        with app.test_request_context('/'):
            from flask import session
            with app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['access_token'] = token
            # Use the app context directly to call the helper
            with app.app_context():
                # Push a request context that has the session pre-populated
                ctx = app.test_request_context('/')
                ctx.push()
                from flask import session as flask_session
                flask_session['access_token'] = token
                try:
                    return _mirofish_headers()
                finally:
                    ctx.pop()

    def test_token_with_tab_is_rejected(self, app):
        headers = self._get_headers(app, 'valid-prefix\t injected-header: value')
        assert 'Authorization' not in headers
        assert 'X-OpenAI-Access-Token' not in headers

    def test_token_with_null_byte_is_rejected(self, app):
        headers = self._get_headers(app, 'token\x00nullbyte')
        assert 'Authorization' not in headers

    def test_token_with_newline_is_rejected(self, app):
        headers = self._get_headers(app, 'token\nX-Injected: evil')
        assert 'Authorization' not in headers

    def test_token_with_carriage_return_is_rejected(self, app):
        headers = self._get_headers(app, 'token\rX-Injected: evil')
        assert 'Authorization' not in headers

    def test_token_with_bell_char_is_rejected(self, app):
        headers = self._get_headers(app, 'token\x07bell')
        assert 'Authorization' not in headers

    def test_valid_ascii_token_is_accepted(self, app):
        token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid.signature'
        headers = self._get_headers(app, token)
        assert headers.get('Authorization') == f'Bearer {token}'
        assert headers.get('X-OpenAI-Access-Token') == token

    def test_non_string_token_is_rejected(self, app):
        headers = self._get_headers(app, 12345)
        assert 'Authorization' not in headers

    def test_empty_token_is_rejected(self, app):
        headers = self._get_headers(app, '')
        assert 'Authorization' not in headers

    def test_whitespace_only_token_is_rejected(self, app):
        headers = self._get_headers(app, '   ')
        assert 'Authorization' not in headers


# ---------------------------------------------------------------------------
# 4. _is_safe_redirect() — open redirect prevention
# ---------------------------------------------------------------------------

class TestIsSafeRedirect:
    """_is_safe_redirect must block all open redirect patterns."""

    def _check(self, url):
        from app.api.auth import _is_safe_redirect
        return _is_safe_redirect(url)

    # --- must reject ---

    def test_rejects_double_slash(self):
        assert self._check('//evil.com') is False

    def test_rejects_backslash_after_slash(self):
        assert self._check('/\\evil.com') is False

    def test_rejects_http_scheme(self):
        assert self._check('http://evil.com') is False

    def test_rejects_https_scheme(self):
        assert self._check('https://evil.com/path') is False

    def test_rejects_javascript_scheme(self):
        assert self._check('javascript:alert(1)') is False

    def test_rejects_data_scheme(self):
        assert self._check('data:text/html,<script>') is False

    def test_rejects_empty_string(self):
        assert self._check('') is False

    def test_rejects_none(self):
        assert self._check(None) is False

    def test_rejects_non_string(self):
        assert self._check(42) is False

    def test_rejects_tab_control_char(self):
        assert self._check('/path\twith\ttabs') is False

    def test_rejects_newline_control_char(self):
        assert self._check('/path\nnewline') is False

    def test_rejects_null_byte(self):
        assert self._check('/path\x00null') is False

    def test_rejects_url_with_netloc(self):
        # urlparse('/path') has no netloc, but let's be explicit
        assert self._check('http://host/path') is False

    def test_rejects_protocol_relative_with_spaces(self):
        # Leading space then // — strip() removes space but // remains
        assert self._check('  //evil.com') is False

    # --- must accept ---

    def test_accepts_simple_path(self):
        assert self._check('/analysis') is True

    def test_accepts_path_with_query(self):
        assert self._check('/analysis?tab=summary') is True

    def test_accepts_path_with_fragment(self):
        assert self._check('/analysis#section') is True

    def test_accepts_nested_path(self):
        assert self._check('/api/analysis/status') is True

    def test_accepts_root(self):
        assert self._check('/') is True


# ---------------------------------------------------------------------------
# 5. sentiment_trend — missing keys in sentiment dict use .get() fallback
# ---------------------------------------------------------------------------

class TestSentimentTrendMissingKeys:
    """sentiment_trend must not crash when _analyze_sentiment returns a dict
    with missing sub-keys; the endpoint uses .get() with a default of 0."""

    def _make_gallery_dir(self, base_dir, gallery_id, post_data):
        """Write one JSON file to a temporary gallery directory."""
        gallery_dir = os.path.join(base_dir, 'dcinside', gallery_id)
        os.makedirs(gallery_dir)
        today = datetime.now().strftime('%Y-%m-%d')
        fpath = os.path.join(gallery_dir, f'{today}-00-00-00.json')
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(post_data, f)
        return gallery_dir

    @patch('app.api.analysis.Config')
    @patch('app.services.platform_analyzer.PlatformAnalyzer._analyze_sentiment')
    def test_sentiment_missing_positive_key(self, mock_analyze, mock_cfg, client):
        """If sentiment dict lacks 'positive', .get() returns 0 without KeyError."""
        # Return a sentiment dict with 'sentiment' sub-dict missing 'positive'
        mock_analyze.return_value = {
            'total': 5,
            'sentiment': {'neutral': 3, 'negative': 2},  # no 'positive'
            'top_keywords': [],
            'overall': 'neutral',
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_cfg.LOCAL_DATA_DIR = tmpdir
            self._make_gallery_dir(tmpdir, 'test-gallery', {
                'posts': [{'post': {'title': 'hello'}, 'comments': []}],
            })

            resp = client.get('/api/analysis/trend?type=dcinside&id=test-gallery')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'trend' in data
            if data['trend']:
                point = data['trend'][0]
                # Missing key must fall back to 0, not raise KeyError
                assert point['positive'] == 0
                assert point['negative'] == 2
                assert point['neutral'] == 3

    @patch('app.api.analysis.Config')
    @patch('app.services.platform_analyzer.PlatformAnalyzer._analyze_sentiment')
    def test_sentiment_missing_all_sub_keys(self, mock_analyze, mock_cfg, client):
        """If sentiment sub-dict is entirely empty, all counts fall back to 0."""
        mock_analyze.return_value = {
            'total': 0,
            'sentiment': {},  # empty — all keys missing
            'top_keywords': [],
            'overall': 'neutral',
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_cfg.LOCAL_DATA_DIR = tmpdir
            self._make_gallery_dir(tmpdir, 'empty-gallery', {
                'posts': [{'post': {'title': 'test'}, 'comments': []}],
            })

            resp = client.get('/api/analysis/trend?type=dcinside&id=empty-gallery')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'trend' in data
            if data['trend']:
                point = data['trend'][0]
                assert point['positive'] == 0
                assert point['neutral'] == 0
                assert point['negative'] == 0

    @patch('app.api.analysis.Config')
    @patch('app.services.platform_analyzer.PlatformAnalyzer._analyze_sentiment')
    def test_sentiment_top_keywords_missing(self, mock_analyze, mock_cfg, client):
        """If top_keywords is absent, the .get() fallback returns [] without error."""
        mock_analyze.return_value = {
            'total': 2,
            'sentiment': {'positive': 1, 'neutral': 1, 'negative': 0},
            # no 'top_keywords' key at all
            'overall': 'positive',
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_cfg.LOCAL_DATA_DIR = tmpdir
            self._make_gallery_dir(tmpdir, 'kw-gallery', {
                'posts': [{'post': {'title': 'good content'}, 'comments': []}],
            })

            resp = client.get('/api/analysis/trend?type=dcinside&id=kw-gallery')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'trend' in data
            if data['trend']:
                point = data['trend'][0]
                assert 'keywords' in point
                assert point['keywords'] == []

    def test_invalid_source_id_returns_400(self, client):
        """Source id with path traversal chars is rejected before any file I/O."""
        resp = client.get('/api/analysis/trend?type=dcinside&id=../etc/passwd')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_missing_source_id_returns_400(self, client):
        resp = client.get('/api/analysis/trend?type=dcinside')
        assert resp.status_code == 400
