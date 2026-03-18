"""
OAuth 2.0 authentication for LLM-powered analysis.

Supports:
1. Anthropic Console OAuth (PKCE) - Claude Code compatible
2. OpenAI OAuth - for ChatGPT API access
3. Browser API Key input - stored in session (no .env needed)
"""

import hashlib
import logging
import os
import secrets
from base64 import urlsafe_b64encode
from functools import wraps
from urllib.parse import urlencode, urlparse, quote

import requests as http_requests
from flask import request, jsonify, redirect, session

from . import auth_bp
from .. import limiter
from ..config import Config

logger = logging.getLogger(__name__)

# Anthropic Console OAuth (same as Claude Code)
_ANTHROPIC_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_ANTHROPIC_AUTHORIZE_URL = "https://console.anthropic.com/oauth/authorize"
_ANTHROPIC_TOKEN_URL = "https://console.anthropic.com/oauth/token"
_ANTHROPIC_SCOPES = "org:create_api_key user:profile user:inference"


def require_analysis_auth(f):
    """Decorator: require session when AUTH_REQUIRED_FOR_ANALYSIS is True."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not Config.AUTH_REQUIRED_FOR_ANALYSIS:
            return f(*args, **kwargs)
        if session.get("user"):
            return f(*args, **kwargs)
        return jsonify({"error": "Login required for analysis", "code": "auth_required"}), 401
    return wrapped


def _oauth_configured():
    return bool(
        Config.OPENAI_OAUTH_CLIENT_ID
        and Config.OPENAI_OAUTH_CLIENT_SECRET
        and Config.OAUTH_REDIRECT_URI
    )


def _get_redirect_uri():
    """Get OAuth redirect URI from config or build from request."""
    if Config.OAUTH_REDIRECT_URI:
        return Config.OAUTH_REDIRECT_URI
    # Auto-detect from request
    return f"{request.scheme}://{request.host}/api/auth/callback"


# ==========================================
# Auth status
# ==========================================
@auth_bp.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Return current user session info."""
    user = session.get("user")
    has_api_key = bool(session.get("session_api_key"))
    has_token = bool(session.get("access_token"))

    if user:
        return jsonify({
            "logged_in": True,
            "user": user,
            "auth_required": Config.AUTH_REQUIRED_FOR_ANALYSIS,
            "has_api_key": has_api_key,
            "has_token": has_token,
        })
    return jsonify({
        "logged_in": False,
        "auth_required": Config.AUTH_REQUIRED_FOR_ANALYSIS,
        "anthropic_oauth_available": True,  # Always available (built-in client ID)
        "openai_oauth_available": _oauth_configured(),
    })


# ==========================================
# Anthropic Console OAuth (PKCE)
# ==========================================
@auth_bp.route("/api/auth/anthropic", methods=["GET"])
@limiter.limit("10 per minute")
def auth_anthropic_start():
    """Start Anthropic Console OAuth with PKCE."""
    # Generate PKCE verifier and challenge
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    session["pkce_verifier"] = code_verifier
    session["oauth_provider"] = "anthropic"

    return_to = request.args.get("return_to", "").strip() or "/analysis"
    parsed = urlparse(return_to)
    if return_to.startswith("/") and not return_to.startswith("//") and not parsed.netloc:
        session["oauth_return_to"] = return_to
    else:
        session["oauth_return_to"] = "/analysis"

    params = {
        "response_type": "code",
        "client_id": _ANTHROPIC_CLIENT_ID,
        "redirect_uri": _get_redirect_uri(),
        "scope": _ANTHROPIC_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    url = f"{_ANTHROPIC_AUTHORIZE_URL}?{urlencode(params)}"
    return redirect(url)


# ==========================================
# OpenAI OAuth
# ==========================================
@auth_bp.route("/api/auth/openai", methods=["GET"])
@limiter.limit("10 per minute")
def auth_openai_start():
    """Redirect to OpenAI OAuth authorize URL."""
    if not _oauth_configured():
        return jsonify({"error": "OpenAI OAuth not configured. Use Anthropic OAuth or set API key.", "auth_url": None}), 503
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    session["oauth_provider"] = "openai"

    return_to = request.args.get("return_to", "").strip() or "/analysis"
    parsed = urlparse(return_to)
    if return_to.startswith("/") and not return_to.startswith("//") and not parsed.netloc:
        session["oauth_return_to"] = return_to
    else:
        session["oauth_return_to"] = "/analysis"

    params = {
        "response_type": "code",
        "client_id": Config.OPENAI_OAUTH_CLIENT_ID,
        "redirect_uri": Config.OAUTH_REDIRECT_URI,
        "scope": Config.OAUTH_SCOPES,
        "state": state,
    }
    url = f"{Config.OAUTH_AUTHORIZE_URL}?{urlencode(params)}"
    return redirect(url)


# ==========================================
# OAuth callback (handles both providers)
# ==========================================
@auth_bp.route("/api/auth/callback", methods=["GET"])
@limiter.limit("10 per minute")
def auth_callback():
    """Exchange OAuth code for tokens (Anthropic PKCE or OpenAI)."""
    err = request.args.get("error")
    if err:
        logger.warning("OAuth error: %s", err)
        return redirect(_frontend_redirect(f"/analysis?auth_error={quote(err, safe='')}"))

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return redirect(_frontend_redirect("/analysis?auth_error=missing_code_or_state"))

    saved_state = session.pop("oauth_state", None)
    if not saved_state or saved_state != state:
        logger.warning("OAuth state mismatch")
        return redirect(_frontend_redirect("/analysis?auth_error=invalid_state"))

    provider = session.pop("oauth_provider", "openai")

    if provider == "anthropic":
        return _handle_anthropic_callback(code)
    else:
        return _handle_openai_callback(code)


def _handle_anthropic_callback(code):
    """Exchange Anthropic OAuth code for tokens using PKCE."""
    code_verifier = session.pop("pkce_verifier", None)
    if not code_verifier:
        return redirect(_frontend_redirect("/analysis?auth_error=missing_pkce_verifier"))

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _get_redirect_uri(),
        "client_id": _ANTHROPIC_CLIENT_ID,
        "code_verifier": code_verifier,
    }
    try:
        resp = http_requests.post(
            _ANTHROPIC_TOKEN_URL,
            data=data,
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except http_requests.RequestException as e:
        logger.exception("Anthropic token exchange failed: %s", e)
        return redirect(_frontend_redirect("/analysis?auth_error=token_exchange_failed"))

    access_token = token_data.get("access_token")
    if not access_token:
        return redirect(_frontend_redirect("/analysis?auth_error=no_access_token"))

    session["access_token"] = access_token
    session["token_provider"] = "anthropic"
    if token_data.get("refresh_token"):
        session["refresh_token"] = token_data["refresh_token"]
    session["user"] = {
        "id": token_data.get("user_id") or token_data.get("sub") or "anthropic-user",
        "provider": "anthropic",
    }

    return_to = session.pop("oauth_return_to", "/analysis")
    return redirect(_frontend_redirect(return_to))


def _handle_openai_callback(code):
    """Exchange OpenAI OAuth code for tokens."""
    if not _oauth_configured():
        return redirect(_frontend_redirect("/analysis?auth_error=openai_oauth_not_configured"))

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": Config.OAUTH_REDIRECT_URI,
        "client_id": Config.OPENAI_OAUTH_CLIENT_ID,
        "client_secret": Config.OPENAI_OAUTH_CLIENT_SECRET,
    }
    try:
        resp = http_requests.post(
            Config.OAUTH_TOKEN_URL,
            data=data,
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except http_requests.RequestException as e:
        logger.exception("OpenAI token exchange failed: %s", e)
        return redirect(_frontend_redirect("/analysis?auth_error=token_exchange_failed"))

    access_token = token_data.get("access_token")
    if not access_token:
        return redirect(_frontend_redirect("/analysis?auth_error=no_access_token"))

    session["access_token"] = access_token
    session["token_provider"] = "openai"
    session["user"] = {
        "id": token_data.get("id") or token_data.get("sub") or "openai-user",
        "provider": "openai",
    }
    return_to = session.pop("oauth_return_to", "/analysis")
    return redirect(_frontend_redirect(return_to))


# ==========================================
# Browser API key input (session-based)
# ==========================================
@auth_bp.route("/api/auth/apikey", methods=["POST"])
@limiter.limit("10 per minute")
def set_api_key():
    """Store API key in session (no .env needed).

    Request JSON: {"provider": "openai"|"anthropic", "api_key": "sk-..."}
    """
    data = request.get_json() or {}
    provider = data.get("provider", "").strip()
    api_key = data.get("api_key", "").strip()

    if provider not in ("openai", "anthropic"):
        return jsonify({"error": "Provider must be 'openai' or 'anthropic'"}), 400
    if not api_key:
        return jsonify({"error": "API key is required"}), 400

    # Basic validation
    if provider == "openai" and not api_key.startswith("sk-"):
        return jsonify({"error": "OpenAI API key should start with 'sk-'"}), 400
    if provider == "anthropic" and not api_key.startswith("sk-ant-"):
        return jsonify({"error": "Anthropic API key should start with 'sk-ant-'"}), 400

    session["session_api_key"] = api_key
    session["session_api_provider"] = provider
    session["user"] = {
        "id": f"{provider}-apikey-user",
        "provider": provider,
    }

    return jsonify({"ok": True, "provider": provider})


# ==========================================
# Logout
# ==========================================
@auth_bp.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Clear session and log out."""
    session.clear()
    return jsonify({"ok": True})


# ==========================================
# Helpers
# ==========================================
def _frontend_redirect(path):
    """Redirect to frontend; use env FRONTEND_URL or same host."""
    base = (os.environ.get("FRONTEND_URL") or "").strip()
    if not base:
        return path
    if not base.endswith("/"):
        base += "/"
    path = path.lstrip("/")
    return f"{base}{path}"
