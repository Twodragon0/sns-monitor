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
    app.config["SECRET_KEY"] = config_class.SECRET_KEY

    # JSON encoding for Korean characters
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False

    # Setup logging
    logger = setup_logger('sns-monitor')

    # CORS (allow credentials for session when frontend origin is set)
    _cors_origins = os.environ.get("CORS_ORIGINS", "").strip() or os.environ.get("FRONTEND_URL", "").strip()
    if _cors_origins:
        _origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
        CORS(app, resources={r"/api/*": {"origins": _origins, "supports_credentials": True}})
    else:
        CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3080", "http://localhost:3000"]}})

    # Health check (frontend calls /api/health via nginx proxy)
    def _health():
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

    @app.route('/health', methods=['GET'])
    def health():
        return _health()

    @app.route('/api/health', methods=['GET'])
    def api_health():
        return _health()

    # Register API blueprints
    from .api import register_blueprints
    register_blueprints(app)

    logger.info("SNS Monitor Backend started (local_mode=%s)", Config.LOCAL_MODE)
    return app
