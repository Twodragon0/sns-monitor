"""
CSRF rejection tests for the 9 POST endpoints secured with @csrf_protect.

Verified endpoints:
  1. POST /api/analysis/report/generate
  2. POST /api/analysis/local-summary
  3. POST /api/analysis/report/generate-daily
  4. POST /api/analysis/ai-summary
  5. POST /api/analysis/ai-chat
  6. POST /api/analysis/ai-url-analyze
  7. POST /api/analysis/ai-url-chat
  8. POST /api/auth/logout
  9. POST /api/auth/apikey

Each endpoint is tested for three scenarios:
  A. No Origin header → 403
  B. Wrong/evil Origin → 403
  C. Valid Origin → NOT 403 (CSRF check passes; handler may return other codes)
"""

import pytest
from unittest.mock import patch

VALID_ORIGIN = "http://localhost:3080"
EVIL_ORIGIN = "http://evil.com"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(client, url, origin, body=None):
    """Issue a POST request with an explicit Origin header (or no header)."""
    headers = {}
    if origin is not None:
        headers["Origin"] = origin
    return client.post(url, json=body or {}, headers=headers)


# ---------------------------------------------------------------------------
# Parametrize: (url, minimal_body)
# ---------------------------------------------------------------------------

ENDPOINTS = [
    ("/api/analysis/report/generate",       {}),
    ("/api/analysis/local-summary",         {"sources": [{"type": "youtube", "id": "testchan"}]}),
    ("/api/analysis/report/generate-daily", {}),
    ("/api/analysis/ai-summary",            {}),
    ("/api/analysis/ai-chat",               {"message": "hello"}),
    ("/api/analysis/ai-url-analyze",        {"url": "https://www.youtube.com/watch?v=test"}),
    ("/api/analysis/ai-url-chat",           {"message": "hello", "url": "https://www.youtube.com/watch?v=test"}),
    ("/api/auth/logout",                    {}),
    ("/api/auth/apikey",                    {"provider": "openai", "api_key": "sk-test"}),
]


# ---------------------------------------------------------------------------
# Test class: no Origin header → 403
# ---------------------------------------------------------------------------

class TestCsrfRejectsMissingOrigin:
    """POST without any Origin or Referer header must return 403 from all 9 endpoints."""

    @pytest.mark.parametrize("url,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_no_origin_returns_403(self, app, url, body):
        with app.test_client() as c:
            resp = c.post(url, json=body)
        assert resp.status_code == 403, (
            f"Expected 403 CSRF rejection for {url!r} with no Origin, got {resp.status_code}"
        )

    @pytest.mark.parametrize("url,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_no_origin_error_message(self, app, url, body):
        with app.test_client() as c:
            resp = c.post(url, json=body)
        data = resp.get_json()
        assert data is not None
        assert "Missing Origin header" in data.get("error", ""), (
            f"Expected 'Missing Origin header' in error body for {url!r}, got {data!r}"
        )


# ---------------------------------------------------------------------------
# Test class: wrong/evil Origin → 403
# ---------------------------------------------------------------------------

class TestCsrfRejectsInvalidOrigin:
    """POST with an untrusted Origin header must return 403 from all 9 endpoints."""

    @pytest.mark.parametrize("url,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_evil_origin_returns_403(self, app, url, body):
        with app.test_client() as c:
            resp = c.post(url, json=body, headers={"Origin": EVIL_ORIGIN})
        assert resp.status_code == 403, (
            f"Expected 403 CSRF rejection for {url!r} with evil origin, got {resp.status_code}"
        )

    @pytest.mark.parametrize("url,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_evil_origin_error_message(self, app, url, body):
        with app.test_client() as c:
            resp = c.post(url, json=body, headers={"Origin": EVIL_ORIGIN})
        data = resp.get_json()
        assert data is not None
        error_msg = data.get("error", "")
        assert "Forbidden" in error_msg or "invalid origin" in error_msg, (
            f"Expected forbidden/invalid-origin message for {url!r}, got {data!r}"
        )

    @pytest.mark.parametrize("url,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_subdomain_of_allowed_is_rejected(self, app, url, body):
        # http://sub.localhost:3080 is not the same as http://localhost:3080
        with app.test_client() as c:
            resp = c.post(url, json=body, headers={"Origin": "http://sub.localhost:3080"})
        assert resp.status_code == 403, (
            f"Subdomain of allowed origin should be rejected for {url!r}, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Test class: valid Origin → passes CSRF (status is NOT 403)
# ---------------------------------------------------------------------------

class TestCsrfPassesWithValidOrigin:
    """POST with the allowed Origin must pass the CSRF layer.

    The handler may return any non-403 code (200, 400, 401, 503, …) —
    what we verify is that the request was NOT blocked at the CSRF gate.

    Note: PROPAGATE_EXCEPTIONS is disabled so that handler-level errors
    (e.g. missing local-data directories in CI) become 500 responses
    rather than raised exceptions.  A 500 proves the CSRF gate was
    cleared; only a 403 indicates CSRF rejection.
    """

    @pytest.fixture(autouse=True)
    def _no_propagate(self, app):
        """Disable exception propagation so handler crashes → 500, not raised."""
        app.config["PROPAGATE_EXCEPTIONS"] = False
        yield
        app.config["PROPAGATE_EXCEPTIONS"] = True

    @pytest.mark.parametrize("url,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_valid_origin_not_blocked_by_csrf(self, app, url, body):
        with app.test_client() as c:
            resp = c.post(url, json=body, headers={"Origin": VALID_ORIGIN})
        assert resp.status_code != 403, (
            f"Valid origin should NOT be CSRF-rejected for {url!r}, got 403 unexpectedly"
        )

    @pytest.mark.parametrize("url,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_valid_origin_with_trailing_slash_not_blocked(self, app, url, body):
        # The decorator strips trailing slashes from the Origin value
        with app.test_client() as c:
            resp = c.post(url, json=body, headers={"Origin": VALID_ORIGIN + "/"})
        assert resp.status_code != 403, (
            f"Origin with trailing slash should not be CSRF-rejected for {url!r}, got 403"
        )

    @pytest.mark.parametrize("url,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_valid_referer_without_origin_not_blocked(self, app, url, body):
        # Referer fallback: older browsers may not send Origin but will send Referer
        with app.test_client() as c:
            resp = c.post(
                url, json=body,
                headers={"Referer": f"{VALID_ORIGIN}/some/page"},
            )
        assert resp.status_code != 403, (
            f"Valid Referer (no Origin) should not be CSRF-rejected for {url!r}, got 403"
        )


# ---------------------------------------------------------------------------
# Test class: Bearer token bypasses CSRF check entirely
# ---------------------------------------------------------------------------

class TestCsrfBearerBypassOnEndpoints:
    """A Bearer Authorization token skips the CSRF origin check on all 9 endpoints."""

    @pytest.fixture(autouse=True)
    def _no_propagate(self, app):
        """Disable exception propagation so handler crashes → 500, not raised."""
        app.config["PROPAGATE_EXCEPTIONS"] = False
        yield
        app.config["PROPAGATE_EXCEPTIONS"] = True

    @pytest.mark.parametrize("url,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_bearer_with_no_origin_not_blocked(self, app, url, body):
        with app.test_client() as c:
            resp = c.post(
                url, json=body,
                headers={"Authorization": "Bearer some-valid-jwt-token"},
                # Deliberately omit Origin
            )
        assert resp.status_code != 403, (
            f"Bearer token should bypass CSRF for {url!r}, got 403"
        )

    @pytest.mark.parametrize("url,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_bearer_with_evil_origin_not_blocked(self, app, url, body):
        # Stateless API tokens are not susceptible to CSRF
        with app.test_client() as c:
            resp = c.post(
                url, json=body,
                headers={
                    "Authorization": "Bearer some-valid-jwt-token",
                    "Origin": EVIL_ORIGIN,
                },
            )
        assert resp.status_code != 403, (
            f"Bearer token should bypass CSRF regardless of origin for {url!r}, got 403"
        )
