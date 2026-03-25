"""Reddit platform mixin for PlatformAnalyzer."""

import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class RedditMixin:
    """Mixin providing Reddit analysis methods for PlatformAnalyzer."""

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
