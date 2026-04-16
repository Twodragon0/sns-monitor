"""Regression tests for DCInside comment-collection fixes."""

import time
from unittest.mock import MagicMock, call, patch

import pytest

from app.services.platform_analyzer import PlatformAnalyzer


@pytest.fixture()
def analyzer():
    with patch.dict(
        "os.environ",
        {"YOUTUBE_API_KEY": "", "REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""},
    ):
        pa = PlatformAnalyzer()
    return pa


# ── _dcinside_galltype_value mapping ──────────────────────────


class TestGalltypeValue:
    def test_board_returns_G(self, analyzer):
        assert analyzer._dcinside_galltype_value("board") == "G"

    def test_major_returns_G(self, analyzer):
        assert analyzer._dcinside_galltype_value("major") == "G"

    def test_mini_returns_MI(self, analyzer):
        assert analyzer._dcinside_galltype_value("mini") == "MI"

    def test_mgallery_returns_M(self, analyzer):
        assert analyzer._dcinside_galltype_value("mgallery") == "M"

    def test_unknown_returns_M(self, analyzer):
        assert analyzer._dcinside_galltype_value("something_else") == "M"


# ── Stale cookie removal in _get_dcinside_comment_token ──────


class TestStaleCookieRemoval:
    def _make_token_response(self, token="TOKEN123"):
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.text = f'var e_s_n_o = "{token}";'
        return resp

    def test_stale_cookies_removed_keep_others(self, analyzer):
        # Pre-populate the session cookie jar with stale + safe cookies
        analyzer._session.cookies.set("csid", "x")
        analyzer._session.cookies.set("gallRecom", "y")
        analyzer._session.cookies.set("service_code", "z")
        analyzer._session.cookies.set("keep_me", "ok")

        analyzer._session.get = MagicMock(return_value=self._make_token_response())

        token = analyzer._get_dcinside_comment_token(
            gallery_id="programming",
            post_no=12345,
            gallery_type="board",
            headers={"User-Agent": "test"},
        )

        # Stale cookies must be gone
        assert "csid" not in analyzer._session.cookies
        assert "gallRecom" not in analyzer._session.cookies
        assert "service_code" not in analyzer._session.cookies
        # Safe cookie must survive
        assert "keep_me" in analyzer._session.cookies
        # Token must be parsed correctly
        assert token == "TOKEN123"

    def test_only_present_stale_cookies_removed(self, analyzer):
        """Should not fail when stale cookies are already absent."""
        # Only set one of the three stale cookies
        analyzer._session.cookies.set("csid", "present")

        analyzer._session.get = MagicMock(return_value=self._make_token_response("ABC"))

        token = analyzer._get_dcinside_comment_token(
            gallery_id="test",
            post_no=1,
            gallery_type="board",
            headers={"User-Agent": "test"},
        )
        assert "csid" not in analyzer._session.cookies
        assert token == "ABC"


# ── Cookie reset + list re-hydration before comment loop ─────


def _make_gallery_list_html(post_no=12345, comment_count=3):
    """Minimal HTML that produces one parseable post row."""
    return f"""
    <html><body>
    <table>
    <tbody>
    <tr class="ub-content">
      <td class="gall_num">{post_no}</td>
      <td class="gall_tit">
        <a href="#">Test post</a>
        <span class="reply_num">[{comment_count}]</span>
      </td>
      <td class="gall_writer" data-nick="author1">author1</td>
      <td class="gall_date" title="2024-01-01">2024-01-01</td>
      <td class="gall_count">100</td>
      <td class="gall_recommend">5</td>
    </tr>
    </tbody>
    </table>
    </body></html>
    """


class TestCookieResetBeforeComments:
    def test_cookies_cleared_and_list_rehydrated(self, analyzer):
        """cookies.clear() then GET list_url must be called before comment loop."""
        list_html = _make_gallery_list_html(post_no=11111, comment_count=2)

        list_resp = MagicMock()
        list_resp.status_code = 200
        list_resp.ok = True
        list_resp.text = list_html
        list_resp.raise_for_status = MagicMock()

        # Track call order: clear() then get(list_url)
        call_log = []

        real_clear = analyzer._session.cookies.clear

        def recording_clear(domain=None, path=None, name=None):
            call_log.append("clear")
            try:
                real_clear(domain=domain, path=path, name=name)
            except KeyError:
                pass

        analyzer._session.cookies.clear = recording_clear

        def recording_get(url, **kwargs):
            call_log.append(("get", url))
            return list_resp

        analyzer._session.get = recording_get

        # Stub comment fetching so we don't hit the network
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[{"author": "a", "text": "b", "date": ""}])

        analyzer._analyze_options = {
            "fetch_comments": True,
            "max_comment_posts": 1,
            "max_comments": 100,
        }

        analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists/?id=programming")

        # cookies.clear must appear before any GET to list_url_base after list scraping
        clear_idx = next((i for i, v in enumerate(call_log) if v == "clear"), None)
        assert clear_idx is not None, "cookies.clear() was never called"

        # After clear, there must be a GET to the list URL
        post_clear_gets = [v for v in call_log[clear_idx:] if isinstance(v, tuple) and v[0] == "get"]
        assert any("board/lists" in url for _, url in post_clear_gets), (
            "No GET to list URL after cookies.clear()"
        )

    def test_no_cookie_reset_when_fetch_comments_false(self, analyzer):
        """When fetch_comments=False, cookies.clear() must NOT be called."""
        list_html = _make_gallery_list_html(post_no=22222, comment_count=5)

        list_resp = MagicMock()
        list_resp.status_code = 200
        list_resp.ok = True
        list_resp.text = list_html
        list_resp.raise_for_status = MagicMock()

        clear_called = []

        def spy_clear(domain=None, path=None, name=None):
            clear_called.append(True)

        analyzer._session.cookies.clear = spy_clear
        analyzer._session.get = MagicMock(return_value=list_resp)

        analyzer._analyze_options = {"fetch_comments": False}

        analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists/?id=programming")

        assert not clear_called, "cookies.clear() should not be called when fetch_comments=False"


# ── Rate-limit delay between posts ───────────────────────────


class TestRateLimitDelay:
    def test_sleep_called_after_second_post(self, analyzer):
        """time.sleep(1.5) must be invoked when attempted > 1."""
        list_html = (
            _make_gallery_list_html(post_no=1001, comment_count=1) +
            _make_gallery_list_html(post_no=1002, comment_count=1)
        )
        # Two valid rows need two separate <tr class="ub-content"> blocks — already the case
        # because _make_gallery_list_html wraps in its own table; combine inside one table:
        two_post_html = f"""
        <html><body><table><tbody>
        <tr class="ub-content">
          <td class="gall_num">1001</td>
          <td class="gall_tit">
            <a href="#">Post 1</a>
            <span class="reply_num">[2]</span>
          </td>
          <td class="gall_writer" data-nick="a">a</td>
          <td class="gall_date" title="2024-01-01">2024-01-01</td>
          <td class="gall_count">10</td>
          <td class="gall_recommend">1</td>
        </tr>
        <tr class="ub-content">
          <td class="gall_num">1002</td>
          <td class="gall_tit">
            <a href="#">Post 2</a>
            <span class="reply_num">[3]</span>
          </td>
          <td class="gall_writer" data-nick="b">b</td>
          <td class="gall_date" title="2024-01-02">2024-01-02</td>
          <td class="gall_count">20</td>
          <td class="gall_recommend">2</td>
        </tr>
        </tbody></table></body></html>
        """

        list_resp = MagicMock()
        list_resp.status_code = 200
        list_resp.ok = True
        list_resp.text = two_post_html
        list_resp.raise_for_status = MagicMock()

        analyzer._session.get = MagicMock(return_value=list_resp)
        analyzer._fetch_dcinside_post_comments = MagicMock(
            return_value=[{"author": "x", "text": "y", "date": ""}]
        )
        analyzer._analyze_options = {
            "fetch_comments": True,
            "max_comment_posts": 2,
            "max_comments": 50,
        }

        with patch("app.services.platforms.dcinside.time.sleep") as mock_sleep:
            analyzer._analyze_dcinside(
                "https://gall.dcinside.com/board/lists/?id=programming"
            )

        # sleep(1.5) must appear at least once (after attempted > 1)
        sleep_calls = [c for c in mock_sleep.call_args_list if c == call(1.5)]
        assert sleep_calls, f"time.sleep(1.5) not called; all calls: {mock_sleep.call_args_list}"

    def test_no_sleep_for_single_post(self, analyzer):
        """time.sleep(1.5) must NOT be called when only one post is attempted."""
        single_post_html = """
        <html><body><table><tbody>
        <tr class="ub-content">
          <td class="gall_num">9001</td>
          <td class="gall_tit">
            <a href="#">Only post</a>
            <span class="reply_num">[1]</span>
          </td>
          <td class="gall_writer" data-nick="x">x</td>
          <td class="gall_date" title="2024-01-01">2024-01-01</td>
          <td class="gall_count">5</td>
          <td class="gall_recommend">0</td>
        </tr>
        </tbody></table></body></html>
        """
        empty_html = "<html><body><table><tbody></tbody></table></body></html>"

        page1_resp = MagicMock()
        page1_resp.status_code = 200
        page1_resp.ok = True
        page1_resp.text = single_post_html
        page1_resp.raise_for_status = MagicMock()

        page2_resp = MagicMock()
        page2_resp.status_code = 200
        page2_resp.ok = True
        page2_resp.text = empty_html
        page2_resp.raise_for_status = MagicMock()

        # First call: page 1 (has post), subsequent calls: empty (stops pagination + rehydration)
        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return page1_resp
            return page2_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)
        analyzer._fetch_dcinside_post_comments = MagicMock(
            return_value=[{"author": "a", "text": "b", "date": ""}]
        )
        analyzer._analyze_options = {
            "fetch_comments": True,
            "max_comment_posts": 5,
            "max_comments": 50,
        }

        with patch("app.services.platforms.dcinside.time.sleep") as mock_sleep:
            analyzer._analyze_dcinside(
                "https://gall.dcinside.com/board/lists/?id=programming"
            )

        sleep_15_calls = [c for c in mock_sleep.call_args_list if c == call(1.5)]
        assert not sleep_15_calls, (
            f"time.sleep(1.5) should not be called for a single post; "
            f"got calls: {mock_sleep.call_args_list}"
        )
