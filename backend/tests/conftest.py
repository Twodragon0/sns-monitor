"""Shared test fixtures for Flask app tests."""

import os
import sys
import pytest

# Ensure tests can import from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Override Redis host BEFORE importing the app so limiter uses memory://
os.environ['REDIS_HOST'] = ''
os.environ['REDIS_PASSWORD'] = ''


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
    """Flask test client."""
    with app.test_client() as c:
        yield c
