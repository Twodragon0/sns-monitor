"""
MiroFish AI analysis service proxy routes.
All routes proxy requests to the external MiroFish service.
"""

import logging
import os
import tempfile
from datetime import datetime

import requests
from flask import request, jsonify, session

from . import analysis_bp, csrf_protect
from .auth import require_analysis_auth
from .. import limiter
from ..config import Config

logger = logging.getLogger(__name__)

MIROFISH_URL = os.environ.get('MIROFISH_ENDPOINT', 'http://mirofish:5001')

# Alphanumeric + hyphens + underscores only for path IDs
import re
_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_@-]{1,128}$')


def _proxy_json(resp):
    """Safely extract JSON from a proxied response, returning a Flask tuple."""
    try:
        return jsonify(resp.json()), resp.status_code
    except (ValueError, requests.exceptions.JSONDecodeError):
        logger.warning("MiroFish returned non-JSON (status %d): %s", resp.status_code, resp.text[:200])
        return jsonify({'error': 'Invalid response from AI analysis service'}), 502


def _mirofish_headers():
    """Forward OpenAI OAuth access token to AI analysis service."""
    headers = {}
    token = session.get('access_token')
    if isinstance(token, str) and token.strip() and all(c >= ' ' and c <= '~' for c in token):
        headers['Authorization'] = f'Bearer {token}'
        headers['X-OpenAI-Access-Token'] = token
    elif token is not None:
        logger.warning("Ignoring invalid access_token type in session: %s", type(token).__name__)
    return headers


def _transform_youtube_to_document(channel_handle):
    """Transform YouTube crawler data into a Markdown document for AI analysis."""
    from .analysis import _transform_youtube_to_document as _impl
    return _impl(channel_handle)


def _transform_dcinside_to_document(gallery_id):
    """Transform DCInside crawler data into a Markdown document for AI analysis."""
    from .analysis import _transform_dcinside_to_document as _impl
    return _impl(gallery_id)


@analysis_bp.route('/api/analysis/status', methods=['GET'])
@limiter.limit("30 per minute")
def analysis_status():
    """Check AI analysis service availability."""
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
@csrf_protect
@require_analysis_auth
def transform_sns_data():
    """Transform SNS crawled data into a document and send to AI analysis service."""
    data = request.get_json() or {}
    sources = data.get('sources', [])
    project_name = data.get('project_name', f'SNS Analysis - {datetime.now().strftime("%Y-%m-%d")}')
    simulation_requirement = data.get('simulation_requirement',
        'Analyze social media community sentiment, identify key trends, and predict audience reactions')

    if not sources:
        return jsonify({'error': 'No data sources specified'}), 400

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

    files = []
    temp_files = []
    try:
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

        if resp.status_code != 200:
            logger.warning("MiroFish returned %d: %s", resp.status_code, resp.text[:200])
        try:
            result = resp.json()
        except ValueError:
            return jsonify({'error': 'Invalid response from AI analysis service'}), 502
        return jsonify(result), resp.status_code

    except requests.ConnectionError:
        return jsonify({
            'error': 'AI analysis service not available. Start with: docker-compose --profile analysis up -d'
        }), 503
    except Exception as e:
        logger.error("AI analysis transform failed: %s", e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        for f_tuple in files:
            try:
                f_tuple[1][1].close()
            except Exception:
                pass
        for tmp_path in temp_files:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@analysis_bp.route('/api/analysis/graph/build', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_protect
@require_analysis_auth
def build_analysis_graph():
    """Proxy graph build request to AI analysis service."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/graph/build',
            json=request.get_json(),
            timeout=30,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/graph/task/<task_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_analysis_auth
def get_analysis_task(task_id):
    """Proxy task status query to AI analysis service."""
    if not _SAFE_ID_RE.match(task_id):
        return jsonify({'error': 'Invalid task_id'}), 400
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/task/{task_id}',
            timeout=10,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/graph/data/<graph_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_analysis_auth
def get_analysis_graph_data(graph_id):
    """Proxy graph data query to AI analysis service."""
    if not _SAFE_ID_RE.match(graph_id):
        return jsonify({'error': 'Invalid graph_id'}), 400
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/data/{graph_id}',
            timeout=30,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/report/generate', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_protect
@require_analysis_auth
def generate_analysis_report():
    """Proxy report generation to AI analysis service."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/report/generate',
            json=request.get_json(),
            timeout=30,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/report/<report_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_analysis_auth
def get_analysis_report(report_id):
    """Proxy report retrieval from AI analysis service."""
    if not _SAFE_ID_RE.match(report_id):
        return jsonify({'error': 'Invalid report_id'}), 400
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/report/{report_id}',
            timeout=30,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/report/chat', methods=['POST'])
@limiter.limit("20 per minute")
@csrf_protect
@require_analysis_auth
def chat_with_analysis():
    """Proxy chat with AI analysis ReportAgent."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/report/chat',
            json=request.get_json(),
            timeout=60,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/projects', methods=['GET'])
@limiter.limit("30 per minute")
@require_analysis_auth
def list_analysis_projects():
    """Proxy project list from AI analysis service."""
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/project/list',
            timeout=10,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503
