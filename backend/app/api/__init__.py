"""
API route modules.
Each module registers its routes on a Blueprint.
"""

import os
from functools import wraps
from flask import Blueprint, request, jsonify

analyze_bp = Blueprint('analyze', __name__)
analysis_bp = Blueprint('analysis', __name__)
auth_bp = Blueprint('auth', __name__)
dashboard_bp = Blueprint('dashboard', __name__)
dcinside_bp = Blueprint('dcinside', __name__)
data_bp = Blueprint('data', __name__)

def _get_allowed_origins():
    """Return the set of trusted origins from environment config."""
    raw = (
        os.environ.get("CORS_ORIGINS", "").strip()
        or os.environ.get("FRONTEND_URL", "").strip()
    )
    if raw:
        origins = {o.strip().rstrip("/") for o in raw.split(",") if o.strip()}
    else:
        origins = {"http://localhost:3080", "http://localhost:3000"}
    return origins


def csrf_protect(f):
    """Decorator that validates the Origin (or Referer) header on mutating requests.

    This is the appropriate CSRF defence for a REST API with SameSite=Lax cookies:
    browsers attach cookies on cross-site navigations but include an Origin header
    that allows the server to reject requests from untrusted origins.

    Rules:
    - Only applied to non-safe methods (POST, PUT, PATCH, DELETE).
    - Requests without an Origin or Referer header are rejected (explicit is safer).
    - The Origin (or extracted Referer scheme+host) must match an allowed origin.
    - Requests with a valid Bearer token in Authorization skip the check
      (they are stateless and do not rely on session cookies).
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return f(*args, **kwargs)

        # Bearer-authenticated requests are stateless – skip cookie-CSRF concern.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if len(token) >= 10:
                return f(*args, **kwargs)

        origin = request.headers.get("Origin", "").rstrip("/")
        if not origin:
            # Fall back to Referer (older Safari, some proxies)
            referer = request.headers.get("Referer", "")
            if referer:
                from urllib.parse import urlparse as _up
                p = _up(referer)
                origin = f"{p.scheme}://{p.netloc}".rstrip("/")

        if not origin:
            return jsonify({"error": "Missing Origin header"}), 403

        allowed = _get_allowed_origins()
        if origin not in allowed:
            return jsonify({"error": "Forbidden: invalid origin"}), 403

        return f(*args, **kwargs)
    return wrapper


from . import analyze  # noqa: E402, F401
from . import analysis  # noqa: E402, F401
from . import analysis_mirofish  # noqa: E402, F401
from . import auth      # noqa: E402, F401
from . import dashboard  # noqa: E402, F401
from . import dcinside   # noqa: E402, F401
from . import data       # noqa: E402, F401
from .vuddy import vuddy_bp  # noqa: E402, F401
from .members import members_bp  # noqa: E402, F401


def register_blueprints(app):
    """Register all API blueprints with the Flask app."""
    app.register_blueprint(analyze_bp)
    app.register_blueprint(members_bp)   # unified group members — before dashboard
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(dcinside_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(vuddy_bp)
