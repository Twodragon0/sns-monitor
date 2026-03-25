"""
Shared helpers for legacy api_handlers bridge modules.
"""

import logging

from flask import request, Response

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
