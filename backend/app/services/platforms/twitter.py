"""
Twitter/X platform mixin for PlatformAnalyzer.
Provides methods: _analyze_twitter, _analyze_twitter_profile,
_fetch_twitter_timeline_v2, _analyze_twitter_tweet, _fetch_twitter_replies
"""

import os
import re
import logging
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class TwitterMixin:
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

        # Method 2: Twitter API v2 direct tweet lookup (if bearer token available)
        if not tweet_info["posts"]:
            bearer_token = (os.environ.get("TWITTER_BEARER_TOKEN") or "").strip()
            if bearer_token:
                try:
                    resp = self._session.get(
                        f"https://api.twitter.com/2/tweets/{tweet_id}",
                        params={
                            "tweet.fields": "created_at,public_metrics,text,author_id",
                            "expansions": "author_id",
                            "user.fields": "username,name,profile_image_url",
                        },
                        headers={
                            "Authorization": f"Bearer {bearer_token}",
                            "User-Agent": "SNSMonitor/1.0",
                        },
                        timeout=15,
                    )
                    if resp.ok:
                        data = resp.json()
                        tweet_data = data.get("data", {})
                        if tweet_data:
                            text = tweet_data.get("text", "")
                            metrics = tweet_data.get("public_metrics", {})
                            tweet_info["title"] = text[:100] if text else f"Tweet by @{username}"
                            tweet_info["description"] = text
                            tweet_info["posts"].append({
                                "text": text[:500],
                                "author": f"@{username}",
                                "like_count": metrics.get("like_count", 0),
                                "date": tweet_data.get("created_at", ""),
                            })
                            tweet_info["reply_count"] = metrics.get("reply_count", 0)
                            tweet_info["retweet_count"] = metrics.get("retweet_count", 0)
                            tweet_info["view_count"] = metrics.get("impression_count", 0)
                            # Author from expansions
                            users = data.get("includes", {}).get("users", [])
                            if users:
                                tweet_info["author_name"] = users[0].get("name", "")
                                tweet_info["thumbnail"] = users[0].get("profile_image_url", "")
                except Exception as e:
                    logger.warning("Twitter API v2 tweet lookup failed for %s: %s", tweet_id, e)

        # Method 3: Fallback to og:meta
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

        # Fetch replies (comments) for the tweet
        comments = self._fetch_twitter_replies(tweet_id, username)
        tweet_info["comments"] = comments
        tweet_info["comment_count"] = tweet_info.get("reply_count", len(comments))
        tweet_info["total_posts"] = len(tweet_info["posts"])
        return tweet_info

    def _fetch_twitter_replies(self, tweet_id, username):
        """Fetch replies to a tweet via Twitter API v2 conversation search."""
        bearer_token = (os.environ.get("TWITTER_BEARER_TOKEN") or "").strip()
        if not bearer_token:
            return []

        comments = []
        try:
            headers = {
                "Authorization": f"Bearer {bearer_token}",
                "User-Agent": "SNSMonitor/1.0",
            }
            resp = self._session.get(
                "https://api.twitter.com/2/tweets/search/recent",
                params={
                    "query": f"conversation_id:{tweet_id}",
                    "max_results": 100,
                    "tweet.fields": "created_at,public_metrics,author_id,in_reply_to_user_id",
                    "expansions": "author_id",
                    "user.fields": "username,name",
                },
                headers=headers,
                timeout=15,
            )
            if not resp.ok:
                logger.warning("Twitter v2 replies search failed: %s %s", resp.status_code, resp.text[:200])
                return []

            data = resp.json()
            tweets = data.get("data", [])
            # Build author_id -> username mapping
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            for tweet in tweets:
                metrics = tweet.get("public_metrics", {})
                author_id = tweet.get("author_id", "")
                author_info = users.get(author_id, {})
                author_username = author_info.get("username", "")
                comments.append({
                    "text": tweet.get("text", "")[:500],
                    "author": f"@{author_username}" if author_username else "",
                    "like_count": metrics.get("like_count", 0),
                    "date": tweet.get("created_at", ""),
                })
        except Exception as e:
            logger.warning("Twitter replies fetch failed for %s: %s", tweet_id, e)

        return comments
