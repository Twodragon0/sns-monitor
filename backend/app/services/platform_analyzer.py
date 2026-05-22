"""
Multi-platform SNS content analyzer.
Detects platform from URL, fetches content, and provides analysis.
Supported: YouTube, DCInside, Reddit, Telegram, Kakao, X (Twitter)
"""

import json
import os
import re
import logging
import threading
from contextlib import contextmanager
from typing import Any, Optional
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
from collections import Counter

import ipaddress
import socket

import requests


# ---------------------------------------------------------------------------
# DNS-pinning for SSRF protection (DNS rebinding mitigation).
# The hostname is resolved and validated once; subsequent socket lookups for
# that hostname within the pinned scope return the validated IP so a malicious
# authoritative DNS server cannot swap to an internal IP between validation
# and the actual HTTP connection (TOCTOU rebinding).
# ---------------------------------------------------------------------------
_pinning_state = threading.local()
_orig_getaddrinfo = socket.getaddrinfo


def _pinned_getaddrinfo(host, port, *args, **kwargs):
    pinned = getattr(_pinning_state, "map", None)
    if pinned and host in pinned:
        # Delegate to the real getaddrinfo using the pinned IP literal. This
        # preserves the platform-correct sockaddr tuple shape (4-tuple for
        # AF_INET6) and honors caller-supplied family / socktype / proto /
        # flags arguments — a hand-fabricated tuple gets these wrong for IPv6
        # and breaks callers that pass non-default socket parameters.
        return _orig_getaddrinfo(pinned[host], port, *args, **kwargs)
    return _orig_getaddrinfo(host, port, *args, **kwargs)


# Install once. Falls through to original when no pin is active, so other
# code in the process is unaffected.
if socket.getaddrinfo is not _pinned_getaddrinfo:
    socket.getaddrinfo = _pinned_getaddrinfo


@contextmanager
def _pin_dns(host, ip):
    """Pin host -> ip for the duration of the context (thread-local)."""
    if not host or not ip:
        yield
        return
    cur = getattr(_pinning_state, "map", None) or {}
    _pinning_state.map = dict(cur, **{host: ip})
    try:
        yield
    finally:
        _pinning_state.map = cur

from .platforms import (
    YouTubeMixin, DCInsideMixin, NaverCafeMixin,
    RedditMixin, TwitterMixin, ThreadsMixin, OtherPlatformsMixin,
)
from .http_client import HttpClientService
from .sentiment_analyzer import SentimentAnalyzer
from .rate_limiter import RateLimiterService

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# Hostnames that must never be fetched (cloud metadata, localhost).
# Note: numeric IP addresses like 169.254.169.254 are already blocked by the
# IP-range check in _validate_url_host; only add hostnames here.
_BLOCKED_HOSTS = frozenset({
    'metadata.google.internal',
    'metadata.google.com',
    'fd00:ec2::254',
    '100.100.100.200',
    'metadata.azure.com',
})


class PlatformAnalyzer(
    YouTubeMixin, DCInsideMixin, NaverCafeMixin,
    RedditMixin, TwitterMixin, ThreadsMixin, OtherPlatformsMixin,
):
    """Analyze content from various SNS platforms given a URL."""

    PLATFORM_PATTERNS = {
        "youtube": [
            r"(?:youtube\.com|youtu\.be)",
        ],
        "dcinside": [
            r"gall\.dcinside\.com",
        ],
        "reddit": [
            r"(?:www\.)?reddit\.com",
            r"old\.reddit\.com",
        ],
        "telegram": [
            r"t\.me/",
        ],
        "kakao": [
            r"open\.kakao\.com",
            r"story\.kakao\.com",
            r"pf\.kakao\.com",
        ],
        "twitter": [
            r"(?:www\.)?(?:twitter\.com|x\.com)",
            r"mobile\.(?:twitter\.com|x\.com)",
        ],
        "naver_cafe": [
            r"cafe\.naver\.com",
        ],
        "instagram": [
            r"(?:www\.)?instagram\.com",
        ],
        "facebook": [
            r"(?:www\.)?(?:facebook\.com|fb\.com|fb\.watch)",
        ],
        "threads": [
            r"(?:www\.)?threads\.net",
            r"(?:www\.)?threads\.com",
        ],
        "tiktok": [
            r"(?:www\.)?tiktok\.com",
            r"vm\.tiktok\.com",
        ],
        "vuddy": [
            r"(?:www\.)?vuddy\.io",
        ],
    }

    def __init__(self, data_dir="/app/local-data"):
        self.data_dir = data_dir

        # Delegate session creation and configuration to HttpClientService
        self._http = HttpClientService()

        # BACKWARDS COMPATIBLE: Mixins continue using self._session unchanged
        self._session = self._http.session

        # Expose Naver config via the service (thin references for backward compat)
        self._naver_cookie = self._http.naver_cookie
        self._naver_proxies = self._http.naver_proxies
        self._naver_disable_ssl_verify = self._http.naver_disable_ssl_verify
        self._naver_search_client_id = self._http.naver_search_client_id
        self._naver_search_client_secret = self._http.naver_search_client_secret

        # Rate limit tracking for Naver Open API (25,000 calls/day)
        self._naver_api_daily_limit = 25000
        self._naver_api_call_count = 0
        self._naver_api_count_date = ""
        self._redis = None
        try:
            from .redis_client import get_redis
            self._redis = get_redis()
        except Exception as e:
            logger.debug("Redis client unavailable in PlatformAnalyzer: %s", e)
        self._rate_limiter = RateLimiterService(self._redis)

        # Expose Reddit config via the service (thin references for backward compat)
        self._reddit_client_id = self._http.reddit_client_id
        self._reddit_client_secret = self._http._reddit_client_secret
        self._reddit_user_agent = self._http.reddit_user_agent
        self._reddit_token: Optional[str] = None
        self._reddit_token_expiry: float = 0
        self._sentiment = SentimentAnalyzer()

    def _reddit_get_token(self, force_refresh: bool = False) -> Optional[str]:
        """Obtain Reddit OAuth2 access token (client credentials).

        Delegates to HttpClientService while keeping token state synchronized.
        """
        # Sync local token state to the service before requesting
        self._http._reddit_token = self._reddit_token
        self._http._reddit_token_expiry = self._reddit_token_expiry
        token = self._http.reddit_get_token(force_refresh=force_refresh)
        # Sync token state back from service
        self._reddit_token = self._http._reddit_token
        self._reddit_token_expiry = self._http._reddit_token_expiry
        return token

    def _reddit_request(self, url, headers, params=None, timeout=15):
        """Make a Reddit API request with automatic token refresh on 401 and rate tracking."""
        self._rate_incr("reddit")
        # Sync token state to service before the request
        self._http._reddit_token = self._reddit_token
        self._http._reddit_token_expiry = self._reddit_token_expiry
        resp = self._http.reddit_request(url, headers, params=params, timeout=timeout)
        # Sync token state back from service
        self._reddit_token = self._http._reddit_token
        self._reddit_token_expiry = self._http._reddit_token_expiry
        return resp

    def _naver_get(self, url, headers, timeout):
        """Make a Naver GET request with proxy and SSL settings.

        Reads from self._naver_proxies / self._naver_disable_ssl_verify so that
        tests can override these attributes directly on the analyzer instance.
        """
        kwargs = {"headers": headers, "timeout": timeout}
        if self._naver_proxies:
            kwargs["proxies"] = self._naver_proxies
        if self._naver_disable_ssl_verify:
            kwargs["verify"] = False
        return self._session.get(url, **kwargs)

    def _append_naver_fetch_reason(self, reason_list, default_reason, err):
        if isinstance(err, requests.exceptions.SSLError):
            reason_list.append("ssl_verify_failed")
            return
        reason_list.append(default_reason)

    @staticmethod
    def _validate_url_host(url):
        """Block requests to private/internal/metadata addresses (SSRF protection).

        Returns ``(hostname, primary_ip)`` so callers can pin the resolved IP
        and prevent DNS-rebinding (TOCTOU) where a second resolution returns
        a different IP. Backward compatible: callers ignoring the return get
        the same raise-on-bad-host behavior as before.
        """
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid URL: missing hostname")
        if hostname in _BLOCKED_HOSTS:
            raise ValueError("Blocked host")
        # Pin map is empty during validation (we populate it after this returns),
        # so socket.getaddrinfo falls through to the real resolver via our hook.
        try:
            addr_infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            raise ValueError("Cannot resolve hostname")
        if not addr_infos:
            raise ValueError("Cannot resolve hostname")
        primary_ip = None
        for family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    raise ValueError("Internal addresses not allowed")
            except ValueError as ve:
                if "Internal" in str(ve) or "Blocked" in str(ve):
                    raise
                raise ValueError("Internal addresses not allowed")
            if primary_ip is None:
                primary_ip = ip_str
        return hostname, primary_ip

    def detect_platform(self, url):
        """Detect which platform a URL belongs to by matching against parsed hostname."""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        full = f"{hostname}{parsed.path or ''}"
        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, full, re.IGNORECASE):
                    return platform
        return None

    def analyze(self, url, options=None):
        """Main entry point: detect platform and analyze content.
        options: dict with platform-specific flags (e.g. fetch_comments, max_comments).
        """
        # Validate now and capture the resolved IP; pin it for the request scope
        # so a malicious authoritative DNS cannot rebind to an internal IP.
        validated = self._validate_url_host(url)
        pinned_host, pinned_ip = (validated if isinstance(validated, tuple) else (None, None))

        platform = self.detect_platform(url)
        if not platform:
            raise ValueError(
                f"Unsupported platform. Supported: {', '.join(self.PLATFORM_PATTERNS.keys())}"
            )

        handler = getattr(self, f"_analyze_{platform}", None)
        if not handler:
            raise ValueError(f"Analyzer not implemented for: {platform}")

        self._analyze_options = options or {}
        with _pin_dns(pinned_host, pinned_ip):
            result = handler(url)
        result["platform"] = platform
        result["source_url"] = url
        result["analyzed_at"] = datetime.now(KST).isoformat()

        # Add sentiment analysis
        items = self._collect_sentiment_items(platform, result)
        if items:
            result["analysis"] = self._analyze_sentiment(items)

        # Save result
        self._save_result(platform, url, result)
        return result

    def list_platforms(self):
        """List all supported platforms with example URLs."""
        return [
            {
                "name": "YouTube",
                "id": "youtube",
                "examples": [
                    "https://www.youtube.com/watch?v=VIDEO_ID",
                    "https://www.youtube.com/@CHANNEL_HANDLE",
                    "https://youtu.be/VIDEO_ID",
                ],
                "description": "Video comments and channel analysis",
            },
            {
                "name": "DCInside",
                "id": "dcinside",
                "examples": [
                    "https://gall.dcinside.com/mini/board/lists?id=GALLERY_ID",
                    "https://gall.dcinside.com/mgallery/board/lists/?id=GALLERY_ID",
                    "https://gall.dcinside.com/board/view/?id=GALLERY_ID&no=POST_NO",
                ],
                "description": "Gallery list or single post: analysis, stats, content, comments",
            },
            {
                "name": "Reddit",
                "id": "reddit",
                "examples": [
                    "https://www.reddit.com/r/SUBREDDIT/",
                    "https://www.reddit.com/r/SUBREDDIT/comments/POST_ID/title/",
                ],
                "description": "Subreddit posts and comment analysis",
            },
            {
                "name": "Telegram",
                "id": "telegram",
                "examples": [
                    "https://t.me/CHANNEL_NAME",
                    "https://t.me/s/CHANNEL_NAME",
                ],
                "description": "Public channel messages",
            },
            {
                "name": "Kakao",
                "id": "kakao",
                "examples": [
                    "https://pf.kakao.com/PROFILE_ID",
                    "https://story.kakao.com/PROFILE_ID",
                ],
                "description": "Kakao profile and story analysis",
            },
            {
                "name": "X (Twitter)",
                "id": "twitter",
                "examples": [
                    "https://x.com/USERNAME",
                    "https://twitter.com/USERNAME",
                    "https://x.com/USERNAME/status/TWEET_ID",
                ],
                "description": "Profile info and recent posts analysis",
            },
            {
                "name": "Naver Cafe",
                "id": "naver_cafe",
                "examples": [
                    "https://cafe.naver.com/f-e/cafes/31093618/menus/0?viewType=L",
                    "https://cafe.naver.com/ArticleList.nhn?search.clubid=CLUB_ID",
                ],
                "description": "Cafe article list: title, author, date, link (same UI as DCInside)",
            },
            {
                "name": "TikTok",
                "id": "tiktok",
                "examples": [
                    "https://www.tiktok.com/@USERNAME",
                    "https://www.tiktok.com/@USERNAME/video/VIDEO_ID",
                ],
                "description": "TikTok profile or video info via oEmbed API",
            },
        ]

    # --- Unified rate limit helpers (thin wrappers around RateLimiterService) ---
    # API limits: YouTube 10,000 quota/day, Reddit 600 req/10min, Naver 25,000/day

    def _sync_rate_limiter_redis(self):
        """Keep RateLimiterService in sync with self._redis (supports test injection)."""
        self._rate_limiter._redis = self._redis

    def _rate_window(self, service):
        """Return the current window key for the given service."""
        self._sync_rate_limiter_redis()
        return self._rate_limiter.window(service)

    def _rate_get(self, service):
        """Get current call count for a service."""
        self._sync_rate_limiter_redis()
        return self._rate_limiter.get(service)

    def _rate_incr(self, service):
        """Increment call count for a service."""
        self._sync_rate_limiter_redis()
        self._rate_limiter.increment(service)

    def _rate_check(self, service):
        """Check if service is within rate limit. Returns (allowed, count, limit)."""
        limit = self._rate_limiter._API_LIMITS.get(service, {}).get("limit", 999999)
        count = self._rate_get(service)
        return count < limit, count, limit

    # Backwards-compatible aliases for Naver
    def _get_naver_api_count(self, _date_str=None):
        return self._rate_get("naver_search")

    def _incr_naver_api_count(self, _date_str=None):
        self._rate_incr("naver_search")

    def get_api_usage(self):
        """Return API usage stats for all rate-limited services."""
        self._sync_rate_limiter_redis()
        yt_key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
        return self._rate_limiter.get_usage(
            naver_configured=bool(self._naver_search_client_id),
            youtube_configured=bool(yt_key) and yt_key.lower() not in ("your_youtube_api_key_here",),
            reddit_configured=bool(self._reddit_client_id),
        )

    # Platform-specific methods are provided by mixins:
    # YouTubeMixin, DCInsideMixin, NaverCafeMixin, RedditMixin,
    # TwitterMixin, ThreadsMixin, OtherPlatformsMixin

    # ==========================================
    # Sentiment Analysis
    # ==========================================
    def _collect_sentiment_items(self, platform, result):
        """Collect flat list of text items for sentiment (post content + comments)."""
        if platform == "dcinside":
            if result.get("type") == "post":
                items = []
                content = (result.get("content") or "").strip()
                if content:
                    items.append({"text": content})
                items.extend(result.get("comments", []))
                return items
            if result.get("type") == "gallery":
                items = []
                for post in result.get("posts", []):
                    if post.get("text"):
                        items.append({"text": post["text"]})
                    for c in post.get("comments", []):
                        if c.get("text"):
                            items.append(c)
                return items
        if platform == "naver_cafe" and result.get("type") == "gallery":
            items = []
            for post in result.get("posts", []):
                if post.get("text"):
                    items.append({"text": post["text"]})
                for c in post.get("comments", []):
                    if c.get("text"):
                        items.append(c)
            return items
        if platform == "threads" and result.get("type") == "post":
            items = []
            content = (result.get("content") or result.get("description") or "").strip()
            if content:
                items.append({"text": content})
            items.extend(result.get("replies", []))
            return items
        if "comments" in result or "posts" in result:
            return result.get("comments", result.get("posts", []))
        if "replies" in result:
            return result.get("replies", [])
        return []

    def _analyze_sentiment(self, items):
        """Analyze sentiment distribution from text items. Delegates to SentimentAnalyzer."""
        return self._sentiment.analyze(items)

    # Backwards-compatible class-level Kiwi singleton.
    # Tests access PlatformAnalyzer._kiwi directly; keeping it here avoids
    # breaking those tests while SentimentAnalyzer manages its own singleton.
    _kiwi = None

    @classmethod
    def _get_kiwi(cls):
        """Return Kiwi instance, lazy-loading and caching on PlatformAnalyzer."""
        if cls._kiwi is None:
            try:
                from kiwipiepy import Kiwi
                from .sentiment_analyzer import SentimentAnalyzer as _SA
                kiwi = Kiwi()
                for word, tag in _SA._CUSTOM_WORDS:
                    try:
                        kiwi.add_user_word(word, tag)
                    except Exception as e:
                        logger.debug("Kiwi add_user_word failed for %r: %s", word, e)
                cls._kiwi = kiwi
                logger.info("Kiwi morphological analyzer loaded with %d custom words", len(_SA._CUSTOM_WORDS))
            except ImportError:
                logger.info("kiwipiepy not available, using regex keyword extraction")
                cls._kiwi = False
        return cls._kiwi if cls._kiwi is not False else None

    def _extract_keywords(self, text):
        """Delegates to SentimentAnalyzer._extract_keywords."""
        return self._sentiment._extract_keywords(text)

    # ==========================================
    # Save Results
    # ==========================================
    def _save_result(self, platform, url, result):
        """Save analysis result to local data directory."""
        try:
            save_dir = os.path.join(self.data_dir, "analysis", platform)
            os.makedirs(save_dir, exist_ok=True)

            timestamp = datetime.now(KST).strftime("%Y-%m-%d-%H-%M-%S")
            # Create safe filename from URL
            safe_name = re.sub(r"[^\w\-.]", "_", urlparse(url).path.strip("/"))[:50]
            filename = f"{safe_name}_{timestamp}.json"

            filepath = os.path.join(save_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)

            logger.info("Saved analysis result: %s", filepath)
        except Exception as e:
            logger.warning("Failed to save result: %s", e)
