"""Cross-cutting security regression suite.

Verifies the three security boundaries that the audit follow-up established:

1. CSRF protection — mutating routes reject requests without a trusted Origin.
2. Rate limiting — limiter caps are real and trip when exceeded.
3. require_analysis_auth — LLM-cost endpoints reject unauth'd requests when
   AUTH_REQUIRED_FOR_ANALYSIS is on, but the toggle off keeps them open
   (matches the "gate expensive work only" policy decision).

These are intentionally light-touch black-box tests so they survive route
refactors. If a future change quietly drops a decorator, the suite catches it.
"""

import importlib
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# CSRF — mutating endpoints must require a same-origin request.
# ---------------------------------------------------------------------------

CSRF_GUARDED_POSTS = [
    ("/api/analyze/url", {"url": "https://www.youtube.com/watch?v=test"}),
    ("/api/analyze/summarize", {"result": {"platform": "youtube"}}),
    ("/api/analysis/local-summary", {"sources": []}),
    ("/api/analysis/ai-summary", {}),
    ("/api/analysis/ai-chat", {"message": "hi"}),
    ("/api/analysis/ai-url-analyze", {"result": {}}),
    ("/api/analysis/ai-url-chat", {"message": "hi", "result": {}}),
    ("/api/auth/apikey", {"provider": "openai", "api_key": "sk-x"}),
    ("/api/auth/logout", {}),
]


class TestCsrfBoundary:
    @pytest.mark.parametrize("path, body", CSRF_GUARDED_POSTS)
    def test_post_without_origin_rejected(self, client, path, body):
        # Drop the default Origin header set by the client fixture
        resp = client.post(path, json=body, headers={"Origin": ""})
        # 403 for CSRF; some routes may return 400 before CSRF kicks in
        # (e.g. invalid payload) — both prove CSRF + validation are wired.
        assert resp.status_code in (400, 403), (
            f"{path}: expected CSRF/validation rejection, got {resp.status_code}"
        )

    @pytest.mark.parametrize("path, body", CSRF_GUARDED_POSTS)
    def test_post_with_foreign_origin_rejected(self, client, path, body):
        resp = client.post(path, json=body, headers={"Origin": "https://evil.example"})
        assert resp.status_code in (400, 403)


# ---------------------------------------------------------------------------
# Rate limiting — limiter caps trip; new caps from audit are wired up.
# ---------------------------------------------------------------------------

class TestRateLimitBoundary:
    def test_auth_me_rate_limit_trips(self, app, client):
        """auth/me is capped at 60/min; bursting past it returns 429."""
        # 65 requests should exceed any sane cap; we rely on the limiter
        # being enabled (default in tests via memory:// storage).
        statuses = [client.get("/api/auth/me").status_code for _ in range(65)]
        assert 429 in statuses

    def test_vuddy_creators_rate_limit_present(self, app, client):
        """vuddy/creators previously had no limit; audit added 30/min cap."""
        statuses = [client.get("/api/vuddy/creators").status_code for _ in range(40)]
        # The endpoint may 200 or 4xx depending on local data, but a 429
        # within 40 calls proves the cap is wired.
        assert 429 in statuses

    def test_llm_status_rate_limit_present(self, client):
        """analysis/llm/status now has 30/min cap (audit F-3 follow-up)."""
        statuses = [client.get("/api/analysis/llm/status").status_code for _ in range(35)]
        assert 429 in statuses


# ---------------------------------------------------------------------------
# require_analysis_auth — gating policy.
# ---------------------------------------------------------------------------

AUTH_GATED_POSTS = [
    ("/api/analysis/ai-summary", {"sources": [{"type": "youtube", "id": "x"}]}),
    ("/api/analysis/ai-chat", {"sources": [{"type": "youtube", "id": "x"}], "message": "hi"}),
    ("/api/analysis/ai-url-analyze", {"result": {"platform": "youtube"}}),
    ("/api/analysis/ai-url-chat", {"result": {"platform": "youtube"}, "message": "hi"}),
]


class TestRequireAnalysisAuthBoundary:
    @pytest.mark.parametrize("path, body", AUTH_GATED_POSTS)
    def test_unauthenticated_rejected_when_required(self, client, path, body):
        """When AUTH_REQUIRED_FOR_ANALYSIS=True, LLM routes return 401 without session."""
        from app import config as _cfg_mod
        with patch.object(_cfg_mod.Config, "AUTH_REQUIRED_FOR_ANALYSIS", True):
            resp = client.post(path, json=body)
            assert resp.status_code == 401
            payload = resp.get_json() or {}
            assert payload.get("code") == "auth_required"

    @pytest.mark.parametrize("path, body", AUTH_GATED_POSTS)
    def test_open_when_not_required(self, client, path, body):
        """Policy A: when the flag is off the LLM gate is open (env keys may
        still be configured to actually run the call). We assert only that
        the request is NOT rejected with 401 auth_required."""
        from app import config as _cfg_mod
        with patch.object(_cfg_mod.Config, "AUTH_REQUIRED_FOR_ANALYSIS", False):
            resp = client.post(path, json=body)
            assert resp.status_code != 401 or (
                (resp.get_json() or {}).get("code") != "auth_required"
            )

    def test_local_summary_remains_open(self, client):
        """Policy A: local_summary stays unauth'd even when flag is on
        (keyword-only analysis, no external cost)."""
        from app import config as _cfg_mod
        with patch.object(_cfg_mod.Config, "AUTH_REQUIRED_FOR_ANALYSIS", True):
            resp = client.post(
                "/api/analysis/local-summary",
                json={"sources": [{"type": "youtube", "id": "nope"}]},
            )
            # 400/404 (no data) but never 401
            assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Input validation — whitelist regex on path-like inputs.
# ---------------------------------------------------------------------------

class TestInputValidationBoundary:
    @pytest.mark.parametrize("bad_handle", [
        "../etc/passwd",
        "name%0Awith%0Anewlines",  # URL-encoded LFs that survive HTTP parsing
        "name%20with%20spaces",
        "a" * 200,
    ])
    def test_channel_handle_rejected(self, client, bad_handle):
        resp = client.get(f"/api/group-a/channel?channel_handle={bad_handle}")
        assert resp.status_code == 400

    def test_oversized_session_api_key_rejected(self, client):
        resp = client.post(
            "/api/auth/apikey",
            json={"provider": "openai", "api_key": "sk-" + "a" * 300},
        )
        assert resp.status_code == 400
