"""
MiroFish Analysis Bridge API.
Transforms SNS crawled data into documents and proxies analysis requests to MiroFish.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import requests
from flask import request, jsonify

from . import analysis_bp
from ..config import Config

logger = logging.getLogger(__name__)

MIROFISH_URL = os.environ.get('MIROFISH_ENDPOINT', 'http://mirofish:5001')


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
        resp = requests.get(f'{MIROFISH_URL}/api/graph/project/list', timeout=5)
        available = resp.status_code == 200
    except Exception:
        available = False

    return jsonify({
        'mirofish_available': available,
        'mirofish_endpoint': MIROFISH_URL
    })


@analysis_bp.route('/api/analysis/transform', methods=['POST'])
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
        src_id = src.get('id')

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
            timeout=120
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
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/api/analysis/graph/build', methods=['POST'])
def build_analysis_graph():
    """Proxy graph build request to MiroFish."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/graph/build',
            json=request.get_json(),
            timeout=30
        )
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/graph/task/<task_id>', methods=['GET'])
def get_analysis_task(task_id):
    """Proxy task status query to MiroFish."""
    try:
        resp = requests.get(f'{MIROFISH_URL}/api/graph/task/{task_id}', timeout=10)
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/graph/data/<graph_id>', methods=['GET'])
def get_analysis_graph_data(graph_id):
    """Proxy graph data query to MiroFish."""
    try:
        resp = requests.get(f'{MIROFISH_URL}/api/graph/data/{graph_id}', timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/report/generate', methods=['POST'])
def generate_analysis_report():
    """Proxy report generation to MiroFish."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/report/generate',
            json=request.get_json(),
            timeout=30
        )
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/report/<report_id>', methods=['GET'])
def get_analysis_report(report_id):
    """Proxy report retrieval from MiroFish."""
    try:
        resp = requests.get(f'{MIROFISH_URL}/api/report/{report_id}', timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/report/chat', methods=['POST'])
def chat_with_analysis():
    """Proxy chat with MiroFish ReportAgent."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/report/chat',
            json=request.get_json(),
            timeout=60
        )
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/projects', methods=['GET'])
def list_analysis_projects():
    """Proxy project list from MiroFish."""
    try:
        resp = requests.get(f'{MIROFISH_URL}/api/graph/project/list', timeout=10)
        return jsonify(resp.json()), resp.status_code
    except requests.ConnectionError:
        return jsonify({'error': 'MiroFish service not available'}), 503


@analysis_bp.route('/api/analysis/sources', methods=['GET'])
def list_available_sources():
    """List available SNS data sources that can be analyzed."""
    data_dir = Path(Config.LOCAL_DATA_DIR)
    sources = []

    # YouTube channels
    yt_dir = data_dir / 'youtube' / 'channels'
    if yt_dir.exists():
        for f in yt_dir.glob('*.json'):
            sources.append({
                'type': 'youtube',
                'id': f.stem,
                'name': f.stem,
                'file': str(f.name),
                'size': f.stat().st_size
            })

    # DCInside galleries
    dc_dir = data_dir / 'dcinside'
    if dc_dir.exists():
        for gallery_dir in dc_dir.iterdir():
            if gallery_dir.is_dir():
                json_files = list(gallery_dir.glob('*.json'))
                if json_files:
                    sources.append({
                        'type': 'dcinside',
                        'id': gallery_dir.name,
                        'name': gallery_dir.name,
                        'files': len(json_files),
                        'latest': max(f.name for f in json_files)
                    })

    return jsonify({'sources': sources})
