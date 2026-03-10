"""SNS Monitor API - Flask Application"""
import json
import os
import logging

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Import the existing lambda handler
import lambda_function

# Lazy import for platform analyzer
_platform_analyzer = None

def get_platform_analyzer():
    global _platform_analyzer
    if _platform_analyzer is None:
        from platform_analyzer import PlatformAnalyzer
        _platform_analyzer = PlatformAnalyzer(
            data_dir=os.environ.get('LOCAL_DATA_DIR', '/app/local-data')
        )
    return _platform_analyzer

# Redis connection (optional, graceful fallback)
_redis_client = None

def get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.Redis(
                host=os.environ.get('REDIS_HOST', 'redis'),
                port=int(os.environ.get('REDIS_PORT', 6379)),
                decode_responses=True,
                socket_connect_timeout=2
            )
            _redis_client.ping()
        except Exception:
            logger.warning("Redis not available, running without cache")
            _redis_client = None
    return _redis_client


@app.route('/health', methods=['GET'])
def health():
    redis_ok = False
    try:
        r = get_redis()
        if r:
            redis_ok = r.ping()
    except Exception:
        pass
    return jsonify({
        'status': 'healthy',
        'redis': redis_ok,
        'local_mode': os.environ.get('LOCAL_MODE', 'true') == 'true'
    })


@app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_proxy(path):
    """Proxy requests to lambda_handler for backward compatibility"""
    # Handle platform analysis separately
    if path == 'analyze/url':
        return handle_analyze_url()
    if path == 'platforms':
        return handle_list_platforms()

    event = {
        'httpMethod': request.method,
        'path': f'/{path}',
        'queryStringParameters': dict(request.args) if request.args else None,
        'body': request.get_data(as_text=True) or None,
        'headers': dict(request.headers)
    }

    try:
        result = lambda_function.lambda_handler(event, {})
        status_code = result.get('statusCode', 200)
        body = result.get('body', '{}')
        headers = result.get('headers', {})

        response = Response(body, status=status_code, content_type='application/json')
        for key, value in headers.items():
            if key.lower() != 'content-type':
                response.headers[key] = value
        return response
    except Exception as e:
        logger.error(f"API error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def handle_analyze_url():
    """POST /api/analyze/url - Analyze content from any supported platform URL"""
    if request.method != 'POST':
        return jsonify({'error': 'Method not allowed'}), 405

    data = request.get_json(silent=True)
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required', 'usage': {'url': 'https://...'}}), 400

    url = data['url'].strip()
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    try:
        analyzer = get_platform_analyzer()
        result = analyzer.analyze(url)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Analysis error for {url}: {e}", exc_info=True)
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


def handle_list_platforms():
    """GET /api/platforms - List supported platforms"""
    analyzer = get_platform_analyzer()
    return jsonify({
        'platforms': analyzer.list_platforms()
    })


if __name__ == '__main__':
    port = int(os.environ.get('API_PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
