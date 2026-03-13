"""
OpenAI OAuth 2.0 login for MiroFish / analysis.
When AUTH_REQUIRED_FOR_ANALYSIS is true, analysis endpoints require a valid session.
"""

import logging
import secrets
from functools import wraps
from urllib.parse import urlencode, urlparse, quote

import requests
from flask import request, jsonify, redirect, session

from . import auth_bp
from .. import limiter
from ..config import Config

logger = logging.getLogger(__name__)


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


@auth_bp.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Return current user if logged in."""
    if not _oauth_configured():
        return jsonify({"logged_in": False, "auth_required": False})
    user = session.get("user")
    if user:
        return jsonify({"logged_in": True, "user": user, "auth_required": Config.AUTH_REQUIRED_FOR_ANALYSIS})
    return jsonify({"logged_in": False, "auth_required": Config.AUTH_REQUIRED_FOR_ANALYSIS})


@auth_bp.route("/api/auth/openai", methods=["GET"])
@limiter.limit("10 per minute")
def auth_openai_start():
    """Redirect to OpenAI (or configured IdP) OAuth authorize URL."""
    if not _oauth_configured():
        return jsonify({"error": "OAuth not configured", "auth_url": None}), 503
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    return_to = request.args.get("return_to", "").strip() or "/"
    # Validate return_to is a safe relative path (reject protocol-relative //evil.com, backslash tricks)
    parsed = urlparse(return_to)
    if return_to.startswith("/") and not return_to.startswith("//") and not parsed.netloc:
        session["oauth_return_to"] = return_to
    else:
        session["oauth_return_to"] = "/"
    params = {
        "response_type": "code",
        "client_id": Config.OPENAI_OAUTH_CLIENT_ID,
        "redirect_uri": Config.OAUTH_REDIRECT_URI,
        "scope": Config.OAUTH_SCOPES,
        "state": state,
    }
    url = f"{Config.OAUTH_AUTHORIZE_URL}?{urlencode(params)}"
    return redirect(url)


@auth_bp.route("/api/auth/callback", methods=["GET"])
@limiter.limit("10 per minute")
def auth_callback():
    """Exchange OAuth code for tokens and create session."""
    if not _oauth_configured():
        return jsonify({"error": "OAuth not configured"}), 503
    err = request.args.get("error")
    if err:
        logger.warning("OAuth error: %s", err)
        return redirect(_frontend_redirect("/?auth_error=" + quote(err, safe='')))
    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return redirect(_frontend_redirect("/?auth_error=missing_code_or_state"))
    saved_state = session.pop("oauth_state", None)
    if not saved_state or saved_state != state:
        logger.warning("OAuth state mismatch")
        return redirect(_frontend_redirect("/?auth_error=invalid_state"))
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": Config.OAUTH_REDIRECT_URI,
        "client_id": Config.OPENAI_OAUTH_CLIENT_ID,
        "client_secret": Config.OPENAI_OAUTH_CLIENT_SECRET,
    }
    try:
        resp = requests.post(
            Config.OAUTH_TOKEN_URL,
            data=data,
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except requests.RequestException as e:
        logger.exception("Token exchange failed: %s", e)
        return redirect(_frontend_redirect("/?auth_error=token_exchange_failed"))
    access_token = token_data.get("access_token")
    if not access_token:
        return redirect(_frontend_redirect("/?auth_error=no_access_token"))
    session["access_token"] = access_token
    session["user"] = {
        "id": token_data.get("id") or token_data.get("sub") or "openai-user",
        "provider": "openai",
    }
    return_to = session.pop("oauth_return_to", "/")
    return redirect(_frontend_redirect(return_to))


def _frontend_redirect(path):
    """Redirect to frontend; use env FRONTEND_URL or same host."""
    base = (__import__("os").environ.get("FRONTEND_URL") or "").strip()
    if not base:
        return path
    if not base.endswith("/"):
        base += "/"
    path = path.lstrip("/")
    return f"{base}{path}"


@auth_bp.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Clear session and log out."""
    session.clear()
    return jsonify({"ok": True})
