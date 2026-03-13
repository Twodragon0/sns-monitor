#!/usr/bin/env python3
"""네이버 카페 분석 API 테스트."""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

DEFAULT_URL = "https://cafe.naver.com/f-e/cafes/31581843/menus/0?viewType=L"
API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8888").rstrip("/")


def parse_menu_range(raw: str) -> tuple[int, int]:
    text = (raw or "1-60").strip()
    if "-" not in text:
        value = int(text)
        return value, value
    left, right = text.split("-", 1)
    start = int(left.strip())
    end = int(right.strip())
    if start > end:
        start, end = end, start
    return start, end


def cache_file_path(cafe_id: str) -> Path:
    local_data_dir = Path(os.environ.get("LOCAL_DATA_DIR", "./local-data"))
    return (
        local_data_dir / "naver_cafe" / str(cafe_id) / "latest_accessible_article.json"
    )


def load_cached_article(cafe_id: str, ttl_hours: int):
    path = cache_file_path(cafe_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        saved_at = float(data.get("saved_at", 0))
        if ttl_hours > 0 and time.time() - saved_at > ttl_hours * 3600:
            return None
        article_id = data.get("article_id")
        if article_id is None:
            return None
        menu_id = data.get("menu_id")
        return {
            "article_id": int(article_id),
            "menu_id": int(menu_id) if menu_id is not None else None,
            "title": str(data.get("title") or ""),
        }
    except Exception:
        return None


def save_cached_article(cafe_id: str, article_id: int, menu_id: int | None, title: str):
    path = cache_file_path(cafe_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "article_id": article_id,
        "menu_id": menu_id,
        "title": title,
        "saved_at": time.time(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_single_post_check(analyze_url: str, single_url: str, require_comments: bool):
    response = requests.post(
        analyze_url,
        json={"url": single_url},
        headers={"Content-Type": "application/json"},
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    status = data.get("fetch_status")
    has_content = bool(data.get("content"))
    comments = data.get("comments") or []
    has_comments = isinstance(comments, list) and len(comments) > 0
    if require_comments:
        success = has_comments
    else:
        success = bool(status in ("ok", "partial") or has_content or has_comments)
    return data, success


def check_membership_signals(list_url: str):
    verify_ssl = not (
        os.environ.get("NAVER_CAFE_DISABLE_SSL_VERIFY", "").lower()
        in ("1", "true", "yes")
    )
    cookie = (os.environ.get("NAVER_CAFE_COOKIE") or "").strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://cafe.naver.com/",
    }
    if cookie:
        headers["Cookie"] = cookie

    signals = {
        "need_login_phrase": False,
        "join_required_phrase": False,
        "grade_or_permission_phrase": False,
        "logout_or_profile_phrase": False,
    }
    try:
        response = requests.get(
            list_url, headers=headers, timeout=20, verify=verify_ssl
        )
        text = response.text or ""
        signals["need_login_phrase"] = any(
            token in text for token in ("로그인이 필요", "로그인 후 이용")
        )
        signals["join_required_phrase"] = any(
            token in text for token in ("카페 가입", "가입 후", "회원가입")
        )
        signals["grade_or_permission_phrase"] = any(
            token in text for token in ("권한", "등급", "열람 권한", "접근이 제한")
        )
        signals["logout_or_profile_phrase"] = any(
            token in text for token in ("로그아웃", "내카페", "내 프로필", "닉네임")
        )
    except Exception:
        pass
    return signals


def extract_cafe_id(url: str) -> str | None:
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    m = re.search(
        r"(?:^|/)(?:f-e/)?(?:ca-fe/web/)?cafes/(\d+)(?:/menus/\d+)?",
        path,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    params = parse_qs(parsed.query)
    return (params.get("clubid") or params.get("search.clubid") or [None])[0]


def probe_latest_article_candidates(
    cafe_id: str, menu_start: int = 1, menu_end: int = 60, max_candidates: int = 15
):
    cookie = (os.environ.get("NAVER_CAFE_COOKIE") or "").strip()
    verify_ssl = not (
        os.environ.get("NAVER_CAFE_DISABLE_SSL_VERIFY", "").lower()
        in ("1", "true", "yes")
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": f"https://cafe.naver.com/f-e/cafes/{cafe_id}/menus/0?viewType=L",
        "Origin": "https://cafe.naver.com",
        "X-Requested-With": "XMLHttpRequest",
    }
    if cookie:
        headers["Cookie"] = cookie

    candidates = []
    seen_ids = set()

    for menu_id in range(menu_start, menu_end + 1):
        api_url = (
            "https://apis.naver.com/cafe-web/cafe2/ArticleListV2dot1.json"
            f"?search.clubid={cafe_id}&search.menuid={menu_id}&search.page=1&search.perPage=20&search.queryType=lastArticle"
        )
        try:
            resp = requests.get(api_url, headers=headers, timeout=8, verify=verify_ssl)
            if not resp.ok:
                continue
            payload = resp.json()
            msg = payload.get("message") if isinstance(payload, dict) else {}
            result = (
                msg.get("result")
                if isinstance(msg, dict)
                else payload.get("result")
                if isinstance(payload, dict)
                else {}
            )
            if not isinstance(result, dict):
                result = {}
            article_list = (
                result.get("articleList")
                or (result.get("articleListMap") or {}).get("list")
                or []
            )
            if not article_list:
                continue
            for article in article_list:
                article_id_raw = (
                    article.get("articleId")
                    or article.get("articleid")
                    or article.get("id")
                )
                if article_id_raw is None:
                    continue
                try:
                    article_id = int(str(article_id_raw))
                except Exception:
                    continue
                if article_id in seen_ids:
                    continue
                seen_ids.add(article_id)
                title = ""
                if isinstance(article, dict):
                    title = str(article.get("subject") or article.get("title") or "")
                candidates.append(
                    {
                        "article_id": article_id,
                        "menu_id": menu_id,
                        "title": title,
                    }
                )
        except Exception:
            continue

    candidates.sort(key=lambda x: x["article_id"], reverse=True)
    return candidates[:max_candidates]


def main():
    parser = argparse.ArgumentParser(description="Test Naver Cafe analyze endpoint")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL, help="Naver Cafe URL")
    parser.add_argument(
        "--show-fetch-diagnostics",
        action="store_true",
        help="Print parsed fetch diagnostics fields",
    )
    parser.add_argument(
        "--auto-find-article",
        action="store_true",
        help="If list result is blocked/empty, probe latest article id and retry single-post analysis",
    )
    parser.add_argument(
        "--menu-range",
        default="1-60",
        help="Menu id scan range for auto-probe (e.g. 1-60)",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=15,
        help="Maximum article candidates to test",
    )
    parser.add_argument(
        "--cache-ttl-hours",
        type=int,
        default=24,
        help="TTL hours for cached successful article id (0 disables TTL)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable local cache read/write for successful article ids",
    )
    parser.add_argument(
        "--require-comments",
        action="store_true",
        help="Treat candidate as success only when comments are collected",
    )
    args = parser.parse_args()

    url = args.url
    analyze_url = f"{API_BASE}/api/analyze/url"
    print(f"POST {analyze_url} with url={url}")
    try:
        r = requests.post(
            analyze_url,
            json={"url": url},
            headers={"Content-Type": "application/json"},
            timeout=90,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            print("Response:", e.response.text[:500])
        sys.exit(1)
    platform = data.get("platform")
    ptype = data.get("type")
    print(f"platform={platform} type={ptype}")
    print(f"gallery_name={data.get('gallery_name', '')}")
    print(
        f"total_posts={data.get('total_posts')} total_comments={data.get('total_comments')}"
    )
    print(
        f"fetch_status={data.get('fetch_status')} fetch_reason={data.get('fetch_reason', '')}"
    )
    if args.show_fetch_diagnostics:
        reason = data.get("fetch_reason") or ""
        reason_tokens = [token.strip() for token in reason.split(",") if token.strip()]
        print("diagnostics:")
        print(f"  status={data.get('fetch_status')}")
        print(f"  reason_tokens={reason_tokens}")
        print(f"  cookie_missing={'cookie_not_set' in reason_tokens}")
        print(f"  proxy_missing={'proxy_not_set' in reason_tokens}")
        if platform == "naver_cafe" and ptype == "gallery":
            print(f"  membership_signals={check_membership_signals(url)}")
    posts = data.get("posts") or []
    print(f"posts count: {len(posts)}")
    for i, p in enumerate(posts[:5]):
        cmts = p.get("comments") or []
        print(
            f"  [{i + 1}] {(p.get('text') or '')[:50]}... article_id={p.get('article_id')} comments={len(cmts)}"
        )
    if not posts and data.get("fetch_status") != "ok":
        print(
            "\nTip: Set NAVER_CAFE_COOKIE in .env (from browser after logging into cafe.naver.com) for post/comment collection."
        )

    if (
        args.auto_find_article
        and platform == "naver_cafe"
        and ptype == "gallery"
        and len(posts) == 0
    ):
        cafe_id = extract_cafe_id(url)
        if not cafe_id:
            print("auto_probe: failed to extract cafe_id")
        else:
            menu_start, menu_end = parse_menu_range(args.menu_range)
            print(
                f"auto_probe: cafe_id={cafe_id}, menu_range={menu_start}-{menu_end}, max_candidates={args.max_candidates}"
            )
            if args.require_comments:
                print("auto_probe: strict mode enabled (require comments)")

            if not args.no_cache:
                cached = load_cached_article(cafe_id, args.cache_ttl_hours)
                if cached:
                    cached_url = f"https://cafe.naver.com/ArticleRead.nhn?clubid={cafe_id}&articleid={cached['article_id']}"
                    print(
                        f"auto_probe: trying cached article_id={cached['article_id']} menu_id={cached.get('menu_id')}"
                    )
                    try:
                        cached_data, cached_ok = run_single_post_check(
                            analyze_url, cached_url, args.require_comments
                        )
                        print(
                            f"auto_probe_cache_result: fetch_status={cached_data.get('fetch_status')} "
                            f"fetch_reason={cached_data.get('fetch_reason', '')} comment_count={cached_data.get('comment_count')}"
                        )
                        if cached_ok:
                            print("auto_probe: cache hit success")
                            print("OK")
                            return
                    except requests.RequestException as e:
                        print(f"auto_probe_cache_result: request failed: {e}")

            print("auto_probe: scanning latest article ids ...")
            candidates = probe_latest_article_candidates(
                cafe_id,
                menu_start=menu_start,
                menu_end=menu_end,
                max_candidates=args.max_candidates,
            )
            if not candidates:
                print("auto_probe: no accessible article id found")
            else:
                print(
                    f"auto_probe: found {len(candidates)} article candidates, trying newest first"
                )
                successful = False
                for cand in candidates:
                    article_id = cand["article_id"]
                    menu_id = cand["menu_id"]
                    title = cand["title"]
                    print(
                        f"auto_probe: try article_id={article_id} menu_id={menu_id} title={(title or '')[:60]}"
                    )
                    single_url = f"https://cafe.naver.com/ArticleRead.nhn?clubid={cafe_id}&articleid={article_id}"
                    try:
                        d2, candidate_ok = run_single_post_check(
                            analyze_url, single_url, args.require_comments
                        )
                        print(
                            f"auto_probe_result: article_id={article_id} type={d2.get('type')} "
                            f"fetch_status={d2.get('fetch_status')} fetch_reason={d2.get('fetch_reason', '')} "
                            f"comment_count={d2.get('comment_count')}"
                        )
                        has_content = bool(d2.get("content"))
                        has_comments = bool(d2.get("comments"))
                        if candidate_ok:
                            successful = True
                            print(
                                f"auto_probe: success candidate article_id={article_id} "
                                f"content={has_content} comments={len(d2.get('comments') or [])}"
                            )
                            if not args.no_cache:
                                save_cached_article(cafe_id, article_id, menu_id, title)
                                print("auto_probe: cached successful article_id")
                            break
                    except requests.RequestException as e:
                        print(
                            f"auto_probe_result: article_id={article_id} request failed: {e}"
                        )
                if not successful:
                    print(
                        "auto_probe: no candidate returned accessible content/comments"
                    )
    print(
        "OK"
        if (posts or data.get("type") == "post")
        else "No posts (check NAVER_CAFE_COOKIE)"
    )


if __name__ == "__main__":
    main()
