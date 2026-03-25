"""
Threads platform mixin for PlatformAnalyzer.
Provides methods: _analyze_threads, _fetch_threads_api,
_fetch_threads_html, _extract_threads_json_data
"""

import json
import os
import logging
from urllib.parse import urlparse, quote

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ThreadsMixin:
    def _analyze_threads(self, url):
        """Threads 게시글 URL 분석.
        1) THREADS_ACCESS_TOKEN이 있으면 공식 API로 포스트+댓글 수집
        2) 없으면 HTML 스크래핑 (og:meta + embedded JSON) fallback
        3) 최종 fallback: oEmbed
        """
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/").rstrip("/")
        segments = [s for s in path.split("/") if s]
        # threads.net/@user/post/CODE or threads.com/@user/post/CODE or threads.com/t/CODE
        is_post = ("post" in segments and len(segments) >= 3) or (
            len(segments) >= 2 and segments[0] == "t"
        )
        username = "unknown"
        shortcode = ""
        for i, seg in enumerate(segments):
            if seg.startswith("@"):
                username = seg.lstrip("@")
            if seg == "post" and i + 1 < len(segments):
                shortcode = segments[i + 1]
            if seg == "t" and i + 1 < len(segments):
                shortcode = segments[i + 1]

        # Canonical URL for scraping/oEmbed
        path_only = "/".join(segments) if segments else ""
        canonical_url = f"https://www.threads.net/{path_only}/" if path_only else url

        if not is_post:
            return {
                "type": "profile",
                "username": username,
                "title": f"@{username}" if username != "unknown" else "Threads",
                "description": "Threads 프로필 URL입니다. 게시글 분석은 개별 게시글 URL을 입력해 주세요.",
                "url": url.split("?")[0],
                "content": "",
                "replies": [],
            }

        # Try official Threads API first (requires THREADS_ACCESS_TOKEN)
        access_token = (os.environ.get("THREADS_ACCESS_TOKEN") or "").strip()
        if access_token:
            api_result = self._fetch_threads_api(access_token, shortcode, username, url)
            if api_result:
                return api_result

        # Fallback: HTML scraping for post content + embedded JSON
        result = self._fetch_threads_html(canonical_url, username, shortcode, url)
        return result

    def _fetch_threads_api(self, access_token, shortcode, username, original_url):
        """Fetch Threads post + replies via official Meta Threads API."""
        api_base = "https://graph.threads.net/v1.0"
        headers_auth = {"Authorization": f"Bearer {access_token}"}

        # Step 1: Search for media ID using user's threads
        # The API requires media ID, not shortcode. Try to find via user threads.
        # First, get user profile to find user ID
        try:
            me_resp = self._session.get(
                f"{api_base}/me",
                params={"fields": "id,username", "access_token": access_token},
                timeout=15,
            )
            if not me_resp.ok:
                logger.warning("Threads API /me failed: %s %s", me_resp.status_code, me_resp.text[:200])
                return None
            me_data = me_resp.json()
            user_id = me_data.get("id")
            if not user_id:
                return None
        except Exception as e:
            logger.warning("Threads API auth failed: %s", e)
            return None

        # Step 2: Search user's threads for the matching shortcode
        thread_id = None
        try:
            threads_resp = self._session.get(
                f"{api_base}/{user_id}/threads",
                params={
                    "fields": "id,text,username,timestamp,permalink,shortcode,media_type",
                    "limit": 50,
                    "access_token": access_token,
                },
                timeout=15,
            )
            if threads_resp.ok:
                for item in threads_resp.json().get("data", []):
                    item_sc = item.get("shortcode") or ""
                    item_permalink = item.get("permalink") or ""
                    if shortcode and (shortcode == item_sc or shortcode in item_permalink):
                        thread_id = item.get("id")
                        break
        except Exception as e:
            logger.debug("Threads API user threads search: %s", e)

        if not thread_id:
            logger.info("Threads API: could not find thread_id for shortcode %s", shortcode)
            return None

        # Step 3: Fetch post details
        post_text = ""
        post_username = username
        post_timestamp = ""
        permalink = original_url
        try:
            post_resp = self._session.get(
                f"{api_base}/{thread_id}",
                params={
                    "fields": "id,text,username,timestamp,permalink,media_type,is_quote_post",
                    "access_token": access_token,
                },
                timeout=15,
            )
            if post_resp.ok:
                pd = post_resp.json()
                post_text = pd.get("text", "")
                post_username = pd.get("username", username)
                post_timestamp = pd.get("timestamp", "")
                permalink = pd.get("permalink", permalink)
        except Exception as e:
            logger.debug("Threads API post fetch: %s", e)

        # Step 4: Fetch engagement metrics
        like_count = 0
        reply_count = 0
        view_count = 0
        try:
            insights_resp = self._session.get(
                f"{api_base}/{thread_id}/insights",
                params={
                    "metric": "likes,replies,views",
                    "access_token": access_token,
                },
                timeout=15,
            )
            if insights_resp.ok:
                for metric in insights_resp.json().get("data", []):
                    name = metric.get("name", "")
                    val = metric.get("values", [{}])[0].get("value", 0) if metric.get("values") else 0
                    if name == "likes":
                        like_count = val
                    elif name == "replies":
                        reply_count = val
                    elif name == "views":
                        view_count = val
        except Exception as e:
            logger.debug("Threads API insights: %s", e)

        # Step 5: Fetch replies
        replies = []
        try:
            replies_resp = self._session.get(
                f"{api_base}/{thread_id}/replies",
                params={
                    "fields": "id,text,username,timestamp,has_replies",
                    "limit": 100,
                    "access_token": access_token,
                },
                timeout=15,
            )
            if replies_resp.ok:
                for r_item in replies_resp.json().get("data", []):
                    text = (r_item.get("text") or "").strip()
                    if text:
                        replies.append({
                            "text": text[:500],
                            "author": r_item.get("username", "—"),
                            "date": r_item.get("timestamp", ""),
                        })
        except Exception as e:
            logger.debug("Threads API replies: %s", e)

        return {
            "type": "post",
            "username": post_username,
            "title": f"@{post_username}",
            "description": post_text[:500] if post_text else "",
            "content": post_text,
            "url": permalink,
            "like_count": like_count,
            "reply_count": reply_count,
            "view_count": view_count,
            "comment_count": len(replies),
            "replies": replies,
            "source": "threads_api",
        }

    def _fetch_threads_html(self, canonical_url, username, shortcode, original_url):
        """Fetch Threads post content via HTML scraping (og:meta + embedded JSON)."""
        title = f"@{username}" if username != "unknown" else "Threads"
        description = ""
        content = ""
        embed_html = ""
        like_count = None
        reply_count = None
        replies = []

        # Try HTML page scraping
        try:
            page = self._session.get(
                canonical_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
                },
                timeout=15,
            )
            if page.ok:
                html_text = page.text
                soup = BeautifulSoup(html_text, "html.parser")

                # Extract og:meta
                og_title = soup.select_one('meta[property="og:title"]')
                og_desc = soup.select_one('meta[property="og:description"]')
                if og_title and og_title.get("content"):
                    title = (og_title["content"]).strip()[:200]
                if og_desc and og_desc.get("content"):
                    content = (og_desc["content"]).strip()[:2000]
                    description = content

                # Try to extract embedded JSON data from script tags
                for script in soup.select("script[type='application/json']"):
                    try:
                        script_text = script.string or ""
                        if not script_text or len(script_text) < 50:
                            continue
                        sdata = json.loads(script_text)
                        # Threads embeds post data in various JSON structures
                        extracted = self._extract_threads_json_data(sdata, username)
                        if extracted:
                            if extracted.get("text"):
                                content = extracted["text"]
                                description = content[:500]
                            if extracted.get("like_count") is not None:
                                like_count = extracted["like_count"]
                            if extracted.get("reply_count") is not None:
                                reply_count = extracted["reply_count"]
                            if extracted.get("replies"):
                                replies = extracted["replies"]
                            if extracted.get("username"):
                                username = extracted["username"]
                                title = f"@{username}"
                            break
                    except (json.JSONDecodeError, TypeError):
                        continue

                # Also try ld+json for structured data
                for script in soup.select("script[type='application/ld+json']"):
                    try:
                        ld = json.loads(script.string or "")
                        if isinstance(ld, dict):
                            if ld.get("articleBody"):
                                content = content or ld["articleBody"][:2000]
                            if ld.get("author", {}).get("name"):
                                author_name = ld["author"]["name"]
                                if username == "unknown":
                                    username = author_name
                                    title = f"@{username}"
                            interaction = ld.get("interactionStatistic", [])
                            if isinstance(interaction, list):
                                for stat in interaction:
                                    stype = stat.get("interactionType", "")
                                    count = stat.get("userInteractionCount", 0)
                                    if "Like" in stype:
                                        like_count = like_count or int(count)
                                    if "Comment" in stype or "Reply" in stype:
                                        reply_count = reply_count or int(count)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        continue

        except Exception as e:
            logger.warning("Threads HTML scraping failed: %s", e)

        # Final fallback: oEmbed for embed HTML
        if not content:
            try:
                oembed_target = canonical_url.replace("threads.net", "threads.com")
                api_url = f"https://graph.threads.net/v1.0/oembed?url={quote(oembed_target, safe='')}"
                r = self._session.get(api_url, timeout=15)
                if r.ok:
                    data = r.json()
                    embed_html = (data.get("html") or "").strip()
                    if not content and embed_html:
                        # Extract text from embed HTML
                        embed_soup = BeautifulSoup(embed_html, "html.parser")
                        content = embed_soup.get_text(separator="\n", strip=True)[:2000]
                        description = content[:500]
            except Exception as e:
                logger.debug("Threads oEmbed fallback: %s", e)

        if not content and not description:
            description = (
                "Threads 게시글을 불러오지 못했습니다. "
                "THREADS_ACCESS_TOKEN을 설정하면 게시글과 댓글을 수집할 수 있습니다."
            )

        display_url = original_url.split("?")[0] if original_url else canonical_url

        result = {
            "type": "post",
            "username": username,
            "title": title,
            "description": description,
            "content": content,
            "url": display_url,
            "embed_html": embed_html,
            "comment_count": len(replies) if replies else (reply_count or 0),
            "replies": replies,
            "source": "html_scraping",
        }
        if like_count is not None:
            result["like_count"] = like_count
        if reply_count is not None:
            result["reply_count"] = reply_count
        return result

    def _extract_threads_json_data(self, data, target_username=""):
        """Recursively search embedded JSON for Threads post data."""
        if not isinstance(data, (dict, list)):
            return None

        # If it's a dict, check if it looks like a post object
        if isinstance(data, dict):
            text = data.get("text") or data.get("caption") or data.get("body") or ""
            user = (
                data.get("username")
                or (data.get("user", {}) or {}).get("username", "")
                or (data.get("author", {}) or {}).get("username", "")
            )
            has_text = bool(text and len(str(text)) > 5)
            has_user = bool(user)

            if has_text and (has_user or not target_username):
                result = {"text": str(text)[:2000], "username": user}
                result["like_count"] = (
                    data.get("like_count")
                    or data.get("likes", {}).get("count") if isinstance(data.get("likes"), dict) else None
                )
                result["reply_count"] = (
                    data.get("reply_count")
                    or data.get("replies", {}).get("count") if isinstance(data.get("replies"), dict) else None
                )
                # Extract inline replies if present
                reply_list = data.get("replies") or data.get("text_post_app_replies") or {}
                if isinstance(reply_list, dict):
                    edges = reply_list.get("edges") or reply_list.get("data") or []
                    if isinstance(edges, list):
                        result["replies"] = []
                        for edge in edges[:100]:
                            node = edge.get("node", edge) if isinstance(edge, dict) else {}
                            r_text = (
                                node.get("text")
                                or node.get("caption")
                                or (node.get("post", {}) or {}).get("caption", {}).get("text", "")
                                or ""
                            )
                            r_user = (
                                node.get("username")
                                or (node.get("user", {}) or {}).get("username", "—")
                            )
                            r_date = node.get("taken_at") or node.get("timestamp") or ""
                            if r_text:
                                result["replies"].append({
                                    "text": str(r_text)[:500],
                                    "author": r_user,
                                    "date": str(r_date),
                                })
                return result

            # Recurse into dict values
            for key in data:
                found = self._extract_threads_json_data(data[key], target_username)
                if found:
                    return found

        # Recurse into list items
        if isinstance(data, list):
            for item in data:
                found = self._extract_threads_json_data(item, target_username)
                if found:
                    return found

        return None
