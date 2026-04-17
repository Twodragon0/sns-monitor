"""Naver Cafe comment fetching and parsing mixin.
Extracted from naver_cafe.py to keep file size manageable.
"""

import logging
from datetime import datetime, timezone

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class NaverCafeCommentMixin:
    """Mixin providing Naver Cafe comment fetching/parsing methods.

    Expects the host class to have: _session, _naver_get.
    """

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
            if not text and item.get("sticker"):
                text = "[스티커]"
            if not text:
                continue
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
