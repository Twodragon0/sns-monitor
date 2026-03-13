"""
MiroFish Analysis Bridge API.
Transforms SNS crawled data into documents and proxies analysis requests to MiroFish.
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import requests
from flask import request, jsonify, session

from . import analysis_bp
from .auth import require_analysis_auth
from .. import limiter
from ..config import Config

# Alphanumeric + hyphens + underscores only for path IDs
_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{1,128}$')

logger = logging.getLogger(__name__)

MIROFISH_URL = os.environ.get('MIROFISH_ENDPOINT', 'http://mirofish:5001')


def _mirofish_headers():
    """Forward OpenAI OAuth access token to MiroFish so it can call OpenAI API without LLM_API_KEY."""
    headers = {}
    token = session.get('access_token')
    if token:
        headers['Authorization'] = f'Bearer {token}'
        headers['X-OpenAI-Access-Token'] = token  # MiroFish can use either
    return headers


def _get_local_data_dir():
    return Path(Config.LOCAL_DATA_DIR)


def _transform_youtube_to_document(channel_handle):
    """Transform YouTube crawler data into a Markdown document for MiroFish."""
    data_dir = _get_local_data_dir() / 'youtube' / 'channels'
    lines = []

    for json_file in sorted(data_dir.glob(f'{channel_handle}*.json'), reverse=True)[:5]:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            channel_name = data.get('channel_name', channel_handle)
            lines.append(f"# YouTube Analysis: {channel_name} ({json_file.stem})")
            lines.append("")

            for video_entry in data.get('recent_videos', data.get('data', []))[:10]:
                video = video_entry.get('video', video_entry)
                title = video.get('title', 'Unknown')
                views = video.get('view_count', video.get('views', 0))
                likes = video.get('like_count', video.get('likes', 0))
                comments_count = video.get('comment_count', video.get('comments', 0))

                lines.append(f"## Video: {title}")
                lines.append(f"- Views: {views:,} / Likes: {likes:,} / Comments: {comments_count}")
                lines.append("")

                comments = video_entry.get('comments', [])
                if comments:
                    lines.append("### Comments")
                    for c in comments[:20]:
                        text = c.get('text', '')
                        c_likes = c.get('likes', c.get('like_count', 0))
                        sentiment = c.get('sentiment', '')
                        lines.append(f"- \"{text}\" (likes: {c_likes}, sentiment: {sentiment})")
                    lines.append("")
        except Exception as e:
            logger.warning("Failed to read %s: %s", json_file, e)

    return '\n'.join(lines) if lines else None


def _transform_dcinside_to_document(gallery_id):
    """Transform DCInside crawler data into a Markdown document for MiroFish."""
    data_dir = _get_local_data_dir() / 'dcinside' / gallery_id
    lines = []

    if not data_dir.exists():
        return None

    for json_file in sorted(data_dir.glob('*.json'), reverse=True)[:5]:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            lines.append(f"# DCInside Gallery: {gallery_id} ({json_file.stem})")
            lines.append("")

            posts = data.get('posts', data.get('data', []))
            for post_entry in posts[:20]:
                post = post_entry.get('post', post_entry)
                title = post.get('title', 'No title')
                author = post.get('author', 'anonymous')
                views = post.get('views', post.get('view_count', 0))

                lines.append(f"## Post: {title}")
                lines.append(f"- Author: {author} / Views: {views}")

                content = post_entry.get('content', post.get('content', ''))
                if content:
                    lines.append(f"- Content: {content[:500]}")

                comments = post_entry.get('comments', [])
                if comments:
                    for c in comments[:10]:
                        c_text = c.get('text', c.get('content', ''))
                        lines.append(f"  - Comment: \"{c_text}\"")
                lines.append("")
        except Exception as e:
            logger.warning("Failed to read %s: %s", json_file, e)

    return '\n'.join(lines) if lines else None


@analysis_bp.route('/api/analysis/status', methods=['GET'])
def analysis_status():
    """Check MiroFish service availability."""
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/project/list',
            timeout=5,
            headers=_mirofish_headers(),
        )
        available = resp.status_code == 200
    except Exception:
        available = False

    return jsonify({
        'mirofish_available': available,
        'mirofish_endpoint': MIROFISH_URL
    })


@analysis_bp.route('/api/analysis/transform', methods=['POST'])
@limiter.limit("5 per minute")
@require_analysis_auth
def transform_sns_data():
    """
    Transform SNS crawled data into a document and send to MiroFish for analysis.

    Request JSON:
    {
        "sources": [
            {"type": "youtube", "id": "example-creator-1"},
            {"type": "dcinside", "id": "example-gallery-1"}
        ],
        "project_name": "SNS Analysis - Jan 2025",
        "simulation_requirement": "Analyze community sentiment trends and predict reactions"
    }
    """
    data = request.get_json() or {}
    sources = data.get('sources', [])
    project_name = data.get('project_name', f'SNS Analysis - {datetime.now().strftime("%Y-%m-%d")}')
    simulation_requirement = data.get('simulation_requirement',
        'Analyze social media community sentiment, identify key trends, and predict audience reactions')

    if not sources:
        return jsonify({'error': 'No data sources specified'}), 400

    # Transform each source to Markdown document
    documents = []
    for src in sources:
        src_type = src.get('type')
        src_id = src.get('id', '')
        if not _SAFE_ID_RE.match(src_id):
            return jsonify({'error': f'Invalid source id'}), 400

        if src_type == 'youtube':
            doc = _transform_youtube_to_document(src_id)
        elif src_type == 'dcinside':
            doc = _transform_dcinside_to_document(src_id)
        else:
            continue

        if doc:
            documents.append({
                'filename': f'{src_type}_{src_id}.md',
                'content': doc
            })

    if not documents:
        return jsonify({'error': 'No data found for specified sources'}), 404

    # Send to MiroFish as file upload
    try:
        import tempfile
        files = []
        temp_files = []

        for doc in documents:
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
            tmp.write(doc['content'])
            tmp.close()
            temp_files.append(tmp.name)
            files.append(('files', (doc['filename'], open(tmp.name, 'rb'), 'text/markdown')))

        resp = requests.post(
            f'{MIROFISH_URL}/api/graph/ontology/generate',
            data={
                'simulation_requirement': simulation_requirement,
                'project_name': project_name,
            },
            files=files,
            timeout=120,
            headers=_mirofish_headers(),
        )

        # Clean up temp files
        for f_tuple in files:
            f_tuple[1][1].close()
        for tmp_path in temp_files:
            os.unlink(tmp_path)

        result = resp.json()
        return jsonify(result), resp.status_code

    except requests.ConnectionError:
        return jsonify({
            'error': 'MiroFish service not available. Start with: docker-compose --profile analysis up -d'
        }), 503
    except Exception as e:
        logger.error("MiroFish transform failed: %s", e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@analysis_bp.route('/api/analysis/graph/build', methods=['POST'])
@require_analysis_auth
def build_analysis_graph():
    """Proxy graph build request to MiroFish."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/graph/build',
            json=request.get_json(),
            timeout=30,
            headers=_mirofish_headers(),
        )
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/graph/task/<task_id>', methods=['GET'])
@require_analysis_auth
def get_analysis_task(task_id):
    """Proxy task status query to MiroFish."""
    if not _SAFE_ID_RE.match(task_id):
        return jsonify({'error': 'Invalid task_id'}), 400
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/task/{task_id}',
            timeout=10,
            headers=_mirofish_headers(),
        )
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/graph/data/<graph_id>', methods=['GET'])
@require_analysis_auth
def get_analysis_graph_data(graph_id):
    """Proxy graph data query to MiroFish."""
    if not _SAFE_ID_RE.match(graph_id):
        return jsonify({'error': 'Invalid graph_id'}), 400
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/data/{graph_id}',
            timeout=30,
            headers=_mirofish_headers(),
        )
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/report/generate', methods=['POST'])
@require_analysis_auth
def generate_analysis_report():
    """Proxy report generation to MiroFish."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/report/generate',
            json=request.get_json(),
            timeout=30,
            headers=_mirofish_headers(),
        )
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/report/<report_id>', methods=['GET'])
@require_analysis_auth
def get_analysis_report(report_id):
    """Proxy report retrieval from MiroFish."""
    if not _SAFE_ID_RE.match(report_id):
        return jsonify({'error': 'Invalid report_id'}), 400
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/report/{report_id}',
            timeout=30,
            headers=_mirofish_headers(),
        )
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/report/chat', methods=['POST'])
@limiter.limit("20 per minute")
@require_analysis_auth
def chat_with_analysis():
    """Proxy chat with MiroFish ReportAgent."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/report/chat',
            json=request.get_json(),
            timeout=60,
            headers=_mirofish_headers(),
        )
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/projects', methods=['GET'])
@require_analysis_auth
def list_analysis_projects():
    """Proxy project list from MiroFish."""
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/project/list',
            timeout=10,
            headers=_mirofish_headers(),
        )
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


def _source_display_name_youtube(json_path):
    """Extract channel display name from YouTube crawler JSON."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('channel_title') or data.get('channel_name') or json_path.stem
    except Exception:
        return json_path.stem


@analysis_bp.route('/api/analysis/sources', methods=['GET'])
def list_available_sources():
    """List available SNS data sources that can be analyzed (for MiroFish analysis/summary)."""
    data_dir = Path(Config.LOCAL_DATA_DIR)
    sources = []

    # YouTube channels (local-data/youtube/channels/*.json)
    yt_dir = data_dir / 'youtube' / 'channels'
    if yt_dir.exists():
        for f in yt_dir.glob('*.json'):
            sources.append({
                'type': 'youtube',
                'id': f.stem,
                'name': _source_display_name_youtube(f),
                'file': str(f.name),
                'size': f.stat().st_size,
            })

    # DCInside galleries (local-data/dcinside/<gallery_id>/*.json)
    dc_dir = data_dir / 'dcinside'
    if dc_dir.exists():
        for gallery_dir in dc_dir.iterdir():
            if gallery_dir.is_dir():
                json_files = list(gallery_dir.glob('*.json'))
                if json_files:
                    # Prefer gallery name from latest JSON if available
                    name = gallery_dir.name
                    try:
                        latest = max(json_files, key=lambda p: p.stat().st_mtime)
                        with open(latest, 'r', encoding='utf-8') as fp:
                            data = json.load(fp)
                        name = data.get('gallery_name') or name
                    except Exception:
                        pass
                    sources.append({
                        'type': 'dcinside',
                        'id': gallery_dir.name,
                        'name': name,
                        'files': len(json_files),
                        'latest': max(f.name for f in json_files),
                    })

    return jsonify({'sources': sources})


def _read_source_items(src_type, src_id):
    """Read crawled items from local JSON files for local sentiment analysis."""
    data_dir = _get_local_data_dir()
    items = []
    stats = {}

    if src_type == 'youtube':
        yt_dir = data_dir / 'youtube' / 'channels'
        for json_file in sorted(yt_dir.glob(f'{src_id}*.json'), reverse=True)[:3]:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                stats['channel_name'] = data.get('channel_name', src_id)
                for video in data.get('recent_videos', data.get('data', []))[:10]:
                    v = video.get('video', video)
                    stats.setdefault('video_count', 0)
                    stats['video_count'] += 1
                    for c in video.get('comments', [])[:30]:
                        items.append({'text': c.get('text', ''), 'author': c.get('author', '')})
            except Exception:
                pass

    elif src_type == 'dcinside':
        dc_dir = data_dir / 'dcinside' / src_id
        if dc_dir.exists():
            for json_file in sorted(dc_dir.glob('*.json'), reverse=True)[:3]:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    stats['gallery_name'] = data.get('gallery_name', src_id)
                    for post in data.get('posts', data.get('data', []))[:20]:
                        p = post.get('post', post)
                        items.append({'text': p.get('title', '') + ' ' + (post.get('content', p.get('content', ''))[:300]), 'author': p.get('author', '')})
                        for c in post.get('comments', [])[:10]:
                            items.append({'text': c.get('text', c.get('content', '')), 'author': c.get('author', '')})
                except Exception:
                    pass

    return items, stats


@analysis_bp.route('/api/analysis/local-summary', methods=['POST'])
@limiter.limit("10 per minute")
def local_summary():
    """
    Local analysis without MiroFish: reads crawled data and runs keyword-based sentiment analysis.
    Works offline — no external AI service required.
    """
    from ..services.platform_analyzer import PlatformAnalyzer

    data = request.get_json() or {}
    sources_list = data.get('sources', [])
    if not sources_list:
        return jsonify({'error': 'No data sources specified'}), 400

    analyzer = PlatformAnalyzer(data_dir=str(_get_local_data_dir()))
    all_items = []
    source_summaries = []

    for src in sources_list:
        src_type = src.get('type', '')
        src_id = src.get('id', '')
        if not _SAFE_ID_RE.match(src_id):
            return jsonify({'error': 'Invalid source id'}), 400

        items, stats = _read_source_items(src_type, src_id)
        if not items:
            continue

        sentiment = analyzer._analyze_sentiment(items)
        all_items.extend(items)
        source_summaries.append({
            'type': src_type,
            'id': src_id,
            'name': stats.get('channel_name') or stats.get('gallery_name') or src_id,
            'item_count': len(items),
            'sentiment': sentiment,
        })

    if not source_summaries:
        return jsonify({'error': 'No data found for specified sources'}), 404

    # Overall combined sentiment
    overall_sentiment = analyzer._analyze_sentiment(all_items)

    return jsonify({
        'success': True,
        'mode': 'local',
        'sources': source_summaries,
        'overall': overall_sentiment,
        'total_items': len(all_items),
    })
