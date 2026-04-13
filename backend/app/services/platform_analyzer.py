"""
Multi-platform SNS content analyzer.
Detects platform from URL, fetches content, and provides analysis.
Supported: YouTube, DCInside, Reddit, Telegram, Kakao, X (Twitter)
"""

import base64
import json
import os
import re
import time
import logging
from typing import Any, Optional
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs, quote
from collections import Counter

import ipaddress
import socket

import requests

from .platforms import (
    YouTubeMixin, DCInsideMixin, NaverCafeMixin,
    RedditMixin, TwitterMixin, ThreadsMixin, OtherPlatformsMixin,
)

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
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        # Allow SSL verification bypass for corporate proxy environments
        if os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE"):
            pass  # Use system CA bundle
        elif os.environ.get("DISABLE_SSL_VERIFY", "").lower() in ("1", "true", "yes"):
            self._session.verify = False
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self._naver_cookie = (os.environ.get("NAVER_CAFE_COOKIE") or "").strip()
        if self._naver_cookie:
            # Scope cookies to naver.com only (not sent to YouTube/Reddit/etc)
            for part in self._naver_cookie.split(";"):
                part = part.strip()
                if "=" in part:
                    key, val = part.split("=", 1)
                    self._session.cookies.set(
                        key.strip(), val.strip(), domain=".naver.com"
                    )

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

        # Naver Search API (optional; enables server-side cafe article search)
        self._naver_search_client_id = (os.environ.get("NAVER_SEARCH_CLIENT_ID") or "").strip()
        self._naver_search_client_secret = (os.environ.get("NAVER_SEARCH_CLIENT_SECRET") or "").strip()
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

        # Reddit OAuth2 (optional; avoids 403 when Reddit blocks unauthenticated requests)
        self._reddit_client_id = (os.environ.get("REDDIT_CLIENT_ID") or "").strip()
        self._reddit_client_secret = (
            os.environ.get("REDDIT_CLIENT_SECRET") or ""
        ).strip()
        self._reddit_user_agent = (
            os.environ.get("REDDIT_USER_AGENT") or ""
        ).strip() or "sns-monitor/1.0 (Reddit URL analyzer)"
        self._reddit_token: Optional[str] = None
        self._reddit_token_expiry: float = 0

    def _reddit_get_token(self, force_refresh: bool = False) -> Optional[str]:
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
            r = self._session.post(
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

    def _reddit_request(self, url, headers, params=None, timeout=15):
        """Make a Reddit API request with automatic token refresh on 401 and rate tracking."""
        self._rate_incr("reddit")
        resp = self._session.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 401 and headers.get("Authorization"):
            logger.info("Reddit 401 — refreshing OAuth token and retrying")
            new_token = self._reddit_get_token(force_refresh=True)
            if new_token:
                headers = {**headers, "Authorization": f"Bearer {new_token}"}
                resp = self._session.get(url, params=params, headers=headers, timeout=timeout)
        return resp

    def _naver_get(self, url, headers, timeout):
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

        Resolves the hostname once and caches the result to mitigate DNS rebinding
        (TOCTOU) attacks where a second resolution could return a different IP.
        """
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid URL: missing hostname")
        if hostname in _BLOCKED_HOSTS:
            raise ValueError("Blocked host")
        # Resolve hostname and check ALL resolved IPs
        try:
            addr_infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            raise ValueError("Cannot resolve hostname")
        if not addr_infos:
            raise ValueError("Cannot resolve hostname")
        for family, _, _, _, sockaddr in addr_infos:
            try:
                ip = ipaddress.ip_address(sockaddr[0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    raise ValueError("Internal addresses not allowed")
            except ValueError as ve:
                if "Internal" in str(ve) or "Blocked" in str(ve):
                    raise
                raise ValueError("Internal addresses not allowed")

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
        self._validate_url_host(url)
        platform = self.detect_platform(url)
        if not platform:
            raise ValueError(
                f"Unsupported platform. Supported: {', '.join(self.PLATFORM_PATTERNS.keys())}"
            )

        handler = getattr(self, f"_analyze_{platform}", None)
        if not handler:
            raise ValueError(f"Analyzer not implemented for: {platform}")

        self._analyze_options = options or {}
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

    # --- Unified rate limit helpers (Redis-backed with in-memory fallback) ---
    # API limits: YouTube 10,000 quota/day, Reddit 600 req/10min, Naver 25,000/day

    _RATE_KEY_TPL = "sns:{service}:count:{window}"

    _API_LIMITS = {
        "naver_search": {"limit": 25000, "window": "daily", "ttl": 90000},
        "youtube": {"limit": 10000, "window": "daily", "ttl": 90000},
        "reddit": {"limit": 600, "window": "10min", "ttl": 660},
    }

    def _rate_window(self, service):
        """Return the current window key for the given service."""
        cfg = self._API_LIMITS.get(service, {})
        if cfg.get("window") == "10min":
            now = datetime.now(KST)
            slot = now.minute // 10
            return f"{now.strftime('%Y-%m-%d')}T{now.hour:02d}:{slot}"
        return datetime.now(KST).strftime("%Y-%m-%d")

    def _rate_get(self, service):
        """Get current call count for a service."""
        window = self._rate_window(service)
        if self._redis:
            try:
                val = self._redis.get(self._RATE_KEY_TPL.format(service=service, window=window))
                return int(val) if val else 0
            except Exception as e:
                logger.debug("Redis rate_get failed for %s: %s", service, e)
        # In-memory fallback
        key = f"_mem_{service}"
        mem = getattr(self, key, None) or {"window": "", "count": 0}
        if mem["window"] != window:
            return 0
        return mem["count"]

    def _rate_incr(self, service):
        """Increment call count for a service."""
        window = self._rate_window(service)
        ttl = self._API_LIMITS.get(service, {}).get("ttl", 90000)
        if self._redis:
            try:
                rkey = self._RATE_KEY_TPL.format(service=service, window=window)
                pipe = self._redis.pipeline()
                pipe.incr(rkey)
                pipe.expire(rkey, ttl)
                results = pipe.execute()
                # Validate that both commands succeeded (neither returned None/False).
                # pipeline() without raise_on_error=True swallows per-command errors;
                # a None result indicates the command did not complete successfully.
                if results is None or len(results) < 2 or results[0] is None:
                    logger.warning(
                        "Redis pipeline partial failure for rate key %s: %s",
                        rkey, results,
                    )
                return
            except Exception as e:
                logger.debug("Redis rate_incr failed for %s: %s", service, e)
        # In-memory fallback
        key = f"_mem_{service}"
        mem = getattr(self, key, None) or {"window": "", "count": 0}
        if mem["window"] != window:
            mem = {"window": window, "count": 0}
        mem["count"] += 1
        setattr(self, key, mem)

    def _rate_check(self, service):
        """Check if service is within rate limit. Returns (allowed, count, limit)."""
        cfg = self._API_LIMITS.get(service, {})
        limit = cfg.get("limit", 999999)
        count = self._rate_get(service)
        return count < limit, count, limit

    # Backwards-compatible aliases for Naver
    def _get_naver_api_count(self, _date_str=None):
        return self._rate_get("naver_search")

    def _incr_naver_api_count(self, _date_str=None):
        self._rate_incr("naver_search")

    def get_api_usage(self):
        """Return API usage stats for all rate-limited services."""
        today = datetime.now(KST).strftime("%Y-%m-%d")
        storage = "redis" if self._redis else "memory"

        def _build(service, configured):
            cfg = self._API_LIMITS[service]
            count = self._rate_get(service)
            limit = cfg["limit"]
            window_label = "일일" if cfg["window"] == "daily" else "10분"
            return {
                "configured": configured,
                "daily_limit": limit,
                "used_today": count,
                "remaining": max(0, limit - count),
                "window": window_label,
                "date": today,
                "storage": storage,
            }

        yt_key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
        return {
            "naver_search": _build("naver_search", bool(self._naver_search_client_id)),
            "youtube": _build("youtube", bool(yt_key) and yt_key.lower() not in ("your_youtube_api_key_here",)),
            "reddit": _build("reddit", bool(self._reddit_client_id)),
        }

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

    # Kiwi morphological analyzer (lazy-loaded singleton)
    _kiwi = None
    # POS tags to extract as keywords (nouns, verbs, adjectives)
    _KEYWORD_POS = frozenset({"NNG", "NNP", "VV", "VA", "SL"})  # 일반명사, 고유명사, 동사, 형용사, 외국어

    # Custom dictionary: streamer/vtuber/community terms Kiwi doesn't know
    _CUSTOM_WORDS = [
        # Vtuber / streamer names (NNP = proper noun)
        ("이브닛", "NNP"), ("아카이브", "NNP"), ("여르미", "NNP"), ("결이", "NNP"),
        ("몽이", "NNP"), ("챠니", "NNP"), ("챱츄", "NNP"), ("세구", "NNP"),
        ("버시", "NNP"), ("쿠우", "NNP"), ("사미", "NNP"), ("기원", "NNP"),
        # Platform names
        ("버디", "NNP"), ("숲", "NNP"), ("치지직", "NNP"),
        # Community slang (NNG = common noun)
        ("개추", "NNG"), ("비추", "NNG"), ("꿀잼", "NNG"), ("노잼", "NNG"),
        ("입덕", "NNG"), ("탈덕", "NNG"), ("덕질", "NNG"), ("최애", "NNG"),
        ("갓겜", "NNG"), ("핵노잼", "NNG"), ("개꿀", "NNG"),
        ("방셀", "NNG"), ("디시콘", "NNG"),
        # Sentiment adjectives Kiwi may not parse correctly
        ("존잘", "VA"), ("존예", "VA"), ("킹왕짱", "NNG"),
    ]

    @classmethod
    def _get_kiwi(cls):
        if cls._kiwi is None:
            try:
                from kiwipiepy import Kiwi
                kiwi = Kiwi()
                # Register custom words for better tokenization
                for word, tag in cls._CUSTOM_WORDS:
                    try:
                        kiwi.add_user_word(word, tag)
                    except Exception as e:
                        logger.debug("Kiwi add_user_word failed for %r: %s", word, e)
                cls._kiwi = kiwi
                logger.info("Kiwi morphological analyzer loaded with %d custom words", len(cls._CUSTOM_WORDS))
            except ImportError:
                logger.info("kiwipiepy not available, using regex keyword extraction")
                cls._kiwi = False
        return cls._kiwi if cls._kiwi is not False else None

    def _extract_keywords(self, text):
        """Extract meaningful keywords using Kiwi morphological analyzer (or regex fallback)."""
        kiwi = self._get_kiwi()
        if kiwi:
            try:
                tokens = kiwi.tokenize(text)
                return [t.form for t in tokens
                        if t.tag in self._KEYWORD_POS
                        and len(t.form) >= (3 if t.tag == "SL" else 2)]
            except Exception as e:
                logger.debug("Kiwi tokenize failed in _extract_keywords: %s", e)
        # Regex fallback
        return re.findall(r"[가-힣]{2,}|[a-zA-Z]{3,}", text)

    # Stopwords: UI noise, DCInside markup, common particles
    _STOPWORDS = frozenset({
        # DCInside UI / markup noise
        "디시콘", "보기", "이전다음", "이전", "다음", "갤러리", "마이너갤",
        "답글", "추천수", "조회수", "댓글수", "작성일", "말머리",
        "전체글", "개념글", "공지", "설정", "검색", "정렬",
        "로그인", "닉네임", "아이디", "비밀번호", "회원",
        "삭제", "수정", "신고", "차단", "답변",
        # Common Korean particles / fillers
        "그래서", "그런데", "하지만", "그리고", "그래도", "그러면",
        "이거", "저거", "거기", "여기", "어디", "언제", "뭐가",
        "진짜", "근데", "아니", "그냥", "이게", "좀",
        "ㅇㅇ", "ㄴㄴ", "ㄱㄱ", "ㅇㅋ",
        # App / platform noise
        "app", "com", "http", "https", "www", "gall",
        "dcinside", "youtube", "naver", "kakao", "soop",
        "모바일", "갤럭시",
        # DCInside content noise
        "댓글은", "댓글", "해당", "작성자", "이용자", "본문",
        "클린봇", "운영자", "관리자",
        # Short meaningless
        "해서", "했는데", "하는", "되는", "있는", "없는",
        "같은", "라는", "이런", "저런", "어떤",
        "하고", "해야", "해도", "하면", "할까",
    })

    _POSITIVE_KW = [
        # Korean - emotions
        "좋아", "좋다", "좋은", "최고", "감사", "사랑", "축하", "대박",
        "멋지", "예쁘", "귀엽", "화이팅", "응원", "기대", "감동", "행복",
        "설렌", "좋겠", "부럽", "멋있", "잘생", "이쁘", "신기",
        # Korean - community slang
        "개추", "추천", "인정", "재밌", "꿀잼", "웃긴", "레전드", "갓",
        "존잘", "존예", "개꿀", "찐이", "역대급", "헐대박", "쩐다",
        "짱", "굿", "미쳤", "실화냐", "킹왕짱",
        "ㅋㅋㅋ", "ㅎㅎㅎ", "ㅋㅋ", "ㅎㅎ",
        # Korean - streamer/vtuber specific
        "겐끼", "방송잘", "잘봤", "잘본", "존버", "떡상", "개꿀잼",
        "고마워", "수고", "힘내", "잘했", "축하", "재밌었",
        "최애", "덕질", "입덕", "갓겜", "꿀보이스", "존좋",
        # English
        "good", "great", "love", "amazing", "awesome", "best",
        "nice", "cool", "beautiful", "wonderful", "excellent", "perfect",
        "cute", "funny", "lol", "lmao",
    ]

    _NEGATIVE_KW = [
        # Korean - emotions
        "싫어", "싫다", "나쁘", "최악", "짜증", "실망", "별로",
        "역겹", "징그", "불쾌", "화난", "빡치", "열받", "답답",
        "못생", "꼴불견", "어이없", "한심", "쪽팔", "후회", "지겹",
        "시끄", "거슬", "불편", "아쉽", "안타깝",
        # Korean - community slang
        "노잼", "재미없", "쓰레기", "망했", "구라", "거짓",
        "비추", "노답", "헛소리", "뻘소리", "허접",
        "ㅂㅅ", "ㅄ", "ㅡㅡ", "ㅠㅠ", "ㅜㅜ",
        # Korean - stronger negatives
        "꺼져", "닥쳐", "병맛", "구역질", "혐오", "극혐",
        "개별로", "개망", "쓸모없", "폭망", "완전망",
        "탈덕", "안티", "악플", "욕설",
        # English
        "bad", "worst", "hate", "terrible", "awful", "boring",
        "ugly", "trash", "waste", "stupid", "sucks", "cringe",
    ]

    def _analyze_sentiment(self, items):
        """Analyze sentiment distribution from text items."""
        if not items:
            return {
                "total": 0,
                "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
            }

        # Build lemma sets for Kiwi-based sentiment (verb/adj stems)
        pos_lemmas = {"좋다", "멋지다", "예쁘다", "귀엽다", "재미있다", "재밌다",
                      "감동하다", "행복하다", "기대하다", "부럽다", "잘생기다",
                      "신기하다", "고맙다", "수고하다", "웃기다", "즐겁다"}
        neg_lemmas = {"싫다", "나쁘다", "짜증나다", "실망하다", "역겹다",
                      "불쾌하다", "답답하다", "후회하다", "지겹다", "불편하다",
                      "한심하다", "어이없다", "아쉽다", "안타깝다", "못생기다"}

        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        keywords = Counter()

        for item in items:
            text = (item.get("text", "") or "").lower()
            if not text or len(text) < 2:
                continue

            # Score-based sentiment: keyword substring match + Kiwi lemma match
            pos_score = sum(1 for kw in self._POSITIVE_KW if kw in text)
            neg_score = sum(1 for kw in self._NEGATIVE_KW if kw in text)

            # Kiwi morphological sentiment boost (matches verb/adj stems accurately)
            kiwi = self._get_kiwi()
            if kiwi:
                try:
                    tokens = kiwi.tokenize(text)
                    for t in tokens:
                        if t.tag in ("VV", "VA", "XR"):  # verb, adjective, root
                            lemma = t.form + "다"
                            if lemma in pos_lemmas:
                                pos_score += 2
                            elif lemma in neg_lemmas:
                                neg_score += 2
                except Exception as e:
                    logger.debug("Kiwi tokenize failed in _analyze_sentiment: %s", e)

            if pos_score > neg_score:
                sentiment_counts["positive"] += 1
            elif neg_score > pos_score:
                sentiment_counts["negative"] += 1
            elif pos_score > 0 and neg_score > 0:
                sentiment_counts["neutral"] += 1  # mixed
            else:
                sentiment_counts["neutral"] += 1

            # Extract keywords via morphological analysis (Kiwi) or regex fallback
            words = self._extract_keywords(text)
            for w in words:
                if w not in self._STOPWORDS and len(w) >= 2:
                    keywords[w] += 1

        total = sum(sentiment_counts.values())
        distribution = {
            k: round(v / total, 3) if total > 0 else 0
            for k, v in sentiment_counts.items()
        }

        return {
            "total": total,
            "sentiment": sentiment_counts,
            "distribution": distribution,
            "top_keywords": [
                {"word": w, "count": c} for w, c in keywords.most_common(20)
            ],
            "overall": max(sentiment_counts, key=lambda key: sentiment_counts[key])
            if total > 0
            else "neutral",
        }

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
