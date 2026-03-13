"""
네이버 카페 크롤러
설정된 카페 목록 URL로 백엔드 분석 API를 호출해 포스팅·댓글을 수집하고 로컬/S3에 저장합니다.
NAVER_CAFE_COOKIE가 설정되어 있으면 로그인 상태로 수집됩니다.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def now_kst():
    return datetime.now(KST)


def isoformat_kst():
    return now_kst().isoformat()


LOCAL_DATA_DIR = os.environ.get("LOCAL_DATA_DIR", "./local-data")
LOCAL_MODE = os.environ.get("LOCAL_MODE", "true").lower() == "true"
API_BASE_URL = (os.environ.get("API_BASE_URL") or "http://api-backend:8080").rstrip("/")


def extract_cafe_id_from_url(url: str) -> str:
    """URL에서 카페(클럽) ID 추출. 예: f-e/cafes/31581843/menus/0 -> 31581843"""
    if not url:
        return "unknown"
    path = (urlparse(url).path or "").strip("/")
    m = re.search(r"(?:^|/)(?:f-e/)?(?:ca-fe/web/)?cafes/(\d+)(?:/menus/(\d+))?", path, re.IGNORECASE)
    if m:
        return m.group(1)
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    club_id = (params.get("search.clubid") or params.get("clubid") or [None])[0]
    if club_id:
        return str(club_id)
    return "unknown"


def fetch_cafe_via_api(url: str, timeout: int = 90) -> Optional[dict]:
    """백엔드 /api/analyze/url 을 호출해 네이버 카페 목록·포스트·댓글 분석 결과를 반환합니다."""
    analyze_url = f"{API_BASE_URL}/api/analyze/url"
    try:
        resp = requests.post(
            analyze_url,
            json={"url": url},
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning("API request failed for %s: %s", url, e)
        return None
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Invalid JSON from API for %s: %s", url, e)
        return None


def save_result(cafe_id: str, data: dict) -> Optional[str]:
    """분석 결과를 로컬 또는 S3에 저장. 로컬 경로: LOCAL_DATA_DIR/naver_cafe/{cafe_id}/{timestamp}.json"""
    timestamp = now_kst().strftime("%Y-%m-%d-%H-%M-%S")
    if LOCAL_MODE:
        dir_path = os.path.join(LOCAL_DATA_DIR, "naver_cafe", cafe_id)
        os.makedirs(dir_path, exist_ok=True)
        filepath = os.path.join(dir_path, f"{timestamp}.json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Saved locally: %s", filepath)
            return filepath
        except OSError as e:
            logger.error("Failed to save %s: %s", filepath, e)
            return None
    # S3 등 다른 저장소는 필요 시 확장
    return None


def run_crawl(urls: list[str]) -> list[dict]:
    """여러 카페 URL에 대해 수집·저장 후 결과 목록 반환."""
    results = []
    for url in urls:
        url = (url or "").strip()
        if not url or "cafe.naver.com" not in url.lower():
            logger.warning("Skipping invalid Naver Cafe URL: %s", url)
            continue
        cafe_id = extract_cafe_id_from_url(url)
        logger.info("Crawling Naver Cafe: %s (cafe_id=%s)", url, cafe_id)
        data = fetch_cafe_via_api(url)
        if not data:
            results.append({"url": url, "cafe_id": cafe_id, "ok": False, "error": "api_failed"})
            continue
        if data.get("platform") != "naver_cafe":
            results.append({"url": url, "cafe_id": cafe_id, "ok": False, "error": "platform_mismatch"})
            continue
        saved = save_result(cafe_id, data)
        total_posts = data.get("total_posts") or 0
        total_comments = data.get("total_comments") or 0
        posts = data.get("posts") or []
        results.append({
            "url": url,
            "cafe_id": cafe_id,
            "ok": True,
            "saved": saved,
            "total_posts": total_posts,
            "total_comments": total_comments,
            "posts_count": len(posts),
            "fetch_status": data.get("fetch_status"),
            "gallery_name": data.get("gallery_name"),
        })
        logger.info(
            "Cafe %s: posts=%s total_posts=%s total_comments=%s fetch_status=%s",
            cafe_id, len(posts), total_posts, total_comments, data.get("fetch_status"),
        )
    return results


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    urls_str = os.environ.get("NAVER_CAFE_URLS", "")
    urls = [u.strip() for u in urls_str.split(",") if u.strip()]
    if not urls:
        logger.warning("NAVER_CAFE_URLS is empty. Set e.g. NAVER_CAFE_URLS=https://cafe.naver.com/f-e/cafes/31581843/menus/0")
        return
    results = run_crawl(urls)
    logger.info("Crawl finished: %d URLs, %d ok", len(results), sum(1 for r in results if r.get("ok")))


if __name__ == "__main__":
    main()
