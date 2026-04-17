"""
DCInside comment fetching and parsing mixin.
Extracted from dcinside.py to keep file size manageable.
"""

import json
import logging
import re
import time

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DCInsideCommentMixin:
    """Mixin providing DCInside comment fetching/parsing methods.

    Expects the host class to have: _session, _analyze_options (optional).
    Also provides URL builder and gallery type helpers used by both
    gallery analysis and comment fetching.
    """

    def _build_dcinside_view_url(self, gallery_type, gallery_id, post_no):
        if gallery_type in ("board", "major"):
            return f"https://gall.dcinside.com/board/view/?id={gallery_id}&no={post_no}"
        return f"https://gall.dcinside.com/{gallery_type}/board/view/?id={gallery_id}&no={post_no}"

    @staticmethod
    def _dcinside_galltype_value(gallery_type):
        """Map gallery_type to the _GALLTYPE_ form value expected by DCInside comment API."""
        if gallery_type in ("board", "major"):
            return "G"
        if gallery_type == "mini":
            return "MI"
        # mgallery
        return "M"

    def _build_dcinside_comment_api_url(self, gallery_type):
        """Comment API base URL; mini/mgallery use type-prefixed path. 'major' => board."""
        if gallery_type in ("board", "major"):
            return "https://gall.dcinside.com/board/comment/"
        return f"https://gall.dcinside.com/{gallery_type}/board/comment/"

    def _get_dcinside_comment_token(self, gallery_id, post_no, gallery_type, headers):
        """Extract e_s_n_o token from view page (required for comment API)."""
        view_url = self._build_dcinside_view_url(gallery_type, gallery_id, post_no)
        view_headers = dict(headers)
        view_headers.setdefault(
            "Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        )
        try:
            # Clear stale tracking cookies that cause DCInside to block subsequent requests
            for stale_cookie in ("csid", "gallRecom", "service_code"):
                if stale_cookie in self._session.cookies:
                    del self._session.cookies[stale_cookie]
            resp = self._session.get(view_url, headers=view_headers, timeout=12)
            if resp.status_code != 200:
                logger.debug(
                    "DCInside view page status %s for %s", resp.status_code, view_url
                )
                return ""
            text = resp.text
            # Try multiple patterns (page structure may vary)
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
        """Parse comment list from DCInside HTML fragment."""
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
        """Fetch comments via DCInside comment API (JSON)."""
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
            "_GALLTYPE_": self._dcinside_galltype_value(referer_gallery_type or gallery_type),
        }
        opts = getattr(self, "_analyze_options", {})
        max_comments = int(opts.get("max_comments", 500))
        max_pages = max(max_comments // 20, 5)
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
                delay = 0.5 + (page * 0.1)
                time.sleep(min(delay, 2.0))
            except Exception as e:
                logger.debug("DCInside comment API page %s: %s", page, e)
                break
        return comments[:max_comments]

    def _parse_dcinside_comment_item(self, item):
        """Extract author, text, date from a comment DOM item."""
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
        """Try to extract comment array from view page script/JSON."""
        comments = []
        if not html_text or not html_text.strip():
            return comments
        try:
            for pattern in (
                r'"comments"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
                r'"comment_list"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
                r'"commentList"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
            ):
                match = re.search(pattern, html_text)
                if not match:
                    continue
                raw_json = match.group(1)
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
        """Fetch comments: try AJAX API first, then HTML fallback, then Playwright."""
        opts = getattr(self, "_analyze_options", {})
        max_comments = int(opts.get("max_comments", 500))
        if gallery_type == "mgallery":
            comments = self._fetch_dcinside_comments_ajax(
                gallery_id, post_no, "board", headers, referer_gallery_type="mgallery"
            )
            if not comments:
                comments = self._fetch_dcinside_comments_ajax(
                    gallery_id, post_no, gallery_type, headers
                )
        elif gallery_type == "mini":
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
        logger.info(
            "DCInside comment API/HTML had no comments; trying Playwright for post %s",
            post_no,
        )
        comments = self._fetch_dcinside_comments_playwright(
            gallery_id, post_no, gallery_type
        )
        return comments[:max_comments] if comments else []

    def _fetch_dcinside_comments_playwright(self, gallery_id, post_no, gallery_type):
        """Playwright fallback when comment API is blocked."""
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
