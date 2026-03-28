"""
Comprehensive tests for the csrf_protect decorator and _get_allowed_origins helper.

Tests use a minimal Flask test app with a dedicated /test/csrf-target route so that
assertions are isolated from the platform analyzer logic inside /api/analyze/url.
The existing /api/analyze/url endpoint (which carries @csrf_protect) is also exercised
in a handful of integration-style cases to confirm decorator wiring is live in
production routes.
"""

import os
import importlib
import pytest
from flask import Flask, jsonify


# ---------------------------------------------------------------------------
# Minimal app fixture – lets us mount csrf_protect without the full SNS stack
# ---------------------------------------------------------------------------

@pytest.fixture()
def csrf_app():
    """Return a minimal Flask app with a single POST-only route protected by
    csrf_protect.  No Redis, no limiter, no external services."""
    # Import the decorator from the real module so we exercise the actual code.
    from app.api import csrf_protect

    mini = Flask(__name__)
    mini.config["TESTING"] = True

    @mini.route("/test/csrf-target", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    @csrf_protect
    def csrf_target():
        return jsonify({"ok": True}), 200

    return mini


@pytest.fixture()
def csrf_client(csrf_app):
    """Test client for the minimal CSRF app with *no* default Origin header."""
    with csrf_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# 1. POST without Origin or Referer → 403
# ---------------------------------------------------------------------------

class TestMissingOriginAndReferer:
    def test_post_no_headers_returns_403(self, csrf_client):
        resp = csrf_client.post("/test/csrf-target", json={})
        assert resp.status_code == 403

    def test_error_body_describes_problem(self, csrf_client):
        resp = csrf_client.post("/test/csrf-target", json={})
        data = resp.get_json()
        assert data is not None
        assert "Missing Origin header" in data.get("error", "")

    def test_put_no_headers_returns_403(self, csrf_client):
        resp = csrf_client.put("/test/csrf-target", json={})
        assert resp.status_code == 403

    def test_patch_no_headers_returns_403(self, csrf_client):
        resp = csrf_client.patch("/test/csrf-target", json={})
        assert resp.status_code == 403

    def test_delete_no_headers_returns_403(self, csrf_client):
        resp = csrf_client.delete("/test/csrf-target")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 2. POST with invalid (untrusted) Origin → 403
# ---------------------------------------------------------------------------

class TestInvalidOrigin:
    def test_unknown_origin_returns_403(self, csrf_client):
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.status_code == 403

    def test_error_body_says_forbidden(self, csrf_client):
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Origin": "http://evil.example.com"},
        )
        data = resp.get_json()
        assert "Forbidden" in data.get("error", "") or "invalid origin" in data.get("error", "")

    def test_subdomain_of_allowed_is_rejected(self, csrf_client):
        # http://sub.localhost:3080 is NOT http://localhost:3080
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Origin": "http://sub.localhost:3080"},
        )
        assert resp.status_code == 403

    def test_trailing_slash_stripped_then_still_invalid(self, csrf_client):
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Origin": "http://attacker.com/"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. POST with valid Origin → 200
# ---------------------------------------------------------------------------

class TestValidOrigin:
    def test_allowed_origin_passes(self, csrf_client):
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Origin": "http://localhost:3080"},
        )
        assert resp.status_code == 200

    def test_response_body_is_ok(self, csrf_client):
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Origin": "http://localhost:3080"},
        )
        assert resp.get_json() == {"ok": True}

    def test_origin_with_trailing_slash_is_stripped_and_accepted(self, csrf_client):
        # The decorator calls .rstrip("/") on the incoming Origin value.
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Origin": "http://localhost:3080/"},
        )
        assert resp.status_code == 200

    def test_second_default_origin_passes(self, csrf_client):
        # http://localhost:3000 is also in the default allowed set when no
        # CORS_ORIGINS env var is present.  Force a fresh import without the var.
        import app.api as api_module
        original_cors = os.environ.pop("CORS_ORIGINS", None)
        original_frontend = os.environ.pop("FRONTEND_URL", None)
        try:
            # Re-evaluate _get_allowed_origins without env var so defaults kick in.
            allowed = api_module._get_allowed_origins()
            assert "http://localhost:3000" in allowed
            assert "http://localhost:3080" in allowed
        finally:
            if original_cors is not None:
                os.environ["CORS_ORIGINS"] = original_cors
            if original_frontend is not None:
                os.environ["FRONTEND_URL"] = original_frontend


# ---------------------------------------------------------------------------
# 4. POST with valid Referer (no Origin header) → 200
# ---------------------------------------------------------------------------

class TestRefererFallback:
    def test_referer_without_origin_passes(self, csrf_client):
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Referer": "http://localhost:3080/some/page"},
        )
        assert resp.status_code == 200

    def test_referer_extracts_scheme_and_host_correctly(self, csrf_client):
        # Path and query string in Referer must not leak into the origin string.
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Referer": "http://localhost:3080/deep/path?q=1"},
        )
        assert resp.status_code == 200

    def test_invalid_referer_returns_403(self, csrf_client):
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Referer": "http://evil.example.com/page"},
        )
        assert resp.status_code == 403

    def test_origin_takes_precedence_over_referer(self, csrf_client):
        # Valid Origin but invalid Referer → should pass because Origin wins.
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={
                "Origin": "http://localhost:3080",
                "Referer": "http://evil.example.com/page",
            },
        )
        assert resp.status_code == 200

    def test_invalid_origin_with_valid_referer_returns_403(self, csrf_client):
        # Origin is always checked first; valid Referer cannot rescue a bad Origin.
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={
                "Origin": "http://evil.example.com",
                "Referer": "http://localhost:3080/page",
            },
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 5. POST with Bearer Authorization → bypasses CSRF check entirely
# ---------------------------------------------------------------------------

class TestBearerBypass:
    def test_bearer_token_bypasses_csrf(self, csrf_client):
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Authorization": "Bearer some-jwt-token"},
            # Deliberately no Origin/Referer – should still succeed.
        )
        assert resp.status_code == 200

    def test_bearer_with_invalid_origin_still_passes(self, csrf_client):
        # Stateless API tokens are not susceptible to CSRF; origin is irrelevant.
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={
                "Authorization": "Bearer token-xyz",
                "Origin": "http://evil.example.com",
            },
        )
        assert resp.status_code == 200

    def test_basic_auth_does_not_bypass_csrf(self, csrf_client):
        # Only "Bearer " prefix triggers the bypass; Basic auth must still pass origin.
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 403

    def test_bearer_lowercase_does_not_bypass(self, csrf_client):
        # The check is case-sensitive per the HTTP spec ("Bearer " with capital B).
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Authorization": "bearer some-token"},
        )
        assert resp.status_code == 403

    def test_empty_bearer_does_not_bypass(self, csrf_client):
        # "Bearer" with no trailing space or token must not skip the check.
        resp = csrf_client.post(
            "/test/csrf-target",
            json={},
            headers={"Authorization": "Bearer"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 6. Safe (read-only) HTTP methods → CSRF check is skipped entirely
# ---------------------------------------------------------------------------

class TestSafeMethodsPassThrough:
    def test_get_passes_without_origin(self, csrf_client):
        resp = csrf_client.get("/test/csrf-target")
        assert resp.status_code == 200

    def test_get_passes_with_bad_origin(self, csrf_client):
        resp = csrf_client.get(
            "/test/csrf-target",
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.status_code == 200

    def test_get_passes_with_no_headers_at_all(self, csrf_client):
        resp = csrf_client.get("/test/csrf-target")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 7. Custom CORS_ORIGINS env var is respected
# ---------------------------------------------------------------------------

class TestCustomCorsOriginsEnvVar:
    def test_custom_single_origin_is_allowed(self, csrf_app):
        """When CORS_ORIGINS is set to a custom value, that origin is accepted."""
        original = os.environ.get("CORS_ORIGINS")
        os.environ["CORS_ORIGINS"] = "https://my-app.example.com"
        try:
            with csrf_app.test_client() as c:
                resp = c.post(
                    "/test/csrf-target",
                    json={},
                    headers={"Origin": "https://my-app.example.com"},
                )
            assert resp.status_code == 200
        finally:
            if original is None:
                del os.environ["CORS_ORIGINS"]
            else:
                os.environ["CORS_ORIGINS"] = original

    def test_default_origins_rejected_when_custom_set(self, csrf_app):
        """Default localhost origins must NOT be accepted if custom CORS_ORIGINS is set."""
        original = os.environ.get("CORS_ORIGINS")
        os.environ["CORS_ORIGINS"] = "https://my-app.example.com"
        try:
            with csrf_app.test_client() as c:
                resp = c.post(
                    "/test/csrf-target",
                    json={},
                    headers={"Origin": "http://localhost:3080"},
                )
            assert resp.status_code == 403
        finally:
            if original is None:
                del os.environ["CORS_ORIGINS"]
            else:
                os.environ["CORS_ORIGINS"] = original

    def test_frontend_url_fallback(self, csrf_app):
        """FRONTEND_URL is used when CORS_ORIGINS is absent."""
        cors_original = os.environ.pop("CORS_ORIGINS", None)
        frontend_original = os.environ.get("FRONTEND_URL")
        os.environ["FRONTEND_URL"] = "https://frontend.example.com"
        try:
            import app.api as api_module
            allowed = api_module._get_allowed_origins()
            assert "https://frontend.example.com" in allowed
        finally:
            if cors_original is not None:
                os.environ["CORS_ORIGINS"] = cors_original
            if frontend_original is None:
                os.environ.pop("FRONTEND_URL", None)
            else:
                os.environ["FRONTEND_URL"] = frontend_original

    def test_empty_cors_origins_falls_back_to_defaults(self):
        """An empty CORS_ORIGINS string falls back to the hardcoded defaults."""
        original_cors = os.environ.get("CORS_ORIGINS")
        original_frontend = os.environ.pop("FRONTEND_URL", None)
        os.environ["CORS_ORIGINS"] = "   "  # whitespace-only counts as empty
        try:
            import app.api as api_module
            allowed = api_module._get_allowed_origins()
            assert "http://localhost:3080" in allowed
            assert "http://localhost:3000" in allowed
        finally:
            if original_cors is None:
                os.environ.pop("CORS_ORIGINS", None)
            else:
                os.environ["CORS_ORIGINS"] = original_cors
            if original_frontend is not None:
                os.environ["FRONTEND_URL"] = original_frontend


# ---------------------------------------------------------------------------
# 8. Multiple origins in CORS_ORIGINS (comma-separated)
# ---------------------------------------------------------------------------

class TestMultipleOriginsInEnvVar:
    def test_all_listed_origins_are_accepted(self, csrf_app):
        """Every origin in the comma-separated list should be individually allowed."""
        original = os.environ.get("CORS_ORIGINS")
        os.environ["CORS_ORIGINS"] = (
            "https://app.example.com, https://admin.example.com, http://localhost:3000"
        )
        try:
            for origin in [
                "https://app.example.com",
                "https://admin.example.com",
                "http://localhost:3000",
            ]:
                with csrf_app.test_client() as c:
                    resp = c.post(
                        "/test/csrf-target",
                        json={},
                        headers={"Origin": origin},
                    )
                assert resp.status_code == 200, f"Expected 200 for origin {origin!r}"
        finally:
            if original is None:
                del os.environ["CORS_ORIGINS"]
            else:
                os.environ["CORS_ORIGINS"] = original

    def test_origin_not_in_list_is_rejected(self, csrf_app):
        """An origin absent from the list must still be blocked."""
        original = os.environ.get("CORS_ORIGINS")
        os.environ["CORS_ORIGINS"] = (
            "https://app.example.com, https://admin.example.com"
        )
        try:
            with csrf_app.test_client() as c:
                resp = c.post(
                    "/test/csrf-target",
                    json={},
                    headers={"Origin": "https://intruder.example.com"},
                )
            assert resp.status_code == 403
        finally:
            if original is None:
                del os.environ["CORS_ORIGINS"]
            else:
                os.environ["CORS_ORIGINS"] = original

    def test_trailing_slash_stripped_from_env_origins(self):
        """Origins with trailing slashes in env var are normalised correctly."""
        original = os.environ.get("CORS_ORIGINS")
        os.environ["CORS_ORIGINS"] = "https://app.example.com/"
        try:
            import app.api as api_module
            allowed = api_module._get_allowed_origins()
            # Trailing slash must have been stripped.
            assert "https://app.example.com" in allowed
            assert "https://app.example.com/" not in allowed
        finally:
            if original is None:
                os.environ.pop("CORS_ORIGINS", None)
            else:
                os.environ["CORS_ORIGINS"] = original

    def test_empty_segments_in_comma_list_ignored(self):
        """Stray commas (e.g. 'a,,b') should not produce empty-string origins."""
        original = os.environ.get("CORS_ORIGINS")
        os.environ["CORS_ORIGINS"] = "https://a.example.com,,https://b.example.com,"
        try:
            import app.api as api_module
            allowed = api_module._get_allowed_origins()
            assert "" not in allowed
            assert "https://a.example.com" in allowed
            assert "https://b.example.com" in allowed
        finally:
            if original is None:
                os.environ.pop("CORS_ORIGINS", None)
            else:
                os.environ["CORS_ORIGINS"] = original


# ---------------------------------------------------------------------------
# 9. Integration: @csrf_protect wired to the real /api/analyze/url route
# ---------------------------------------------------------------------------

class TestCsrfOnAnalyzeEndpoint:
    """Smoke-tests that csrf_protect is actually applied to the production route.

    These do NOT call the platform analyzer; they only verify the HTTP layer.
    """

    def test_post_without_origin_returns_403(self, app):
        """No Origin / Referer on the real route → 403, not 400/422."""
        with app.test_client() as c:
            # Intentionally provide no Origin header.
            resp = c.post(
                "/api/analyze/url",
                json={"url": "https://www.youtube.com/watch?v=test"},
            )
        assert resp.status_code == 403

    def test_post_with_valid_origin_reaches_handler(self, app):
        """A request with a valid Origin passes CSRF and reaches the handler.

        The handler itself may return 400/422 if the URL is unanalysable,
        but it must NOT return 403 (which would indicate CSRF rejection).
        """
        with app.test_client() as c:
            resp = c.post(
                "/api/analyze/url",
                json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                headers={"Origin": "http://localhost:3080"},
            )
        assert resp.status_code != 403

    def test_bearer_bypasses_csrf_on_real_route(self, app):
        """Bearer token lets the request through the CSRF layer on the real route."""
        with app.test_client() as c:
            resp = c.post(
                "/api/analyze/url",
                json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                headers={"Authorization": "Bearer fake-token-for-csrf-test"},
            )
        assert resp.status_code != 403
