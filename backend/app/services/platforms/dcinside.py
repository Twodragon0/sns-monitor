"""
DCInside platform analyzer mixin.
All DCInside-specific methods extracted from PlatformAnalyzer.
Comment fetching/parsing methods are in dcinside_comments.py.
"""

import logging
import re
import time
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup

from .dcinside_comments import DCInsideCommentMixin

logger = logging.getLogger(__name__)


class DCInsideMixin(DCInsideCommentMixin):
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
        seen_post_numbers = set()
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

                # DCInside returns page 1 content for out-of-range pages, so
                # dedupe by post number. If an entire page adds no new posts,
                # we've run past the last real page — stop scraping.
                posts_before = len(posts)
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
                    if post_number in seen_post_numbers:
                        continue
                    seen_post_numbers.add(post_number)
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

                # If this page produced no new posts, DCInside is looping —
                # we've hit the end of the gallery. Stop.
                if len(posts) == posts_before:
                    break

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
        if fetch_comments and posts:
            # Reset DCInside-specific cookies before comment collection — stale cookies
            # from gallery list scraping (especially 'csid') cause DCInside to block
            # the comment API with "정상적인 접근이 아닙니다".
            # Only clear cookies scoped to DCInside domains to avoid destroying
            # cookies set by other platforms (e.g. Naver Cafe authentication).
            for dc_domain in ("gall.dcinside.com", ".dcinside.com", "dcinside.com"):
                try:
                    self._session.cookies.clear(domain=dc_domain)
                except KeyError:
                    pass
            try:
                self._session.get(list_url_base, headers=headers, timeout=15)
            except Exception as e:
                logger.debug("DCInside cookie rehydration request failed: %s", e)
            t_start = time.monotonic()
            for post in posts:
                if comment_fetch_stats["attempted"] >= max_comment_posts:
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
                # Delay between posts to avoid DCInside rate limiting on view/token pages
                if comment_fetch_stats["attempted"] > 1:
                    time.sleep(1.5)
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
