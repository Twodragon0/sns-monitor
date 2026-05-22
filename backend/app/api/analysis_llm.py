"""
LLM-powered analysis routes (status/summary/chat for sources and URL results).

Split from analysis.py for feature-domain separation. Sentiment/report routes
remain in analysis.py; MiroFish proxies stay in analysis_mirofish.py.
"""

import logging

from flask import request, jsonify, session

from . import analysis_bp, csrf_protect
from .analysis import (
    _build_document_from_url_result,
    _build_documents_from_sources,
    _validate_chat_history,
)
from .auth import require_analysis_auth
from .. import limiter

logger = logging.getLogger(__name__)


def _session_llm_kwargs():
    """Extract LLM credentials from Flask session."""
    return {
        'oauth_token': session.get('access_token'),
        'token_provider': session.get('token_provider'),
        'session_api_key': session.get('session_api_key'),
        'session_api_provider': session.get('session_api_provider'),
    }


@analysis_bp.route('/api/analysis/llm/status', methods=['GET'])
@limiter.limit("30 per minute")
def llm_status():
    """Check local LLM availability (Claude / OpenAI / OAuth)."""
    from ..services.llm_analyzer import get_llm_status
    status = get_llm_status(**_session_llm_kwargs())
    return jsonify(status)


@analysis_bp.route('/api/analysis/ai-summary', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_protect
@require_analysis_auth
def ai_summary():
    """
    AI-powered analysis using local LLM (Claude or ChatGPT).
    Works standalone — calls LLM APIs directly.
    """
    from ..services.llm_analyzer import analyze_with_llm, get_available_provider

    provider = get_available_provider(**_session_llm_kwargs())
    if not provider:
        return jsonify({
            'error': 'LLM 인증이 필요합니다. Anthropic OAuth 로그인 또는 API Key를 입력하세요.'
        }), 503

    data = request.get_json() or {}
    sources_list = data.get('sources', [])
    question = data.get('question', '')

    if not sources_list:
        return jsonify({'error': 'No data sources specified'}), 400

    documents = _build_documents_from_sources(sources_list)
    if documents is None:
        return jsonify({'error': 'Invalid source id'}), 400
    if not documents:
        return jsonify({'error': 'No data found for specified sources'}), 404

    full_document = '\n\n---\n\n'.join(documents)
    result = analyze_with_llm(full_document, question if question else None, **_session_llm_kwargs())

    if 'error' in result and not result.get('success'):
        return jsonify(result), 500

    return jsonify(result)


@analysis_bp.route('/api/analysis/ai-chat', methods=['POST'])
@limiter.limit("20 per minute")
@csrf_protect
@require_analysis_auth
def ai_chat():
    """Chat with local LLM about SNS data."""
    from ..services.llm_analyzer import chat_with_llm, get_available_provider

    provider = get_available_provider(**_session_llm_kwargs())
    if not provider:
        return jsonify({'error': 'LLM 인증이 필요합니다. OAuth 로그인 또는 API Key를 입력하세요.'}), 503

    data = request.get_json() or {}
    sources_list = data.get('sources', [])
    message = (data.get('message') or '').strip()

    chat_history = _validate_chat_history(data)
    if chat_history is None:
        return jsonify({'error': 'Invalid chat_history format'}), 400

    if not message:
        return jsonify({'error': 'Message is required'}), 400
    if len(message) > 5000:
        return jsonify({'error': 'Message exceeds maximum length of 5000 characters'}), 400
    if not sources_list:
        return jsonify({'error': 'No data sources specified'}), 400

    documents = _build_documents_from_sources(sources_list)
    if documents is None:
        return jsonify({'error': 'Invalid source id'}), 400
    if not documents:
        return jsonify({'error': 'No data found for specified sources'}), 404

    full_document = '\n\n---\n\n'.join(documents)
    result = chat_with_llm(full_document, message, chat_history, **_session_llm_kwargs())

    if 'error' in result and not result.get('success'):
        return jsonify(result), 500

    return jsonify(result)


@analysis_bp.route('/api/analysis/ai-url-analyze', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_protect
@require_analysis_auth
def ai_url_analyze():
    """
    AI analysis of URL analyzer results (direct pass-through from URLAnalyzer).
    """
    from ..services.llm_analyzer import analyze_with_llm, get_available_provider

    provider = get_available_provider(**_session_llm_kwargs())
    if not provider:
        return jsonify({
            'error': 'No LLM available. Set OPENAI_API_KEY or ANTHROPIC_API_KEY, or login with OAuth.'
        }), 503

    data = request.get_json() or {}
    url_result = data.get('result')
    question = data.get('question', '')

    if not url_result:
        return jsonify({'error': 'Analysis result is required'}), 400

    document = _build_document_from_url_result(url_result)
    result = analyze_with_llm(document, question if question else None, **_session_llm_kwargs())

    if 'error' in result and not result.get('success'):
        return jsonify(result), 500

    return jsonify(result)


@analysis_bp.route('/api/analysis/ai-url-chat', methods=['POST'])
@limiter.limit("20 per minute")
@csrf_protect
@require_analysis_auth
def ai_url_chat():
    """Chat about URL analysis results with LLM."""
    from ..services.llm_analyzer import chat_with_llm, get_available_provider

    provider = get_available_provider(**_session_llm_kwargs())
    if not provider:
        return jsonify({'error': 'No LLM available'}), 503

    data = request.get_json() or {}
    url_result = data.get('result')
    message = (data.get('message') or '').strip()

    chat_history = _validate_chat_history(data)
    if chat_history is None:
        return jsonify({'error': 'Invalid chat_history format'}), 400

    if not message:
        return jsonify({'error': 'Message is required'}), 400
    if len(message) > 5000:
        return jsonify({'error': 'Message exceeds maximum length of 5000 characters'}), 400
    if not url_result:
        return jsonify({'error': 'Analysis result is required'}), 400

    document = _build_document_from_url_result(url_result, compact=True)
    result = chat_with_llm(document, message, chat_history, **_session_llm_kwargs())

    if 'error' in result and not result.get('success'):
        return jsonify(result), 500

    return jsonify(result)
