"""
SNS Monitor Backend - Flask Application Factory
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .config import Config
from .utils.logger import setup_logger, get_logger

# Module-level limiter so blueprints can import and decorate routes
def _build_redis_uri():
    if not Config.REDIS_HOST:
        return "memory://"
    if Config.REDIS_PASSWORD:
        return f"redis://:{Config.REDIS_PASSWORD}@{Config.REDIS_HOST}:{Config.REDIS_PORT}"
    return f"redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_build_redis_uri(),
    default_limits=["200 per minute"],
)


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

    # Rate limiter
    limiter.init_app(app)

    # CORS (allow credentials for session when frontend origin is set)
    _cors_origins = os.environ.get("CORS_ORIGINS", "").strip() or os.environ.get("FRONTEND_URL", "").strip()
    if _cors_origins:
        _origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
        CORS(app, resources={r"/api/*": {"origins": _origins, "supports_credentials": True}})
    else:
        _fallback = ["http://localhost:3080", "http://localhost:3000"]
        if not app.debug:
            logger.warning("CORS_ORIGINS not set — falling back to localhost origins")
        CORS(app, resources={r"/api/*": {"origins": _fallback}})

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
