"""
Unit tests for crawlers/naver_cafe/crawler.py

Run from the naver_cafe directory:
    cd crawlers/naver_cafe && python -m pytest tests/ -v

All external I/O (requests) is mocked so tests are fast and deterministic.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, mock_open

import pytest

# ---------------------------------------------------------------------------
# Environment setup BEFORE importing the crawler module.
# ---------------------------------------------------------------------------

os.environ.setdefault("LOCAL_MODE", "true")
os.environ.setdefault("LOCAL_DATA_DIR", "/tmp/test-naver-cafe-data")
os.environ.setdefault("API_BASE_URL", "http://api-backend:8080")

_CRAWLER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _CRAWLER_DIR not in sys.path:
    sys.path.insert(0, _CRAWLER_DIR)

import crawler as _crawler_mod  # noqa: E402


@pytest.fixture(scope="module")
def crawler_module():
    return _crawler_mod


# ===========================================================================
# 1. Timezone helpers
# ===========================================================================

class TestTimezoneHelpers:
    """now_kst() and isoformat_kst() return KST-aware datetimes."""

    def test_now_kst_returns_aware_datetime(self, crawler_module):
        result = crawler_module.now_kst()
        assert result.tzinfo is not None

    def test_now_kst_offset_is_plus_nine_hours(self, crawler_module):
        result = crawler_module.now_kst()
        assert result.utcoffset() == timedelta(hours=9)

    def test_isoformat_kst_returns_string(self, crawler_module):
        assert isinstance(crawler_module.isoformat_kst(), str)

    def test_isoformat_kst_contains_plus09(self, crawler_module):
        result = crawler_module.isoformat_kst()
        assert "+09:00" in result, f"Expected '+09:00' in '{result}'"

    def test_isoformat_kst_is_parseable_as_iso8601(self, crawler_module):
        parsed = datetime.fromisoformat(crawler_module.isoformat_kst())
        assert parsed.tzinfo is not None


# ===========================================================================
# 2. Module-level constants
# ===========================================================================

class TestConstants:

    def test_local_data_dir_is_string(self, crawler_module):
        assert isinstance(crawler_module.LOCAL_DATA_DIR, str)

    def test_local_mode_is_bool(self, crawler_module):
        assert isinstance(crawler_module.LOCAL_MODE, bool)

    def test_local_mode_is_true_from_env(self, crawler_module):
        # Env was set to "true" before import
        assert crawler_module.LOCAL_MODE is True

    def test_api_base_url_is_string(self, crawler_module):
        assert isinstance(crawler_module.API_BASE_URL, str)

    def test_api_base_url_has_no_trailing_slash(self, crawler_module):
        assert not crawler_module.API_BASE_URL.endswith("/")

    def test_api_base_url_default_is_api_backend(self, crawler_module):
        # Set from env before import
        assert "api-backend" in crawler_module.API_BASE_URL or crawler_module.API_BASE_URL.startswith("http")

    def test_kst_offset_is_nine_hours(self, crawler_module):
        assert crawler_module.KST == timezone(timedelta(hours=9))


# ===========================================================================
# 3. extract_cafe_id_from_url
# ===========================================================================

class TestExtractCafeIdFromUrl:

    def test_extracts_id_from_cafes_path(self, crawler_module):
        url = "https://cafe.naver.com/f-e/cafes/31581843/menus/0"
        assert crawler_module.extract_cafe_id_from_url(url) == "31581843"

    def test_extracts_id_from_bare_cafes_path(self, crawler_module):
        url = "https://cafe.naver.com/cafes/12345678"
        assert crawler_module.extract_cafe_id_from_url(url) == "12345678"

    def test_extracts_id_from_ca_fe_web_path(self, crawler_module):
        url = "https://cafe.naver.com/ca-fe/web/cafes/99999/menus/1"
        assert crawler_module.extract_cafe_id_from_url(url) == "99999"

    def test_extracts_id_from_search_clubid_querystring(self, crawler_module):
        url = "https://cafe.naver.com/ArticleList.nhn?search.clubid=12345"
        assert crawler_module.extract_cafe_id_from_url(url) == "12345"

    def test_extracts_id_from_clubid_querystring(self, crawler_module):
        url = "https://cafe.naver.com/something?clubid=67890"
        assert crawler_module.extract_cafe_id_from_url(url) == "67890"

    def test_returns_unknown_for_empty_string(self, crawler_module):
        assert crawler_module.extract_cafe_id_from_url("") == "unknown"

    def test_returns_unknown_for_none(self, crawler_module):
        assert crawler_module.extract_cafe_id_from_url(None) == "unknown"

    def test_returns_unknown_when_no_id_in_url(self, crawler_module):
        assert crawler_module.extract_cafe_id_from_url("https://cafe.naver.com/somecafe") == "unknown"

    def test_extracts_numeric_id_only(self, crawler_module):
        url = "https://cafe.naver.com/f-e/cafes/31581843/menus/0"
        result = crawler_module.extract_cafe_id_from_url(url)
        assert result.isdigit()

    def test_case_insensitive_path_matching(self, crawler_module):
        url = "https://cafe.naver.com/F-E/CAFES/11111/menus/0"
        # regex uses re.IGNORECASE
        result = crawler_module.extract_cafe_id_from_url(url)
        assert result == "11111"


# ===========================================================================
# 4. LOCAL_MODE initialisation
# ===========================================================================

class TestLocalModeInitialisation:

    def test_local_mode_flag_is_true(self, crawler_module):
        assert crawler_module.LOCAL_MODE is True

    def test_local_data_dir_set_from_env(self, crawler_module):
        assert crawler_module.LOCAL_DATA_DIR == "/tmp/test-naver-cafe-data"

    def test_api_base_url_set_from_env(self, crawler_module):
        assert crawler_module.API_BASE_URL == "http://api-backend:8080"


# ===========================================================================
# 5. fetch_cafe_via_api
# ===========================================================================

def _mock_response(json_data=None, status=200, raise_exc=None):
    r = MagicMock()
    r.status_code = status
    if json_data is not None:
        r.json.return_value = json_data
    if raise_exc:
        r.raise_for_status.side_effect = raise_exc
    else:
        r.raise_for_status = MagicMock()
    return r


class TestFetchCafeViaApi:

    @patch("requests.post")
    def test_posts_to_analyze_url_endpoint(self, mock_post, crawler_module):
        mock_post.return_value = _mock_response({"platform": "naver_cafe"})
        crawler_module.fetch_cafe_via_api("https://cafe.naver.com/f-e/cafes/123/menus/0")
        url_called = mock_post.call_args[0][0]
        assert url_called.endswith("/api/analyze/url")

    @patch("requests.post")
    def test_sends_url_in_json_body(self, mock_post, crawler_module):
        target = "https://cafe.naver.com/f-e/cafes/123/menus/0"
        mock_post.return_value = _mock_response({"platform": "naver_cafe"})
        crawler_module.fetch_cafe_via_api(target)
        payload = mock_post.call_args[1]["json"]
        assert payload["url"] == target

    @patch("requests.post")
    def test_returns_parsed_json_on_success(self, mock_post, crawler_module):
        expected = {"platform": "naver_cafe", "total_posts": 5}
        mock_post.return_value = _mock_response(expected)
        result = crawler_module.fetch_cafe_via_api("https://cafe.naver.com/f-e/cafes/123/menus/0")
        assert result == expected

    @patch("requests.post")
    def test_returns_none_on_request_exception(self, mock_post, crawler_module):
        import requests
        mock_post.side_effect = requests.RequestException("connection refused")
        result = crawler_module.fetch_cafe_via_api("https://cafe.naver.com/f-e/cafes/123/menus/0")
        assert result is None

    @patch("requests.post")
    def test_returns_none_on_http_error(self, mock_post, crawler_module):
        import requests
        mock_post.return_value = _mock_response(
            raise_exc=requests.HTTPError("500 Server Error")
        )
        result = crawler_module.fetch_cafe_via_api("https://cafe.naver.com/f-e/cafes/123/menus/0")
        assert result is None

    @patch("requests.post")
    def test_returns_none_on_invalid_json(self, mock_post, crawler_module):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.side_effect = ValueError("not valid JSON")
        mock_post.return_value = r
        result = crawler_module.fetch_cafe_via_api("https://cafe.naver.com/f-e/cafes/123/menus/0")
        assert result is None

    @patch("requests.post")
    def test_uses_content_type_json_header(self, mock_post, crawler_module):
        mock_post.return_value = _mock_response({"platform": "naver_cafe"})
        crawler_module.fetch_cafe_via_api("https://cafe.naver.com/f-e/cafes/123/menus/0")
        headers = mock_post.call_args[1]["headers"]
        assert headers.get("Content-Type") == "application/json"

    @patch("requests.post")
    def test_default_timeout_is_90(self, mock_post, crawler_module):
        mock_post.return_value = _mock_response({"platform": "naver_cafe"})
        crawler_module.fetch_cafe_via_api("https://cafe.naver.com/f-e/cafes/123/menus/0")
        timeout = mock_post.call_args[1]["timeout"]
        assert timeout == 90

    @patch("requests.post")
    def test_custom_timeout_is_forwarded(self, mock_post, crawler_module):
        mock_post.return_value = _mock_response({"platform": "naver_cafe"})
        crawler_module.fetch_cafe_via_api("https://cafe.naver.com/f-e/cafes/123/menus/0", timeout=30)
        timeout = mock_post.call_args[1]["timeout"]
        assert timeout == 30


# ===========================================================================
# 6. save_result
# ===========================================================================

class TestSaveResult:

    def test_creates_directory_and_returns_filepath(self, crawler_module, tmp_path):
        original = crawler_module.LOCAL_DATA_DIR
        original_mode = crawler_module.LOCAL_MODE
        crawler_module.LOCAL_DATA_DIR = str(tmp_path)
        crawler_module.LOCAL_MODE = True
        try:
            path = crawler_module.save_result("31581843", {"platform": "naver_cafe"})
            assert path is not None
            assert "naver_cafe" in path
            assert "31581843" in path
        finally:
            crawler_module.LOCAL_DATA_DIR = original
            crawler_module.LOCAL_MODE = original_mode

    def test_written_file_contains_valid_json(self, crawler_module, tmp_path):
        original = crawler_module.LOCAL_DATA_DIR
        original_mode = crawler_module.LOCAL_MODE
        crawler_module.LOCAL_DATA_DIR = str(tmp_path)
        crawler_module.LOCAL_MODE = True
        try:
            data = {"platform": "naver_cafe", "total_posts": 3}
            crawler_module.save_result("11111", data)
            saved_dir = tmp_path / "naver_cafe" / "11111"
            files = list(saved_dir.glob("*.json"))
            assert len(files) == 1
            with open(files[0], encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == data
        finally:
            crawler_module.LOCAL_DATA_DIR = original
            crawler_module.LOCAL_MODE = original_mode

    def test_filename_contains_timestamp(self, crawler_module, tmp_path):
        original = crawler_module.LOCAL_DATA_DIR
        original_mode = crawler_module.LOCAL_MODE
        crawler_module.LOCAL_DATA_DIR = str(tmp_path)
        crawler_module.LOCAL_MODE = True
        try:
            path = crawler_module.save_result("22222", {"x": 1})
            import re
            filename = os.path.basename(path)
            assert re.match(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.json", filename)
        finally:
            crawler_module.LOCAL_DATA_DIR = original
            crawler_module.LOCAL_MODE = original_mode

    def test_returns_none_when_local_mode_is_false(self, crawler_module, tmp_path):
        original_mode = crawler_module.LOCAL_MODE
        crawler_module.LOCAL_MODE = False
        try:
            result = crawler_module.save_result("33333", {"x": 1})
            assert result is None
        finally:
            crawler_module.LOCAL_MODE = original_mode

    def test_returns_none_on_os_error(self, crawler_module, tmp_path):
        original = crawler_module.LOCAL_DATA_DIR
        original_mode = crawler_module.LOCAL_MODE
        crawler_module.LOCAL_DATA_DIR = str(tmp_path)
        crawler_module.LOCAL_MODE = True
        try:
            with patch("builtins.open", side_effect=OSError("disk full")):
                result = crawler_module.save_result("44444", {"x": 1})
            assert result is None
        finally:
            crawler_module.LOCAL_DATA_DIR = original
            crawler_module.LOCAL_MODE = original_mode

    def test_unicode_data_saved_without_ascii_escaping(self, crawler_module, tmp_path):
        original = crawler_module.LOCAL_DATA_DIR
        original_mode = crawler_module.LOCAL_MODE
        crawler_module.LOCAL_DATA_DIR = str(tmp_path)
        crawler_module.LOCAL_MODE = True
        try:
            data = {"title": "한글 제목 테스트"}
            crawler_module.save_result("55555", data)
            saved_dir = tmp_path / "naver_cafe" / "55555"
            files = list(saved_dir.glob("*.json"))
            content = files[0].read_text(encoding="utf-8")
            assert "한글" in content
        finally:
            crawler_module.LOCAL_DATA_DIR = original
            crawler_module.LOCAL_MODE = original_mode


# ===========================================================================
# 7. run_crawl
# ===========================================================================

class TestRunCrawl:

    def test_returns_empty_list_for_empty_input(self, crawler_module):
        result = crawler_module.run_crawl([])
        assert result == []

    def test_skips_non_naver_cafe_urls(self, crawler_module):
        # run_crawl silently drops URLs that don't contain cafe.naver.com
        result = crawler_module.run_crawl(["https://gall.dcinside.com/board/lists?id=ivnit"])
        assert result == []

    def test_skips_empty_string_urls(self, crawler_module):
        result = crawler_module.run_crawl(["", "   "])
        assert result == []

    def test_skips_whitespace_only_urls(self, crawler_module):
        result = crawler_module.run_crawl(["   "])
        assert result == []

    @patch("crawler.fetch_cafe_via_api", return_value=None)
    def test_returns_api_failed_when_fetch_returns_none(self, mock_fetch, crawler_module):
        result = crawler_module.run_crawl(["https://cafe.naver.com/f-e/cafes/31581843/menus/0"])
        assert len(result) == 1
        assert result[0]["ok"] is False
        assert result[0]["error"] == "api_failed"

    @patch("crawler.fetch_cafe_via_api", return_value={"platform": "dcinside"})
    def test_returns_platform_mismatch_when_platform_is_wrong(self, mock_fetch, crawler_module):
        result = crawler_module.run_crawl(["https://cafe.naver.com/f-e/cafes/31581843/menus/0"])
        assert result[0]["ok"] is False
        assert result[0]["error"] == "platform_mismatch"

    @patch("crawler.save_result", return_value="/tmp/test-naver-cafe-data/naver_cafe/31581843/2026-01-01.json")
    @patch("crawler.fetch_cafe_via_api", return_value={
        "platform": "naver_cafe",
        "total_posts": 10,
        "total_comments": 50,
        "posts": [{"id": 1}, {"id": 2}],
        "fetch_status": "ok",
        "gallery_name": "TestCafe",
    })
    def test_returns_ok_true_on_success(self, mock_fetch, mock_save, crawler_module):
        result = crawler_module.run_crawl(["https://cafe.naver.com/f-e/cafes/31581843/menus/0"])
        assert result[0]["ok"] is True

    @patch("crawler.save_result", return_value="/some/path.json")
    @patch("crawler.fetch_cafe_via_api", return_value={
        "platform": "naver_cafe",
        "total_posts": 10,
        "total_comments": 50,
        "posts": [{"id": 1}, {"id": 2}],
        "fetch_status": "ok",
        "gallery_name": "TestCafe",
    })
    def test_result_contains_posts_count(self, mock_fetch, mock_save, crawler_module):
        result = crawler_module.run_crawl(["https://cafe.naver.com/f-e/cafes/31581843/menus/0"])
        assert result[0]["posts_count"] == 2

    @patch("crawler.save_result", return_value="/some/path.json")
    @patch("crawler.fetch_cafe_via_api", return_value={
        "platform": "naver_cafe",
        "total_posts": 10,
        "total_comments": 50,
        "posts": [],
        "fetch_status": "ok",
        "gallery_name": "TestCafe",
    })
    def test_result_contains_total_posts(self, mock_fetch, mock_save, crawler_module):
        result = crawler_module.run_crawl(["https://cafe.naver.com/f-e/cafes/31581843/menus/0"])
        assert result[0]["total_posts"] == 10

    @patch("crawler.save_result", return_value="/some/path.json")
    @patch("crawler.fetch_cafe_via_api", return_value={
        "platform": "naver_cafe",
        "total_posts": 0,
        "total_comments": 50,
        "posts": [],
        "fetch_status": "ok",
        "gallery_name": "TestCafe",
    })
    def test_result_contains_total_comments(self, mock_fetch, mock_save, crawler_module):
        result = crawler_module.run_crawl(["https://cafe.naver.com/f-e/cafes/31581843/menus/0"])
        assert result[0]["total_comments"] == 50

    @patch("crawler.save_result", return_value="/some/path.json")
    @patch("crawler.fetch_cafe_via_api", return_value={
        "platform": "naver_cafe",
        "total_posts": 0,
        "total_comments": 0,
        "posts": [],
        "fetch_status": "ok",
        "gallery_name": "TestCafe",
    })
    def test_result_contains_cafe_id(self, mock_fetch, mock_save, crawler_module):
        result = crawler_module.run_crawl(["https://cafe.naver.com/f-e/cafes/31581843/menus/0"])
        assert result[0]["cafe_id"] == "31581843"

    @patch("crawler.save_result", return_value="/some/path.json")
    @patch("crawler.fetch_cafe_via_api", return_value={
        "platform": "naver_cafe",
        "total_posts": 0,
        "total_comments": 0,
        "posts": [],
        "fetch_status": "timeout",
        "gallery_name": "TestCafe",
    })
    def test_result_contains_fetch_status(self, mock_fetch, mock_save, crawler_module):
        result = crawler_module.run_crawl(["https://cafe.naver.com/f-e/cafes/31581843/menus/0"])
        assert result[0]["fetch_status"] == "timeout"

    @patch("crawler.save_result", return_value=None)
    @patch("crawler.fetch_cafe_via_api", return_value={
        "platform": "naver_cafe",
        "total_posts": 0,
        "total_comments": 0,
        "posts": [],
        "fetch_status": "ok",
        "gallery_name": "TestCafe",
    })
    def test_ok_is_true_even_when_save_returns_none(self, mock_fetch, mock_save, crawler_module):
        # save_result returning None (S3 path not set) should still mark ok=True
        result = crawler_module.run_crawl(["https://cafe.naver.com/f-e/cafes/31581843/menus/0"])
        assert result[0]["ok"] is True

    @patch("crawler.fetch_cafe_via_api", return_value=None)
    def test_processes_multiple_urls(self, mock_fetch, crawler_module):
        urls = [
            "https://cafe.naver.com/f-e/cafes/11111/menus/0",
            "https://cafe.naver.com/f-e/cafes/22222/menus/0",
        ]
        result = crawler_module.run_crawl(urls)
        assert len(result) == 2

    @patch("crawler.fetch_cafe_via_api", return_value=None)
    def test_result_contains_url_field(self, mock_fetch, crawler_module):
        url = "https://cafe.naver.com/f-e/cafes/31581843/menus/0"
        result = crawler_module.run_crawl([url])
        assert result[0]["url"] == url

    @patch("crawler.save_result", return_value="/some/path.json")
    @patch("crawler.fetch_cafe_via_api", return_value={
        "platform": "naver_cafe",
        "total_posts": None,
        "total_comments": None,
        "posts": None,
        "fetch_status": "ok",
        "gallery_name": "TestCafe",
    })
    def test_handles_none_total_fields_gracefully(self, mock_fetch, mock_save, crawler_module):
        result = crawler_module.run_crawl(["https://cafe.naver.com/f-e/cafes/31581843/menus/0"])
        assert result[0]["total_posts"] == 0
        assert result[0]["total_comments"] == 0
        assert result[0]["posts_count"] == 0
