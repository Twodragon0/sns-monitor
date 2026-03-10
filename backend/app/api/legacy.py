"""
Legacy API bridge.
Proxies /api/* requests to api_handlers.lambda_handler for backward compatibility.
This allows the 3500-line monolith to work without modification
while new routes are added as proper Blueprint modules.
"""

import logging
from flask import request, jsonify, Response

from . import legacy_bp

logger = logging.getLogger(__name__)

# Lazy-loaded legacy handler module
_api_handlers = None


def _get_handlers():
    global _api_handlers
    if _api_handlers is None:
        import api_handlers
        _api_handlers = api_handlers
    return _api_handlers


@legacy_bp.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_proxy(path):
    """Proxy requests to legacy lambda_handler."""
    # Skip routes handled by other blueprints
    if path in ('analyze/url', 'platforms'):
        return '', 404

    event = {
        'httpMethod': request.method,
        'path': f'/{path}',
        'queryStringParameters': dict(request.args) if request.args else None,
        'body': request.get_data(as_text=True) or None,
        'headers': dict(request.headers)
    }

    try:
        handlers = _get_handlers()
        result = handlers.lambda_handler(event, {})
        status_code = result.get('statusCode', 200)
        body = result.get('body', '{}')
        headers = result.get('headers', {})

        response = Response(body, status=status_code, content_type='application/json')
        for key, value in headers.items():
            if key.lower() != 'content-type':
                response.headers[key] = value
        return response
    except Exception as e:
        logger.error("API error on /%s: %s", path, e, exc_info=True)
        return jsonify({'error': str(e)}), 500
