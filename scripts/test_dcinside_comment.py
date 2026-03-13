#!/usr/bin/env python3
"""
One-off script to inspect DCInside comment API response.
Usage (from repo root, needs: pip install requests):
  python scripts/test_dcinside_comment.py
"""
import re
import requests

GALLERY_ID = "vtuber"
POST_NO = "2230"
GALLERY_TYPE = "mgallery"

def main():
    session = requests.Session()
    view_url = f"https://gall.dcinside.com/{GALLERY_TYPE}/board/view/?id={GALLERY_ID}&no={POST_NO}"
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    print("1. GET view page (for token and cookies)...")
    rv = session.get(view_url, headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}, timeout=15)
    print(f"   status={rv.status_code}, len={len(rv.text)}, body_start={repr(rv.text[:80])}")

    token = ""
    match = re.search(r'e_s_n_o\s*[=:]\s*["\']([^"\']+)["\']', rv.text)
    if match:
        token = match.group(1)
        print(f"   e_s_n_o token: {token[:20]}...")
    else:
        match = re.search(r'<input[^>]+name=["\']e_s_n_o["\'][^>]+value=["\']([^"\']*)["\']', rv.text)
        if match:
            token = match.group(1)
            print(f"   e_s_n_o from input: {token[:20] if token else '(empty)'}...")
        else:
            print("   e_s_n_o not found")

    # Try mgallery-specific comment URL (same domain/path as view)
    api_url = f"https://gall.dcinside.com/{GALLERY_TYPE}/board/comment/"
    params = {
        "id": GALLERY_ID,
        "no": POST_NO,
        "cmt_id": GALLERY_ID,
        "cmt_no": POST_NO,
        "e_s_n_o": token,
        "comment_page": "1",
        "sort": "",
    }
    api_headers = {
        **dict(session.headers),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": view_url,
        "Origin": "https://gall.dcinside.com",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
    }
    print("2. GET comment API...")
    ra = session.get(api_url, params=params, headers=api_headers, timeout=12)
    print(f"   status={ra.status_code}, Content-Type={ra.headers.get('Content-Type')}")
    print(f"   body len={len(ra.text)}")
    sample = (ra.text or "")[:800]
    print("   body sample:")
    print("   ---")
    print(sample)
    print("   ---")
    if "cmt_info" in ra.text or "usertxt" in ra.text:
        print("   [OK] body contains cmt_info or usertxt")
    else:
        print("   [--] body does not contain cmt_info/usertxt")

if __name__ == "__main__":
    main()
