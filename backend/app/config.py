"""
Centralized configuration management.
All environment variables are accessed through this class.
"""

import logging
import os
import secrets

logger = logging.getLogger(__name__)


class Config:
    """Flask and application configuration. Do not set FLASK_DEBUG=true in production."""

    # Flask (keep DEBUG false in production)
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # API
    API_PORT = int(os.environ.get("API_PORT", 8080))

    # Storage
    LOCAL_MODE = os.environ.get("LOCAL_MODE", "true").lower() == "true"
    LOCAL_DATA_DIR = os.environ.get("LOCAL_DATA_DIR", "./local-data")

    # Redis (optional)
    REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
    REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

    # YouTube (treat common placeholders as unset)
    _yt_key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    YOUTUBE_API_KEY = (
        _yt_key
        if _yt_key
        and _yt_key.lower() not in ("your_youtube_api_key_here", "your-youtube-api-key")
        else ""
    )

    # X (Twitter) API v2
    TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")

    # Reddit API (OAuth2 app at https://www.reddit.com/prefs/apps)
    REDDIT_CLIENT_ID = (os.environ.get("REDDIT_CLIENT_ID") or "").strip()
    REDDIT_CLIENT_SECRET = (os.environ.get("REDDIT_CLIENT_SECRET") or "").strip()
    REDDIT_USER_AGENT = (
        os.environ.get("REDDIT_USER_AGENT") or ""
    ).strip() or "sns-monitor/1.0 (Reddit URL analyzer)"

    # MiroFish AI
    MIROFISH_ENDPOINT = os.environ.get("MIROFISH_ENDPOINT", "http://mirofish:5001")

    # OpenAI OAuth (optional – gate MiroFish/analysis behind login)
    OPENAI_OAUTH_CLIENT_ID = (os.environ.get("OPENAI_OAUTH_CLIENT_ID") or "").strip()
    OPENAI_OAUTH_CLIENT_SECRET = (os.environ.get("OPENAI_OAUTH_CLIENT_SECRET") or "").strip()
    OAUTH_REDIRECT_URI = (os.environ.get("OAUTH_REDIRECT_URI") or "").strip()
    OAUTH_AUTHORIZE_URL = (
        os.environ.get("OAUTH_AUTHORIZE_URL") or "https://auth.openai.com/oauth/authorize"
    ).strip()
    OAUTH_TOKEN_URL = (
        os.environ.get("OAUTH_TOKEN_URL") or "https://auth.openai.com/oauth/token"
    ).strip()
    OAUTH_SCOPES = os.environ.get("OAUTH_SCOPES", "openid profile email").strip()
    _secret = os.environ.get("SECRET_KEY") or os.environ.get("FLASK_SECRET_KEY") or ""
    if not _secret:
        _secret = secrets.token_hex(32)
        logging.getLogger(__name__).warning(
            "SECRET_KEY not set — using random key (sessions will not survive restarts)"
        )
    SECRET_KEY = _secret
    AUTH_REQUIRED_FOR_ANALYSIS = os.environ.get("AUTH_REQUIRED_FOR_ANALYSIS", "false").lower() in ("1", "true", "yes")
    MIROFISH_SSL_VERIFY = os.environ.get("MIROFISH_SSL_VERIFY", "true").lower() in (
        "1",
        "true",
        "yes",
    )

    # Naver Search API (for cafe article search: https://developers.naver.com/apps)
    NAVER_SEARCH_CLIENT_ID = (os.environ.get("NAVER_SEARCH_CLIENT_ID") or "").strip()
    NAVER_SEARCH_CLIENT_SECRET = (os.environ.get("NAVER_SEARCH_CLIENT_SECRET") or "").strip()

    NAVER_CAFE_COOKIE = os.environ.get("NAVER_CAFE_COOKIE", "")
    NAVER_CAFE_PROXY_URL = os.environ.get("NAVER_CAFE_PROXY_URL", "")
    NAVER_CAFE_PROXY_USERNAME = os.environ.get("NAVER_CAFE_PROXY_USERNAME", "")
    NAVER_CAFE_PROXY_PASSWORD = os.environ.get("NAVER_CAFE_PROXY_PASSWORD", "")

    # AWS (only used when LOCAL_MODE=false)
    S3_BUCKET = os.environ.get("S3_BUCKET", "")
    DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "")

    # Session cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")

    # JSON encoding
    JSON_AS_ASCII = False

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        errors = []
        if not cls.YOUTUBE_API_KEY:
            errors.append("YOUTUBE_API_KEY is not set")
        return errors
