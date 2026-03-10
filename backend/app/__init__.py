"""
SNS Monitor Backend - Flask Application Factory
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # JSON encoding for Korean characters
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False

    # Setup logging
    logger = setup_logger('sns-monitor')

    # CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Health check
    @app.route('/health', methods=['GET'])
    def health():
        from .services.redis_client import get_redis
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
            'local_mode': Config.LOCAL_MODE
        })

    # Register API blueprints
    from .api import register_blueprints
    register_blueprints(app)

    logger.info("SNS Monitor Backend started (local_mode=%s)", Config.LOCAL_MODE)
    return app
