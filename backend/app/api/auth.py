"""
OAuth 2.0 authentication for LLM-powered analysis.

Supports:
1. Anthropic OAuth (PKCE) - Claude Code compatible (claude.ai)
2. OpenAI OAuth (PKCE) - ChatGPT compatible
3. Browser API Key input - stored in session (fallback)
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

from . import auth_bp, csrf_protect
from .. import limiter
from ..config import Config

logger = logging.getLogger(__name__)

# Anthropic OAuth (Claude Code compatible)
# redirect_uri MUST be http://localhost:{port}/callback (Claude Code pattern)
_ANTHROPIC_CLIENT_ID = os.environ.get("ANTHROPIC_OAUTH_CLIENT_ID") or None
_ANTHROPIC_AUTHORIZE_URL = "https://claude.ai/oauth/authorize"
_ANTHROPIC_TOKEN_URL = "https://claude.ai/oauth/token"
_ANTHROPIC_SCOPES = "org:create_api_key user:profile user:inference user:sessions:claude_code user:mcp_servers user:file_upload"


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


def _is_safe_redirect(url):
    """Validate redirect target to prevent open redirect attacks."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith("/"):
        return False
    if url.startswith("//") or url.startswith("/\\"):
        return False
    # Block encoded schemes (javascript:, data:, vbscript:)
    url_lower = url.lower().replace(" ", "").replace("\t", "")
    if any(scheme in url_lower for scheme in ("javascript:", "data:", "vbscript:")):
        return False
    parsed = urlparse(url)
    if parsed.netloc or parsed.scheme:
        return False
    if any(c < ' ' for c in url):
        return False
    return True


def _oauth_configured():
    return bool(Config.OPENAI_OAUTH_CLIENT_ID)


def _get_callback_uri():
    """Build callback URI in Claude Code format: http://localhost:PORT/callback"""
    if Config.OAUTH_REDIRECT_URI:
        return Config.OAUTH_REDIRECT_URI
    # Use external port (Docker maps 8888->8080 internally)
    port = os.environ.get("API_EXTERNAL_PORT") or os.environ.get("API_PORT") or "8888"
    return f"http://localhost:{port}/callback"


# ==========================================
# Auth status
# ==========================================
@auth_bp.route("/api/auth/me", methods=["GET"])
@limiter.limit("60 per minute")
def auth_me():
    """현재 로그인 세션 정보 조회
    세션에 저장된 사용자 정보와 OAuth 설정 상태를 반환합니다.
    ---
    tags:
      - 인증
    responses:
      200:
        description: "세션 상태 반환 성공"
        schema:
          type: object
          properties:
            logged_in:
              type: boolean
              description: "로그인 여부"
            user:
              type: object
              description: "로그인된 사용자 정보 (logged_in=true 시)"
            auth_required:
              type: boolean
              description: "분석 기능 인증 필요 여부"
            anthropic_oauth_available:
              type: boolean
              description: "Anthropic OAuth 지원 여부 (logged_in=false 시)"
            openai_oauth_available:
              type: boolean
              description: "OpenAI OAuth 지원 여부 (logged_in=false 시)"
    """
    user = session.get("user")
    if user:
        return jsonify({
            "logged_in": True,
            "user": user,
            "auth_required": Config.AUTH_REQUIRED_FOR_ANALYSIS,
        })
    return jsonify({
        "logged_in": False,
        "auth_required": Config.AUTH_REQUIRED_FOR_ANALYSIS,
        "anthropic_oauth_available": True,
        "openai_oauth_available": _oauth_configured(),
    })


# ==========================================
# Anthropic OAuth (PKCE) - Claude Code compatible
# ==========================================
@auth_bp.route("/api/auth/anthropic", methods=["GET"])
@limiter.limit("10 per minute")
def auth_anthropic_start():
    """Anthropic OAuth 로그인 시작 (PKCE)
    Claude Code와 동일한 PKCE 방식으로 Anthropic OAuth 인증을 시작합니다.
    ANTHROPIC_OAUTH_CLIENT_ID 환경변수가 설정되어야 합니다.
    ---
    tags:
      - 인증
    parameters:
      - name: return_to
        in: query
        type: string
        required: false
        description: "인증 완료 후 리디렉션할 경로 (기본값: /analysis)"
    responses:
      302:
        description: "Anthropic OAuth 인증 페이지로 리디렉션"
      503:
        description: "ANTHROPIC_OAUTH_CLIENT_ID 미설정"
    """
    if not _ANTHROPIC_CLIENT_ID:
        return jsonify({"error": "Anthropic OAuth is not configured. Set ANTHROPIC_OAUTH_CLIENT_ID."}), 503
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    session["pkce_verifier"] = code_verifier
    session["oauth_provider"] = "anthropic"

    return_to = request.args.get("return_to", "").strip() or "/analysis"
    if _is_safe_redirect(return_to):
        session["oauth_return_to"] = return_to
    else:
        session["oauth_return_to"] = "/analysis"

    params = {
        "code": "true",
        "client_id": _ANTHROPIC_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": _get_callback_uri(),
        "scope": _ANTHROPIC_SCOPES,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    url = f"{_ANTHROPIC_AUTHORIZE_URL}?{urlencode(params)}"
    return redirect(url)


# ==========================================
# OpenAI OAuth (PKCE)
# ==========================================
# OpenAI OAuth (OpenCode / Codex CLI compatible)
_OPENAI_CLIENT_ID = os.environ.get("OPENAI_OAUTH_CLIENT_ID") or None
_OPENAI_AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
_OPENAI_TOKEN_URL = "https://auth.openai.com/oauth/token"
_OPENAI_SCOPES = "openid profile email offline_access"


def _get_openai_callback_uri():
    """OpenAI callback uses /auth/callback path (OpenCode pattern)."""
    if Config.OAUTH_REDIRECT_URI:
        return Config.OAUTH_REDIRECT_URI
    port = os.environ.get("API_EXTERNAL_PORT") or os.environ.get("API_PORT") or "8888"
    return f"http://localhost:{port}/auth/callback"


@auth_bp.route("/api/auth/openai", methods=["GET"])
@limiter.limit("10 per minute")
def auth_openai_start():
    """OpenAI OAuth 로그인 시작 (PKCE)
    OpenCode CLI와 호환되는 PKCE 방식으로 OpenAI OAuth 인증을 시작합니다.
    OPENAI_OAUTH_CLIENT_ID 환경변수가 설정되어야 합니다.
    ---
    tags:
      - 인증
    parameters:
      - name: return_to
        in: query
        type: string
        required: false
        description: "인증 완료 후 리디렉션할 경로 (기본값: /analysis)"
    responses:
      302:
        description: "OpenAI OAuth 인증 페이지로 리디렉션"
      503:
        description: "OPENAI_OAUTH_CLIENT_ID 미설정"
    """
    client_id = Config.OPENAI_OAUTH_CLIENT_ID or _OPENAI_CLIENT_ID
    if not client_id:
        return jsonify({"error": "OpenAI OAuth is not configured. Set OPENAI_OAUTH_CLIENT_ID."}), 503

    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    session["pkce_verifier"] = code_verifier
    session["oauth_provider"] = "openai"

    return_to = request.args.get("return_to", "").strip() or "/analysis"
    if _is_safe_redirect(return_to):
        session["oauth_return_to"] = return_to
    else:
        session["oauth_return_to"] = "/analysis"

    authorize_url = Config.OAUTH_AUTHORIZE_URL or _OPENAI_AUTHORIZE_URL

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": _get_openai_callback_uri(),
        "scope": _OPENAI_SCOPES,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "state": state,
        "originator": "sns-monitor",
    }
    url = f"{authorize_url}?{urlencode(params)}"
    return redirect(url)


# ==========================================
# OAuth callback — http://localhost:PORT/callback
# Claude Code pattern: must be at /callback (not /api/auth/callback)
# ==========================================
@auth_bp.route("/callback", methods=["GET"])
@limiter.limit("10 per minute")
def auth_callback():
    """OAuth 인증 코드 교환 (Anthropic PKCE 또는 OpenAI PKCE)
    OAuth 인증 서버에서 리디렉션된 후 인증 코드를 액세스 토큰으로 교환합니다.
    세션에 저장된 provider에 따라 Anthropic 또는 OpenAI 토큰 교환을 처리합니다.
    ---
    tags:
      - 인증
    parameters:
      - name: code
        in: query
        type: string
        required: true
        description: "OAuth 인증 서버에서 발급된 인증 코드"
      - name: state
        in: query
        type: string
        required: true
        description: "CSRF 방지용 state 파라미터"
      - name: error
        in: query
        type: string
        required: false
        description: "인증 오류 코드 (오류 발생 시)"
    responses:
      302:
        description: "토큰 교환 성공 후 프론트엔드로 리디렉션"
    """
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

    provider = session.pop("oauth_provider", "anthropic")

    if provider == "anthropic":
        return _handle_anthropic_callback(code)
    else:
        return _handle_openai_callback(code)


# OpenAI callback path: /auth/callback (OpenCode pattern)
@auth_bp.route("/auth/callback", methods=["GET"])
@limiter.limit("10 per minute")
def auth_openai_callback():
    """OpenAI OAuth 콜백 경로 (OpenCode 패턴)
    OpenCode CLI와 호환되는 /auth/callback 경로의 OAuth 콜백을 처리합니다.
    내부적으로 auth_callback()을 호출합니다.
    ---
    tags:
      - 인증
    parameters:
      - name: code
        in: query
        type: string
        required: true
        description: "OAuth 인증 코드"
      - name: state
        in: query
        type: string
        required: true
        description: "CSRF 방지용 state 파라미터"
    responses:
      302:
        description: "토큰 교환 후 프론트엔드로 리디렉션"
    """
    return auth_callback()


# Legacy path for backward compatibility
@auth_bp.route("/api/auth/callback", methods=["GET"])
@limiter.limit("10 per minute")
def auth_callback_legacy():
    """레거시 OAuth 콜백 경로 (하위 호환)
    이전 버전과의 호환성을 위해 /api/auth/callback 경로를 지원합니다.
    내부적으로 auth_callback()을 호출합니다.
    ---
    tags:
      - 인증
    parameters:
      - name: code
        in: query
        type: string
        required: true
        description: "OAuth 인증 코드"
      - name: state
        in: query
        type: string
        required: true
        description: "CSRF 방지용 state 파라미터"
    responses:
      302:
        description: "토큰 교환 후 프론트엔드로 리디렉션"
    """
    return auth_callback()


def _handle_anthropic_callback(code):
    """Exchange Anthropic OAuth code for tokens using PKCE."""
    code_verifier = session.pop("pkce_verifier", None)
    if not code_verifier:
        return redirect(_frontend_redirect("/analysis?auth_error=missing_pkce_verifier"))

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _get_callback_uri(),
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
        logger.warning("Anthropic token response: %s", {k: v for k, v in token_data.items() if k != "access_token"})
        return redirect(_frontend_redirect("/analysis?auth_error=no_access_token"))

    session["access_token"] = access_token
    session["token_provider"] = "anthropic"
    if token_data.get("refresh_token"):
        session["refresh_token"] = token_data["refresh_token"]
    session["user"] = {
        "id": token_data.get("user_id") or token_data.get("sub") or "anthropic-user",
        "provider": "anthropic",
        "display": "Claude (Anthropic)",
    }

    return_to = session.pop("oauth_return_to", "/analysis")
    return redirect(_frontend_redirect(return_to))


def _handle_openai_callback(code):
    """Exchange OpenAI OAuth code for tokens (PKCE)."""
    client_id = Config.OPENAI_OAUTH_CLIENT_ID or _OPENAI_CLIENT_ID
    code_verifier = session.pop("pkce_verifier", None)
    token_url = Config.OAUTH_TOKEN_URL or _OPENAI_TOKEN_URL

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _get_openai_callback_uri(),
        "client_id": client_id,
    }
    if code_verifier:
        data["code_verifier"] = code_verifier
    elif Config.OPENAI_OAUTH_CLIENT_SECRET:
        data["client_secret"] = Config.OPENAI_OAUTH_CLIENT_SECRET

    try:
        resp = http_requests.post(
            token_url,
            data=data,
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
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
    if token_data.get("refresh_token"):
        session["refresh_token"] = token_data["refresh_token"]
    session["user"] = {
        "id": token_data.get("id") or token_data.get("sub") or "openai-user",
        "provider": "openai",
        "display": "ChatGPT (OpenAI)",
    }
    return_to = session.pop("oauth_return_to", "/analysis")
    return redirect(_frontend_redirect(return_to))


# ==========================================
# Browser API key input (session-based fallback)
# ==========================================
@auth_bp.route("/api/auth/apikey", methods=["POST"])
@limiter.limit("10 per minute")
@csrf_protect
def set_api_key():
    """API 키를 세션에 저장 (OAuth 미사용 시 대체 수단)
    OAuth 인증을 사용할 수 없을 때 브라우저 세션에 API 키를 저장합니다.
    Origin 헤더가 필요합니다 (CSRF 보호).
    ---
    tags:
      - 인증
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - provider
            - api_key
          properties:
            provider:
              type: string
              enum: [openai, anthropic]
              description: "API 키 제공자"
            api_key:
              type: string
              description: "API 키 (openai: sk-..., anthropic: sk-ant-...)"
    responses:
      200:
        description: "API 키 저장 성공"
        schema:
          type: object
          properties:
            ok:
              type: boolean
            provider:
              type: string
      400:
        description: "잘못된 provider 또는 API 키 형식"
    """
    data = request.get_json() or {}
    provider = data.get("provider", "").strip()
    api_key = data.get("api_key", "").strip()

    if provider not in ("openai", "anthropic"):
        return jsonify({"error": "Provider must be 'openai' or 'anthropic'"}), 400
    if not api_key:
        return jsonify({"error": "API key is required"}), 400
    if len(api_key) > 256:
        return jsonify({"error": "API key exceeds maximum length"}), 400
    if provider == "openai" and not api_key.startswith("sk-"):
        return jsonify({"error": "OpenAI API key should start with 'sk-'"}), 400
    if provider == "anthropic" and not api_key.startswith("sk-ant-"):
        return jsonify({"error": "Anthropic API key should start with 'sk-ant-'"}), 400

    session["session_api_key"] = api_key
    session["session_api_provider"] = provider
    session["user"] = {
        "id": f"{provider}-apikey-user",
        "provider": provider,
        "display": "Claude (API Key)" if provider == "anthropic" else "ChatGPT (API Key)",
    }
    return jsonify({"ok": True, "provider": provider})


# ==========================================
# Logout
# ==========================================
@auth_bp.route("/api/auth/logout", methods=["POST"])
@limiter.limit("30 per minute")
@csrf_protect
def auth_logout():
    """Clear session and log out."""
    session.clear()
    return jsonify({"ok": True})


def _frontend_redirect(path):
    """Redirect to frontend."""
    base = (os.environ.get("FRONTEND_URL") or "").strip()
    if not base:
        return path
    if not base.endswith("/"):
        base += "/"
    path = path.lstrip("/")
    return f"{base}{path}"
