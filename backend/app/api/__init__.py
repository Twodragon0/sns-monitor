"""
API route modules.
Each module registers its routes on a Blueprint.
"""

from flask import Blueprint

analyze_bp = Blueprint('analyze', __name__)
analysis_bp = Blueprint('analysis', __name__)
auth_bp = Blueprint('auth', __name__)
dashboard_bp = Blueprint('dashboard', __name__)
dcinside_bp = Blueprint('dcinside', __name__)
data_bp = Blueprint('data', __name__)

from . import analyze  # noqa: E402, F401
from . import analysis  # noqa: E402, F401
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
