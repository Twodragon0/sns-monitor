"""
Shared helpers for legacy api_handlers bridge modules.
"""

import functools
import logging

from flask import jsonify, request, Response

logger = logging.getLogger(__name__)

# Lazy-loaded legacy handler module
_api_handlers = None


def get_handlers():
    """Lazy-import api_handlers to avoid circular imports."""
    global _api_handlers
    if _api_handlers is None:
        import api_handlers
        _api_handlers = api_handlers
    return _api_handlers


def legacy_response(result):
    """Convert legacy lambda_handler dict to Flask Response."""
    status = result.get('statusCode', 200)
    body = result.get('body', '{}')
    return Response(body, status=status, content_type='application/json')


def build_event():
    """Build a legacy event dict from the current Flask request."""
    return {
        'httpMethod': request.method,
        'path': request.path,
        'queryStringParameters': dict(request.args) if request.args else None,
        'body': request.get_data(as_text=True) or None,
        'headers': dict(request.headers),
    }


def safe_legacy_call(fn):
    """Decorator that wraps a legacy handler call with error handling."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.error("Legacy handler error on %s: %s", request.path, e, exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500
    return wrapper
