"""Additional tests for dcinside.py Blueprint - internal helpers and edge cases."""

import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


class TestDistributeCommentsToPosts:
    def test_zero_total_comments_no_op(self):
        from app.api.dcinside import _distribute_comments_to_posts
        posts = [{'post': {}, 'comment_count': 0}]
        _distribute_comments_to_posts(posts, 0)
        assert posts[0]['comment_count'] == 0

    def test_empty_posts_no_op(self):
        from app.api.dcinside import _distribute_comments_to_posts
        _distribute_comments_to_posts([], 100)  # should not raise

    def test_posts_with_existing_counts_no_redistribution(self):
        from app.api.dcinside import _distribute_comments_to_posts
        posts = [{'post': {'comment_count': 5}, 'comment_count': 5}]
        _distribute_comments_to_posts(posts, 10)
        # already has counts - no change
        assert posts[0]['post']['comment_count'] == 5

    def test_posts_without_counts_get_average(self):
        from app.api.dcinside import _distribute_comments_to_posts
        posts = [
            {'post': {}, 'comment_count': 0},
            {'post': {}, 'comment_count': 0},
        ]
        _distribute_comments_to_posts(posts, 10)
        assert posts[0]['post']['comment_count'] == 5
        assert posts[1]['post']['comment_count'] == 5

    def test_minimum_average_is_one(self):
        from app.api.dcinside import _distribute_comments_to_posts
        posts = [{'post': {}, 'comment_count': 0}] * 100
        _distribute_comments_to_posts(posts, 1)
        assert posts[0]['post']['comment_count'] >= 1


class TestFormatPost:
    def test_basic_formatting(self):
        from app.api.dcinside import _format_post
        post_data = {
            'post': {
                'post_id': 'p1',
                'title': 'Test Post',
                'author': 'user1',
                'date': '2024-01-01',
                'view_count': 100,
                'recommend_count': 10,
                'url': 'https://dc.co/p1',
                'comment_count': 5,
            },
            'content': 'Post content here',
            'comments': [{'text': 'c1'}, {'text': 'c2'}],
        }
        result = _format_post(post_data)
        assert result['post_id'] == 'p1'
        assert result['title'] == 'Test Post'
        assert result['author'] == 'user1'
        assert result['content'] == 'Post content here'
        assert len(result['comments']) == 2

    def test_max_comments_limit(self):
        from app.api.dcinside import _format_post
        post_data = {
            'post': {},
            'comments': [{'text': f'c{i}'} for i in range(20)],
        }
        result = _format_post(post_data, max_comments=5)
        assert len(result['comments']) == 5

    def test_comment_count_from_post_dict(self):
        from app.api.dcinside import _format_post
        post_data = {
            'post': {'comment_count': 7},
            'comments': [],
        }
        result = _format_post(post_data)
        assert result['comment_count'] == 7

    def test_comment_count_from_actual_comments(self):
        from app.api.dcinside import _format_post
        post_data = {
            'post': {},
            'comments': [{'text': 'c1'}, {'text': 'c2'}, {'text': 'c3'}],
        }
        result = _format_post(post_data)
        assert result['comment_count'] == 3

    def test_default_author_anonymous(self):
        from app.api.dcinside import _format_post
        result = _format_post({'post': {}, 'comments': []})
        assert result['author'] == '익명'

    def test_empty_post_data_no_error(self):
        from app.api.dcinside import _format_post
        result = _format_post({})
        assert result['post_id'] == ''
        assert result['title'] == ''


class TestLoadGalleryDataLocal:
    def test_missing_gallery_dir_returns_empty(self):
        from app.api.dcinside import _load_gallery_data_local
        with patch('app.api.dcinside.Config') as mock_cfg:
            mock_cfg.LOCAL_DATA_DIR = '/nonexistent'
            result = _load_gallery_data_local('test_gallery')
            posts, crawled_at, keywords, total_comments, pos, neg = result
            assert posts == []
            assert total_comments == 0

    def test_valid_gallery_files_loaded(self):
        from app.api.dcinside import _load_gallery_data_local
        with tempfile.TemporaryDirectory() as tmpdir:
            gallery_dir = os.path.join(tmpdir, 'dcinside', 'test_gallery')
            os.makedirs(gallery_dir)
            today = datetime.now().strftime('%Y-%m-%d')
            data = {
                'crawled_at': '2024-01-01T00:00:00',
                'keywords': ['kw1'],
                'total_comments': 10,
                'positive_count': 6,
                'negative_count': 2,
                'data': [
                    {'post': {'post_id': 'p1', 'title': 'Post 1'}, 'comments': []},
                ],
            }
            with open(os.path.join(gallery_dir, f'{today}-12-00-00.json'), 'w') as f:
                json.dump(data, f)
            with patch('app.api.dcinside.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                posts, crawled_at, keywords, total_comments, pos, neg = _load_gallery_data_local('test_gallery')
                assert len(posts) == 1
                assert total_comments == 10
                assert pos == 6
                assert neg == 2
                assert keywords == ['kw1']

    def test_old_files_excluded(self):
        from app.api.dcinside import _load_gallery_data_local
        with tempfile.TemporaryDirectory() as tmpdir:
            gallery_dir = os.path.join(tmpdir, 'dcinside', 'test_gallery')
            os.makedirs(gallery_dir)
            old_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            data = {
                'crawled_at': '2024-01-01',
                'keywords': [],
                'total_comments': 5,
                'positive_count': 0,
                'negative_count': 0,
                'data': [{'post': {'post_id': 'old1'}, 'comments': []}],
            }
            with open(os.path.join(gallery_dir, f'{old_date}-00-00-00.json'), 'w') as f:
                json.dump(data, f)
            with patch('app.api.dcinside.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                posts, _, _, _, _, _ = _load_gallery_data_local('test_gallery', days_back=14)
                assert posts == []

    def test_max_files_limits_loaded(self):
        from app.api.dcinside import _load_gallery_data_local
        with tempfile.TemporaryDirectory() as tmpdir:
            gallery_dir = os.path.join(tmpdir, 'dcinside', 'test_gallery')
            os.makedirs(gallery_dir)
            today = datetime.now().strftime('%Y-%m-%d')
            for i in range(5):
                data = {
                    'crawled_at': '',
                    'keywords': [],
                    'total_comments': 1,
                    'positive_count': 0,
                    'negative_count': 0,
                    'data': [{'post': {'post_id': f'p{i}'}, 'comments': []}],
                }
                with open(os.path.join(gallery_dir, f'{today}-0{i}-00-00.json'), 'w') as f:
                    json.dump(data, f)
            with patch('app.api.dcinside.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                posts, _, _, _, _, _ = _load_gallery_data_local('test_gallery', max_files=2)
                assert len(posts) <= 2

    def test_deduplicates_posts_by_id(self):
        from app.api.dcinside import _load_gallery_data_local
        with tempfile.TemporaryDirectory() as tmpdir:
            gallery_dir = os.path.join(tmpdir, 'dcinside', 'test_gallery')
            os.makedirs(gallery_dir)
            today = datetime.now().strftime('%Y-%m-%d')
            # Two files with the same post_id
            for suffix in ['01', '02']:
                data = {
                    'crawled_at': '',
                    'keywords': [],
                    'total_comments': 1,
                    'positive_count': 0,
                    'negative_count': 0,
                    'data': [{'post': {'post_id': 'dup_post'}, 'comments': []}],
                }
                with open(os.path.join(gallery_dir, f'{today}-{suffix}-00-00.json'), 'w') as f:
                    json.dump(data, f)
            with patch('app.api.dcinside.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                posts, _, _, _, _, _ = _load_gallery_data_local('test_gallery')
                post_ids = [p['post']['post_id'] for p in posts]
                assert post_ids.count('dup_post') == 1


class TestGalleriesRoute:
    def test_galleries_returns_200(self, client):
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'galleries' in data

    @patch('app.api.dcinside.Config')
    def test_galleries_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 501

    def test_galleries_is_list(self, client):
        resp = client.get('/api/dcinside/galleries')
        data = resp.get_json()
        assert isinstance(data['galleries'], list)


class TestGalleryPostsRoute:
    def test_valid_gallery_id_returns_200(self, client):
        resp = client.get('/api/dcinside/gallery/test-gallery/posts')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'posts' in data
        assert 'pagination' in data

    def test_invalid_gallery_id_returns_400(self, client):
        resp = client.get('/api/dcinside/gallery/../posts')
        assert resp.status_code in (400, 404)

    @patch('app.api.dcinside.Config')
    def test_s3_mode_returns_501(self, mock_cfg, client):
        mock_cfg.LOCAL_MODE = False
        mock_cfg._SAFE_ID_RE = __import__('re').compile(r'^[a-zA-Z0-9_@-]{1,128}$')
        resp = client.get('/api/dcinside/gallery/test-gallery/posts')
        assert resp.status_code == 501

    def test_pagination_defaults(self, client):
        resp = client.get('/api/dcinside/gallery/test-gallery/posts')
        data = resp.get_json()
        assert data['pagination']['page'] == 1
        assert data['pagination']['limit'] == 20

    def test_custom_page_and_limit(self, client):
        resp = client.get('/api/dcinside/gallery/test-gallery/posts?page=2&limit=5')
        data = resp.get_json()
        assert data['pagination']['page'] == 2
        assert data['pagination']['limit'] == 5

    def test_limit_capped_at_100(self, client):
        resp = client.get('/api/dcinside/gallery/test-gallery/posts?limit=999')
        data = resp.get_json()
        assert data['pagination']['limit'] <= 100

    def test_gallery_id_in_response(self, client):
        resp = client.get('/api/dcinside/gallery/my-gallery/posts')
        data = resp.get_json()
        assert data['gallery_id'] == 'my-gallery'

    def test_has_more_false_when_no_posts(self, client):
        resp = client.get('/api/dcinside/gallery/empty-gallery/posts')
        data = resp.get_json()
        assert data['pagination']['has_more'] is False

    def test_with_actual_data(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            gallery_dir = os.path.join(tmpdir, 'dcinside', 'test-gallery')
            os.makedirs(gallery_dir)
            today = datetime.now().strftime('%Y-%m-%d')
            data = {
                'crawled_at': '2024-01-01',
                'keywords': [],
                'total_comments': 0,
                'positive_count': 0,
                'negative_count': 0,
                'data': [{'post': {'post_id': f'p{i}', 'title': f'Post {i}'}, 'comments': []} for i in range(5)],
            }
            with open(os.path.join(gallery_dir, f'{today}-00-00-00.json'), 'w') as f:
                json.dump(data, f)
            with patch('app.api.dcinside.Config') as mock_cfg:
                mock_cfg.LOCAL_MODE = True
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                resp = client.get('/api/dcinside/gallery/test-gallery/posts')
                result = resp.get_json()
                assert result['pagination']['total_posts'] == 5
