"""
DCInside platform analyzer mixin.
All DCInside-specific methods extracted from PlatformAnalyzer.
"""

import json
import logging
import os
import re
import time
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DCInsideMixin:
    """Mixin providing DCInside analysis methods for PlatformAnalyzer."""

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

        # Per-post comment collection (opt-in via options or default top 5)
        opts = getattr(self, "_analyze_options", {})
        fetch_comments = opts.get("fetch_comments", True)
        max_comment_posts = int(opts.get("max_comment_posts", 5))
        max_comment_posts = min(max(max_comment_posts, 0), 50)
        # Time budget: prevent request timeout for large collections
        comment_time_budget = min(max_comment_posts * 10, 180)  # ~10s per post, max 3min

        comment_fetch_stats = {"attempted": 0, "collected": 0, "timed_out": False}
        if fetch_comments:
            t_start = time.monotonic()
            for i, post in enumerate(posts):
                if i >= max_comment_posts:
                    break
                if not post.get("comment_count", 0):
                    continue
                elapsed = time.monotonic() - t_start
                if elapsed > comment_time_budget:
                    logger.info(
                        "DCInside comment collection time budget exceeded (%.1fs/%.0fs) after %d posts",
                        elapsed, comment_time_budget, comment_fetch_stats["attempted"],
                    )
                    comment_fetch_stats["timed_out"] = True
                    break
                comment_fetch_stats["attempted"] += 1
                try:
                    comments = self._fetch_dcinside_post_comments(
                        gallery_id, post["number"], gallery_type, headers
                    )
                    post["comments"] = comments if comments else []
                    comment_fetch_stats["collected"] += len(post["comments"])
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

        result = {
            "type": "gallery",
            "gallery_id": gallery_id,
            "gallery_name": gallery_name,
            "gallery_type": "mini"
            if is_mini
            else ("mgallery" if is_mgallery else "major"),
            "total_posts": len(posts),
            "posts": posts,
        }
        if comment_fetch_stats["timed_out"]:
            result["comment_fetch_note"] = (
                f"시간 제한으로 {comment_fetch_stats['attempted']}개 게시글까지 댓글 수집 "
                f"(총 {comment_fetch_stats['collected']}건)"
            )
        return result

    def _build_dcinside_view_url(self, gallery_type, gallery_id, post_no):
        if gallery_type in ("board", "major"):
            return f"https://gall.dcinside.com/board/view/?id={gallery_id}&no={post_no}"
        return f"https://gall.dcinside.com/{gallery_type}/board/view/?id={gallery_id}&no={post_no}"

    def _build_dcinside_comment_api_url(self, gallery_type):
        """Comment API base URL; mini/mgallery use type-prefixed path. 'major' => board."""
        if gallery_type in ("board", "major"):
            return "https://gall.dcinside.com/board/comment/"
        return f"https://gall.dcinside.com/{gallery_type}/board/comment/"

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
        opts = getattr(self, "_analyze_options", {})
        max_comments = int(opts.get("max_comments", 500))

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
            "comments": comments[:max_comments],
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
        referer_url = self._build_dcinside_view_url(ref_type, gallery_id, post_no)
        req_headers = {
            "User-Agent": headers.get(
                "User-Agent", self._session.headers["User-Agent"]
            ),
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": referer_url,
            "Origin": "https://gall.dcinside.com",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        form_data = {
            "id": gallery_id,
            "no": str(post_no),
            "cmt_id": gallery_id,
            "cmt_no": str(post_no),
            "e_s_n_o": token,
            "comment_page": "1",
            "sort": "",
            "prevCnt": "0",
            "_GALLTYPE_": "G" if gallery_type in ("board", "major") else "M",
        }
        opts = getattr(self, "_analyze_options", {})
        max_comments = int(opts.get("max_comments", 500))
        max_pages = max(max_comments // 20, 5)  # ~20 comments per page
        comments = []
        for page in range(1, max_pages + 1):
            try:
                form_data["comment_page"] = str(page)
                form_data["prevCnt"] = str(len(comments))
                r = self._session.post(
                    api_url,
                    data=form_data,
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
                # Adaptive delay: increase with page depth to avoid rate limiting
                delay = 0.5 + (page * 0.1)  # 0.6s, 0.7s, 0.8s...
                time.sleep(min(delay, 2.0))
            except Exception as e:
                logger.debug("DCInside comment API page %s: %s", page, e)
                break
        return comments[:max_comments]

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
        opts = getattr(self, "_analyze_options", {})
        max_comments = int(opts.get("max_comments", 500))
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
                return comments[:max_comments]
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
                return comments[:max_comments]
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
        return comments[:max_comments] if comments else []

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
                    opts = getattr(self, "_analyze_options", {})
                    max_cmt = int(opts.get("max_comments", 500))
                    return comments[:max_cmt]
        except Exception as e:
            logger.warning(
                "DCInside Playwright comment fallback failed (post %s): %s",
                post_no,
                e,
            )
        return []
