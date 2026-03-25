"""Other platform mixins (Telegram, Kakao, Instagram, Facebook, TikTok, Vuddy) for PlatformAnalyzer."""

import json
import logging
import re
from urllib.parse import urlparse, quote

logger = logging.getLogger(__name__)


class OtherPlatformsMixin:
    """Mixin providing Telegram, Kakao, Instagram, Facebook, TikTok, and Vuddy analysis methods."""

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

        profile_info = {"type": "kakao_profile", "url": url, "posts": []}
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            title_el = soup.select_one("title")
            meta_desc = soup.select_one('meta[name="description"]') or soup.select_one(
                'meta[property="og:description"]'
            )
            meta_image = soup.select_one('meta[property="og:image"]')

            profile_info["title"] = title_el.get_text(strip=True) if title_el else ""
            profile_info["description"] = (
                meta_desc.get("content", "") if meta_desc else ""
            )
            if meta_image:
                profile_info["thumbnail"] = meta_image.get("content", "")

            if profile_info.get("title") or profile_info.get("description"):
                profile_info["posts"] = [{
                    "text": profile_info.get("description") or profile_info.get("title") or "",
                    "author": profile_info.get("title", "Kakao"),
                    "url": url,
                }]
                profile_info["total_posts"] = 1
        except ImportError:
            pass

        return profile_info

    def _analyze_kakao_story(self, url, parsed):
        """Analyze Kakao Story profile."""
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()

        story_info = {"type": "kakao_story", "url": url, "posts": []}
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            title_el = soup.select_one("title")
            meta_desc = soup.select_one('meta[property="og:description"]')
            meta_image = soup.select_one('meta[property="og:image"]')

            story_info["title"] = title_el.get_text(strip=True) if title_el else ""
            story_info["description"] = (
                meta_desc.get("content", "") if meta_desc else ""
            )
            if meta_image:
                story_info["thumbnail"] = meta_image.get("content", "")

            if story_info.get("title") or story_info.get("description"):
                story_info["posts"] = [{
                    "text": story_info.get("description") or story_info.get("title") or "",
                    "author": story_info.get("title", "Kakao Story"),
                    "url": url,
                }]
                story_info["total_posts"] = 1
        except ImportError:
            pass

        return story_info

    def _analyze_kakao_openchat(self, url, parsed):
        """Analyze Kakao OpenChat room info."""
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()

        chat_info = {"type": "kakao_openchat", "url": url, "posts": []}
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            title_el = soup.select_one("title")
            meta_desc = soup.select_one('meta[property="og:description"]')
            meta_image = soup.select_one('meta[property="og:image"]')

            chat_info["title"] = title_el.get_text(strip=True) if title_el else ""
            chat_info["description"] = meta_desc.get("content", "") if meta_desc else ""
            chat_info["thumbnail"] = meta_image.get("content", "") if meta_image else ""

            # Extract additional OpenChat metadata
            og_type = soup.select_one('meta[property="og:type"]')
            if og_type:
                chat_info["og_type"] = og_type.get("content", "")

            # Try to extract member count and other info from page content
            page_text = soup.get_text(separator=" ", strip=True)
            member_match = re.search(r'(\d[\d,]*)\s*(?:명|members?)', page_text)
            if member_match:
                chat_info["member_count"] = int(member_match.group(1).replace(",", ""))

            # Build a post entry for display consistency
            if chat_info.get("title") or chat_info.get("description"):
                chat_info["posts"] = [{
                    "text": chat_info.get("description") or chat_info.get("title") or "",
                    "author": "Kakao OpenChat",
                    "url": url,
                }]
                chat_info["total_posts"] = 1
        except ImportError:
            pass

        return chat_info

    # ==========================================
    # Instagram Analyzer
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

        # oEmbed fallback for Instagram posts
        if is_post and not out.get("description"):
            try:
                oembed_url = f"https://graph.facebook.com/v18.0/instagram_oembed?url={quote(url, safe='')}&access_token={quote(url, safe='')}"
                # Public oEmbed (no token needed for basic info)
                oembed_resp = self._session.get(
                    f"https://api.instagram.com/oembed/?url={quote(url, safe='')}",
                    timeout=10,
                    headers={"User-Agent": "SNSMonitor/1.0"},
                )
                if oembed_resp.ok:
                    oembed_data = oembed_resp.json()
                    if oembed_data.get("title"):
                        out["title"] = oembed_data["title"][:200]
                    if oembed_data.get("author_name"):
                        out["username"] = oembed_data["author_name"]
                    if oembed_data.get("thumbnail_url"):
                        out["thumbnail"] = oembed_data["thumbnail_url"]
                    # Extract text from embed HTML
                    embed_html = oembed_data.get("html", "")
                    if embed_html:
                        out["embed_html"] = embed_html
                        from bs4 import BeautifulSoup
                        embed_soup = BeautifulSoup(embed_html, "html.parser")
                        text = embed_soup.get_text(separator="\n", strip=True)
                        if text and not out["description"]:
                            out["description"] = text[:500]
                            out["posts"] = [{
                                "text": text[:500],
                                "author": f"@{out.get('username', username)}",
                                "url": url,
                                "comments": [],
                            }]
                            out["total_posts"] = 1
            except Exception as e:
                logger.debug("Instagram oEmbed fallback failed: %s", e)

        if not out["posts"] and not out["description"]:
            out["description"] = (
                "Instagram URL 분석은 og:meta/oEmbed로 제한됩니다. 댓글 수집은 공식 API가 필요합니다."
            )
        return out

    # ==========================================
    # Facebook Analyzer
    # ==========================================
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

    # ==========================================
    # TikTok Analyzer
    # ==========================================
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

        oembed_ok = False
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
                oembed_ok = True
        except Exception as e:
            logger.warning("TikTok oEmbed failed: %s", e)

        # Fallback: scrape og:meta tags when oEmbed is blocked
        if not oembed_ok:
            try:
                r = self._session.get(url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)",
                    "Accept": "text/html",
                })
                if r.ok:
                    text = r.text[:30000]
                    og_title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', text)
                    og_desc = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"', text)
                    og_image = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"', text)
                    if og_title:
                        title = og_title.group(1)
                    if og_desc:
                        description = og_desc.group(1)
                    if og_image and not thumbnail:
                        thumbnail = og_image.group(1)
            except Exception as e:
                logger.debug("TikTok og:meta fallback failed: %s", e)

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
    # Vuddy.io (creator goods platform)
    # ==========================================
    def _analyze_vuddy(self, url):
        """Analyze vuddy.io creator/product page via og:meta + HTML scraping."""
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/").rstrip("/")
        segments = [s for s in path.split("/") if s]

        out = {
            "type": "platform",
            "title": "Vuddy",
            "description": "",
            "url": url,
            "posts": [],
            "thumbnail": "",
        }

        headers = {
            "User-Agent": self._session.headers["User-Agent"],
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }
        try:
            resp = self._session.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            # og:meta extraction
            og_title = soup.select_one('meta[property="og:title"]')
            og_desc = soup.select_one('meta[property="og:description"]')
            og_image = soup.select_one('meta[property="og:image"]')

            if og_title and og_title.get("content"):
                out["title"] = og_title["content"].strip()[:200]
            if og_desc and og_desc.get("content"):
                out["description"] = og_desc["content"].strip()[:500]
            if og_image and og_image.get("content"):
                out["thumbnail"] = og_image["content"].strip()

            # Detect page type from URL path
            if segments and segments[0] == "creator":
                out["type"] = "creator"
                if len(segments) >= 2:
                    out["creator_id"] = segments[1]
            elif segments and segments[0] in ("product", "goods"):
                out["type"] = "product"
            elif segments and segments[0] == "store":
                out["type"] = "store"

            # Extract visible text content from Next.js rendered page
            # Look for product cards, creator info, etc.
            for script in soup.select("script#__NEXT_DATA__"):
                try:
                    import json as _json
                    next_data = _json.loads(script.string or "")
                    page_props = next_data.get("props", {}).get("pageProps", {})
                    if page_props:
                        # Extract creator info
                        creator = page_props.get("creator") or page_props.get("data", {}).get("creator")
                        if creator and isinstance(creator, dict):
                            out["title"] = creator.get("name") or out["title"]
                            out["description"] = creator.get("description") or out["description"]
                            out["thumbnail"] = creator.get("profileImageUrl") or out["thumbnail"]
                            if creator.get("followerCount"):
                                out["follower_count"] = creator["followerCount"]

                        # Extract products
                        products = page_props.get("products") or page_props.get("data", {}).get("products")
                        if products and isinstance(products, list):
                            for p in products[:50]:
                                out["posts"].append({
                                    "text": p.get("name", p.get("title", "")),
                                    "author": p.get("creatorName", "Vuddy"),
                                    "url": f"https://vuddy.io/product/{p.get('id', '')}",
                                })
                except Exception:
                    pass

            # Fallback: extract from visible elements
            if not out["posts"]:
                for card in soup.select("[class*='product'], [class*='card'], [class*='item']")[:30]:
                    title_el = card.select_one("h3, h4, [class*='title'], [class*='name']")
                    if title_el:
                        out["posts"].append({
                            "text": title_el.get_text(strip=True)[:200],
                            "author": "Vuddy",
                        })

            # Build a summary post if no products found
            if not out["posts"] and out["description"]:
                out["posts"] = [{
                    "text": out["description"],
                    "author": "Vuddy",
                    "url": url,
                }]

            out["total_posts"] = len(out["posts"])

        except Exception as e:
            logger.warning("Vuddy analysis failed: %s", e)
            out["description"] = "Vuddy 페이지를 불러오지 못했습니다."

        return out
