"""Shared test fixtures for Flask app tests."""

import os
import sys
import pytest

# Ensure tests can import from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Override Redis host BEFORE importing the app so limiter uses memory://
os.environ['REDIS_HOST'] = ''
os.environ['REDIS_PASSWORD'] = ''

# Set an allowed origin for CSRF protection so test POST requests pass the check.
_TEST_ORIGIN = 'http://localhost:3080'
os.environ.setdefault('CORS_ORIGINS', _TEST_ORIGIN)


@pytest.fixture
def app():
    """Create Flask app configured for testing."""
    from app import create_app
    application = create_app()
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret-key'
    return application


@pytest.fixture
def client(app):
    """Flask test client with a default Origin header so CSRF checks pass.

    Real browsers always include the Origin header on cross-origin POST requests.
    Setting it here reflects that behaviour without modifying every individual test.
    """
    import app.api.dashboard as _dash
    _dash._stats_cache = {'data': None, 'expires': 0}
    with app.test_client() as c:
        # Inject Origin into every request automatically via the environ_base.
        c.environ_base['HTTP_ORIGIN'] = _TEST_ORIGIN
        yield c
