"""
SNS Monitor Backend - Flask Application Factory
"""

import logging
import os
import time
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .config import Config
from .utils.logger import setup_logger, get_logger

_init_logger = logging.getLogger(__name__)
_request_logger = logging.getLogger(__name__ + ".requests")

# Record the time the module was first imported (proxy for process start time)
_APP_START_TIME = time.time()

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

    # Request logging middleware (only for /api/* routes)
    @app.before_request
    def _before_request():
        if request.path.startswith('/api/'):
            g._req_start = time.time()

    @app.after_request
    def _after_request(response):
        if request.path.startswith('/api/'):
            elapsed_ms = int((time.time() - getattr(g, '_req_start', time.time())) * 1000)
            _request_logger.info(
                "%s %s %s %dms",
                request.method,
                request.path,
                response.status_code,
                elapsed_ms,
            )
        return response

    # Health check (frontend calls /api/health via nginx proxy)
    def _health():
        from .services.redis_client import get_redis

        # Redis connectivity
        redis_status = "disconnected"
        try:
            r = get_redis()
            if r and r.ping():
                redis_status = "connected"
        except Exception as e:
            _init_logger.debug("Redis health check failed: %s", e)

        # local-data directory accessibility
        data_dir_status = "missing"
        try:
            if os.path.isdir(Config.LOCAL_DATA_DIR) and os.access(Config.LOCAL_DATA_DIR, os.R_OK):
                data_dir_status = "accessible"
        except Exception as e:
            _init_logger.debug("Data dir health check failed: %s", e)

        uptime = int(time.time() - _APP_START_TIME)
        overall = "ok" if redis_status == "connected" and data_dir_status == "accessible" else "degraded"

        return jsonify({
            'status': overall,
            'redis': redis_status,
            'data_dir': data_dir_status,
            'uptime_seconds': uptime,
            'local_mode': Config.LOCAL_MODE,
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
