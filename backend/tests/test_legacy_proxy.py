"""Tests for legacy proxy removal verification.

The legacy API proxy (app/api/legacy.py) has been removed.
Routes that were previously handled by the legacy proxy now return 404
or are handled by dedicated blueprints.
"""

import pytest


class TestLegacyProxyRemoved:
    """Verify legacy proxy no longer exists and routes behave correctly."""

    def test_analyze_url_handled_by_blueprint(self, client):
        """POST /api/analyze/url is handled by analyze_bp, not legacy proxy."""
        resp = client.post('/api/analyze/url', json={'url': ''})
        assert resp.status_code == 400
        assert 'URL is required' in resp.get_json()['error']

    def test_unknown_api_route_returns_404(self, client):
        """Routes not claimed by any blueprint return 404."""
        resp = client.get('/api/some-legacy-route')
        assert resp.status_code == 404

    def test_another_unknown_route_returns_404(self, client):
        """Additional routes not handled by blueprints return 404."""
        resp = client.get('/api/nonexistent/route')
        assert resp.status_code == 404

    def test_dashboard_stats_still_works(self, client):
        """Migrated dashboard route is unaffected by legacy removal."""
        resp = client.get('/api/dashboard/stats')
        assert resp.status_code == 200

    def test_dcinside_galleries_still_works(self, client):
        """Migrated dcinside route is unaffected by legacy removal."""
        resp = client.get('/api/dcinside/galleries')
        assert resp.status_code == 200
