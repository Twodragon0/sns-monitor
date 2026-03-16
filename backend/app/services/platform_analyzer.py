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

import requests

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# Hostnames that must never be fetched (cloud metadata, localhost)
_BLOCKED_HOSTS = frozenset({
    'metadata.google.internal',
    'metadata.google.com',
})


class PlatformAnalyzer:
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
            self._session.headers.update({"Cookie": self._naver_cookie})

        self._naver_proxies = None
        proxy_url = (os.environ.get("NAVER_CAFE_PROXY_URL") or "").strip()
        proxy_user = (os.environ.get("NAVER_CAFE_PROXY_USERNAME") or "").strip()
        proxy_pass = (os.environ.get("NAVER_CAFE_PROXY_PASSWORD") or "").strip()
        if proxy_url:
            if proxy_user and proxy_pass and "@" not in proxy_url:
                parts = urlparse(proxy_url)
                if parts.scheme and parts.hostname:
                    auth_host = (
                        f"{parts.scheme}://{proxy_user}:{proxy_pass}@{parts.hostname}"
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
        """Make a Reddit API request with automatic token refresh on 401."""
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
        """Block requests to private/internal/metadata addresses (SSRF protection)."""
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid URL: missing hostname")
        if hostname in _BLOCKED_HOSTS:
            raise ValueError("Blocked host")
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("Internal addresses not allowed")
        except ValueError as ve:
            if "Internal" in str(ve) or "Blocked" in str(ve):
                raise
            # Not an IP literal — hostname is fine

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

    def analyze(self, url):
        """Main entry point: detect platform and analyze content."""
        self._validate_url_host(url)
        platform = self.detect_platform(url)
        if not platform:
            raise ValueError(
                f"Unsupported platform. Supported: {', '.join(self.PLATFORM_PATTERNS.keys())}"
            )

        handler = getattr(self, f"_analyze_{platform}", None)
        if not handler:
            raise ValueError(f"Analyzer not implemented for: {platform}")

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

    # ==========================================
    # YouTube Analyzer
    # ==========================================
    def _analyze_youtube(self, url):
        """Analyze YouTube video or channel."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Extract video ID
        video_id = None
        if "v" in params:
            video_id = params["v"][0]
        elif parsed.hostname and "youtu.be" in parsed.hostname:
            video_id = parsed.path.strip("/")

        # Extract channel handle
        channel_handle = None
        if "/@" in url or "/@" in parsed.path:
            match = re.search(r"/@([^/?]+)", url)
            if match:
                channel_handle = f"@{match.group(1)}"

        api_key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
        # Reject placeholder so we never send it to Google or leak it in errors
        if not api_key or api_key.lower() in (
            "your_youtube_api_key_here",
            "your-youtube-api-key",
            "",
        ):
            raise ValueError(
                "YouTube API key is not configured. Set YOUTUBE_API_KEY in .env with a key from "
                "https://console.cloud.google.com/apis/credentials"
            )

        if video_id:
            return self._analyze_youtube_video(video_id, api_key)
        elif channel_handle:
            return self._analyze_youtube_channel(channel_handle, api_key)
        else:
            raise ValueError("Could not extract video ID or channel handle from URL")

    def _analyze_youtube_video(self, video_id, api_key):
        """Fetch video info and comments."""
        base = "https://www.googleapis.com/youtube/v3"

        # Get video details
        resp = self._session.get(
            f"{base}/videos",
            params={
                "part": "snippet,statistics",
                "id": video_id,
                "key": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            raise ValueError(f"Video not found: {video_id}")

        video = items[0]
        snippet = video["snippet"]
        stats = video.get("statistics", {})

        # Get comments
        comments = []
        try:
            resp = self._session.get(
                f"{base}/commentThreads",
                params={
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": 100,
                    "order": "relevance",
                    "textFormat": "plainText",
                    "key": api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            for item in resp.json().get("items", []):
                comment = item["snippet"]["topLevelComment"]["snippet"]
                comments.append(
                    {
                        "text": comment.get("textDisplay", ""),
                        "author": comment.get("authorDisplayName", ""),
                        "like_count": comment.get("likeCount", 0),
                        "published_at": comment.get("publishedAt", ""),
                        "video_id": video_id,
                        "video_title": snippet.get("title", ""),
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to fetch comments for {video_id}: {e}")

        return {
            "type": "video",
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "description": snippet.get("description", "")[:500],
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "comments": comments,
        }

    def _analyze_youtube_channel(self, channel_handle, api_key):
        """Fetch channel info and recent videos."""
        base = "https://www.googleapis.com/youtube/v3"
        handle = channel_handle.lstrip("@")

        # Get channel by handle
        resp = self._session.get(
            f"{base}/channels",
            params={
                "part": "snippet,statistics",
                "forHandle": handle,
                "key": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            raise ValueError(f"Channel not found: {channel_handle}")

        channel = items[0]
        stats = channel.get("statistics", {})

        # Get recent videos
        videos = []
        try:
            resp = self._session.get(
                f"{base}/search",
                params={
                    "part": "snippet",
                    "channelId": channel["id"],
                    "order": "date",
                    "maxResults": 10,
                    "type": "video",
                    "key": api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            for item in resp.json().get("items", []):
                videos.append(
                    {
                        "video_id": item["id"].get("videoId", ""),
                        "title": item["snippet"].get("title", ""),
                        "published_at": item["snippet"].get("publishedAt", ""),
                        "thumbnail": item["snippet"]
                        .get("thumbnails", {})
                        .get("medium", {})
                        .get("url", ""),
                    }
                )
        except Exception as e:
            logger.warning("Failed to fetch videos for %s: %s", channel_handle, e)

        # Optionally fetch comments for recent videos (channel-level comment view)
        comments = []
        # Limit to first N videos to avoid excessive API calls
        for video in videos[:5]:
            video_id = video.get("video_id")
            if not video_id:
                continue
            try:
                resp = self._session.get(
                    f"{base}/commentThreads",
                    params={
                        "part": "snippet",
                        "videoId": video_id,
                        "maxResults": 50,
                        "order": "relevance",
                        "textFormat": "plainText",
                        "key": api_key,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                for item in resp.json().get("items", []):
                    snippet = item["snippet"]["topLevelComment"]["snippet"]
                    comments.append(
                        {
                            "text": snippet.get("textDisplay", ""),
                            "author": snippet.get("authorDisplayName", ""),
                            "like_count": snippet.get("likeCount", 0),
                            "published_at": snippet.get("publishedAt", ""),
                            "video_id": video_id,
                            "video_title": video.get("title", ""),
                        }
                    )
            except Exception as e:
                logger.warning(
                    "Failed to fetch comments for channel %s video %s: %s",
                    channel_handle,
                    video_id,
                    e,
                )

        return {
            "type": "channel",
            "title": channel["snippet"].get("title", ""),
            "description": channel["snippet"].get("description", "")[:500],
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "thumbnail": channel["snippet"]
            .get("thumbnails", {})
            .get("high", {})
            .get("url", ""),
            "recent_videos": videos,
            # Aggregate collected comments across recent videos so frontend can
            # render channel-level comment list and sentiment analysis.
            "comment_count": len(comments),
            "comments": comments,
        }

    # ==========================================
    # DCInside Analyzer
    # ==========================================
    _DCINSIDE_URL_ALLOWED_HOST = re.compile(
        r"^https?://(?:www\.)?gall\.dcinside\.com/", re.I
    )
    _DCINSIDE_GALLERY_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
    _DCINSIDE_POST_NO_RE = re.compile(r"^\d+$")

    def _validate_dcinside_url(self, url):
        """Validate DCInside URL: only gall.dcinside.com, board/lists or board/view with id (and no)."""
        if not url or not isinstance(url, str):
            return False
        if not self._DCINSIDE_URL_ALLOWED_HOST.match(url):
            return False
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/")
        if "board/lists" in path:
            params = parse_qs(parsed.query)
            id_list = params.get("id", [])
            if len(id_list) != 1 or not self._DCINSIDE_GALLERY_ID_RE.match(id_list[0]):
                return False
            return True
        if "board/view" in path:
            params = parse_qs(parsed.query)
            id_list = params.get("id", [])
            no_list = params.get("no", [])
            if len(id_list) != 1 or not self._DCINSIDE_GALLERY_ID_RE.match(id_list[0]):
                return False
            if len(no_list) != 1 or not self._DCINSIDE_POST_NO_RE.match(no_list[0]):
                return False
            return True
        return False

    def _analyze_dcinside(self, url):
        """Analyze DCInside gallery list or single post view URL."""
        if not self._validate_dcinside_url(url):
            raise ValueError(
                "Invalid DCInside URL. Use gallery list or post view from gall.dcinside.com"
            )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        path = (parsed.path or "").lower()

        # Single post: board/view?id=...&no=...
        if "board/view" in path:
            gallery_id = params.get("id", [None])[0]
            no_list = params.get("no", [None])
            post_no = no_list[0] if no_list else None
            if gallery_id and post_no and str(post_no).isdigit():
                return self._analyze_dcinside_single_post(
                    gallery_id=gallery_id,
                    post_no=int(post_no),
                    url=url,
                )

        # Gallery list
        gallery_id = params.get("id", [None])[0]
        if not gallery_id:
            match = re.search(r"/board/lists/?\?.*id=([^&]+)", url)
            if match:
                gallery_id = match.group(1)

        if not gallery_id:
            raise ValueError("Could not extract gallery ID from URL")

        is_mini = "/mini/" in path
        is_mgallery = "/mgallery/" in path
        gallery_type = "mini" if is_mini else ("mgallery" if is_mgallery else "board")

        if is_mini:
            list_url_base = (
                f"https://gall.dcinside.com/mini/board/lists?id={gallery_id}"
            )
        elif is_mgallery:
            list_url_base = (
                f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}"
            )
        else:
            list_url_base = f"https://gall.dcinside.com/board/lists/?id={gallery_id}"

        headers = {
            "User-Agent": self._session.headers["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://gall.dcinside.com/",
        }
        posts = []
        gallery_name = gallery_id
        max_pages = 100
        try:
            from bs4 import BeautifulSoup

            for page_num in range(1, max_pages + 1):
                list_url = (
                    f"{list_url_base}&page={page_num}"
                    if page_num > 1
                    else list_url_base
                )
                resp = self._session.get(list_url, headers=headers, timeout=15)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                if page_num == 1:
                    title_el = soup.select_one(
                        ".title_head, .gall_titub h1, .board_name"
                    )
                    if title_el:
                        gallery_name = title_el.get_text(strip=True) or gallery_id

                rows = soup.select("tr.ub-content")
                if not rows:
                    rows = soup.select("tbody tr.gall_list_tr, tbody tr[class*='ub']")
                if not rows:
                    rows = [
                        r
                        for r in soup.select("tbody tr")
                        if r.select_one(".gall_tit a")
                    ]
                if not rows:
                    break

                for row in rows:
                    title_el = row.select_one(".gall_tit a")
                    if not title_el:
                        continue

                    num_el = row.select_one(".gall_num")
                    writer_el = row.select_one(".gall_writer")
                    date_el = row.select_one(".gall_date")
                    count_el = row.select_one(".gall_count")
                    recommend_el = row.select_one(".gall_recommend")
                    reply_num_el = row.select_one(".gall_tit .reply_num")

                    post_num = num_el.get_text(strip=True) if num_el else ""
                    if not post_num.isdigit():
                        continue

                    comment_count = 0
                    if reply_num_el:
                        reply_text = reply_num_el.get_text(strip=True) or ""
                        match = re.search(r"\[(\d+)\]", reply_text)
                        if match:
                            comment_count = int(match.group(1))

                    post_number = int(post_num)
                    post_url = self._build_dcinside_view_url(
                        gallery_type, gallery_id, post_number
                    )
                    author_text = ""
                    if writer_el:
                        author_text = writer_el.get(
                            "data-nick", ""
                        ) or writer_el.get_text(strip=True)
                    posts.append(
                        {
                            "text": title_el.get_text(strip=True),
                            "number": post_number,
                            "author": author_text,
                            "date": date_el.get("title", date_el.get_text(strip=True))
                            if date_el
                            else "",
                            "view_count": int(count_el.get_text(strip=True))
                            if count_el and count_el.get_text(strip=True).isdigit()
                            else 0,
                            "recommend": int(recommend_el.get_text(strip=True))
                            if recommend_el
                            and recommend_el.get_text(strip=True).lstrip("-").isdigit()
                            else 0,
                            "comment_count": comment_count,
                            "url": post_url,
                        }
                    )

                time.sleep(0.3)
        except ImportError:
            logger.warning("beautifulsoup4 not installed, using basic scraping")
        except Exception as e:
            logger.warning("DCInside scraping failed: %s", e)

        # Limit to avoid 502 when nginx/proxy timeout; each post may try Playwright (~25s)
        max_posts_with_comments = 5
        for i, post in enumerate(posts):
            if i >= max_posts_with_comments:
                break
            try:
                comments = self._fetch_dcinside_post_comments(
                    gallery_id, post["number"], gallery_type, headers
                )
                post["comments"] = comments if comments else []
                list_count = post.get("comment_count") or 0
                collected = len(post["comments"])
                if list_count > 0 and collected == 0:
                    logger.warning(
                        "DCInside post %s: list comment_count=%s but collected 0",
                        post.get("number"),
                        list_count,
                    )
            except Exception as e:
                logger.warning(
                    "DCInside comments for post %s: %s",
                    post.get("number"),
                    e,
                    exc_info=False,
                )

        return {
            "type": "gallery",
            "gallery_id": gallery_id,
            "gallery_name": gallery_name,
            "gallery_type": "mini"
            if is_mini
            else ("mgallery" if is_mgallery else "major"),
            "total_posts": len(posts),
            "posts": posts,
        }

    def _build_dcinside_view_url(self, gallery_type, gallery_id, post_no):
        if gallery_type in ("board", "major"):
            return f"https://gall.dcinside.com/board/view/?id={gallery_id}&no={post_no}"
        return f"https://gall.dcinside.com/{gallery_type}/board/view/?id={gallery_id}&no={post_no}"

    def _build_dcinside_comment_api_url(self, gallery_type):
        """Comment API base URL; mini/mgallery use type-prefixed path. 'major' => board."""
        if gallery_type in ("board", "major"):
            return "https://gall.dcinside.com/board/comment/"
        return f"https://gall.dcinside.com/{gallery_type}/board/comment/"

    # ==========================================
    # Naver Cafe Analyzer
    # ==========================================
    def _analyze_naver_cafe(self, url):
        """Analyze Naver Cafe: article list (same UI as DCInside gallery)."""
        if "cafe.naver.com" not in url.lower():
            raise ValueError("Invalid Naver Cafe URL. Use cafe.naver.com")

        parsed = urlparse(url)
        path = (parsed.path or "").strip("/")
        params = parse_qs(parsed.query)

        club_id = None
        menu_id = "0"
        search_query = (params.get("q") or params.get("query") or [None])[0]

        # Support /cafes/123, /menus/0 and f-e/cafes/123/menus/0, ca-fe/web/cafes/123
        cafe_match = re.search(
            r"(?:^|/)(?:f-e/)?(?:ca-fe/web/)?cafes/(\d+)(?:/menus/(\d+))?",
            path,
            re.IGNORECASE,
        )
        if cafe_match:
            club_id = cafe_match.group(1)
            lastindex = cafe_match.lastindex if cafe_match.lastindex is not None else 0
            if lastindex >= 2 and cafe_match.group(2):
                menu_id = cafe_match.group(2)
        if not club_id:
            club_id = (params.get("search.clubid") or params.get("clubid") or [None])[0]
            menu_id = (params.get("search.menuid") or params.get("menuid") or ["0"])[0]

        if not club_id or not re.match(r"^\d+$", str(club_id)):
            raise ValueError("Could not extract cafe (club) ID from URL")

        input_article_id = self._extract_naver_article_id(url)

        headers = {
            "User-Agent": self._session.headers["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://cafe.naver.com/",
        }

        if input_article_id:
            return self._analyze_naver_cafe_single_post(
                str(club_id), str(input_article_id), headers
            )

        cafe_name = f"카페 {club_id}"
        posts = []
        total_posts_estimate = None
        fetch_reasons = []

        # 1) Fetch the request URL to get cafe name and optional article list from HTML
        login_verified = False
        try:
            resp = self._naver_get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")
            html_lower = resp.text.lower()

            # 로그인 상태 추정: 쿠키가 있고, "로그인이 필요" 문구가 없고, 로그아웃/내카페/닉네임 등이 있으면 로그인된 것으로 간주
            if self._naver_cookie:
                if (
                    "로그인이 필요" not in resp.text
                    and "login" not in html_lower.split("로그인")[0][-50:]
                ):
                    if any(
                        x in resp.text
                        for x in ("로그아웃", "내카페", "내정보", "닉네임", "내 프로필")
                    ):
                        login_verified = True
                    else:
                        # 글 목록/본문이 보이면 로그인된 것으로 간주 (비로그인 시 빈 목록 또는 로그인 유도 페이지)
                        login_verified = bool(
                            soup.select_one("#cafe_content")
                            or soup.select_one('a[href*="/articles/"]')
                        )

            title_el = soup.select_one('title, meta[property="og:title"]')
            if title_el:
                raw_value = (
                    title_el.get("content")
                    if title_el.name == "meta"
                    else title_el.get_text(strip=True)
                )
                raw: str
                if isinstance(raw_value, str):
                    raw = raw_value
                elif isinstance(raw_value, list):
                    raw = str(raw_value[0]) if raw_value else ""
                else:
                    raw = str(raw_value or "")
                if raw:
                    cafe_name = (
                        re.sub(
                            r"\s*[\|\-]\s*네이버 카페.*", "", raw, flags=re.IGNORECASE
                        ).strip()
                        or cafe_name
                    )

            # 전체 글 수: "N개의 글" (BoardTopOption 등 새 UI 포함)
            count_el = soup.find(string=re.compile(r"[\d,]+\s*개의\s*글"))
            if count_el:
                num_str = re.sub(r"[^\d]", "", str(count_el))
                if num_str:
                    total_posts_estimate = int(num_str)

            # 새 카페 UI(f-e): script 태그에 임베드된 JSON에서 글 목록 추출
            if not posts:
                posts = self._extract_naver_cafe_posts_from_script_json(
                    resp.text, club_id
                )

            rows = soup.select(
                'tr.article-board-row, .article-board tbody tr, .board-list tr, [class*="article"] tr'
            )
            if not rows:
                rows = soup.select(
                    'div.article-board div[class*="list"], .list_content li, a.article'
                )
            # 새 네이버 카페 UI (Layout_CafeLayout, #cafe_content, BoardTopOption 아래 목록형/카드형)
            if not rows:
                cafe_content = soup.select_one("#cafe_content")
                if cafe_content:
                    seen_ids = set()
                    for link in cafe_content.select(
                        'a[href*="/articles/"], a[href*="ArticleRead"], a[href*="articleid="]'
                    )[:80]:
                        href_raw = link.get("href")
                        href = (
                            href_raw
                            if isinstance(href_raw, str)
                            else (
                                href_raw[0]
                                if isinstance(href_raw, list) and href_raw
                                else ""
                            )
                        )
                        if not href or not re.search(
                            r"articles/\d+|articleid=\d+", href
                        ):
                            continue
                        post_url = (
                            href
                            if href.startswith("http")
                            else (
                                f"https://cafe.naver.com{href}"
                                if href.startswith("/")
                                else f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={href}"
                            )
                        )
                        article_id = self._extract_naver_article_id(post_url)
                        if article_id and article_id in seen_ids:
                            continue
                        if article_id:
                            seen_ids.add(article_id)
                        title = (link.get_text(strip=True) or "").strip()
                        if not title or len(title) < 2:
                            continue
                        posts.append(
                            {
                                "text": title[:300],
                                "number": len(posts) + 1,
                                "author": "",
                                "date": "",
                                "view_count": None,
                                "url": post_url,
                                "article_id": article_id,
                            }
                        )
            for row in rows[:50]:
                if row.name == "a":
                    href_raw = row.get("href")
                    href = (
                        href_raw
                        if isinstance(href_raw, str)
                        else (
                            href_raw[0]
                            if isinstance(href_raw, list) and href_raw
                            else ""
                        )
                    )
                    title = row.get_text(strip=True)
                    if not title or len(title) < 2:
                        continue
                    post_url = (
                        href
                        if href.startswith("http")
                        else (
                            f"https://cafe.naver.com{href}"
                            if href.startswith("/")
                            else f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={href}"
                        )
                    )
                    article_id = self._extract_naver_article_id(post_url)
                    posts.append(
                        {
                            "text": title[:300],
                            "author": "",
                            "date": "",
                            "view_count": None,
                            "url": post_url,
                            "article_id": article_id,
                            "number": len(posts) + 1,
                        }
                    )
                    continue
                link_el = row.select_one(
                    'a.article, a[href*="ArticleRead"], a[href*="articles"], .board-list a, .tit a, a[class*="article"]'
                )
                if not link_el:
                    continue
                href_raw = link_el.get("href")
                href = (
                    href_raw
                    if isinstance(href_raw, str)
                    else (
                        href_raw[0] if isinstance(href_raw, list) and href_raw else ""
                    )
                )
                title = (link_el.get_text(strip=True) or "").strip()
                if not title or len(title) < 2:
                    continue
                post_url = (
                    href
                    if href.startswith("http")
                    else (
                        f"https://cafe.naver.com{href}"
                        if href.startswith("/")
                        else f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={href}"
                    )
                )
                article_id = self._extract_naver_article_id(post_url)
                author_el = row.select_one(
                    '.td_name a, .writer, [class*="name"] a, [class*="writer"]'
                )
                author = author_el.get_text(strip=True) if author_el else ""
                date_el = row.select_one('.td_date, .date, [class*="date"]')
                date_str = date_el.get_text(strip=True) if date_el else ""
                view_el = row.select_one('.td_view, .view, [class*="view"]')
                view_count = None
                if view_el:
                    raw = view_el.get_text(strip=True)
                    if raw.isdigit():
                        view_count = int(raw)
                posts.append(
                    {
                        "text": title[:300],
                        "number": len(posts) + 1,
                        "author": author,
                        "date": date_str,
                        "view_count": view_count,
                        "url": post_url,
                        "article_id": article_id,
                    }
                )
        except Exception as e:
            logger.warning("Naver Cafe fetch failed: %s", e)
            self._append_naver_fetch_reason(fetch_reasons, "html_fetch_failed", e)

        # 1b) Resolve actual menu IDs when menuId=0 (전체글보기 — not a real API menu)
        api_menu_ids = [menu_id] if menu_id != "0" else []
        if not posts and menu_id == "0":
            try:
                side_url = f"https://apis.naver.com/cafe-web/cafe2/SideMenuList.json?cafeId={club_id}"
                api_headers_side = {
                    **headers,
                    "Accept": "application/json, text/plain, */*",
                    "Referer": f"https://cafe.naver.com/f-e/cafes/{club_id}/menus/0",
                }
                side_resp = self._naver_get(side_url, headers=api_headers_side, timeout=10)
                if side_resp.ok:
                    side_data = side_resp.json()
                    side_menus = (
                        side_data.get("message", {}).get("result", {}).get("menus") or []
                    )
                    for sm in side_menus:
                        if sm.get("menuType") == "B" and sm.get("boardType") in ("L", "C", "M"):
                            api_menu_ids.append(str(sm["menuId"]))
                    # Also try cafe info for cafeName
                    gate_url = f"https://apis.naver.com/cafe-web/cafe2/CafeGateInfo.json?cafeId={club_id}"
                    gate_resp = self._naver_get(gate_url, headers=api_headers_side, timeout=10)
                    if gate_resp.ok:
                        gate_data = gate_resp.json()
                        gate_info = gate_data.get("message", {}).get("result", {}).get("cafeInfoView") or {}
                        if gate_info.get("cafeName"):
                            cafe_name = gate_info["cafeName"]
            except Exception as e:
                logger.debug("Naver Cafe SideMenuList failed: %s", e)
            if not api_menu_ids:
                api_menu_ids = ["0"]

        if not posts:
            api_headers = {
                **headers,
                "Accept": "application/json, text/plain, */*",
                "Referer": f"https://cafe.naver.com/f-e/cafes/{club_id}/menus/{menu_id}",
            }
            for mid in api_menu_ids[:5]:
                try:
                    api_url_v21 = (
                        "https://apis.naver.com/cafe-web/cafe2/ArticleListV2dot1.json"
                        f"?search.clubid={club_id}&search.menuid={mid}"
                        "&search.page=1&search.perPage=50&search.queryType=lastArticle"
                    )
                    api_resp = self._naver_get(api_url_v21, headers=api_headers, timeout=15)
                    if not api_resp.ok:
                        continue
                    data = api_resp.json()
                    msg = data.get("message") or {}
                    if msg.get("status") != "200":
                        continue
                    result_data = msg.get("result") or {}
                    article_list = (
                        result_data.get("articleList")
                        or result_data.get("articleListMap", {}).get("list")
                        or []
                    )
                    for art in article_list[:50]:
                        title = art.get("subject") or art.get("title") or ""
                        if not title:
                            continue
                        article_id = art.get("articleId") or art.get("id")
                        aid_str = str(article_id) if article_id is not None else None
                        if aid_str and any(p.get("article_id") == aid_str for p in posts):
                            continue
                        post_url = (
                            f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={article_id}"
                            if article_id else ""
                        )
                        writer = art.get("writerNickname") or art.get("writerName") or art.get("nickname") or ""
                        date_str = art.get("writeDate") or art.get("regDate") or ""
                        if not date_str and art.get("writeDateTimestamp"):
                            try:
                                date_str = datetime.fromtimestamp(
                                    art["writeDateTimestamp"] / 1000, tz=KST
                                ).strftime("%Y.%m.%d %H:%M")
                            except Exception:
                                pass
                        view_count = art.get("readCount") or art.get("viewCount")
                        if view_count is not None and not isinstance(view_count, int):
                            try:
                                view_count = int(view_count)
                            except (TypeError, ValueError):
                                view_count = None
                        comment_count_api = art.get("commentCount") or art.get("replyCount") or 0
                        if not isinstance(comment_count_api, int):
                            try:
                                comment_count_api = int(comment_count_api)
                            except (TypeError, ValueError):
                                comment_count_api = 0
                        posts.append({
                            "text": (title[:300] if isinstance(title, str) else str(title))[:300],
                            "number": len(posts) + 1,
                            "author": writer if isinstance(writer, str) else str(writer),
                            "date": date_str if isinstance(date_str, str) else str(date_str or ""),
                            "view_count": view_count,
                            "comment_count": comment_count_api,
                            "url": post_url,
                            "article_id": aid_str,
                        })
                    if len(posts) >= 50:
                        break
                except Exception as e:
                    logger.debug("Naver Cafe ArticleListV2dot1 menu %s failed: %s", mid, e)

        if not posts:
            try:
                # Naver Cafe ArticleList API uses search.clubid (lowercase)
                api_url = (
                    "https://apis.naver.com/cafe-web/cafe2/ArticleList.json"
                    f"?search.clubid={club_id}&search.menuid={menu_id}&search.page=1&search.perPage=50&search.queryType=lastArticle"
                )
                api_headers_v1 = {**headers, "Accept": "application/json, text/plain, */*", "Referer": f"https://cafe.naver.com/f-e/cafes/{club_id}/menus/{menu_id}"}
                api_resp = self._naver_get(api_url, headers=api_headers_v1, timeout=15)
                if api_resp.ok:
                    data = api_resp.json()
                    msg = data.get("message") or {}
                    result = msg.get("result") or {}
                    article_list = (
                        result.get("articleList")
                        or result.get("articleListMap", {}).get("list")
                        or []
                    )
                    for i, art in enumerate(article_list[:50]):
                        title = (
                            art.get("subject")
                            or art.get("title")
                            or art.get("name")
                            or ""
                        )
                        if not title:
                            continue
                        article_id = (
                            art.get("articleId")
                            or art.get("articleid")
                            or art.get("id")
                        )
                        post_url = (
                            f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={article_id}"
                            if article_id
                            else ""
                        )
                        writer = (
                            art.get("writer")
                            or art.get("writerName")
                            or art.get("nickname")
                            or ""
                        )
                        date_str = (
                            art.get("writeDate")
                            or art.get("date")
                            or art.get("regDate")
                            or ""
                        )
                        view_count = art.get("readCount") or art.get("viewCount")
                        if view_count is not None and not isinstance(view_count, int):
                            try:
                                view_count = int(view_count)
                            except (TypeError, ValueError):
                                view_count = None
                        posts.append(
                            {
                                "text": (
                                    title[:300]
                                    if isinstance(title, str)
                                    else str(title)
                                )[:300],
                                "number": i + 1,
                                "author": (writer or "")
                                if isinstance(writer, str)
                                else str(writer),
                                "date": (date_str or "")
                                if isinstance(date_str, str)
                                else str(date_str),
                                "view_count": view_count,
                                "url": post_url,
                                "article_id": str(article_id)
                                if article_id is not None
                                else None,
                            }
                        )
            except Exception as e:
                logger.debug("Naver Cafe API fallback failed: %s", e)
                self._append_naver_fetch_reason(fetch_reasons, "api_fetch_failed", e)

        if not posts:
            try:
                mobile_url = f"https://m.cafe.naver.com/ca-fe/web/cafes/{club_id}/menus/{menu_id}"
                m_resp = self._naver_get(mobile_url, headers=headers, timeout=15)
                m_resp.raise_for_status()
                from bs4 import BeautifulSoup

                m_soup = BeautifulSoup(m_resp.text, "html.parser")
                for link in m_soup.select(
                    'a[href*="/ca-fe/cafes/"][href*="/articles/"]'
                )[:50]:
                    title = (link.get_text(strip=True) or "").strip()
                    if not title:
                        continue
                    href_raw = link.get("href")
                    href = (
                        href_raw
                        if isinstance(href_raw, str)
                        else ("" if href_raw is None else str(href_raw))
                    )
                    post_url = (
                        href
                        if href.startswith("http")
                        else f"https://m.cafe.naver.com{href}"
                    )
                    article_id = self._extract_naver_article_id(post_url)
                    posts.append(
                        {
                            "text": title[:300],
                            "number": len(posts) + 1,
                            "author": "",
                            "date": "",
                            "view_count": None,
                            "url": post_url,
                            "article_id": article_id,
                        }
                    )
            except Exception as e:
                logger.debug("Naver Cafe mobile fallback failed: %s", e)
                self._append_naver_fetch_reason(fetch_reasons, "mobile_fetch_failed", e)

        # Filter posts by search query if present (client-side filtering since Naver API doesn't support search)
        if search_query and posts:
            query_lower = search_query.lower()
            posts = [p for p in posts if query_lower in (p.get("text") or "").lower()]
            # Re-number filtered posts
            for i, p in enumerate(posts):
                p["number"] = i + 1

        max_posts_with_comments = 10
        for i, post in enumerate(posts[:max_posts_with_comments]):
            try:
                article_id = post.get("article_id") or self._extract_naver_article_id(
                    post.get("url", "")
                )
                if not article_id:
                    continue
                comments = self._fetch_naver_cafe_post_comments(
                    club_id, article_id, headers
                )
                post["comments"] = comments if comments else []
                if comments:
                    post["comment_count"] = len(comments)
            except Exception as e:
                logger.debug(
                    "Naver Cafe comments for article %s: %s", post.get("article_id"), e
                )
                post["comments"] = []

        total_comments = 0
        posts_with_comments = 0
        for post in posts:
            post_comments = post.get("comments") or []
            api_count = post.get("comment_count") or 0
            if isinstance(post_comments, list) and post_comments:
                posts_with_comments += 1
                total_comments += len(post_comments)
            elif api_count > 0:
                posts_with_comments += 1
                total_comments += api_count

        fetch_status = "ok"
        fetch_reason = ""
        if not posts and search_query:
            fetch_status = "ok"
            fetch_reason = "no_search_results"
        elif not posts:
            fetch_status = "blocked"
            reason_parts = fetch_reasons[:] if fetch_reasons else ["no_posts_detected"]
            if not self._naver_cookie:
                reason_parts.append("cookie_not_set")
            if not self._naver_proxies and any(
                token in reason_parts
                for token in (
                    "html_fetch_failed",
                    "api_fetch_failed",
                    "mobile_fetch_failed",
                    "ssl_verify_failed",
                )
            ):
                reason_parts.append("proxy_not_set")
            fetch_reason = ",".join(reason_parts)
        elif posts_with_comments == 0:
            fetch_status = "partial"
            fetch_reason = "posts_found_but_comments_unavailable"

        total_posts = (
            total_posts_estimate if total_posts_estimate is not None else len(posts)
        )
        result_data = {
            "type": "gallery",
            "gallery_id": club_id,
            "gallery_name": cafe_name,
            "title": cafe_name,
            "total_posts": total_posts,
            "total_comments": total_comments,
            "fetch_status": fetch_status,
            "fetch_reason": fetch_reason,
            "login_verified": login_verified,
            "posts": posts,
        }
        if search_query:
            result_data["search_query"] = search_query
        return result_data

    def _analyze_naver_cafe_single_post(self, club_id, article_id, headers):
        post_title = f"카페 게시글 {article_id}"
        content = ""
        author = "—"
        date_str = ""
        view_count = 0
        page_fetch_reasons = []

        page_candidates = [
            f"https://m.cafe.naver.com/ca-fe/web/cafes/{club_id}/articles/{article_id}",
            f"https://cafe.naver.com/ca-fe/web/cafes/{club_id}/articles/{article_id}",
            f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={article_id}",
        ]
        for page_url in page_candidates:
            try:
                resp = self._naver_get(page_url, headers=headers, timeout=15)
                if not resp.ok:
                    continue
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(resp.text, "html.parser")
                title_el = soup.select_one(
                    "h3.title_text, .ArticleContentBox .title_text, .article_subject, "
                    ".tit-box .b, .tit-box span.b, title, meta[property='og:title']"
                )
                if title_el:
                    if title_el.name == "meta":
                        title_raw = title_el.get("content")
                        if isinstance(title_raw, str) and title_raw.strip():
                            post_title = title_raw.strip()
                    else:
                        parsed_title = title_el.get_text(strip=True)
                        if parsed_title:
                            post_title = parsed_title

                content_el = soup.select_one(
                    ".ContentRenderer, .ArticleContentBox .se-main-container, "
                    "#tbody, div#tbody, .article_viewer, .content, .cafe_content, .article_body, "
                    "[class*='article-content'], [class*='ArticleContent']"
                )
                if content_el:
                    content = content_el.get_text("\n", strip=True)[:10000]

                author_el = soup.select_one(
                    ".nickname, .writer, .article_info .name, [class*='nick']"
                )
                if author_el:
                    author = author_el.get_text(strip=True) or author

                date_el = soup.select_one(
                    ".date, .article_info .time, time, [class*='date']"
                )
                if date_el:
                    date_str = date_el.get_text(strip=True)

                view_el = soup.select_one(
                    ".count, .view, [class*='readCount'], [class*='view']"
                )
                if view_el:
                    raw_view = re.sub(r"[^\d]", "", view_el.get_text(strip=True))
                    if raw_view.isdigit():
                        view_count = int(raw_view)

                if post_title or content:
                    break
            except Exception as e:
                logger.debug("Naver Cafe single post page parse failed: %s", e)
                self._append_naver_fetch_reason(
                    page_fetch_reasons, "single_post_fetch_failed", e
                )

        comments = self._fetch_naver_cafe_post_comments(club_id, article_id, headers)
        fetch_status = "ok"
        fetch_reason = ""
        if not content and not comments:
            fetch_status = "blocked"
            reasons = ["content_and_comments_unavailable"]
            if page_fetch_reasons:
                reasons.extend(page_fetch_reasons)
            if not self._naver_cookie:
                reasons.append("cookie_not_set")
            if not self._naver_proxies and any(
                token in reasons
                for token in (
                    "single_post_fetch_failed",
                    "ssl_verify_failed",
                )
            ):
                reasons.append("proxy_not_set")
            fetch_reason = ",".join(reasons)
        elif content and not comments:
            fetch_status = "partial"
            fetch_reason = "content_found_but_comments_unavailable"

        # 로그인된 상태로 본문/댓글을 가져왔으면 True
        login_verified = bool(self._naver_cookie and (content or comments))

        return {
            "type": "post",
            "gallery_id": str(club_id),
            "post_no": str(article_id),
            "title": post_title,
            "content": content,
            "author": author,
            "date": date_str,
            "view_count": view_count,
            "comment_count": len(comments),
            "fetch_status": fetch_status,
            "fetch_reason": fetch_reason,
            "login_verified": login_verified,
            "comments": comments[:100],
            "url": f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={article_id}",
        }

    def _extract_naver_cafe_posts_from_script_json(self, html, club_id):
        """Extract article list from JSON embedded in script tags (e.g. f-e SPA initial state)."""
        out = []
        seen_ids = set()

        def extract_json_object(text, start_marker):
            """Find start_marker then extract balanced {...}."""
            idx = text.find(start_marker)
            if idx < 0:
                return None
            idx = text.find("{", idx)
            if idx < 0:
                return None
            depth = 0
            for i in range(idx, min(idx + 500000, len(text))):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return text[idx : i + 1]
            return None

        def collect_articles(data):
            articles = []
            if isinstance(data, list):
                articles = data
            elif isinstance(data, dict):
                articles = (
                    data.get("articles")
                    or data.get("articleList")
                    or data.get("result", {}).get("articleList")
                    or data.get("message", {}).get("result", {}).get("articleList")
                    or []
                )
                if not articles and "articleListMap" in data:
                    articles = (data.get("articleListMap") or {}).get("list") or []
            return articles

        for marker in (
            "__PRELOADED_STATE__",
            "__INITIAL_STATE__",
            '"articleList"',
            '"articles"',
        ):
            articles = []
            raw = extract_json_object(html, marker) if marker.startswith("__") else None
            if raw:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                articles = collect_articles(data)
            else:
                for m in re.finditer(
                    r'"articleList"\s*:\s*(\[[\s\S]{0,20000}?\])\s*[,}]',
                    html,
                ):
                    try:
                        articles = json.loads(m.group(1))
                        break
                    except json.JSONDecodeError:
                        continue
                else:
                    for m in re.finditer(
                        r'"articles"\s*:\s*(\[[\s\S]{0,20000}?\])\s*[,}]',
                        html,
                    ):
                        try:
                            articles = json.loads(m.group(1))
                            break
                        except json.JSONDecodeError:
                            continue
                    else:
                        continue
            for art in articles:
                if not isinstance(art, dict):
                    continue
                aid = (
                    art.get("articleId")
                    or art.get("articleid")
                    or art.get("id")
                    or art.get("article_id")
                )
                if aid is not None:
                    aid = str(aid)
                    if aid in seen_ids:
                        continue
                    seen_ids.add(aid)
                title = (
                    art.get("subject")
                    or art.get("title")
                    or art.get("name")
                    or (art.get("content") or "")[:200]
                )
                if isinstance(title, str) and len(title.strip()) < 2:
                    continue
                title = (
                    (title or "")[:300] if isinstance(title, str) else str(title)[:300]
                )
                post_url = (
                    f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={aid}"
                    if aid
                    else ""
                )
                out.append(
                    {
                        "text": title,
                        "number": len(out) + 1,
                        "author": (
                            art.get("writer")
                            or art.get("writerName")
                            or art.get("nickname")
                            or ""
                        ),
                        "date": (
                            art.get("writeDate")
                            or art.get("date")
                            or art.get("regDate")
                            or ""
                        ),
                        "view_count": art.get("readCount") or art.get("viewCount"),
                        "comment_count": art.get("commentCount") or art.get("replyCount") or 0,
                        "url": post_url,
                        "article_id": aid,
                    }
                )
            if out:
                return out[:50]
        return out

    def _extract_naver_article_id(self, url):
        if not url:
            return None
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            direct = (params.get("articleid") or params.get("articleId") or [None])[0]
            if direct and str(direct).isdigit():
                return str(direct)

            path = (parsed.path or "").strip("/")
            m = re.search(r"/cafes/\d+/articles/(\d+)", f"/{path}", re.IGNORECASE)
            if m:
                return m.group(1)

            m = re.search(r"(?:articleid=|articles/)(\d+)", url, re.IGNORECASE)
            if m:
                return m.group(1)
        except Exception:
            return None
        return None

    def _fetch_naver_cafe_post_comments(self, club_id, article_id, headers):
        comments = []
        req_headers = {
            "User-Agent": headers.get(
                "User-Agent", self._session.headers["User-Agent"]
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={article_id}",
            "X-Requested-With": "XMLHttpRequest",
        }

        api_candidates = [
            f"https://apis.naver.com/cafe-web/cafe-articleapi/cafes/{club_id}/articles/{article_id}/comments?page=1&pageSize=30",
            f"https://apis.naver.com/cafe-web/cafe-articleapi/v2/cafes/{club_id}/articles/{article_id}/comments?page=1&pageSize=30",
            f"https://apis.naver.com/cafe-web/cafe-articleapi/v2/cafes/{club_id}/articles/{article_id}",
        ]

        for api_url in api_candidates:
            try:
                resp = self._naver_get(api_url, headers=req_headers, timeout=12)
                if not resp.ok or not resp.text.strip():
                    continue
                payload = resp.json()
                extracted = self._extract_naver_comments_from_payload(payload)
                if extracted:
                    comments = extracted
                    break
            except Exception as e:
                logger.debug("Naver Cafe comment API %s failed: %s", api_url, e)

        if comments:
            return comments[:100]

        page_candidates = [
            f"https://m.cafe.naver.com/ca-fe/web/cafes/{club_id}/articles/{article_id}",
            f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={article_id}",
        ]
        for page_url in page_candidates:
            try:
                resp = self._naver_get(page_url, headers=headers, timeout=12)
                if not resp.ok:
                    continue
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(resp.text, "html.parser")
                for item in soup.select(
                    '.CommentItem, .comment_item, li[class*="comment"], .cmt_item, '
                    '.CommentList li, .reply_list li, #commentList li, div[class*="comment"]'
                )[:100]:
                    text_el = item.select_one(
                        ".text_comment, .comment_text, .txt, p, [class*='content'], [class*='text']"
                    )
                    text = (text_el.get_text(strip=True) if text_el else "").strip()
                    if not text:
                        continue
                    author_el = item.select_one(
                        '.nickname, .name, .writer, [class*="nick"]'
                    )
                    date_el = item.select_one('.date, .time, [class*="date"]')
                    comments.append(
                        {
                            "author": author_el.get_text(strip=True)
                            if author_el
                            else "—",
                            "text": text[:500],
                            "date": date_el.get_text(strip=True) if date_el else "",
                        }
                    )
                if comments:
                    break
            except Exception as e:
                logger.debug(
                    "Naver Cafe comment HTML fallback %s failed: %s", page_url, e
                )

        return comments[:100]

    def _extract_naver_comments_from_payload(self, payload):
        # New API format: {"comments": {"items": [...]}}
        comments_obj = payload.get("comments")
        if isinstance(comments_obj, dict) and "items" in comments_obj:
            items = comments_obj["items"]
            if isinstance(items, list):
                return self._parse_naver_comment_items(items)

        # Legacy / generic walk: find any list under a key containing "comment"
        candidates = []

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    key = str(k).lower()
                    if "comment" in key and isinstance(v, list):
                        candidates.append(v)
                    walk(v)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)

        comments = []
        for group in candidates:
            parsed = self._parse_naver_comment_items(group)
            if parsed:
                comments = parsed
                break

        return comments

    def _parse_naver_comment_items(self, items):
        """Parse Naver Cafe comment items from API response."""
        comments = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("isDeleted"):
                continue
            text = (
                item.get("content")
                or item.get("comment")
                or item.get("text")
                or item.get("memo")
                or item.get("body")
                or item.get("description")
                or item.get("message")
                or ""
            )
            text = str(text).strip()
            # Include sticker-only comments
            if not text and item.get("sticker"):
                text = "[스티커]"
            if not text:
                continue
            # Author: may be dict (new API) or string (legacy)
            writer = item.get("writer") or {}
            if isinstance(writer, dict):
                author = (
                    writer.get("nick")
                    or writer.get("nickName")
                    or writer.get("memberNickname")
                    or writer.get("name")
                    or writer.get("id")
                    or "—"
                )
            else:
                author = (
                    item.get("writer")
                    or item.get("nickname")
                    or item.get("nickName")
                    or item.get("memberNickname")
                    or item.get("name")
                    or "—"
                )
            # Date: may be epoch ms (new API) or string
            date_str = (
                item.get("updateDate")
                or item.get("createDate")
                or item.get("registerDate")
                or item.get("regDate")
                or item.get("date")
                or item.get("writeDate")
                or ""
            )
            if isinstance(date_str, (int, float)) and date_str > 1_000_000_000_000:
                from datetime import datetime, timezone
                date_str = datetime.fromtimestamp(
                    date_str / 1000, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S")
            comments.append(
                {
                    "author": str(author),
                    "text": text[:500],
                    "date": str(date_str),
                }
            )
        return comments

    def _analyze_dcinside_single_post(self, gallery_id, post_no, url):
        """Analyze a single DCInside post: content, stats, comments."""
        is_mini = "/mini/" in url
        is_mgallery = "/mgallery/" in url
        gallery_type = "mini" if is_mini else ("mgallery" if is_mgallery else "board")

        view_url = self._build_dcinside_view_url(gallery_type, gallery_id, post_no)
        headers = {
            "User-Agent": self._session.headers["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://gall.dcinside.com/",
        }
        try:
            resp = self._session.get(view_url, headers=headers, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("DCInside view page fetch failed: %s", e)
            raise ValueError(f"Could not load post: {e}") from e

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")

        title = ""
        title_el = soup.select_one(
            ".title_subject, .view_content_wrap .tit, .writing_view .tit"
        )
        if title_el:
            title = title_el.get_text(strip=True)

        content_el = soup.select_one(
            ".write_div, .writing_view .content, .view_content"
        )
        content = (
            content_el.get_text(separator="\n", strip=True) if content_el else ""
        )[:10000]

        author_el = soup.select_one(
            ".gall_writer .nickname, .writing_view .writer, [data-nick]"
        )
        author = ""
        if author_el:
            author = author_el.get("data-nick", "") or author_el.get_text(strip=True)

        date_el = soup.select_one(".gall_date, .writing_view .date")
        date_str = date_el.get("title", date_el.get_text(strip=True)) if date_el else ""

        view_count = 0
        count_el = soup.select_one(".gall_count, .view_count")
        if count_el and count_el.get_text(strip=True).isdigit():
            view_count = int(count_el.get_text(strip=True))

        recommend = 0
        rec_el = soup.select_one(".gall_recommend, .recommend_count")
        if rec_el:
            raw = rec_el.get_text(strip=True).lstrip("-")
            if raw.isdigit():
                recommend = int(raw)

        comments = self._fetch_dcinside_post_comments(
            gallery_id, post_no, gallery_type, headers
        )
        comment_count = len(comments)

        return {
            "type": "post",
            "gallery_id": gallery_id,
            "post_no": post_no,
            "title": title or f"게시글 #{post_no}",
            "content": content,
            "author": author or "—",
            "date": date_str,
            "view_count": view_count,
            "recommend": recommend,
            "comment_count": comment_count,
            "comments": comments[:100],
            "url": view_url,
        }

    def _get_dcinside_comment_token(self, gallery_id, post_no, gallery_type, headers):
        """Extract e_s_n_o token from view page (required for comment API)."""
        view_url = self._build_dcinside_view_url(gallery_type, gallery_id, post_no)
        view_headers = dict(headers)
        view_headers.setdefault(
            "Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        )
        try:
            resp = self._session.get(view_url, headers=view_headers, timeout=12)
            if resp.status_code != 200:
                logger.debug(
                    "DCInside view page status %s for %s", resp.status_code, view_url
                )
                return ""
            text = resp.text
            # Try multiple patterns (page structure may vary; crawler uses same token from view page)
            for pattern in (
                r'e_s_n_o\s*[=:]\s*["\']([^"\']+)["\']',
                r'["\']e_s_n_o["\']\s*[=:]\s*["\']([^"\']+)["\']',
                r'"e_s_n_o"\s*:\s*"([^"]+)"',
                r'data-e-s-n-o=["\']([^"\']+)["\']',
                r'decodeURIComponent\s*\(\s*["\']([^"\']+)["\']\s*\)',
            ):
                match = re.search(pattern, text)
                if match:
                    return match.group(1)
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text, "html.parser")
            inp = soup.find("input", {"name": "e_s_n_o"})
            token = inp.get("value", "") if inp else ""
            if not token:
                logger.warning(
                    "DCInside e_s_n_o token not found for post %s (id=%s); comment API may fail",
                    post_no,
                    gallery_id,
                )
            return token
        except Exception as e:
            logger.debug("DCInside e_s_n_o token: %s", e)
            return ""

    def _parse_dcinside_comments_html(self, html_text):
        """Parse comment list from DCInside HTML fragment (e.g. AJAX response)."""
        comments = []
        if not html_text or not html_text.strip():
            return comments
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_text, "html.parser")
            for selector in (
                "div.cmt_info",
                ".cmt_info",
                "div[data-article-no]",
                "div[data-no]",
                ".comment_info",
                ".reply_info",
                "li.cmt_info",
                "li.reply_info",
                "ul.cmt_list li",
                "li[data-no]",
            ):
                items = soup.select(selector)
                if not items:
                    continue
                for item in items:
                    text_el = item.select_one(
                        ".cmt_txtbox .usertxt, .cmt_txtbox p, .usertxt, .cmt_txtbox .txt, .reply_txt, p, .comment_text"
                    )
                    text = (text_el.get_text(strip=True) if text_el else "").strip()
                    if not text or len(text) <= 1 or text.startswith("dccon"):
                        continue
                    author_el = item.select_one(
                        ".nickname, .gall_writer, .writer, [data-nick]"
                    )
                    author = (
                        author_el.get("data-nick", "")
                        if author_el and author_el.get("data-nick")
                        else (author_el.get_text(strip=True) if author_el else "—")
                    )
                    date_el = item.select_one(".date_time, .date, .time")
                    date_str = date_el.get_text(strip=True) if date_el else ""
                    comments.append(
                        {"author": author or "—", "text": text[:500], "date": date_str}
                    )
                if comments:
                    break
        except Exception as e:
            logger.debug("DCInside HTML comment parse: %s", e)
        return comments

    def _fetch_dcinside_comments_ajax(
        self, gallery_id, post_no, gallery_type, headers, referer_gallery_type=None
    ):
        """Fetch comments via DCInside comment API (JSON). Comments are loaded by JS, not in initial HTML.
        referer_gallery_type: when calling board API for mgallery/mini, pass original type for Referer/token.
        """
        ref_type = referer_gallery_type or gallery_type
        token = self._get_dcinside_comment_token(gallery_id, post_no, ref_type, headers)
        if not token:
            logger.debug("DCInside comment API: trying without e_s_n_o token")
        api_url = self._build_dcinside_comment_api_url(gallery_type)
        req_headers = {
            "User-Agent": headers.get(
                "User-Agent", self._session.headers["User-Agent"]
            ),
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": self._build_dcinside_view_url(ref_type, gallery_id, post_no),
        }
        comments = []
        for page in range(1, 6):
            try:
                r = self._session.get(
                    api_url,
                    params={
                        "id": gallery_id,
                        "no": post_no,
                        "cmt_id": gallery_id,
                        "cmt_no": post_no,
                        "e_s_n_o": token,
                        "comment_page": str(page),
                        "sort": "",
                    },
                    headers=req_headers,
                    timeout=12,
                )
                if r.status_code != 200:
                    if page == 1:
                        logger.debug(
                            "DCInside comment API status %s, body: %s",
                            r.status_code,
                            (r.text or "")[:300],
                        )
                    break
                body = (r.text or "").strip()
                if body == "정상적인 접근이 아닙니다." or (
                    len(body) < 50 and "정상적인 접근" in body
                ):
                    if page == 1:
                        logger.warning(
                            "DCInside comment API blocked (정상적인 접근이 아닙니다). "
                            "Comments loaded by JS; server may require browser. "
                            "Try Playwright fallback if installed, or use 원문 보기."
                        )
                    break
                data = None
                try:
                    data = r.json() if body else {}
                except (ValueError, json.JSONDecodeError):
                    html_cmts = self._parse_dcinside_comments_html(body)
                    if html_cmts:
                        comments.extend(html_cmts)
                        if len(html_cmts) < 20:
                            break
                        page += 1
                        time.sleep(0.3)
                        continue
                    if page == 1:
                        logger.debug(
                            "DCInside comment API non-JSON (len=%s), sample: %s",
                            len(r.text or ""),
                            (r.text or "")[:250],
                        )
                    break
                if not isinstance(data, dict) and isinstance(data, list):
                    raw = data
                else:
                    raw = (
                        data.get("comments")
                        or (data.get("data") or {}).get("comments")
                        or (data.get("result") or {}).get("comments")
                        or data.get("comment_list")
                        or data.get("commentList")
                        or (data.get("data") or {}).get("comment_list")
                        or (data.get("data") or {}).get("commentList")
                    )
                    if not raw and isinstance(data, dict):
                        for key in data:
                            if (
                                ("comment" in key.lower() or key in ("items", "list"))
                                and isinstance(data.get(key), list)
                                and data.get(key)
                            ):
                                raw = data[key]
                                break
                    # API may return JSON with HTML string (e.g. comment_list_html, html)
                    if not raw and isinstance(data, dict):
                        for key in (
                            "html",
                            "comment_html",
                            "content",
                            "list_html",
                            "comment_list_html",
                            "comment_list",
                        ):
                            val = data.get(key)
                            if isinstance(val, str) and (
                                "cmt_info" in val
                                or "usertxt" in val
                                or "cmt_txtbox" in val
                            ):
                                html_cmts = self._parse_dcinside_comments_html(val)
                                if html_cmts:
                                    comments.extend(html_cmts)
                                    if len(html_cmts) < 20:
                                        break
                                    time.sleep(0.3)
                                    raw = True
                                    break
                        if raw is True:
                            continue
                if not raw:
                    if page == 1:
                        logger.debug(
                            "DCInside comment API page 1 empty (keys=%s)",
                            list(data.keys()) if isinstance(data, dict) else "n/a",
                        )
                    break
                for cmt in raw:
                    text = (
                        cmt.get("memo") or cmt.get("text") or cmt.get("comment") or ""
                    ).strip()
                    if not text or text.startswith("<") or text.startswith("dccon"):
                        continue
                    comments.append(
                        {
                            "author": cmt.get("name") or cmt.get("author") or "—",
                            "text": text[:500],
                            "date": cmt.get("reg_date") or cmt.get("date") or "",
                        }
                    )
                if len(raw) < 20:
                    break
                time.sleep(0.3)
            except Exception as e:
                logger.debug("DCInside comment API page %s: %s", page, e)
                break
        return comments[:100]

    def _parse_dcinside_comment_item(self, item):
        """Extract author, text, date from a comment DOM item (view page HTML).
        mgallery structure: div.cmt_info > .cmt_nickbox (.gall_writer[data-nick]) + .cmt_txtbox (p.usertxt) + .date_time
        """
        author = "—"
        for sel in (
            ".gall_writer",
            ".nickname",
            ".nick",
            "em",
            ".nick_box",
            "[data-nick]",
            ".writer",
        ):
            el = item.select_one(sel)
            if el:
                author = el.get("data-nick", "") or el.get_text(strip=True) or author
                if author and author != "—":
                    break
        if item.get("data-nick"):
            author = item.get("data-nick")
        text = ""
        for sel in (
            ".cmt_txtbox .usertxt",
            ".cmt_txtbox p",
            ".usertxt",
            ".cmt_txtbox",
            ".txt",
            "p",
            ".comment_text",
            ".reply_txt",
        ):
            el = item.select_one(sel)
            if el:
                text = (el.get_text(strip=True) or "").strip()
                if text:
                    break
        if not text and item.get_text(strip=True):
            raw = item.get_text(strip=True)
            if len(raw) <= 500:
                text = raw
        if (
            not text
            or len(text) <= 1
            or text.startswith("dccon")
            or text.startswith("<")
        ):
            return None
        date_el = item.select_one(".date_time, .date, .time, [data-date]")
        date_str = ""
        if date_el:
            date_str = date_el.get_text(strip=True) or date_el.get("data-date", "")
        return {"author": author or "—", "text": text[:500], "date": date_str}

    def _extract_dcinside_comments_from_view_html(self, html_text):
        """Try to extract comment array from view page script/JSON (e.g. embedded state)."""
        comments = []
        if not html_text or not html_text.strip():
            return comments
        try:
            # Match JSON-like arrays of comment objects (memo/text/comment, name/author, reg_date)
            for pattern in (
                r'"comments"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
                r'"comment_list"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
                r'"commentList"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
            ):
                match = re.search(pattern, html_text)
                if not match:
                    continue
                raw_json = match.group(1)
                # Limit length to avoid runaway match
                if len(raw_json) > 100000:
                    continue
                try:
                    arr = json.loads(raw_json)
                except (ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(arr, list):
                    continue
                for cmt in arr[:100]:
                    if not isinstance(cmt, dict):
                        continue
                    text = (
                        cmt.get("memo") or cmt.get("text") or cmt.get("comment") or ""
                    ).strip()
                    if not text or text.startswith("<") or text.startswith("dccon"):
                        continue
                    comments.append(
                        {
                            "author": cmt.get("name") or cmt.get("author") or "—",
                            "text": text[:500],
                            "date": cmt.get("reg_date") or cmt.get("date") or "",
                        }
                    )
                if comments:
                    return comments[:100]
        except Exception as e:
            logger.debug("DCInside embedded comment extract: %s", e)
        return comments

    def _fetch_dcinside_post_comments(self, gallery_id, post_no, gallery_type, headers):
        """Fetch comments: try AJAX API first (comments loaded by JS), then HTML fallback.
        Crawler uses unified board/comment/ API with gallery-specific Referer for mini/mgallery.
        """
        # mgallery/mini: board comment API + gallery Referer (same as crawlers/dcinside)
        if gallery_type == "mgallery":
            comments = self._fetch_dcinside_comments_ajax(
                gallery_id, post_no, "board", headers, referer_gallery_type="mgallery"
            )
            if not comments:
                comments = self._fetch_dcinside_comments_ajax(
                    gallery_id, post_no, gallery_type, headers
                )
        elif gallery_type == "mini":
            # Mini: try board API with mini Referer first (crawler behavior), then mini API
            comments = self._fetch_dcinside_comments_ajax(
                gallery_id, post_no, "board", headers, referer_gallery_type="mini"
            )
            if not comments:
                comments = self._fetch_dcinside_comments_ajax(
                    gallery_id, post_no, "mini", headers
                )
            if not comments:
                comments = self._fetch_dcinside_comments_ajax(
                    gallery_id, post_no, "board", headers
                )
        else:
            comments = self._fetch_dcinside_comments_ajax(
                gallery_id, post_no, gallery_type, headers
            )
            if not comments and gallery_type != "board":
                comments = self._fetch_dcinside_comments_ajax(
                    gallery_id, post_no, "board", headers
                )
        if comments:
            return comments
        view_url = self._build_dcinside_view_url(gallery_type, gallery_id, post_no)
        comments = []
        try:
            view_headers = dict(headers)
            view_headers.setdefault(
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            )
            resp = self._session.get(view_url, headers=view_headers, timeout=12)
            resp.raise_for_status()
            html_text = resp.text
            comments = self._extract_dcinside_comments_from_view_html(html_text)
            if comments:
                return comments[:100]
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_text, "html.parser")
            # div.cmt_info is the comment block (mgallery: cmt_nickbox + cmt_txtbox + date_time)
            # Include crawler-style selectors: .cmt_info, .comment_info, .reply_info
            for selector in (
                "div.cmt_info",
                ".cmt_info",
                ".comment_info",
                ".reply_info",
                ".comment_box .cmt_info",
                "ul.cmt_list li",
                ".reply_box .reply_info",
                ".comment_list li",
                ".cmt_list li",
                ".cmt_list .cmt_info",
                "li.cmt_info",
                "li.reply_info",
                "li[data-no]",
                "div[data-article-no]",
                ".comment_box li",
                ".reply_box li",
            ):
                items = soup.select(selector)
                if not items:
                    continue
                for item in items:
                    parsed = self._parse_dcinside_comment_item(item)
                    if parsed:
                        comments.append(parsed)
                if comments:
                    break
            if comments:
                return comments[:100]
        except Exception as e:
            logger.debug("DCInside view page comments: %s", e)
        # When API is blocked or view HTML has no comments (JS-loaded): try Playwright
        logger.info(
            "DCInside comment API/HTML had no comments; trying Playwright for post %s",
            post_no,
        )
        comments = self._fetch_dcinside_comments_playwright(
            gallery_id, post_no, gallery_type
        )
        return comments[:100] if comments else []

    def _fetch_dcinside_comments_playwright(self, gallery_id, post_no, gallery_type):
        """Playwright fallback when comment API is blocked. Requires playwright + chromium in environment."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.debug("Playwright not installed; skipping DCInside comment fallback")
            return []
        view_url = self._build_dcinside_view_url(gallery_type, gallery_id, post_no)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )
                page = browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 720},
                )
                page.goto(view_url, wait_until="domcontentloaded", timeout=25000)
                # Wait for comment area (JS-rendered); multiple selectors for mini/major
                for selector in (
                    ".comment_box .cmt_info",
                    ".cmt_list li",
                    "ul.cmt_list li",
                    ".cmt_info",
                    ".reply_list .cmt_info",
                    ".comment_wrap .cmt_info",
                ):
                    try:
                        page.wait_for_selector(selector, timeout=12000)
                        break
                    except Exception:
                        continue
                time.sleep(3)
                html = page.content()
                browser.close()
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            comments = []
            for selector in (
                "div.cmt_info",
                ".cmt_info",
                ".comment_info",
                ".reply_info",
                ".comment_box .cmt_info",
                ".reply_list .cmt_info",
                ".comment_wrap .cmt_info",
                "ul.cmt_list li",
                ".cmt_list li",
                "li[data-no]",
                ".comment_box li",
            ):
                items = soup.select(selector)
                if not items:
                    continue
                for item in items:
                    parsed = self._parse_dcinside_comment_item(item)
                    if parsed:
                        comments.append(parsed)
                if comments:
                    logger.info(
                        "DCInside comments collected via Playwright fallback: %s",
                        len(comments),
                    )
                    return comments[:100]
        except Exception as e:
            logger.warning(
                "DCInside Playwright comment fallback failed (post %s): %s",
                post_no,
                e,
            )
        return []

    # ==========================================
    # Reddit Analyzer
    # ==========================================
    def _analyze_reddit(self, url):
        """Analyze Reddit subreddit or post."""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")

        post_match = re.search(r"/r/([^/]+)/comments/([^/]+)", path)
        subreddit_match = re.search(r"/r/([^/]+)/?$", path)

        # Reddit requires a descriptive User-Agent; prefer OAuth app UA when we have credentials
        headers = {
            "User-Agent": self._reddit_user_agent
            if (self._reddit_client_id and self._reddit_client_secret)
            else self._session.headers["User-Agent"],
            "Accept": "application/json",
        }
        token = self._reddit_get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        if post_match:
            subreddit = post_match.group(1)
            post_id = post_match.group(2)
            return self._analyze_reddit_post(subreddit, post_id, headers)
        elif subreddit_match:
            subreddit = subreddit_match.group(1)
            return self._analyze_reddit_subreddit(subreddit, headers)
        else:
            raise ValueError("Could not extract subreddit or post from URL")

    def _analyze_reddit_subreddit(self, subreddit, headers):
        """Fetch subreddit posts. On 403, return a blocked result with guidance."""
        base_url = (
            "https://oauth.reddit.com"
            if headers.get("Authorization")
            else "https://www.reddit.com"
        )
        list_url = f"{base_url}/r/{subreddit}/hot"
        try:
            resp = self._reddit_request(
                list_url,
                headers=headers,
                params={"limit": 50},
                timeout=15,
            )
            if resp.status_code == 403:
                return self._reddit_blocked_subreddit_result(
                    subreddit,
                    "Reddit이 API 접근을 차단했습니다(403). "
                    "REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET을 .env에 설정한 뒤 재시작해 보세요.",
                )
            resp.raise_for_status()
            # OAuth endpoint returns JSON without .json in path
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                data = data[0].get("data", {})
            else:
                data = {}
        except requests.RequestException as e:
            if (
                getattr(e, "response", None)
                and getattr(e.response, "status_code", None) == 403
            ):
                return self._reddit_blocked_subreddit_result(
                    subreddit,
                    "Reddit이 API 접근을 차단했습니다(403). "
                    "REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET을 .env에 설정한 뒤 재시작해 보세요.",
                )
            logger.warning("Reddit subreddit fetch failed: %s", e)
            return self._reddit_blocked_subreddit_result(
                subreddit,
                f"Reddit 요청 실패: {e!s}. "
                "REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET 설정을 권장합니다.",
            )

        posts = []
        for child in data.get("children", []):
            post = child.get("data", {})
            if post.get("stickied"):
                continue
            posts.append(
                {
                    "text": post.get("title", ""),
                    "author": post.get("author", "[deleted]"),
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "created_utc": post.get("created_utc", 0),
                    "url": post.get("url", ""),
                    "selftext": (post.get("selftext", "") or "")[:300],
                    "permalink": f"https://reddit.com{post.get('permalink', '')}",
                }
            )

        # Fetch top comments for the first N posts
        max_posts_with_comments = 5
        for i, p in enumerate(posts[:max_posts_with_comments]):
            try:
                permalink = p.get("permalink", "")
                if not permalink:
                    continue
                cmt_url = (
                    f"https://oauth.reddit.com{permalink[len('https://reddit.com'):]}"
                    if headers.get("Authorization")
                    else f"https://www.reddit.com{permalink[len('https://reddit.com'):]}"
                )
                cmt_resp = self._reddit_request(
                    cmt_url,
                    headers=headers,
                    params={"limit": 10, "depth": 1},
                    timeout=10,
                )
                if not cmt_resp.ok:
                    continue
                cmt_data = cmt_resp.json()
                if not isinstance(cmt_data, list) or len(cmt_data) < 2:
                    continue
                post_comments = []
                for child in cmt_data[1].get("data", {}).get("children", []):
                    if not isinstance(child, dict) or child.get("kind") != "t1":
                        continue
                    c = child.get("data", {})
                    post_comments.append({
                        "text": (c.get("body", "") or "")[:500],
                        "author": c.get("author", "[deleted]"),
                        "score": c.get("score", 0),
                        "created_utc": c.get("created_utc", 0),
                    })
                p["comments"] = post_comments[:10]
            except Exception as e:
                logger.debug("Reddit comments for post %d: %s", i, e)

        about_url = f"{base_url}/r/{subreddit}/about"
        about = {}
        try:
            about_resp = self._reddit_request(about_url, headers=headers, timeout=10)
            if about_resp.ok:
                raw = about_resp.json()
                about = raw.get("data", {}) if isinstance(raw, dict) else {}
        except Exception:
            pass

        return {
            "type": "subreddit",
            "subreddit": subreddit,
            "subscribers": about.get("subscribers", 0),
            "active_users": about.get("accounts_active", 0),
            "description": (about.get("public_description", "") or "")[:500],
            "total_posts": len(posts),
            "posts": posts,
        }

    def _reddit_blocked_subreddit_result(
        self, subreddit: str, description: str
    ) -> dict[str, Any]:
        """Return a subreddit result when API is blocked (403)."""
        return {
            "type": "subreddit",
            "subreddit": subreddit,
            "subscribers": 0,
            "active_users": 0,
            "description": description,
            "total_posts": 0,
            "posts": [],
            "fetch_status": "blocked",
            "fetch_reason": "reddit_api_403",
        }

    def _analyze_reddit_post(self, subreddit, post_id, headers):
        """Fetch a specific Reddit post with comments. On 403, return blocked result."""
        base_url = (
            "https://oauth.reddit.com"
            if headers.get("Authorization")
            else "https://www.reddit.com"
        )
        url = f"{base_url}/r/{subreddit}/comments/{post_id}"
        try:
            resp = self._reddit_request(
                url,
                headers=headers,
                params={"limit": 100},
                timeout=15,
            )
            if resp.status_code == 403:
                return self._reddit_blocked_post_result(
                    subreddit,
                    post_id,
                    "Reddit이 API 접근을 차단했습니다(403). "
                    "REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET을 .env에 설정한 뒤 재시작해 보세요.",
                )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list) or len(data) < 2:
                raise ValueError("Reddit post not found")
            post_data = data[0]["data"]["children"][0]["data"]
            comments_data = data[1]["data"]["children"]

            comments = []
            for child in comments_data:
                if isinstance(child, dict) and child.get("kind") != "t1":
                    continue
                comment = child.get("data", {}) if isinstance(child, dict) else {}
                comments.append(
                    {
                        "text": comment.get("body", ""),
                        "author": comment.get("author", "[deleted]"),
                        "score": comment.get("score", 0),
                        "created_utc": comment.get("created_utc", 0),
                    }
                )

            return {
                "type": "post",
                "subreddit": subreddit,
                "title": post_data.get("title", ""),
                "author": post_data.get("author", "[deleted]"),
                "score": post_data.get("score", 0),
                "upvote_ratio": post_data.get("upvote_ratio", 0),
                "num_comments": post_data.get("num_comments", 0),
                "selftext": (post_data.get("selftext", "") or "")[:1000],
                "created_utc": post_data.get("created_utc", 0),
                "comments": comments,
            }
        except requests.RequestException as e:
            if (
                getattr(e, "response", None)
                and getattr(e.response, "status_code", None) == 403
            ):
                return self._reddit_blocked_post_result(
                    subreddit,
                    post_id,
                    "Reddit이 API 접근을 차단했습니다(403). "
                    "REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET을 .env에 설정한 뒤 재시작해 보세요.",
                )
            logger.warning("Reddit post fetch failed: %s", e)
            raise

    def _reddit_blocked_post_result(
        self, subreddit: str, post_id: str, description: str
    ) -> dict[str, Any]:
        """Return a post result when Reddit API is blocked (403)."""
        return {
            "type": "post",
            "subreddit": subreddit,
            "title": f"r/{subreddit} (API 차단)",
            "author": "",
            "score": 0,
            "upvote_ratio": 0,
            "num_comments": 0,
            "selftext": "",
            "created_utc": 0,
            "comments": [],
            "fetch_status": "blocked",
            "fetch_reason": "reddit_api_403",
            "description": description,
        }

    # ==========================================
    # Telegram Analyzer
    # ==========================================
    def _analyze_telegram(self, url):
        """Analyze public Telegram channel."""
        match = re.search(r"t\.me/(?:s/)?([^/?]+)", url)
        if not match:
            raise ValueError("Could not extract Telegram channel name from URL")

        channel_name = match.group(1)
        preview_url = f"https://t.me/s/{channel_name}"

        resp = self._session.get(preview_url, timeout=15)
        if resp.status_code == 403:
            return {
                "type": "channel",
                "channel_name": channel_name,
                "title": channel_name,
                "description": "",
                "subscriber_count": "0",
                "total_messages": 0,
                "posts": [],
                "source_url": url,
                "fetch_status": "blocked",
                "fetch_reason": "telegram_403_forbidden",
            }
        resp.raise_for_status()

        messages = []
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            # Channel info
            title_el = soup.select_one(".tgme_channel_info_header_title")
            desc_el = soup.select_one(".tgme_channel_info_description")
            counter_el = soup.select_one(".tgme_channel_info_counter .counter_value")

            channel_title = title_el.get_text(strip=True) if title_el else channel_name
            channel_desc = desc_el.get_text(strip=True) if desc_el else ""
            subscriber_count = counter_el.get_text(strip=True) if counter_el else "0"

            # Messages
            for msg_el in soup.select(".tgme_widget_message_wrap"):
                text_el = msg_el.select_one(".tgme_widget_message_text")
                date_el = msg_el.select_one(".tgme_widget_message_date time")
                views_el = msg_el.select_one(".tgme_widget_message_views")

                if text_el:
                    messages.append(
                        {
                            "text": text_el.get_text(strip=True)[:500],
                            "date": date_el.get("datetime", "") if date_el else "",
                            "views": views_el.get_text(strip=True) if views_el else "0",
                        }
                    )
        except ImportError:
            logger.warning("beautifulsoup4 not installed")
            channel_title = channel_name
            channel_desc = ""
            subscriber_count = "0"

        return {
            "type": "channel",
            "channel_name": channel_name,
            "title": channel_title,
            "description": channel_desc,
            "subscriber_count": subscriber_count,
            "total_messages": len(messages),
            "posts": messages,
        }

    # ==========================================
    # Kakao Analyzer
    # ==========================================
    def _analyze_kakao(self, url):
        """Analyze Kakao profile or story."""
        parsed = urlparse(url)

        if "pf.kakao.com" in parsed.hostname:
            return self._analyze_kakao_profile(url, parsed)
        elif "story.kakao.com" in parsed.hostname:
            return self._analyze_kakao_story(url, parsed)
        elif "open.kakao.com" in parsed.hostname:
            return self._analyze_kakao_openchat(url, parsed)
        else:
            raise ValueError("Unsupported Kakao URL type")

    def _analyze_kakao_profile(self, url, parsed):
        """Analyze Kakao PlusFriend profile page."""
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()

        profile_info = {"type": "kakao_profile", "url": url}
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            title_el = soup.select_one("title")
            meta_desc = soup.select_one('meta[name="description"]') or soup.select_one(
                'meta[property="og:description"]'
            )

            profile_info["title"] = title_el.get_text(strip=True) if title_el else ""
            profile_info["description"] = (
                meta_desc.get("content", "") if meta_desc else ""
            )
        except ImportError:
            pass

        return profile_info

    def _analyze_kakao_story(self, url, parsed):
        """Analyze Kakao Story profile."""
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()

        story_info = {"type": "kakao_story", "url": url}
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            title_el = soup.select_one("title")
            meta_desc = soup.select_one('meta[property="og:description"]')

            story_info["title"] = title_el.get_text(strip=True) if title_el else ""
            story_info["description"] = (
                meta_desc.get("content", "") if meta_desc else ""
            )
        except ImportError:
            pass

        return story_info

    def _analyze_kakao_openchat(self, url, parsed):
        """Analyze Kakao OpenChat room info."""
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()

        chat_info = {"type": "kakao_openchat", "url": url}
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            title_el = soup.select_one("title")
            meta_desc = soup.select_one('meta[property="og:description"]')
            meta_image = soup.select_one('meta[property="og:image"]')

            chat_info["title"] = title_el.get_text(strip=True) if title_el else ""
            chat_info["description"] = meta_desc.get("content", "") if meta_desc else ""
            chat_info["thumbnail"] = meta_image.get("content", "") if meta_image else ""
        except ImportError:
            pass

        return chat_info

    # ==========================================
    # X (Twitter) Analyzer
    # ==========================================
    def _analyze_twitter(self, url):
        """Analyze X (Twitter) profile or tweet."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")

        # Check if it's a specific tweet/status
        status_match = re.search(r"([^/]+)/status/(\d+)", path)
        if status_match:
            username = status_match.group(1)
            tweet_id = status_match.group(2)
            return self._analyze_twitter_tweet(username, tweet_id)

        # Otherwise treat as profile
        username = path.split("/")[0] if path else None
        if not username:
            raise ValueError("Could not extract username from X/Twitter URL")
        return self._analyze_twitter_profile(username)

    def _analyze_twitter_profile(self, username):
        """Fetch X/Twitter profile info via FxTwitter API + Twitter API v2 timeline."""
        profile_posts: list[dict[str, Any]] = []
        profile_info: dict[str, Any] = {
            "type": "profile",
            "username": username,
            "title": f"@{username}",
            "posts": profile_posts,
        }

        # Method 1: Try FxTwitter/FixupX API for profile info
        try:
            resp = self._session.get(
                f"https://api.fxtwitter.com/{username}",
                timeout=15,
                headers={"User-Agent": "SNSMonitor/1.0"},
            )
            if resp.ok:
                data = resp.json()
                user_data = data.get("user", {})
                if user_data:
                    profile_info["title"] = user_data.get("name", f"@{username}")
                    profile_info["description"] = user_data.get("description", "")
                    profile_info["thumbnail"] = user_data.get("avatar_url", "")
                    profile_info["follower_count"] = user_data.get("followers", 0)
                    profile_info["following_count"] = user_data.get("following", 0)
                    profile_info["tweet_count"] = user_data.get("tweets", 0)
                    if user_data.get("banner_url"):
                        profile_info["banner"] = user_data["banner_url"]
        except Exception as e:
            logger.warning(f"FxTwitter profile fetch failed for {username}: {e}")

        # Method 2: Twitter API v2 for timeline posts (requires Bearer Token)
        bearer_token = os.environ.get("TWITTER_BEARER_TOKEN", "").strip()
        if bearer_token:
            try:
                posts = self._fetch_twitter_timeline_v2(username, bearer_token)
                if posts:
                    profile_info["posts"] = posts
            except Exception as e:
                logger.warning(
                    f"Twitter API v2 timeline fetch failed for {username}: {e}"
                )

        # Method 3: Try syndication API for timeline tweets (fallback)
        if not profile_info["posts"]:
            try:
                timeline_url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
                resp = self._session.get(
                    timeline_url,
                    timeout=15,
                    headers={
                        "User-Agent": self._session.headers["User-Agent"],
                        "Accept": "text/html,application/xhtml+xml",
                    },
                )
                if resp.ok:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(resp.text, "html.parser")

                    tweet_elements = soup.select("[data-tweet-id]") or soup.select(
                        ".timeline-Tweet"
                    )
                    for tweet_el in tweet_elements[:50]:
                        text_el = tweet_el.select_one(
                            ".timeline-Tweet-text"
                        ) or tweet_el.select_one(".e-entry-title")
                        if text_el:
                            profile_info["posts"].append(
                                {
                                    "text": text_el.get_text(strip=True)[:500],
                                    "author": f"@{username}",
                                }
                            )
            except Exception as e:
                logger.warning(f"Twitter syndication fetch failed for {username}: {e}")

        # Method 4: Fallback to og:meta from X.com
        if not profile_info.get("description"):
            try:
                page_resp = self._session.get(
                    f"https://x.com/{username}",
                    timeout=15,
                    headers={
                        "User-Agent": self._session.headers["User-Agent"],
                        "Accept": "text/html,application/xhtml+xml",
                    },
                )
                if page_resp.ok:
                    from bs4 import BeautifulSoup

                    page_soup = BeautifulSoup(page_resp.text, "html.parser")

                    og_title = page_soup.select_one('meta[property="og:title"]')
                    og_desc = page_soup.select_one('meta[property="og:description"]')
                    og_image = page_soup.select_one('meta[property="og:image"]')

                    if og_title and profile_info["title"] == f"@{username}":
                        title_val = og_title.get("content")
                        profile_info["title"] = (
                            title_val
                            if isinstance(title_val, str) and title_val
                            else f"@{username}"
                        )
                    if og_desc:
                        desc_val = og_desc.get("content")
                        profile_info["description"] = (
                            desc_val
                            if isinstance(desc_val, str)
                            else str(desc_val or "")
                        )
                    if og_image and "thumbnail" not in profile_info:
                        image_val = og_image.get("content")
                        profile_info["thumbnail"] = (
                            image_val
                            if isinstance(image_val, str)
                            else str(image_val or "")
                        )
            except Exception as e:
                logger.warning(f"Twitter page fetch failed for {username}: {e}")

        profile_info["total_posts"] = len(profile_info["posts"])
        return profile_info

    def _fetch_twitter_timeline_v2(self, username, bearer_token):
        """Fetch user timeline via Twitter API v2."""
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "User-Agent": "SNSMonitor/1.0",
        }

        # Step 1: Get user ID from username
        resp = self._session.get(
            f"https://api.twitter.com/2/users/by/username/{username}",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        user_data = resp.json().get("data", {})
        user_id = user_data.get("id")
        if not user_id:
            logger.warning(f"Twitter API v2: user not found: {username}")
            return []

        # Step 2: Get recent tweets
        resp = self._session.get(
            f"https://api.twitter.com/2/users/{user_id}/tweets",
            params={
                "max_results": 50,
                "tweet.fields": "created_at,public_metrics,text",
                "exclude": "retweets",
            },
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        tweets = resp.json().get("data", [])

        posts = []
        for tweet in tweets:
            metrics = tweet.get("public_metrics", {})
            posts.append(
                {
                    "text": tweet.get("text", "")[:500],
                    "author": f"@{username}",
                    "like_count": metrics.get("like_count", 0),
                    "retweet_count": metrics.get("retweet_count", 0),
                    "reply_count": metrics.get("reply_count", 0),
                    "date": tweet.get("created_at", ""),
                }
            )
        return posts

    def _analyze_twitter_tweet(self, username, tweet_id):
        """Fetch a specific tweet via FxTwitter API or og:meta."""
        tweet_posts: list[dict[str, Any]] = []
        tweet_info: dict[str, Any] = {
            "type": "tweet",
            "username": username,
            "tweet_id": tweet_id,
            "title": f"Tweet by @{username}",
            "posts": tweet_posts,
        }

        # Method 1: FxTwitter API (returns JSON with tweet content)
        try:
            resp = self._session.get(
                f"https://api.fxtwitter.com/{username}/status/{tweet_id}",
                timeout=15,
                headers={"User-Agent": "SNSMonitor/1.0"},
            )
            if resp.ok:
                data = resp.json()
                tweet_data = data.get("tweet", {})
                if tweet_data:
                    text = tweet_data.get("text", "")
                    tweet_info["title"] = (
                        text[:100] if text else f"Tweet by @{username}"
                    )
                    tweet_info["description"] = text
                    tweet_info["posts"].append(
                        {
                            "text": text[:500],
                            "author": f"@{tweet_data.get('author', {}).get('screen_name', username)}",
                            "like_count": tweet_data.get("likes", 0),
                            "date": tweet_data.get("created_at", ""),
                        }
                    )
                    if tweet_data.get("retweets"):
                        tweet_info["retweet_count"] = tweet_data["retweets"]
                    if tweet_data.get("replies"):
                        tweet_info["reply_count"] = tweet_data["replies"]
                    if tweet_data.get("views"):
                        tweet_info["view_count"] = tweet_data["views"]
                    # Author info
                    author = tweet_data.get("author", {})
                    if author:
                        tweet_info["author_name"] = author.get("name", "")
                        tweet_info["thumbnail"] = author.get("avatar_url", "")
        except Exception as e:
            logger.warning(f"FxTwitter tweet fetch failed for {tweet_id}: {e}")

        # Method 2: Fallback to og:meta
        if not tweet_info["posts"]:
            try:
                page_resp = self._session.get(
                    f"https://x.com/{username}/status/{tweet_id}",
                    timeout=15,
                    headers={
                        "User-Agent": self._session.headers["User-Agent"],
                        "Accept": "text/html,application/xhtml+xml",
                    },
                )
                if page_resp.ok:
                    from bs4 import BeautifulSoup

                    page_soup = BeautifulSoup(page_resp.text, "html.parser")

                    og_title = page_soup.select_one('meta[property="og:title"]')
                    og_desc = page_soup.select_one('meta[property="og:description"]')

                    if og_title:
                        current_title = str(
                            tweet_info.get("title") or f"Tweet by @{username}"
                        )
                        title_val = og_title.get("content")
                        tweet_info["title"] = (
                            title_val
                            if isinstance(title_val, str) and title_val
                            else current_title
                        )
                    if og_desc:
                        desc_value = og_desc.get("content", "")
                        desc = (
                            desc_value
                            if isinstance(desc_value, str)
                            else str(desc_value or "")
                        )
                        tweet_info["description"] = desc
                        tweet_info["posts"].append(
                            {
                                "text": desc[:500],
                                "author": f"@{username}",
                            }
                        )
            except Exception as e:
                logger.warning(f"Twitter tweet page fetch failed: {e}")

        tweet_info["total_posts"] = len(tweet_info["posts"])
        return tweet_info

    # ==========================================
    # Instagram (og:meta 기반 게시글/프로필 내용 수집, 댓글은 공식 API 필요)
    # ==========================================
    def _analyze_instagram(self, url):
        """Instagram URL에서 og:meta로 게시글/프로필 제목·설명·이미지 수집. 실패 시 URL 기반 제목과 안내만 반환."""
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/").rstrip("/")
        segments = [s for s in path.split("/") if s]
        username = segments[0] if segments else "unknown"
        is_post = len(segments) >= 2 and segments[0] in ("p", "reel") and segments[1]
        # URL만으로 제목 결정 (수집 실패 시에도 표시용)
        if is_post:
            label = "Reel" if segments[0] == "reel" else "게시글"
            title_from_url = f"Instagram {label} · @{username}"
        else:
            title_from_url = f"@{username}" if username != "unknown" else "Instagram"

        out = {
            "type": "post" if is_post else "profile",
            "username": username,
            "title": title_from_url,
            "description": "",
            "url": url,
            "posts": [],
            "thumbnail": "",
        }

        headers = {
            "User-Agent": self._session.headers["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Referer": "https://www.instagram.com/",
        }
        try:
            resp = self._session.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")
            og_title = soup.select_one('meta[property="og:title"]')
            og_desc = soup.select_one('meta[property="og:description"]')
            og_image = soup.select_one('meta[property="og:image"]')

            title_raw = og_title.get("content", "") if og_title else ""
            desc_raw = og_desc.get("content", "") if og_desc else ""
            image_raw = og_image.get("content", "") if og_image else ""
            title_val = (
                title_raw if isinstance(title_raw, str) else str(title_raw or "")
            )
            desc_val = desc_raw if isinstance(desc_raw, str) else str(desc_raw or "")
            image_val = (
                image_raw if isinstance(image_raw, str) else str(image_raw or "")
            )
            title_val = title_val.strip()
            desc_val = desc_val.strip()
            image_val = image_val.strip()

            if title_val:
                out["title"] = title_val
                if " on Instagram" in title_val:
                    out["username"] = title_val.split(" on Instagram")[0].strip()
            if desc_val:
                out["description"] = desc_val
            if image_val:
                out["thumbnail"] = image_val

            author_label = f"@{out.get('username', username)}"
            post_entry = {
                "text": desc_val or title_val or "(내용 없음)",
                "author": author_label,
                "url": url,
                "comments": [],
            }
            if is_post:
                out["posts"] = [post_entry]
                out["total_posts"] = 1
            else:
                if desc_val or title_val:
                    out["posts"] = [post_entry]
                out["total_posts"] = len(out["posts"])
        except Exception as e:
            logger.warning("Instagram fetch failed (og:meta): %s", e)
            out["description"] = (
                "Instagram이 비로그인 요청을 제한해 페이지 내용을 가져오지 못했습니다. "
                "아래 '원문 보기'로 브라우저에서 직접 확인하거나, Meta 개발자 앱·Instagram Graph API 연동 시 수집할 수 있습니다. "
                "댓글 수집은 Instagram 공식 API가 필요합니다."
            )
            # 수집 실패해도 원문 링크용 포스트 1건 추가
            out["posts"] = [
                {
                    "text": "원문에서 확인",
                    "author": f"@{username}",
                    "url": url,
                    "comments": [],
                },
            ]
            out["total_posts"] = 1

        if not out["posts"] and not out["description"]:
            out["description"] = (
                "Instagram URL 분석은 og:meta로 제한됩니다. 댓글 수집은 공식 API가 필요합니다."
            )
        return out

    def _analyze_facebook(self, url):
        """Facebook URL 인식. 실제 수집·분석은 준비 중."""
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/")
        segment = path.split("/")[0] if path else "unknown"
        return {
            "type": "profile",
            "username": segment,
            "title": segment,
            "description": "Facebook URL 분석은 현재 준비 중입니다. YouTube, DCInside, 네이버 카페, Reddit, X(Twitter) 등을 이용해 주세요.",
            "url": url,
        }

    def _analyze_threads(self, url):
        """Threads 게시글 URL 분석. oEmbed로 임베드 정보 수집, 댓글은 공식 API 미제공으로 빈 목록."""
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/").rstrip("/")
        segments = [s for s in path.split("/") if s]
        # threads.net/@user/post/CODE or threads.com/@user/post/CODE or threads.com/t/CODE
        is_post = ("post" in segments and len(segments) >= 3) or (
            len(segments) >= 2 and segments[0] == "t"
        )
        username = "unknown"
        for i, seg in enumerate(segments):
            if seg.startswith("@"):
                username = seg.lstrip("@")
                break
            if seg == "post" and i + 1 < len(segments):
                break

        # oEmbed API용 URL: 쿼리/프래그먼트 제거, threads.com 고정, trailing slash (Meta 문서 형식)
        path_only = "/".join(segments) if segments else ""
        oembed_url = f"https://www.threads.com/{path_only}/" if path_only else url
        if "threads.net" in url and path_only:
            oembed_url = f"https://www.threads.com/{path_only}/"

        embed_html = ""
        title = f"@{username}" if username != "unknown" else "Threads"
        description = ""

        if is_post:
            try:
                api_url = f"https://graph.threads.net/v1.0/oembed?url={quote(oembed_url, safe='')}"
                r = self._session.get(api_url, timeout=15)
                body = r.text
                if not r.ok:
                    logger.warning(
                        "Threads oEmbed HTTP %s: %s",
                        r.status_code,
                        body[:500] if body else "",
                    )
                    raise ValueError(f"oEmbed returned {r.status_code}")
                data = r.json()
                if isinstance(data, dict) and "error" in data:
                    raise ValueError(data.get("error", {}).get("message", str(data)))
                embed_html = (data.get("html") or "").strip()
                if data.get("provider_name"):
                    title = f"Threads · {data.get('provider_name', '')} @{username}".strip()
                if embed_html:
                    description = "Threads 게시글 임베드입니다. 댓글은 Threads 공식 API 미제공으로 표시되지 않습니다."
            except Exception as e:
                logger.warning("Threads oEmbed fetch failed: %s", e)
                description = (
                    "Threads oEmbed로 게시글을 불러오지 못했습니다. URL이 공개 게시글인지 확인해 주세요. "
                    "아래 원문 보기에서 내용을 확인할 수 있습니다. 댓글은 Threads API 미지원으로 표시되지 않습니다."
                )
                # Fallback: og:meta로 제목·설명만 수집 (임베드 없음)
                try:
                    page = self._session.get(
                        oembed_url,
                        headers={
                            "User-Agent": self._session.headers["User-Agent"],
                            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
                        },
                        timeout=12,
                    )
                    if page.ok:
                        from bs4 import BeautifulSoup

                        soup = BeautifulSoup(page.text, "html.parser")
                        og_title = soup.select_one('meta[property="og:title"]')
                        og_desc = soup.select_one('meta[property="og:description"]')
                        if og_title and og_title.get("content"):
                            title = (og_title.get("content") or "").strip()[:200]
                        if og_desc and og_desc.get("content"):
                            description = (og_desc.get("content") or "").strip()[:500]
                except Exception as fallback_e:
                    logger.debug("Threads og:meta fallback failed: %s", fallback_e)
        else:
            description = "Threads 프로필 URL입니다. 게시글 분석은 개별 게시글 URL을 입력해 주세요."

        # 원문 링크는 사용자 입력 URL 유지 (쿼리 포함 가능)
        display_url = url.split("?")[0] if url else oembed_url

        return {
            "type": "post" if is_post else "profile",
            "username": username,
            "title": title,
            "description": description or "Threads 게시글 · 댓글은 API 미제공",
            "url": display_url,
            "content": description,
            "embed_html": embed_html,
            "replies": [],
        }

    def _analyze_tiktok(self, url):
        """TikTok URL analysis using oEmbed API."""
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/")
        segments = [s for s in path.split("/") if s]

        username = ""
        video_id = None
        for seg in segments:
            if seg.startswith("@"):
                username = seg.lstrip("@")
            if seg.isdigit() and len(seg) > 10:
                video_id = seg

        is_video = "video" in segments and video_id
        title = f"@{username}" if username else "TikTok"
        description = ""
        embed_html = ""
        author_name = username
        thumbnail = ""

        try:
            oembed_api = f"https://www.tiktok.com/oembed?url={quote(url, safe='')}"
            r = self._session.get(oembed_api, timeout=15)
            if r.ok:
                data = r.json()
                title = data.get("title") or title
                author_name = data.get("author_name") or username
                embed_html = data.get("html") or ""
                thumbnail = data.get("thumbnail_url") or ""
                if data.get("author_url"):
                    description = f"TikTok @{author_name}"
        except Exception as e:
            logger.warning("TikTok oEmbed failed: %s", e)

        if not description:
            if is_video:
                description = "TikTok 동영상입니다. 댓글은 TikTok API 제한으로 수집되지 않습니다."
            else:
                description = f"TikTok @{username} 프로필입니다. 개별 동영상 URL을 입력하면 더 자세한 분석이 가능합니다."

        return {
            "type": "video" if is_video else "profile",
            "username": username or author_name,
            "title": title,
            "description": description,
            "thumbnail": thumbnail,
            "url": url.split("?")[0] if url else url,
            "content": description,
            "embed_html": embed_html,
            "comments": [],
        }

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
        """Analyze sentiment distribution from text items."""
        if not items:
            return {
                "total": 0,
                "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
            }

        positive_kw = [
            "좋아",
            "굿",
            "최고",
            "감사",
            "사랑",
            "축하",
            "대박",
            "멋지",
            "예쁘",
            "귀엽",
            "화이팅",
            "응원",
            "레전드",
            "갓",
            "good",
            "great",
            "love",
            "amazing",
            "awesome",
            "best",
            "nice",
            "cool",
            "beautiful",
            "wonderful",
            "excellent",
            "perfect",
        ]
        negative_kw = [
            "싫어",
            "나쁘",
            "최악",
            "짜증",
            "실망",
            "별로",
            "노잼",
            "재미없",
            "쓰레기",
            "망했",
            "bad",
            "worst",
            "hate",
            "terrible",
            "awful",
            "boring",
            "ugly",
            "trash",
            "waste",
            "stupid",
            "sucks",
        ]

        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        keywords = Counter()

        for item in items:
            text = (item.get("text", "") or "").lower()
            if not text:
                continue

            has_pos = any(kw in text for kw in positive_kw)
            has_neg = any(kw in text for kw in negative_kw)

            if has_pos and not has_neg:
                sentiment_counts["positive"] += 1
            elif has_neg and not has_pos:
                sentiment_counts["negative"] += 1
            else:
                sentiment_counts["neutral"] += 1

            # Extract keywords (simple word frequency)
            words = re.findall(r"[가-힣]{2,}|[a-zA-Z]{3,}", text)
            keywords.update(words)

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

            logger.info(f"Saved analysis result: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to save result: {e}")
