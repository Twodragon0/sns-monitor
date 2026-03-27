"""
DCInside API routes.
Direct implementation (no legacy api_handlers delegation).
"""

import glob
import json
import logging
import os
import re
from datetime import datetime, timedelta

from flask import jsonify, request, Response

from . import dcinside_bp
from ..config import Config
from ..services.local_data import decimal_default

logger = logging.getLogger(__name__)

_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_@-]{1,128}$')

# DC인사이드 갤러리 목록 (정적 설정)
_GALLERY_IDS = [
    'example-gallery-1',
    'example-gallery-2',
    'example-gallery-3',
    'example-gallery-4',
    'example-gallery-5',
]
_GALLERY_NAMES = {
    'example-gallery-1': 'Example Gallery 1',
    'example-gallery-2': 'Example Gallery 2',
    'example-gallery-3': 'Example Gallery 3',
    'example-gallery-4': 'Example Gallery 4',
    'example-gallery-5': 'Example Gallery 5',
}


def _distribute_comments_to_posts(all_posts_data, total_comments):
    """total_comments가 있지만 각 게시글의 comment_count가 없는 경우 평균 분배."""
    if total_comments <= 0 or not all_posts_data:
        return

    posts_with_count = [
        p for p in all_posts_data
        if (p.get('post', {}).get('comment_count', 0) > 0 or p.get('comment_count', 0) > 0)
    ]
    if posts_with_count:
        return

    avg_comments_per_post = max(1, total_comments // len(all_posts_data))
    for post_data in all_posts_data:
        post = post_data.get('post', {})
        if not post.get('comment_count', 0):
            post['comment_count'] = avg_comments_per_post
        if not post_data.get('comment_count', 0):
            post_data['comment_count'] = avg_comments_per_post


def _load_gallery_data_local(gallery_id, max_files=0, days_back=14):
    """로컬 파일시스템에서 갤러리 데이터 로드.

    Returns:
        (all_posts_data, crawled_at, keywords, total_comments, positive_count, negative_count)
    """
    gallery_dir = os.path.join(Config.LOCAL_DATA_DIR, 'dcinside', gallery_id)
    if not os.path.exists(gallery_dir):
        return [], '', [], 0, 0, 0

    all_posts_data = []
    seen_post_ids = set()
    total_comments = 0
    positive_count = 0
    negative_count = 0
    crawled_at = ''
    keywords = []

    cutoff_date = datetime.now() - timedelta(days=days_back)

    files = sorted(glob.glob(os.path.join(gallery_dir, '*.json')), reverse=True)

    files_to_read = []
    for file_path in files:
        filename = os.path.basename(file_path)
        try:
            date_str = filename[:10]  # 'YYYY-MM-DD'
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
            if file_date >= cutoff_date:
                files_to_read.append(file_path)
            else:
                break
        except (ValueError, IndexError):
            files_to_read.append(file_path)

    if max_files > 0:
        files_to_read = files_to_read[:max_files]

    for i, file_path in enumerate(files_to_read):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_data = json.load(f)

            if i == 0:
                crawled_at = file_data.get('crawled_at', '')
                keywords = file_data.get('keywords', [])

            file_total_comments = file_data.get('total_comments', 0)
            total_comments += file_total_comments
            positive_count += file_data.get('positive_count', 0)
            negative_count += file_data.get('negative_count', 0)

            posts_in_file = file_data.get('data', [])
            if file_total_comments > 0 and posts_in_file:
                _distribute_comments_to_posts(posts_in_file, file_total_comments)

            for post_data in posts_in_file:
                post_id = post_data.get('post', {}).get('post_id', '')
                if post_id and post_id not in seen_post_ids:
                    seen_post_ids.add(post_id)
                    all_posts_data.append(post_data)
        except Exception as e:
            logger.error("Error reading file %s: %s", file_path, e, exc_info=True)
            continue

    return all_posts_data, crawled_at, keywords, total_comments, positive_count, negative_count


def _format_post(post_data, max_comments=None):
    """post_data dict를 응답용 dict로 변환."""
    post = post_data.get('post', {})
    comments = post_data.get('comments', [])
    comment_count = (
        post.get('comment_count', 0)
        or post_data.get('comment_count', 0)
        or (len(comments) if comments else 0)
    )
    result = {
        'post_id': post.get('post_id', ''),
        'title': post.get('title', ''),
        'author': post.get('author', '익명'),
        'date': post.get('date', ''),
        'view_count': post.get('view_count', 0),
        'recommend_count': post.get('recommend_count', 0),
        'url': post.get('url', ''),
        'content': post_data.get('content', ''),
        'comment_count': comment_count,
        'comments': comments[:max_comments] if max_comments is not None else comments,
        'matched_keyword': post.get('matched_keyword', ''),
    }
    return result


@dcinside_bp.route('/api/dcinside/galleries', methods=['GET'])
def galleries():
    """DC인사이드 갤러리 목록 반환."""
    if not Config.LOCAL_MODE:
        return jsonify({"error": "S3 mode not supported. Set LOCAL_MODE=true"}), 501

    galleries_data = []

    for gallery_id in _GALLERY_IDS:
        try:
            all_posts_data, crawled_at, keywords, total_comments, positive_count, negative_count = \
                _load_gallery_data_local(gallery_id, max_files=0, days_back=14)
            _distribute_comments_to_posts(all_posts_data, total_comments)

            if all_posts_data:
                posts_with_comments = [
                    p for p in all_posts_data
                    if p.get('comments') and len(p.get('comments', [])) > 0
                ]
                posts_without_comments = [
                    p for p in all_posts_data
                    if not p.get('comments') or len(p.get('comments', [])) == 0
                ]
                sorted_posts = posts_with_comments + posts_without_comments

                # total_comments가 있지만 모든 게시글 comment_count가 0인 경우 재분배
                posts_with_actual_comments = [
                    p for p in sorted_posts
                    if (
                        p.get('post', {}).get('comment_count', 0) > 0
                        or p.get('comment_count', 0) > 0
                        or (p.get('comments') and len(p.get('comments', [])) > 0)
                    )
                ]
                if total_comments > 0 and not posts_with_actual_comments and sorted_posts:
                    avg = max(1, total_comments // len(sorted_posts))
                    for post_data in sorted_posts:
                        post = post_data.get('post', {})
                        if not post.get('comment_count', 0):
                            post['comment_count'] = avg
                        if not post_data.get('comment_count', 0):
                            post_data['comment_count'] = avg

                posts = [_format_post(p, max_comments=10) for p in sorted_posts[:20]]

                galleries_data.append({
                    'gallery_id': gallery_id,
                    'gallery_name': _GALLERY_NAMES.get(gallery_id, gallery_id),
                    'total_posts': len(all_posts_data),
                    'total_comments': total_comments,
                    'positive_count': positive_count,
                    'negative_count': negative_count,
                    'crawled_at': crawled_at,
                    'keywords': keywords,
                    'posts': posts,
                })
        except Exception as e:
            logger.error("Error loading gallery %s: %s", gallery_id, e, exc_info=True)
            continue

    body = json.dumps({'galleries': galleries_data}, default=decimal_default, ensure_ascii=False)
    return Response(body, status=200, content_type='application/json')


@dcinside_bp.route('/api/dcinside/gallery/<gallery_id>/posts', methods=['GET'])
def gallery_posts(gallery_id):
    """DC인사이드 특정 갤러리의 게시글 페이지네이션 엔드포인트."""
    try:
        if not gallery_id or not _SAFE_ID_RE.match(gallery_id):
            return Response(
                json.dumps({'error': 'Gallery ID is required'}),
                status=400,
                content_type='application/json',
            )

        page = int(request.args.get('page', 1))
        limit = min(int(request.args.get('limit', 20)), 100)
        offset = (page - 1) * limit

        if not Config.LOCAL_MODE:
            return jsonify({"error": "S3 mode not supported. Set LOCAL_MODE=true"}), 501

        all_posts_data, _, _, _, _, _ = _load_gallery_data_local(
            gallery_id, max_files=0, days_back=14
        )

        if not all_posts_data:
            body = json.dumps(
                {
                    'gallery_id': gallery_id,
                    'posts': [],
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total_posts': 0,
                        'total_pages': 0,
                        'has_more': False,
                    },
                },
                ensure_ascii=False,
            )
            return Response(body, status=200, content_type='application/json')

        total_posts = len(all_posts_data)
        paginated = all_posts_data[offset:offset + limit]
        posts = [_format_post(p) for p in paginated]

        body = json.dumps(
            {
                'gallery_id': gallery_id,
                'posts': posts,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total_posts': total_posts,
                    'total_pages': (total_posts + limit - 1) // limit,
                    'has_more': offset + limit < total_posts,
                },
            },
            default=decimal_default,
            ensure_ascii=False,
        )
        return Response(body, status=200, content_type='application/json')

    except Exception as e:
        logger.error("Error in gallery_posts %s: %s", gallery_id, e, exc_info=True)
        body = json.dumps({'error': str(e)}, ensure_ascii=False)
        return Response(body, status=500, content_type='application/json')
