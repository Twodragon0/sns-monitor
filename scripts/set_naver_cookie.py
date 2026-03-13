#!/usr/bin/env python3
import argparse
import importlib
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(REPO_ROOT, ".env")


def _extract_cookie_from_text(raw):
    text = (raw or "").strip()
    if not text:
        return ""

    text = text.replace("\r", " ").replace("\n", " ").strip()

    m = re.search(r"(?:^|\s)cookie\s*:\s*([^\"']+)", text, flags=re.IGNORECASE)
    if m:
        text = m.group(1).strip()

    m = re.search(r"-H\s+[\"']cookie:\s*([^\"']+)[\"']", text, flags=re.IGNORECASE)
    if m:
        text = m.group(1).strip()

    m = re.search(
        r"['\"]cookie['\"]\s*:\s*['\"]([^'\"]+)['\"]", text, flags=re.IGNORECASE
    )
    if m:
        text = m.group(1).strip()

    parts = []
    for seg in text.split(";"):
        seg = seg.strip()
        if not seg:
            continue
        if "=" not in seg:
            continue
        key, value = seg.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if any(ch in key for ch in " ,\t"):
            continue
        parts.append(f"{key}={value}")

    return "; ".join(parts)


def _read_clipboard():
    if sys.platform == "darwin":
        out = subprocess.check_output(["pbpaste"], text=True)
        return out
    if sys.platform.startswith("linux"):
        try:
            return subprocess.check_output(["wl-paste", "-n"], text=True)
        except Exception:
            return subprocess.check_output(
                ["xclip", "-selection", "clipboard", "-o"], text=True
            )
    raise RuntimeError("Clipboard mode is currently supported on macOS/Linux")


def _load_browser_cookie(browser):
    try:
        browser_cookie3 = importlib.import_module("browser_cookie3")
    except Exception as e:
        raise RuntimeError(
            "browser-cookie3 not installed. Install with: pip install browser-cookie3"
        ) from e

    browser = (browser or "chrome").lower()
    if browser == "chrome":
        jar = browser_cookie3.chrome(domain_name="cafe.naver.com")
    elif browser == "edge":
        jar = browser_cookie3.edge(domain_name="cafe.naver.com")
    elif browser == "brave":
        jar = browser_cookie3.brave(domain_name="cafe.naver.com")
    elif browser == "firefox":
        jar = browser_cookie3.firefox(domain_name="cafe.naver.com")
    else:
        raise RuntimeError("Unsupported browser. Use: chrome|edge|brave|firefox")

    cookies = []
    for c in jar:
        if "naver.com" not in (c.domain or ""):
            continue
        if not c.name:
            continue
        cookies.append(f"{c.name}={c.value}")

    if not cookies:
        raise RuntimeError(
            "No Naver cookies found. Please login to cafe.naver.com first, then retry."
        )
    return "; ".join(cookies)


def _update_env_cookie(cookie):
    cookie = " ".join(cookie.split())
    if not os.path.exists(ENV_PATH):
        raise RuntimeError(f".env not found at {ENV_PATH}")

    with open(ENV_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    escaped = cookie.replace("\\", "\\\\").replace('"', '\\"')
    new_line = f'NAVER_CAFE_COOKIE="{escaped}"'
    if re.search(r"^\s*NAVER_CAFE_COOKIE\s*=", content, re.MULTILINE):
        content = re.sub(
            r"^\s*NAVER_CAFE_COOKIE\s*=.*$",
            new_line,
            content,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        if "NAVER_CAFE_PROXY_PASSWORD=" in content:
            content = content.replace(
                "NAVER_CAFE_PROXY_PASSWORD=",
                f"{new_line}\nNAVER_CAFE_PROXY_PASSWORD=",
                1,
            )
        else:
            content = content.rstrip() + "\n" + new_line + "\n"

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def _restart_api_backend():
    commands = [
        ["docker-compose", "up", "-d", "--build", "api-backend"],
        ["docker", "compose", "up", "-d", "--build", "api-backend"],
        ["docker-compose", "up", "-d", "api-backend"],
        ["docker", "compose", "up", "-d", "api-backend"],
    ]
    last_error = None
    for cmd in commands:
        try:
            subprocess.run(cmd, cwd=REPO_ROOT, check=True)
            return
        except Exception as e:
            last_error = e
    raise RuntimeError(
        f"Failed to restart api-backend with docker compose commands: {last_error}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Set NAVER_CAFE_COOKIE in .env from paste/clipboard/browser"
    )
    parser.add_argument(
        "cookie",
        nargs="*",
        help="Cookie string, Cookie header, or copied cURL/fetch snippet",
    )
    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="Read cookie source text from clipboard",
    )
    parser.add_argument(
        "--from-browser",
        choices=["chrome", "edge", "brave", "firefox"],
        help="Read cookie directly from local browser profile (requires browser-cookie3)",
    )
    parser.add_argument(
        "--restart-api",
        action="store_true",
        help="Restart api-backend after updating .env",
    )

    args = parser.parse_args()

    try:
        if args.from_browser:
            cookie = _load_browser_cookie(args.from_browser)
        elif args.clipboard:
            cookie = _extract_cookie_from_text(_read_clipboard())
        elif args.cookie:
            cookie = _extract_cookie_from_text(" ".join(args.cookie))
        else:
            print(
                "Paste cookie string (or copied cURL/fetch text), then press Enter and Ctrl-D:"
            )
            cookie = _extract_cookie_from_text(sys.stdin.read())

        if not cookie:
            raise RuntimeError("No valid cookie pairs found in input")

        _update_env_cookie(cookie)
        print("Updated .env: NAVER_CAFE_COOKIE has been set.")
        if args.restart_api:
            _restart_api_backend()
            print("api-backend restarted.")
        else:
            print("Next: docker-compose up -d --build api-backend")
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
