"""Naver Cafe platform analyzer mixin."""
import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs, quote

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class NaverCafeMixin:
    """Naver Cafe analysis methods.

    Expects the following attributes on the host class:
        _session, _naver_cookie, _naver_proxies, _naver_disable_ssl_verify,
        _naver_search_client_id, _naver_search_client_secret,
        _naver_api_daily_limit, _rate_check, _rate_incr,
        _get_naver_api_count, _incr_naver_api_count,
        _naver_get, _append_naver_fetch_reason
    """

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
                            except Exception as e:
                                logger.debug("Naver Cafe timestamp parse failed: %s", e)
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

        # Search: try Naver Open API first, then fall back to client-side filtering
        if search_query and posts:
            naver_search_posts = self._naver_search_cafe_articles(
                search_query, cafe_name, club_id
            )
            if naver_search_posts is not None:
                # Merge: keep Open API results but enrich with existing post data
                existing_by_aid = {p.get("article_id"): p for p in posts if p.get("article_id")}
                merged = []
                for sp in naver_search_posts:
                    aid = sp.get("article_id")
                    if aid and aid in existing_by_aid:
                        # Prefer existing post (has comments etc), but update URL if missing
                        merged.append(existing_by_aid[aid])
                    else:
                        merged.append(sp)
                posts = merged
            else:
                # Fallback: client-side filtering
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

    def _naver_search_cafe_articles(self, query, cafe_name, club_id):
        """Search cafe articles using Naver Open API (cafearticle).

        Returns list of post dicts if API is configured, None otherwise.
        The Open API searches all cafes, so we filter by cafe_name or link pattern.
        """
        if not self._naver_search_client_id or not self._naver_search_client_secret:
            return None

        # Rate limit check (25,000 calls/day) — persist to Redis if available
        today = datetime.now(KST).strftime("%Y-%m-%d")
        count = self._get_naver_api_count(today)
        if count >= self._naver_api_daily_limit:
            logger.warning("Naver Search API daily limit reached (%d/%d)", count, self._naver_api_daily_limit)
            return None

        try:
            self._incr_naver_api_count(today)
            resp = self._session.get(
                "https://openapi.naver.com/v1/search/cafearticle.json",
                params={"query": query, "display": 50, "start": 1, "sort": "date"},
                headers={
                    "X-Naver-Client-Id": self._naver_search_client_id,
                    "X-Naver-Client-Secret": self._naver_search_client_secret,
                },
                timeout=10,
            )
            if not resp.ok:
                logger.warning("Naver Search API error: %s %s", resp.status_code, resp.text[:200])
                return None

            data = resp.json()
            items = data.get("items", [])
            if not items:
                return []

            # Filter to this specific cafe by matching club_id in link or cafename
            cafe_name_lower = (cafe_name or "").lower()
            cafe_link_pattern = f"/{club_id}/" if club_id else None
            filtered = []
            for item in items:
                link = item.get("link", "")
                item_cafe = item.get("cafename", "").lower()
                # Match by club_id in URL or cafe name
                if cafe_link_pattern and cafe_link_pattern in link:
                    pass
                elif cafe_name_lower and item_cafe == cafe_name_lower:
                    pass
                else:
                    continue

                # Extract article_id from link
                aid_match = re.search(r'/(\d+)(?:\?|$)', link)
                aid = aid_match.group(1) if aid_match else None

                # Clean HTML tags from title/description
                title = re.sub(r'<[^>]+>', '', item.get("title", ""))
                desc = re.sub(r'<[^>]+>', '', item.get("description", ""))

                filtered.append({
                    "text": title[:300],
                    "number": len(filtered) + 1,
                    "author": "",
                    "date": item.get("postdate", ""),
                    "url": link,
                    "article_id": aid,
                    "search_snippet": desc[:200],
                })

            logger.info(
                "Naver Search API: %d results, %d matched cafe %s",
                len(items), len(filtered), cafe_name or club_id,
            )
            return filtered if filtered else None  # None = fallback to client-side

        except Exception as e:
            logger.warning("Naver Search API failed: %s", e)
            return None

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
