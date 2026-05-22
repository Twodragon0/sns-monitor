"""HTTP client service for managing session creation and configuration.

Extracted from PlatformAnalyzer to separate HTTP transport concerns
from platform analysis logic. PlatformAnalyzer delegates session setup
here while keeping self._session as a reference for backward compatibility.
"""

import base64
import logging
import os
import time
from typing import Optional
from urllib.parse import urlparse, quote

import requests

logger = logging.getLogger(__name__)


class HttpClientService:
    """Manages HTTP session creation, configuration, and platform-specific request helpers."""

    def __init__(self, config=None):
        config = config or {}

        # --- Core session setup ---
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

        # --- SSL verification ---
        # NOTE: a previous DISABLE_SSL_VERIFY env override was removed (security
        # audit F-6). SSL verification is always on for the shared HTTP session;
        # platform-scoped opt-out (e.g. NAVER_CAFE_DISABLE_SSL_VERIFY below) is
        # the only supported way to relax it for a specific upstream.
        if os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE"):
            pass  # Use system CA bundle
        if os.environ.get("DISABLE_SSL_VERIFY", "").lower() in ("1", "true", "yes"):
            logger.warning(
                "DISABLE_SSL_VERIFY env var is set but is no longer honored. "
                "Use NAVER_CAFE_DISABLE_SSL_VERIFY for the Naver-specific path "
                "or set REQUESTS_CA_BUNDLE/SSL_CERT_FILE for a custom CA."
            )

        # --- Naver cookie configuration ---
        self._naver_cookie = (os.environ.get("NAVER_CAFE_COOKIE") or "").strip()
        if self._naver_cookie:
            for part in self._naver_cookie.split(";"):
                part = part.strip()
                if "=" in part:
                    key, val = part.split("=", 1)
                    self.session.cookies.set(
                        key.strip(), val.strip(), domain=".naver.com"
                    )

        # --- Naver proxy configuration ---
        self._naver_proxies = None
        proxy_url = (os.environ.get("NAVER_CAFE_PROXY_URL") or "").strip()
        proxy_user = (os.environ.get("NAVER_CAFE_PROXY_USERNAME") or "").strip()
        proxy_pass = (os.environ.get("NAVER_CAFE_PROXY_PASSWORD") or "").strip()
        if proxy_url:
            if proxy_user and proxy_pass and "@" not in proxy_url:
                parts = urlparse(proxy_url)
                if parts.scheme and parts.hostname:
                    auth_host = (
                        f"{parts.scheme}://{quote(proxy_user, safe='')}:{quote(proxy_pass, safe='')}@{parts.hostname}"
                    )
                    if parts.port:
                        auth_host += f":{parts.port}"
                    if parts.path:
                        auth_host += parts.path
                    proxy_url = auth_host
            self._naver_proxies = {"http": proxy_url, "https": proxy_url}

        self._naver_disable_ssl_verify = os.environ.get(
            "NAVER_CAFE_DISABLE_SSL_VERIFY", ""
        ).lower() in ("1", "true", "yes")
        if self._naver_disable_ssl_verify:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # --- Naver Search API credentials ---
        self._naver_search_client_id = (os.environ.get("NAVER_SEARCH_CLIENT_ID") or "").strip()
        self._naver_search_client_secret = (os.environ.get("NAVER_SEARCH_CLIENT_SECRET") or "").strip()

        # --- Reddit OAuth2 state ---
        self._reddit_client_id = (os.environ.get("REDDIT_CLIENT_ID") or "").strip()
        self._reddit_client_secret = (
            os.environ.get("REDDIT_CLIENT_SECRET") or ""
        ).strip()
        self._reddit_user_agent = (
            os.environ.get("REDDIT_USER_AGENT") or ""
        ).strip() or "sns-monitor/1.0 (Reddit URL analyzer)"
        self._reddit_token: Optional[str] = None
        self._reddit_token_expiry: float = 0

    # --- Properties for backward compatibility ---

    @property
    def naver_cookie(self):
        return self._naver_cookie

    @property
    def naver_proxies(self):
        return self._naver_proxies

    @property
    def naver_disable_ssl_verify(self):
        return self._naver_disable_ssl_verify

    @property
    def naver_search_client_id(self):
        return self._naver_search_client_id

    @property
    def naver_search_client_secret(self):
        return self._naver_search_client_secret

    @property
    def reddit_client_id(self):
        return self._reddit_client_id

    @property
    def reddit_user_agent(self):
        return self._reddit_user_agent

    # --- Naver request helper ---

    def naver_get(self, url, headers, timeout):
        """Make a GET request with Naver-specific proxy and SSL settings."""
        kwargs = {"headers": headers, "timeout": timeout}
        if self._naver_proxies:
            kwargs["proxies"] = self._naver_proxies
        if self._naver_disable_ssl_verify:
            kwargs["verify"] = False
        return self.session.get(url, **kwargs)

    # --- Reddit OAuth2 helpers ---

    def reddit_get_token(self, force_refresh: bool = False) -> Optional[str]:
        """Obtain Reddit OAuth2 access token (client credentials)."""
        if not self._reddit_client_id or not self._reddit_client_secret:
            return None
        if (
            not force_refresh
            and self._reddit_token
            and time.time() < self._reddit_token_expiry - 60
        ):
            return self._reddit_token
        try:
            auth = base64.b64encode(
                f"{self._reddit_client_id}:{self._reddit_client_secret}".encode()
            ).decode()
            r = self.session.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                headers={
                    "User-Agent": self._reddit_user_agent,
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            self._reddit_token = data.get("access_token")
            self._reddit_token_expiry = time.time() + int(data.get("expires_in", 3600))
            logger.debug("Reddit OAuth2 token refreshed, expires in %ss", data.get("expires_in", 3600))
            return self._reddit_token
        except Exception as e:
            logger.warning("Reddit OAuth2 token failed: %s", e)
            self._reddit_token = None
            self._reddit_token_expiry = 0
            return None

    def reddit_request(self, url, headers, params=None, timeout=15):
        """Make a Reddit API request with automatic token refresh on 401."""
        resp = self.session.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 401 and headers.get("Authorization"):
            logger.info("Reddit 401 — refreshing OAuth token and retrying")
            new_token = self.reddit_get_token(force_refresh=True)
            if new_token:
                headers = {**headers, "Authorization": f"Bearer {new_token}"}
                resp = self.session.get(url, params=params, headers=headers, timeout=timeout)
        return resp
