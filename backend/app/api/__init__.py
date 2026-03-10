"""
API route modules.
Each module registers its routes on a Blueprint.
"""

from flask import Blueprint

analyze_bp = Blueprint('analyze', __name__)
legacy_bp = Blueprint('legacy', __name__)

from . import analyze  # noqa: E402, F401
from . import legacy   # noqa: E402, F401


def register_blueprints(app):
    """Register all API blueprints with the Flask app."""
    app.register_blueprint(analyze_bp)
    app.register_blueprint(legacy_bp)
