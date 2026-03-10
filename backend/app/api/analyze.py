"""
URL analysis API routes.
POST /api/analyze/url - Analyze content from any supported platform URL
GET  /api/platforms   - List supported platforms
"""

import logging
from flask import request, jsonify

from . import analyze_bp
from ..config import Config

logger = logging.getLogger(__name__)

# Lazy-loaded platform analyzer
_platform_analyzer = None


def _get_analyzer():
    global _platform_analyzer
    if _platform_analyzer is None:
        from ..services.platform_analyzer import PlatformAnalyzer
        _platform_analyzer = PlatformAnalyzer(
            data_dir=Config.LOCAL_DATA_DIR
        )
    return _platform_analyzer


@analyze_bp.route('/api/analyze/url', methods=['POST'])
def analyze_url():
    """Analyze content from any supported platform URL."""
    data = request.get_json(silent=True)
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required', 'usage': {'url': 'https://...'}}), 400

    url = data['url'].strip()
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    try:
        result = _get_analyzer().analyze(url)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error("Analysis error for %s: %s", url, e, exc_info=True)
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


@analyze_bp.route('/api/platforms', methods=['GET'])
def list_platforms():
    """List supported platforms with example URLs."""
    return jsonify({
        'platforms': _get_analyzer().list_platforms()
    })
