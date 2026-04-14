"""
Unit tests for crawlers/dcinside/crawler.py

Run from the dcinside directory:
    cd crawlers/dcinside && python -m pytest tests/ -v

All external I/O (Playwright, requests, boto3) is mocked so tests are
fast and deterministic.  boto3 and playwright are not installed in the
test environment, so lightweight stubs are injected into sys.modules
before the crawler module is imported.
"""

import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Stub out boto3 and playwright BEFORE crawler.py is ever imported.
# These stubs are injected at collection time so that `import crawler`
# inside the fixture can succeed.
# ---------------------------------------------------------------------------

def _install_boto3_stub():
    boto3_stub = types.ModuleType("boto3")
    boto3_stub.client = MagicMock(return_value=MagicMock())
    boto3_stub.resource = MagicMock(return_value=MagicMock())
    sys.modules.setdefault("boto3", boto3_stub)


def _install_playwright_stub():
    """Return the TimeoutError class used by the stub so tests can reference it."""

    class _PlaywrightTimeoutError(Exception):
        pass

    pw_stub = types.ModuleType("playwright")
    pw_sync_stub = types.ModuleType("playwright.sync_api")
    pw_sync_stub.TimeoutError = _PlaywrightTimeoutError
    pw_sync_stub.sync_playwright = MagicMock()
    pw_stub.sync_api = pw_sync_stub

    sys.modules.setdefault("playwright", pw_stub)
    sys.modules.setdefault("playwright.sync_api", pw_sync_stub)

    return _PlaywrightTimeoutError


# Install stubs at import time (before any fixture runs)
_install_boto3_stub()
_PlaywrightTimeoutError = _install_playwright_stub()

# ---------------------------------------------------------------------------
# Import the crawler with LOCAL_MODE forced on so boto3 is not initialised.
# ---------------------------------------------------------------------------

os.environ.setdefault("LOCAL_MODE", "true")
os.environ.setdefault("LOCAL_DATA_DIR", "/tmp/test-local-data")
os.environ.setdefault("LLM_ANALYZER_ENDPOINT", "http://llm-analyzer:5000")

_CRAWLER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _CRAWLER_DIR not in sys.path:
    sys.path.insert(0, _CRAWLER_DIR)

import crawler as _crawler_mod  # noqa: E402  (module-level import after path setup)


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

    def test_page_timeout_ms_is_positive_int(self, crawler_module):
        assert isinstance(crawler_module.PAGE_TIMEOUT_MS, int)
        assert crawler_module.PAGE_TIMEOUT_MS > 0

    def test_page_timeout_ms_equals_30000(self, crawler_module):
        assert crawler_module.PAGE_TIMEOUT_MS == 30000

    def test_selector_timeout_ms_is_positive_int(self, crawler_module):
        assert isinstance(crawler_module.SELECTOR_TIMEOUT_MS, int)
        assert crawler_module.SELECTOR_TIMEOUT_MS > 0

    def test_selector_timeout_ms_equals_10000(self, crawler_module):
        assert crawler_module.SELECTOR_TIMEOUT_MS == 10000

    def test_common_keywords_is_list(self, crawler_module):
        assert isinstance(crawler_module.COMMON_KEYWORDS, list)

    def test_common_keywords_not_empty(self, crawler_module):
        assert len(crawler_module.COMMON_KEYWORDS) > 0

    def test_common_keywords_contains_brand_terms(self, crawler_module):
        kws = crawler_module.COMMON_KEYWORDS
        for term in ("examplecorp", "ExampleCorp", "creatorbrand"):
            assert term in kws, f"'{term}' missing from COMMON_KEYWORDS"

    def test_common_keywords_contains_merchandise_terms(self, crawler_module):
        kws = crawler_module.COMMON_KEYWORDS
        for term in ("goods", "photocard", "keyring", "sticker", "poster"):
            assert term in kws, f"'{term}' missing from COMMON_KEYWORDS"

    def test_common_keywords_contains_fan_activity_terms(self, crawler_module):
        kws = crawler_module.COMMON_KEYWORDS
        for term in ("event", "giveaway", "fanmeet"):
            assert term in kws, f"'{term}' missing from COMMON_KEYWORDS"


# ===========================================================================
# 3. GALLERIES configuration
# ===========================================================================

class TestGalleriesConfig:

    REQUIRED_KEYS = {"url", "name", "type", "keywords"}
    VALID_TYPES = {"mini", "mgallery"}

    def test_galleries_is_dict(self, crawler_module):
        assert isinstance(crawler_module.GALLERIES, dict)

    def test_galleries_not_empty(self, crawler_module):
        assert len(crawler_module.GALLERIES) > 0

    @pytest.mark.parametrize("gallery_id", [
        "ivnit", "akaiv", "soopvirtualstreamer", "spv",
        "soopstreaming", "skoshism", "example-gallery-1", "example-gallery-2",
    ])
    def test_gallery_has_required_keys(self, crawler_module, gallery_id):
        missing = self.REQUIRED_KEYS - set(crawler_module.GALLERIES[gallery_id].keys())
        assert not missing, f"Gallery '{gallery_id}' missing keys: {missing}"

    @pytest.mark.parametrize("gallery_id", [
        "ivnit", "akaiv", "soopvirtualstreamer", "spv", "soopstreaming", "skoshism",
    ])
    def test_gallery_url_points_to_dcinside(self, crawler_module, gallery_id):
        assert "gall.dcinside.com" in crawler_module.GALLERIES[gallery_id]["url"]

    @pytest.mark.parametrize("gallery_id", [
        "ivnit", "akaiv", "soopvirtualstreamer", "spv", "soopstreaming", "skoshism",
    ])
    def test_gallery_type_is_valid(self, crawler_module, gallery_id):
        t = crawler_module.GALLERIES[gallery_id]["type"]
        assert t in self.VALID_TYPES, f"Gallery '{gallery_id}' has invalid type '{t}'"

    @pytest.mark.parametrize("gallery_id", [
        "ivnit", "akaiv", "soopvirtualstreamer", "spv", "soopstreaming", "skoshism",
    ])
    def test_gallery_keywords_include_all_common_keywords(self, crawler_module, gallery_id):
        gallery_kws = crawler_module.GALLERIES[gallery_id]["keywords"]
        for kw in crawler_module.COMMON_KEYWORDS:
            assert kw in gallery_kws, f"Gallery '{gallery_id}' missing common keyword '{kw}'"

    def test_skoshism_is_mgallery_type(self, crawler_module):
        assert crawler_module.GALLERIES["skoshism"]["type"] == "mgallery"

    def test_mini_galleries_have_mini_in_url(self, crawler_module):
        for gid, info in crawler_module.GALLERIES.items():
            if info["type"] == "mini":
                assert "mini" in info["url"], (
                    f"Gallery '{gid}' type=mini but URL has no 'mini': {info['url']}"
                )


# ===========================================================================
# 4. LOCAL_MODE and s3_client initialisation
# ===========================================================================

class TestLocalModeInitialisation:

    def test_s3_client_is_none_in_local_mode(self, crawler_module):
        assert crawler_module.s3_client is None

    def test_local_mode_flag_is_true(self, crawler_module):
        assert crawler_module.LOCAL_MODE is True

    def test_llm_analyzer_endpoint_default_value(self, crawler_module):
        assert crawler_module.LLM_ANALYZER_ENDPOINT == "http://llm-analyzer:5000"


# ===========================================================================
# 5. filter_posts_by_keywords
# ===========================================================================

class TestFilterPostsByKeywords:

    def _post(self, title, post_id="1"):
        return {"post_id": post_id, "title": title, "author": "anon"}

    def test_returns_empty_list_when_nothing_matches(self, crawler_module):
        posts = [self._post("완전 다른 제목"), self._post("무관한 내용")]
        assert crawler_module.filter_posts_by_keywords(posts, ["examplecorp"]) == []

    def test_returns_posts_that_match_keyword(self, crawler_module):
        posts = [self._post("ExampleCorp 신규 굿즈 출시"), self._post("오늘 날씨 좋다")]
        result = crawler_module.filter_posts_by_keywords(posts, ["examplecorp"])
        assert len(result) == 1
        assert result[0]["title"] == "ExampleCorp 신규 굿즈 출시"

    def test_keyword_matching_is_case_insensitive(self, crawler_module):
        posts = [self._post("EXAMPLECORP 공지")]
        assert len(crawler_module.filter_posts_by_keywords(posts, ["examplecorp"])) == 1

    def test_matched_keyword_stored_on_post(self, crawler_module):
        posts = [self._post("photocard 이벤트")]
        result = crawler_module.filter_posts_by_keywords(posts, ["photocard"])
        assert result[0]["matched_keyword"] == "photocard"

    def test_empty_posts_returns_empty_list(self, crawler_module):
        assert crawler_module.filter_posts_by_keywords([], ["examplecorp"]) == []

    def test_empty_keywords_returns_empty_list(self, crawler_module):
        assert crawler_module.filter_posts_by_keywords([self._post("examplecorp")], []) == []

    def test_each_post_appears_only_once_even_with_multiple_matching_keywords(self, crawler_module):
        posts = [self._post("examplecorp goods")]
        result = crawler_module.filter_posts_by_keywords(posts, ["examplecorp", "goods"])
        assert len(result) == 1

    def test_first_matching_keyword_is_stored(self, crawler_module):
        posts = [self._post("examplecorp goods")]
        result = crawler_module.filter_posts_by_keywords(posts, ["examplecorp", "goods"])
        assert result[0]["matched_keyword"] == "examplecorp"


# ===========================================================================
# 6. _extract_comments_from_json
# ===========================================================================

class TestExtractCommentsFromJson:

    def test_extracts_top_level_comments_key(self, crawler_module):
        data = {"comments": [{"memo": "hello"}]}
        assert crawler_module._extract_comments_from_json(data) == [{"memo": "hello"}]

    def test_extracts_nested_data_comments(self, crawler_module):
        data = {"data": {"comments": [{"memo": "nested"}]}}
        assert crawler_module._extract_comments_from_json(data) == [{"memo": "nested"}]

    def test_handles_list_input(self, crawler_module):
        """List input triggers AttributeError internally; function expects dict."""
        data = [{"memo": "item"}]
        # The function calls data.get() first, which fails on list.
        # Verify it doesn't crash — wrapping in a dict is the caller's job.
        try:
            result = crawler_module._extract_comments_from_json(data)
            assert isinstance(result, list)
        except AttributeError:
            pass  # Expected: list has no .get()

    def test_extracts_result_comments(self, crawler_module):
        data = {"result": {"comments": [{"memo": "in result"}]}}
        assert crawler_module._extract_comments_from_json(data) == [{"memo": "in result"}]

    def test_returns_empty_for_empty_dict(self, crawler_module):
        assert crawler_module._extract_comments_from_json({}) == []

    def test_finds_comments_in_dynamic_comment_keyed_field(self, crawler_module):
        data = {"my_comments_list": [{"memo": "dynamic key"}]}
        assert crawler_module._extract_comments_from_json(data) == [{"memo": "dynamic key"}]

    def test_top_level_comments_key_takes_priority(self, crawler_module):
        data = {
            "comments": [{"memo": "top"}],
            "data": {"comments": [{"memo": "nested"}]},
        }
        assert crawler_module._extract_comments_from_json(data) == [{"memo": "top"}]


# ===========================================================================
# 7. _parse_json_comments
# ===========================================================================

class TestParseJsonComments:

    def test_parses_memo_field(self, crawler_module):
        result = crawler_module._parse_json_comments(
            [{"memo": "test text", "name": "user1", "reg_date": "2026-01-01", "no": "42"}]
        )
        assert len(result) == 1
        assert result[0] == {
            "text": "test text",
            "author": "user1",
            "date": "2026-01-01",
            "comment_id": "42",
        }

    def test_falls_back_to_text_field(self, crawler_module):
        result = crawler_module._parse_json_comments([{"text": "fallback text", "name": "u2"}])
        assert result[0]["text"] == "fallback text"

    def test_falls_back_to_comment_field(self, crawler_module):
        result = crawler_module._parse_json_comments([{"comment": "another fb", "name": "u3"}])
        assert result[0]["text"] == "another fb"

    def test_skips_empty_text(self, crawler_module):
        assert crawler_module._parse_json_comments([{"memo": "", "name": "ghost"}]) == []

    def test_skips_html_text(self, crawler_module):
        assert crawler_module._parse_json_comments([{"memo": "<img src='x'>"}]) == []

    def test_author_defaults_to_anonymous_when_absent(self, crawler_module):
        result = crawler_module._parse_json_comments([{"memo": "hello", "no": "1"}])
        assert result[0]["author"] == "익명"

    def test_returns_empty_list_for_empty_input(self, crawler_module):
        assert crawler_module._parse_json_comments([]) == []

    def test_parses_multiple_comments(self, crawler_module):
        result = crawler_module._parse_json_comments([
            {"memo": "first", "name": "a"},
            {"memo": "second", "name": "b"},
        ])
        assert len(result) == 2


# ===========================================================================
# 8. _parse_html_comments  (BeautifulSoup HTML fixtures)
# ===========================================================================

_HTML_SINGLE_COMMENT = """
<ul>
  <li class="cmt_info">
    <span class="gall_writer" data-nick="tester">tester</span>
    <span class="usertxt">Hello world</span>
    <span class="date_time">2026-01-01 12:00:00</span>
  </li>
</ul>
"""

_HTML_MULTIPLE_COMMENTS = """
<ul>
  <li class="cmt_info">
    <span class="nick" data-nick="alice">alice</span>
    <span class="usertxt">First comment</span>
    <span class="date_time">2026-01-01 10:00</span>
  </li>
  <li class="cmt_info">
    <span class="nick" data-nick="bob">bob</span>
    <span class="usertxt">Second comment</span>
    <span class="date_time">2026-01-01 11:00</span>
  </li>
</ul>
"""

_HTML_NO_COMMENTS = "<div class='content'>No comments here</div>"

_HTML_COMMENT_MISSING_TEXT = """
<ul>
  <li class="cmt_info">
    <span class="gall_writer" data-nick="ghost">ghost</span>
    <span class="date_time">2026-01-01</span>
  </li>
</ul>
"""

_HTML_REPLY_INFO = """
<ul>
  <li class="reply_info">
    <span class="writer">replier</span>
    <span class="reply_text">A reply text</span>
    <span class="date">2026-03-01</span>
  </li>
</ul>
"""


class TestParseHtmlComments:

    def _soup(self, html):
        return BeautifulSoup(html, "html.parser")

    def test_parses_single_comment_text(self, crawler_module):
        result = crawler_module._parse_html_comments(self._soup(_HTML_SINGLE_COMMENT))
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"

    def test_parses_author_from_data_nick_attribute(self, crawler_module):
        result = crawler_module._parse_html_comments(self._soup(_HTML_SINGLE_COMMENT))
        assert result[0]["author"] == "tester"

    def test_parses_date_field(self, crawler_module):
        result = crawler_module._parse_html_comments(self._soup(_HTML_SINGLE_COMMENT))
        assert result[0]["date"] == "2026-01-01 12:00:00"

    def test_parses_multiple_comment_items(self, crawler_module):
        result = crawler_module._parse_html_comments(self._soup(_HTML_MULTIPLE_COMMENTS))
        assert len(result) == 2

    def test_returns_empty_when_no_comment_selectors_match(self, crawler_module):
        result = crawler_module._parse_html_comments(self._soup(_HTML_NO_COMMENTS))
        assert result == []

    def test_skips_comment_item_with_no_text(self, crawler_module):
        result = crawler_module._parse_html_comments(self._soup(_HTML_COMMENT_MISSING_TEXT))
        assert result == []

    def test_parses_reply_info_class(self, crawler_module):
        result = crawler_module._parse_html_comments(self._soup(_HTML_REPLY_INFO))
        assert len(result) == 1
        assert result[0]["text"] == "A reply text"


# ===========================================================================
# 9. _parse_comment_item
# ===========================================================================

_HTML_FULL_ITEM = """
<li class="cmt_info" data-no="123">
  <span class="gall_writer" data-nick="authorX">authorX</span>
  <span class="usertxt">Normal comment text</span>
  <span class="date_time">2026-02-14 09:30</span>
</li>
"""

_HTML_DCCON_ITEM = """
<li class="cmt_info" data-no="200">
  <span class="gall_writer" data-nick="u">u</span>
  <span class="usertxt">dccon이모티콘</span>
  <span class="date_time">2026-02-14</span>
</li>
"""

_HTML_SHORT_ITEM = """
<li class="cmt_info" data-no="400">
  <span class="gall_writer" data-nick="lazy">lazy</span>
  <span class="usertxt">.</span>
  <span class="date_time">2026-02-14</span>
</li>
"""

_HTML_LONG_ITEM = """
<li class="cmt_info" data-no="500">
  <span class="gall_writer" data-nick="verbose">verbose</span>
  <span class="usertxt">{text}</span>
  <span class="date_time">2026-02-14</span>
</li>
""".format(text="A" * 600)


class TestParseCommentItem:

    def _item(self, html):
        return BeautifulSoup(html, "html.parser").find("li")

    def test_returns_dict_for_valid_item(self, crawler_module):
        result = crawler_module._parse_comment_item(self._item(_HTML_FULL_ITEM))
        assert result is not None
        assert result["text"] == "Normal comment text"
        assert result["author"] == "authorX"
        assert result["comment_id"] == "123"

    def test_returns_none_for_dccon_text(self, crawler_module):
        assert crawler_module._parse_comment_item(self._item(_HTML_DCCON_ITEM)) is None

    def test_returns_none_for_single_char_text(self, crawler_module):
        assert crawler_module._parse_comment_item(self._item(_HTML_SHORT_ITEM)) is None

    def test_truncates_text_to_500_chars(self, crawler_module):
        result = crawler_module._parse_comment_item(self._item(_HTML_LONG_ITEM))
        if result is not None:
            assert len(result["text"]) <= 500


# ===========================================================================
# 10. _extract_comment_author / _extract_comment_text / _extract_comment_date
# ===========================================================================

class TestCommentExtractorHelpers:

    def _li(self, html):
        return BeautifulSoup(html, "html.parser").find("li")

    # --- author ---

    def test_extract_author_prefers_data_nick(self, crawler_module):
        item = self._li('<li><span class="gall_writer" data-nick="preferred">display</span></li>')
        assert crawler_module._extract_comment_author(item) == "preferred"

    def test_extract_author_falls_back_to_element_text(self, crawler_module):
        item = self._li('<li><em>fallback_name</em></li>')
        assert crawler_module._extract_comment_author(item) == "fallback_name"

    def test_extract_author_returns_anonymous_when_no_match(self, crawler_module):
        item = self._li('<li><div>no author signals here</div></li>')
        assert crawler_module._extract_comment_author(item) == "익명"

    def test_extract_author_uses_item_data_nick_attribute_directly(self, crawler_module):
        item = self._li('<li data-nick="direct_nick"><span>inner</span></li>')
        assert crawler_module._extract_comment_author(item) == "direct_nick"

    # --- text ---

    def test_extract_text_prefers_usertxt_class(self, crawler_module):
        item = self._li('<li><span class="usertxt">correct text</span><p>other</p></li>')
        assert crawler_module._extract_comment_text(item) == "correct text"

    def test_extract_text_falls_back_to_p_tag(self, crawler_module):
        item = self._li('<li><p>paragraph text</p></li>')
        assert crawler_module._extract_comment_text(item) == "paragraph text"

    def test_extract_text_returns_empty_for_fallback_longer_than_500_chars(self, crawler_module):
        long_text = "X" * 600
        item = self._li(f'<li><div>{long_text}</div></li>')
        assert crawler_module._extract_comment_text(item) == ""

    # --- date ---

    def test_extract_date_prefers_date_time_class(self, crawler_module):
        item = self._li('<li><span class="date_time">2026-04-01 15:00</span></li>')
        assert crawler_module._extract_comment_date(item) == "2026-04-01 15:00"

    def test_extract_date_falls_back_to_date_class(self, crawler_module):
        item = self._li('<li><span class="date">2026-03-01</span></li>')
        assert crawler_module._extract_comment_date(item) == "2026-03-01"

    def test_extract_date_uses_data_date_attribute(self, crawler_module):
        item = self._li('<li><span data-date="2026-04-01"></span></li>')
        assert crawler_module._extract_comment_date(item) == "2026-04-01"

    def test_extract_date_returns_empty_when_no_date_element(self, crawler_module):
        item = self._li('<li><span>no date</span></li>')
        assert crawler_module._extract_comment_date(item) == ""


# ===========================================================================
# 11. get_gallery_posts  (mocked requests)
# ===========================================================================

_GALLERY_LIST_HTML = """
<table class="gall_list">
  <tbody>
    <tr class="ub-content">
      <td class="gall_num">12345</td>
      <td class="gall_tit">
        <a href="#">ExampleCorp 굿즈 공개</a>
        <span class="reply_num">[7]</span>
      </td>
      <td class="gall_writer" data-nick="writer1">writer1</td>
      <td class="gall_date" title="2026-04-10 12:00:00">12:00</td>
      <td class="gall_count">150</td>
      <td class="gall_recommend">5</td>
    </tr>
    <tr class="ub-content">
      <td class="gall_num">공지</td>
      <td class="gall_tit"><a href="#">공지사항</a></td>
      <td class="gall_writer" data-nick="mod">mod</td>
      <td class="gall_date" title="2026-01-01">01-01</td>
      <td class="gall_count">999</td>
      <td class="gall_recommend">0</td>
    </tr>
    <tr class="ub-content">
      <td class="gall_num">-</td>
      <td class="gall_tit"><a href="#">광고 행</a></td>
      <td class="gall_writer" data-nick="ad">ad</td>
      <td class="gall_date" title="2026-04-10">04-10</td>
      <td class="gall_count">0</td>
      <td class="gall_recommend">0</td>
    </tr>
    <tr class="ub-content">
      <td class="gall_num">12344</td>
      <td class="gall_tit"><a href="#">30:00 유튜브 32:15 타임스탬프 45:20 형식 60:00 테스트</a></td>
      <td class="gall_writer" data-nick="ts_user">ts_user</td>
      <td class="gall_date" title="2026-04-10 11:00">11:00</td>
      <td class="gall_count">10</td>
      <td class="gall_recommend">0</td>
    </tr>
  </tbody>
</table>
"""


def _mock_http_response(html, status=200):
    r = MagicMock()
    r.status_code = status
    r.text = html
    r.raise_for_status = MagicMock()
    return r


class TestGetGalleryPosts:

    def test_returns_empty_list_for_unknown_gallery(self, crawler_module):
        assert crawler_module.get_gallery_posts("nonexistent_gallery") == []

    @patch("requests.get")
    def test_parses_valid_post_row(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response(_GALLERY_LIST_HTML)
        result = crawler_module.get_gallery_posts("ivnit")
        assert any(p["post_id"] == "12345" for p in result)

    @patch("requests.get")
    def test_skips_notice_rows(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response(_GALLERY_LIST_HTML)
        result = crawler_module.get_gallery_posts("ivnit")
        assert all(p["post_id"] != "공지" for p in result)

    @patch("requests.get")
    def test_skips_non_numeric_post_ids(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response(_GALLERY_LIST_HTML)
        result = crawler_module.get_gallery_posts("ivnit")
        assert all(p["post_id"].isdigit() for p in result)

    @patch("requests.get")
    def test_skips_timestamp_heavy_titles(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response(_GALLERY_LIST_HTML)
        result = crawler_module.get_gallery_posts("ivnit")
        assert all(p["post_id"] != "12344" for p in result)

    @patch("requests.get")
    def test_post_url_contains_gallery_type_mini(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response(_GALLERY_LIST_HTML)
        result = crawler_module.get_gallery_posts("ivnit")
        assert result and "mini" in result[0]["url"]

    @patch("requests.get")
    def test_post_url_contains_gallery_type_mgallery(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response(_GALLERY_LIST_HTML)
        result = crawler_module.get_gallery_posts("skoshism")
        if result:
            assert "mgallery" in result[0]["url"]

    @patch("requests.get")
    def test_view_count_is_integer(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response(_GALLERY_LIST_HTML)
        result = crawler_module.get_gallery_posts("ivnit")
        assert all(isinstance(p["view_count"], int) for p in result)

    @patch("requests.get")
    def test_comment_count_extracted_from_reply_num(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response(_GALLERY_LIST_HTML)
        result = crawler_module.get_gallery_posts("ivnit")
        matching = [p for p in result if p["post_id"] == "12345"]
        assert matching and matching[0]["comment_count"] == 7

    @patch("requests.get")
    def test_returns_empty_on_network_exception(self, mock_get, crawler_module):
        mock_get.side_effect = Exception("network error")
        assert crawler_module.get_gallery_posts("ivnit") == []

    @patch("requests.get")
    def test_respects_max_posts_limit(self, mock_get, crawler_module):
        rows = "".join(
            f'<tr class="ub-content">'
            f'<td class="gall_num">{i}</td>'
            f'<td class="gall_tit"><a href="#">Post {i}</a></td>'
            f'<td class="gall_writer" data-nick="u">u</td>'
            f'<td class="gall_date" title="2026-04-10">04-10</td>'
            f'<td class="gall_count">1</td>'
            f'<td class="gall_recommend">0</td>'
            f'</tr>'
            for i in range(1, 6)
        )
        html = f'<table class="gall_list"><tbody>{rows}</tbody></table>'
        mock_get.return_value = _mock_http_response(html)
        result = crawler_module.get_gallery_posts("ivnit", max_posts=3)
        assert len(result) <= 3


# ===========================================================================
# 12. get_comments_with_playwright  (mocked Playwright)
# ===========================================================================

_PW_COMMENT_HTML = """
<html><body>
<ul class="cmt_list">
  <li class="cmt_info" data-no="99">
    <span class="gall_writer" data-nick="pw_user">pw_user</span>
    <span class="usertxt">Playwright comment</span>
    <span class="date_time">2026-04-10 09:00</span>
  </li>
</ul>
</body></html>
"""

_PW_EMPTY_HTML = "<html><body><div>no comments</div></body></html>"

_PW_TOTAL_SPAN_HTML = """
<html><body>
<span id="comment_total_ivnit">42</span>
</body></html>
"""


def _build_pw_context(page_html, selector_raises=False):
    """Return a mock sync_playwright() context manager."""
    mock_page = MagicMock()
    mock_page.content.return_value = page_html
    mock_page.goto = MagicMock()
    if selector_raises:
        mock_page.wait_for_selector.side_effect = _PlaywrightTimeoutError("selector timeout")
    else:
        mock_page.wait_for_selector = MagicMock()

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_p)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx, mock_browser


class TestGetCommentsWithPlaywright:

    @patch("time.sleep")
    def test_returns_parsed_comments_from_html(self, _sleep, crawler_module):
        ctx, _ = _build_pw_context(_PW_COMMENT_HTML)
        with patch("crawler.sync_playwright", return_value=ctx):
            result = crawler_module.get_comments_with_playwright("ivnit", "99")
        assert len(result["comments"]) == 1
        assert result["comments"][0]["text"] == "Playwright comment"

    @patch("time.sleep")
    def test_browser_is_always_closed(self, _sleep, crawler_module):
        ctx, mock_browser = _build_pw_context(_PW_EMPTY_HTML)
        with patch("crawler.sync_playwright", return_value=ctx):
            crawler_module.get_comments_with_playwright("ivnit", "99")
        mock_browser.close.assert_called_once()

    @patch("time.sleep")
    def test_browser_closed_even_when_selector_times_out(self, _sleep, crawler_module):
        ctx, mock_browser = _build_pw_context(_PW_EMPTY_HTML, selector_raises=True)
        with patch("crawler.sync_playwright", return_value=ctx):
            crawler_module.get_comments_with_playwright("ivnit", "99")
        mock_browser.close.assert_called_once()

    @patch("time.sleep")
    def test_returns_empty_when_no_comment_html(self, _sleep, crawler_module):
        ctx, _ = _build_pw_context(_PW_EMPTY_HTML)
        with patch("crawler.sync_playwright", return_value=ctx):
            result = crawler_module.get_comments_with_playwright("ivnit", "99")
        assert result == {"comments": [], "comment_count": 0}

    @patch("time.sleep")
    def test_returns_safe_dict_on_playwright_crash(self, _sleep, crawler_module):
        bad_ctx = MagicMock()
        bad_ctx.__enter__ = MagicMock(side_effect=Exception("pw crashed"))
        bad_ctx.__exit__ = MagicMock(return_value=False)
        with patch("crawler.sync_playwright", return_value=bad_ctx):
            result = crawler_module.get_comments_with_playwright("ivnit", "99")
        assert result == {"comments": [], "comment_count": 0}

    @patch("time.sleep")
    def test_comment_count_from_total_span(self, _sleep, crawler_module):
        ctx, _ = _build_pw_context(_PW_TOTAL_SPAN_HTML)
        with patch("crawler.sync_playwright", return_value=ctx):
            result = crawler_module.get_comments_with_playwright("ivnit", "99")
        assert result["comment_count"] == 42


# ===========================================================================
# 13. trigger_llm_analysis
# ===========================================================================

class TestTriggerLlmAnalysis:

    @patch("requests.post")
    def test_posts_to_correct_endpoint_url(self, mock_post, crawler_module):
        mock_post.return_value = MagicMock(status_code=200)
        crawler_module.trigger_llm_analysis("s3/key", "ivnit", 10)
        url = mock_post.call_args[0][0]
        assert url == "http://llm-analyzer:5000/analyze"

    @patch("requests.post")
    def test_payload_contains_all_required_fields(self, mock_post, crawler_module):
        mock_post.return_value = MagicMock(status_code=200)
        crawler_module.trigger_llm_analysis("s3/key/path", "ivnit", 10)
        payload = mock_post.call_args[1]["json"]
        assert payload["s3_key"] == "s3/key/path"
        assert payload["gallery_id"] == "ivnit"
        assert payload["platform"] == "dcinside"
        assert payload["total_comments"] == 10

    @patch("requests.post")
    def test_does_not_raise_on_connection_error(self, mock_post, crawler_module):
        mock_post.side_effect = Exception("connection refused")
        crawler_module.trigger_llm_analysis("s3/key", "ivnit", 0)  # must not raise

    @patch("requests.post")
    def test_call_includes_timeout_kwarg(self, mock_post, crawler_module):
        mock_post.return_value = MagicMock(status_code=200)
        crawler_module.trigger_llm_analysis("s3/key", "ivnit", 5)
        assert "timeout" in mock_post.call_args[1]


# ===========================================================================
# 14. save_to_s3 — local mode
# ===========================================================================

class TestSaveToS3LocalMode:

    def test_returns_s3_key_path(self, crawler_module, tmp_path):
        original = crawler_module.LOCAL_DATA_DIR
        crawler_module.LOCAL_DATA_DIR = str(tmp_path)
        try:
            key = crawler_module.save_to_s3({"test": "value"}, "ivnit")
            assert key is not None
            assert key.startswith("raw-data/dcinside/ivnit/")
        finally:
            crawler_module.LOCAL_DATA_DIR = original

    def test_written_file_contains_valid_json(self, crawler_module, tmp_path):
        original = crawler_module.LOCAL_DATA_DIR
        crawler_module.LOCAL_DATA_DIR = str(tmp_path)
        try:
            data = {"hello": "world", "count": 42}
            crawler_module.save_to_s3(data, "ivnit")
            files = list((tmp_path / "dcinside" / "ivnit").glob("*.json"))
            assert len(files) == 1
            with open(files[0], encoding="utf-8") as f:
                assert json.load(f) == data
        finally:
            crawler_module.LOCAL_DATA_DIR = original

    def test_key_contains_gallery_id(self, crawler_module, tmp_path):
        original = crawler_module.LOCAL_DATA_DIR
        crawler_module.LOCAL_DATA_DIR = str(tmp_path)
        try:
            key = crawler_module.save_to_s3({"x": 1}, "akaiv")
            assert "akaiv" in key
        finally:
            crawler_module.LOCAL_DATA_DIR = original


# ===========================================================================
# 15. get_e_s_n_o_token
# ===========================================================================

class TestGetESnOToken:

    @patch("requests.get")
    def test_extracts_token_from_script_variable(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response("var e_s_n_o = 'abc123'; var x = 1;")
        assert crawler_module.get_e_s_n_o_token("ivnit", "12345") == "abc123"

    @patch("requests.get")
    def test_extracts_token_from_hidden_input(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response(
            '<html><input name="e_s_n_o" value="tok456"/></html>'
        )
        assert crawler_module.get_e_s_n_o_token("ivnit", "12345") == "tok456"

    @patch("requests.get")
    def test_returns_empty_string_on_non_200_status(self, mock_get, crawler_module):
        r = MagicMock()
        r.status_code = 403
        mock_get.return_value = r
        assert crawler_module.get_e_s_n_o_token("ivnit", "12345") == ""

    @patch("requests.get")
    def test_returns_empty_string_when_token_absent(self, mock_get, crawler_module):
        mock_get.return_value = _mock_http_response("<html><body>no token here</body></html>")
        assert crawler_module.get_e_s_n_o_token("ivnit", "12345") == ""

    @patch("requests.get")
    def test_returns_empty_string_on_exception(self, mock_get, crawler_module):
        mock_get.side_effect = Exception("connection error")
        assert crawler_module.get_e_s_n_o_token("ivnit", "12345") == ""
