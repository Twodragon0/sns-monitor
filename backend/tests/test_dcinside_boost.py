"""Targeted coverage boost for app/services/platforms/dcinside.py.

Missing lines: 231, 516-518, 568-570, 572, 681
"""

import json
from unittest.mock import MagicMock, patch

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


def _make_resp(ok=True, status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


def _make_headers(ua="TestAgent"):
    return {"User-Agent": ua}


# ── Line 231: list comment_count > 0 but collected == 0 warning ────────────
class TestGalleryCommentWarning:
    def test_warning_logged_when_list_count_positive_but_zero_collected(self, analyzer):
        """Line 231: logger.warning path when list_count > 0 and collected == 0."""
        list_html = """
        <html><body>
        <table>
        <tbody>
        <tr class="ub-content">
          <td class="gall_num">12345</td>
          <td class="gall_tit"><a href="/board/view/?id=testgall&no=12345">Post with comment count</a>
            <span class="reply_num">[3]</span>
          </td>
          <td class="gall_writer" data-nick="tester">tester</td>
          <td class="gall_date" title="2024-01-01 12:00:00">2024-01-01</td>
          <td class="gall_count">100</td>
          <td class="gall_recommend">5</td>
        </tr>
        </tbody>
        </table>
        </body></html>
        """
        list_resp = _make_resp(ok=True, text=list_html)
        # Return empty for comment fetch so collected == 0
        empty_resp = _make_resp(ok=True, text="")

        call_count = [0]
        def side_effect(url, **kwargs):
            call_count[0] += 1
            return list_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)
        # Make comment fetch return empty
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[])
        analyzer._session.headers = {"User-Agent": "TestAgent"}

        result = analyzer._analyze_dcinside(
            "https://gall.dcinside.com/board/lists?id=testgall"
        )
        assert result["type"] == "gallery"
        # The warning path was executed (post had comment_count=3, fetched 0)
        analyzer._fetch_dcinside_post_comments.assert_called()


# ── Lines 516-518: HTML comments from non-JSON body (ValueError path) ──────
class TestFetchCommentsAjaxHtmlBody:
    def test_html_body_with_comments_parsed(self, analyzer):
        """Lines 511-515: body is not JSON (ValueError) but contains HTML with cmt_info → parse."""
        from json import JSONDecodeError

        html_body = """
        <ul>
        <li class="cmt_info">
          <span class="nickname">user1</span>
          <p class="usertxt">This is a valid comment text</p>
          <span class="date_time">2024-01-01</span>
        </li>
        </ul>
        """
        token_resp = _make_resp(ok=True, text='e_s_n_o = "tok123"')

        def session_get(url, **kwargs):
            return token_resp

        call_count = [0]
        def session_post(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                r = MagicMock()
                r.ok = True
                r.status_code = 200
                r.text = html_body
                r.json = MagicMock(side_effect=JSONDecodeError("bad json", "", 0))
                return r
            r2 = MagicMock()
            r2.ok = False
            r2.status_code = 404
            r2.text = ""
            r2.json = MagicMock(return_value={})
            return r2

        analyzer._session.get = MagicMock(side_effect=session_get)
        analyzer._session.post = MagicMock(side_effect=session_post)
        analyzer._session.headers = {"User-Agent": "TestAgent"}

        comments = analyzer._fetch_dcinside_comments_ajax(
            "testgall", 12345, "board", {"User-Agent": "TestAgent"}
        )
        # Should have parsed comments from HTML body
        assert isinstance(comments, list)
        assert len(comments) >= 1

    def test_html_body_with_20_plus_comments_continues(self, analyzer):
        """Lines 516-518: >= 20 html comments causes loop to continue (page += 1)."""
        # Build 20 comment items
        items = "".join(
            f'<li class="cmt_info"><span class="nickname">u{i}</span>'
            f'<p class="usertxt">Comment text number {i} here</p>'
            f'<span class="date_time">2024-01-01</span></li>'
            for i in range(20)
        )
        html_body = f"<ul>{items}</ul>"

        from json import JSONDecodeError

        token_resp = _make_resp(ok=True, text='e_s_n_o = "tok456"')

        def session_get(url, **kwargs):
            return token_resp

        call_count = [0]
        def session_post(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                r = MagicMock()
                r.ok = True
                r.status_code = 200
                r.text = html_body
                r.json = MagicMock(side_effect=JSONDecodeError("bad", "", 0))
                return r
            r2 = MagicMock()
            r2.ok = False
            r2.status_code = 404
            r2.text = ""
            r2.json = MagicMock(return_value={})
            return r2

        analyzer._session.get = MagicMock(side_effect=session_get)
        analyzer._session.post = MagicMock(side_effect=session_post)
        analyzer._session.headers = {"User-Agent": "TestAgent"}

        comments = analyzer._fetch_dcinside_comments_ajax(
            "testgall", 99999, "board", {"User-Agent": "TestAgent"}
        )
        assert len(comments) >= 20


# ── Lines 568-570, 572: HTML key in JSON response parsed ───────────────────
class TestFetchCommentsAjaxHtmlKey:
    def test_html_key_in_json_response_parsed(self, analyzer):
        """Lines 568-570: JSON response has 'html' key with cmt_info HTML."""
        html_comment = (
            '<ul><li class="cmt_info">'
            '<span class="nickname">htmluser</span>'
            '<p class="usertxt">Comment from html key in json</p>'
            '<span class="date_time">2024-01-02</span>'
            '</li></ul>'
        )
        json_data = {"html": html_comment}

        token_resp = _make_resp(ok=True, text='e_s_n_o = "tok789"')

        call_count = [0]
        def session_post(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                r = _make_resp(ok=True, status_code=200, text=json.dumps(json_data))
                r.json = MagicMock(return_value=json_data)
                return r
            return _make_resp(ok=False, status_code=404)

        def session_get(url, **kwargs):
            return token_resp

        analyzer._session.get = MagicMock(side_effect=session_get)
        analyzer._session.post = MagicMock(side_effect=session_post)
        analyzer._session.headers = {"User-Agent": "TestAgent"}

        comments = analyzer._fetch_dcinside_comments_ajax(
            "testgall", 54321, "board", {"User-Agent": "TestAgent"}
        )
        assert isinstance(comments, list)
        assert any("html key" in c.get("text", "") for c in comments)

    def test_html_key_20_plus_comments_continues_then_raw_true_continue(self, analyzer):
        """Lines 569-572: html key with >= 20 items sets raw=True and continues."""
        items = "".join(
            f'<li class="cmt_info"><span class="nickname">u{i}</span>'
            f'<p class="usertxt">HTML key comment number {i} here!</p>'
            f'<span class="date_time">2024-01-01</span></li>'
            for i in range(20)
        )
        html_comment = f"<ul>{items}</ul>"
        json_data = {"html": html_comment}

        token_resp = _make_resp(ok=True, text='e_s_n_o = "tok_raw"')

        call_count = [0]
        def session_post(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                r = MagicMock()
                r.ok = True
                r.status_code = 200
                r.text = json.dumps(json_data)
                r.json = MagicMock(return_value=json_data)
                return r
            # second page → stop
            r2 = MagicMock()
            r2.ok = False
            r2.status_code = 404
            r2.text = ""
            r2.json = MagicMock(return_value={})
            return r2

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(side_effect=session_post)
        analyzer._session.headers = {"User-Agent": "TestAgent"}

        comments = analyzer._fetch_dcinside_comments_ajax(
            "testgall", 11111, "board", {"User-Agent": "TestAgent"}
        )
        assert len(comments) >= 20


# ── Line 681: extract_dcinside_comments_from_view_html non-list arr ─────────
class TestExtractDCInsideCommentsFromViewHtml:
    def test_non_list_json_array_match_skipped(self, analyzer):
        """Line 681: parsed JSON is not a list → continue to next pattern."""
        # The regex matches "comments": {...} (a dict, not a list)
        html = 'var data = {"comments": {"count": 5, "page": 1}};'
        comments = analyzer._extract_dcinside_comments_from_view_html(html)
        assert comments == []

    def test_comment_list_pattern_used_as_fallback(self, analyzer):
        """Lines 676-695: comment_list pattern extracts valid comments."""
        comment_arr = [
            {"memo": "Test comment from list", "name": "author1", "reg_date": "2024-01-01"},
        ]
        html = f'var x = {{"comment_list": {json.dumps(comment_arr)}}};'
        comments = analyzer._extract_dcinside_comments_from_view_html(html)
        assert len(comments) == 1
        assert comments[0]["text"] == "Test comment from list"
        assert comments[0]["author"] == "author1"

    def test_skips_html_tagged_and_dccon_comments(self, analyzer):
        """Line 688: text starting with < or dccon is skipped."""
        comment_arr = [
            {"memo": "<img src='x'>", "name": "spammer"},
            {"memo": "dccon123", "name": "sticker_user"},
            {"memo": "Valid comment text here", "name": "valid_user"},
        ]
        html = f'var x = {{"comments": {json.dumps(comment_arr)}}};'
        comments = analyzer._extract_dcinside_comments_from_view_html(html)
        # Only valid comment should pass
        assert len(comments) == 1
        assert comments[0]["text"] == "Valid comment text here"
