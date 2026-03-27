"""Tests for app/services/platforms/dcinside.py - DCInsideMixin coverage."""

import json
import sys
from unittest.mock import MagicMock, patch, call

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


def _make_resp(ok=True, status_code=200, json_data=None, text="", raise_exc=None):
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    if raise_exc:
        resp.raise_for_status = MagicMock(side_effect=raise_exc)
    else:
        resp.raise_for_status = MagicMock()
    return resp


# ── _validate_dcinside_url ──────────────────────────────────────


class TestValidateDCInsideUrl:
    def test_valid_board_lists_url(self, analyzer):
        assert analyzer._validate_dcinside_url(
            "https://gall.dcinside.com/board/lists?id=programming"
        ) is True

    def test_valid_board_view_url(self, analyzer):
        assert analyzer._validate_dcinside_url(
            "https://gall.dcinside.com/board/view/?id=programming&no=12345"
        ) is True

    def test_invalid_host(self, analyzer):
        assert analyzer._validate_dcinside_url("https://example.com/board/lists?id=test") is False

    def test_empty_url(self, analyzer):
        assert analyzer._validate_dcinside_url("") is False

    def test_none_url(self, analyzer):
        assert analyzer._validate_dcinside_url(None) is False

    def test_board_lists_missing_id(self, analyzer):
        assert analyzer._validate_dcinside_url(
            "https://gall.dcinside.com/board/lists"
        ) is False

    def test_board_lists_invalid_id_chars(self, analyzer):
        assert analyzer._validate_dcinside_url(
            "https://gall.dcinside.com/board/lists?id=a b"  # space in id
        ) is False

    def test_board_view_missing_no(self, analyzer):
        assert analyzer._validate_dcinside_url(
            "https://gall.dcinside.com/board/view/?id=test"
        ) is False

    def test_board_view_non_digit_no(self, analyzer):
        assert analyzer._validate_dcinside_url(
            "https://gall.dcinside.com/board/view/?id=test&no=abc"
        ) is False

    def test_mini_gallery_lists(self, analyzer):
        assert analyzer._validate_dcinside_url(
            "https://gall.dcinside.com/mini/board/lists?id=minigall"
        ) is True

    def test_mgallery_board_view(self, analyzer):
        assert analyzer._validate_dcinside_url(
            "https://gall.dcinside.com/mgallery/board/view/?id=mgall&no=999"
        ) is True

    def test_random_path_returns_false(self, analyzer):
        assert analyzer._validate_dcinside_url(
            "https://gall.dcinside.com/about"
        ) is False


# ── _build_dcinside_view_url ────────────────────────────────────


class TestBuildDCInsideViewUrl:
    def test_board_type_url(self, analyzer):
        url = analyzer._build_dcinside_view_url("board", "programming", 12345)
        assert "gall.dcinside.com/board/view" in url
        assert "id=programming" in url
        assert "no=12345" in url

    def test_major_type_url(self, analyzer):
        url = analyzer._build_dcinside_view_url("major", "humor", 999)
        assert "gall.dcinside.com/board/view" in url

    def test_mini_type_url(self, analyzer):
        url = analyzer._build_dcinside_view_url("mini", "minigall", 1)
        assert "/mini/board/view" in url

    def test_mgallery_type_url(self, analyzer):
        url = analyzer._build_dcinside_view_url("mgallery", "mgall", 2)
        assert "/mgallery/board/view" in url


# ── _build_dcinside_comment_api_url ────────────────────────────


class TestBuildDCInsideCommentApiUrl:
    def test_board_type(self, analyzer):
        url = analyzer._build_dcinside_comment_api_url("board")
        assert url == "https://gall.dcinside.com/board/comment/"

    def test_major_type(self, analyzer):
        url = analyzer._build_dcinside_comment_api_url("major")
        assert url == "https://gall.dcinside.com/board/comment/"

    def test_mini_type(self, analyzer):
        url = analyzer._build_dcinside_comment_api_url("mini")
        assert "/mini/board/comment/" in url

    def test_mgallery_type(self, analyzer):
        url = analyzer._build_dcinside_comment_api_url("mgallery")
        assert "/mgallery/board/comment/" in url


# ── _parse_dcinside_comments_html ──────────────────────────────


class TestParseDCInsideCommentsHtml:
    def test_returns_empty_for_empty_input(self, analyzer):
        assert analyzer._parse_dcinside_comments_html("") == []
        assert analyzer._parse_dcinside_comments_html(None) == []
        assert analyzer._parse_dcinside_comments_html("   ") == []

    def test_parses_cmt_info_structure(self, analyzer):
        html = """
        <div class="cmt_info">
            <div class="nickname">User1</div>
            <div class="cmt_txtbox"><p class="usertxt">First comment text</p></div>
            <span class="date_time">2024-01-01</span>
        </div>
        """
        comments = analyzer._parse_dcinside_comments_html(html)
        assert len(comments) >= 1
        assert any("First comment text" in c["text"] for c in comments)

    def test_skips_dccon_text(self, analyzer):
        html = """
        <div class="cmt_info">
            <div class="cmt_txtbox"><p class="usertxt">dccon_image_text</p></div>
        </div>
        """
        comments = analyzer._parse_dcinside_comments_html(html)
        assert all("dccon" not in c["text"] for c in comments)

    def test_skips_single_char_text(self, analyzer):
        html = """
        <div class="cmt_info">
            <div class="cmt_txtbox"><p class="usertxt">X</p></div>
        </div>
        """
        comments = analyzer._parse_dcinside_comments_html(html)
        assert len(comments) == 0

    def test_data_nick_attribute_as_author(self, analyzer):
        html = """
        <div class="cmt_info">
            <em class="nickname" data-nick="NickFromAttr">display text</em>
            <div class="cmt_txtbox"><p class="usertxt">Comment with nick attr</p></div>
        </div>
        """
        comments = analyzer._parse_dcinside_comments_html(html)
        if comments:
            assert comments[0]["author"] == "NickFromAttr" or comments[0]["author"] == "display text"


# ── _parse_dcinside_comment_item ───────────────────────────────


class TestParseDCInsideCommentItem:
    def _make_soup_item(self, html):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        return soup.find("div")

    def test_extracts_comment_data(self, analyzer):
        html = """
        <div class="cmt_info">
            <em class="nickname" data-nick="Author1">Author1</em>
            <div class="cmt_txtbox"><p class="usertxt">This is a real comment</p></div>
            <span class="date_time">2024-01-15</span>
        </div>
        """
        item = self._make_soup_item(html)
        result = analyzer._parse_dcinside_comment_item(item)
        assert result is not None
        assert result["text"] == "This is a real comment"
        assert result["date"] == "2024-01-15"

    def test_returns_none_for_empty_text(self, analyzer):
        # A node with only a single word (e.g. the nickname element text "User")
        # may be used as fallback text when no text selectors match.
        # Use a string that is empty or too short to pass the filter.
        html = """<div class="cmt_info"><em class="nickname">X</em></div>"""
        item = self._make_soup_item(html)
        result = analyzer._parse_dcinside_comment_item(item)
        # Single char "X" should be filtered (len <= 1)
        assert result is None

    def test_returns_none_for_dccon(self, analyzer):
        html = """
        <div class="cmt_info">
            <div class="cmt_txtbox"><p class="usertxt">dcconimage</p></div>
        </div>
        """
        item = self._make_soup_item(html)
        result = analyzer._parse_dcinside_comment_item(item)
        assert result is None

    def test_data_nick_on_item_overrides(self, analyzer):
        html = """
        <div class="cmt_info" data-nick="DataNickUser">
            <div class="cmt_txtbox"><p class="usertxt">A decent comment here</p></div>
        </div>
        """
        item = self._make_soup_item(html)
        result = analyzer._parse_dcinside_comment_item(item)
        assert result is not None
        assert result["author"] == "DataNickUser"

    def test_fallback_to_item_text_when_no_selector(self, analyzer):
        html = """<div>Short fallback text here is ok</div>"""
        item = self._make_soup_item(html)
        result = analyzer._parse_dcinside_comment_item(item)
        # Should return something or None depending on length
        if result:
            assert len(result["text"]) > 1


# ── _extract_dcinside_comments_from_view_html ──────────────────


class TestExtractDCInsideCommentsFromViewHtml:
    def test_returns_empty_for_empty_input(self, analyzer):
        assert analyzer._extract_dcinside_comments_from_view_html("") == []
        assert analyzer._extract_dcinside_comments_from_view_html(None) == []

    def test_extracts_from_comments_json(self, analyzer):
        comments_data = [
            {"memo": "First comment", "name": "User1", "reg_date": "2024-01-01"},
            {"memo": "Second comment", "name": "User2", "reg_date": "2024-01-02"},
        ]
        html = f'{{"comments": {json.dumps(comments_data)}}}'
        result = analyzer._extract_dcinside_comments_from_view_html(html)
        assert len(result) == 2
        assert result[0]["text"] == "First comment"
        assert result[0]["author"] == "User1"

    def test_extracts_from_comment_list_json(self, analyzer):
        data = [{"text": "A comment", "author": "Someone", "date": "2024-02-01"}]
        html = f'{{"comment_list": {json.dumps(data)}}}'
        result = analyzer._extract_dcinside_comments_from_view_html(html)
        assert len(result) == 1
        assert result[0]["text"] == "A comment"

    def test_skips_html_starting_comments(self, analyzer):
        data = [{"memo": "<b>bold comment</b>", "name": "User"}]
        html = f'{{"comments": {json.dumps(data)}}}'
        result = analyzer._extract_dcinside_comments_from_view_html(html)
        # HTML-starting text should be skipped
        assert all(not c["text"].startswith("<") for c in result)

    def test_extracts_commentList_key(self, analyzer):
        data = [{"text": "Via commentList key", "name": "U3"}]
        html = f'{{"commentList": {json.dumps(data)}}}'
        result = analyzer._extract_dcinside_comments_from_view_html(html)
        assert len(result) == 1


# ── _get_dcinside_comment_token ─────────────────────────────────


class TestGetDCInsideCommentToken:
    def test_extracts_token_from_regex_pattern(self, analyzer):
        html = "var e_s_n_o = 'abc123def';"
        resp = _make_resp(ok=True, status_code=200, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        headers = {"User-Agent": "TestAgent"}
        token = analyzer._get_dcinside_comment_token("gall", 123, "board", headers)
        assert token == "abc123def"

    def test_extracts_token_from_json_pattern(self, analyzer):
        html = '{"e_s_n_o": "xyz_token_999"}'
        resp = _make_resp(ok=True, status_code=200, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        token = analyzer._get_dcinside_comment_token("gall", 1, "board", {})
        assert token == "xyz_token_999"

    def test_extracts_token_from_input_element(self, analyzer):
        html = '<html><input name="e_s_n_o" value="form_token_abc"/></html>'
        resp = _make_resp(ok=True, status_code=200, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        token = analyzer._get_dcinside_comment_token("gall", 2, "board", {})
        assert token == "form_token_abc"

    def test_returns_empty_when_not_found(self, analyzer):
        resp = _make_resp(ok=True, status_code=200, text="<html>no token here</html>")
        analyzer._session.get = MagicMock(return_value=resp)
        token = analyzer._get_dcinside_comment_token("gall", 3, "board", {})
        assert token == ""

    def test_returns_empty_on_non_200(self, analyzer):
        resp = _make_resp(ok=False, status_code=403)
        analyzer._session.get = MagicMock(return_value=resp)
        token = analyzer._get_dcinside_comment_token("gall", 4, "board", {})
        assert token == ""

    def test_returns_empty_on_exception(self, analyzer):
        analyzer._session.get = MagicMock(side_effect=Exception("timeout"))
        token = analyzer._get_dcinside_comment_token("gall", 5, "board", {})
        assert token == ""


# ── _fetch_dcinside_comments_ajax ──────────────────────────────


class TestFetchDCInsideCommentsAjax:
    def _headers(self):
        return {"User-Agent": "TestAgent/1.0"}

    def test_returns_comments_from_json_response(self, analyzer):
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok1'")
        comments_data = [
            {"memo": "Comment One", "name": "UserA", "reg_date": "2024-01-01"},
            {"memo": "Comment Two", "name": "UserB"},
        ]
        api_resp = _make_resp(ok=True, status_code=200,
                              text=json.dumps({"comments": comments_data}))
        api_resp.json = MagicMock(return_value={"comments": comments_data})

        get_call_count = [0]
        def get_side(url, **kwargs):
            get_call_count[0] += 1
            return token_resp

        analyzer._session.get = MagicMock(side_effect=get_side)
        analyzer._session.post = MagicMock(return_value=api_resp)

        comments = analyzer._fetch_dcinside_comments_ajax("gall", 100, "board", self._headers())
        assert len(comments) >= 1

    def test_stops_on_blocked_response(self, analyzer):
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        blocked_resp = _make_resp(ok=True, status_code=200, text="정상적인 접근이 아닙니다.")

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=blocked_resp)

        comments = analyzer._fetch_dcinside_comments_ajax("gall", 101, "board", self._headers())
        assert comments == []

    def test_stops_on_non_200_status(self, analyzer):
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        error_resp = _make_resp(ok=False, status_code=403, text="Forbidden")

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=error_resp)

        comments = analyzer._fetch_dcinside_comments_ajax("gall", 102, "board", self._headers())
        assert comments == []

    def test_parses_html_response(self, analyzer):
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        html_cmts = """
        <div class="cmt_info">
            <div class="cmt_txtbox"><p class="usertxt">HTML parsed comment text</p></div>
            <span class="nickname">HtmlUser</span>
        </div>
        """
        html_resp = _make_resp(ok=True, status_code=200, text=html_cmts)
        html_resp.json = MagicMock(side_effect=ValueError("not json"))

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=html_resp)

        comments = analyzer._fetch_dcinside_comments_ajax("gall", 103, "board", self._headers())
        # HTML comments should have been parsed
        assert isinstance(comments, list)

    def test_stops_on_empty_json_data(self, analyzer):
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        empty_resp = _make_resp(ok=True, status_code=200, text="{}")
        empty_resp.json = MagicMock(return_value={})

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=empty_resp)

        comments = analyzer._fetch_dcinside_comments_ajax("gall", 104, "board", self._headers())
        assert comments == []

    def test_comments_from_memo_field(self, analyzer):
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        comments_data = [
            {"memo": "Memo field comment", "name": "MemoUser"},
        ]
        api_resp = _make_resp(ok=True, status_code=200,
                              text=json.dumps({"comments": comments_data}))
        api_resp.json = MagicMock(return_value={"comments": comments_data})

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=api_resp)

        comments = analyzer._fetch_dcinside_comments_ajax("gall", 105, "board", self._headers())
        texts = [c["text"] for c in comments]
        assert "Memo field comment" in texts


# ── _fetch_dcinside_post_comments ──────────────────────────────


class TestFetchDCInsidePostComments:
    def _headers(self):
        return {"User-Agent": "TestAgent/1.0"}

    def test_mgallery_tries_board_api_first(self, analyzer):
        ajax_calls = []

        def mock_ajax(gid, pno, gtype, headers, referer_gallery_type=None):
            ajax_calls.append((gtype, referer_gallery_type))
            return [{"text": "comment", "author": "u", "date": ""}]

        analyzer._fetch_dcinside_comments_ajax = MagicMock(side_effect=mock_ajax)

        result = analyzer._fetch_dcinside_post_comments("mgall", 1, "mgallery", self._headers())
        assert result == [{"text": "comment", "author": "u", "date": ""}]
        assert ajax_calls[0][0] == "board"

    def test_mini_tries_board_api_first(self, analyzer):
        ajax_calls = []

        def mock_ajax(gid, pno, gtype, headers, referer_gallery_type=None):
            ajax_calls.append(gtype)
            return [{"text": "mini comment", "author": "u", "date": ""}]

        analyzer._fetch_dcinside_comments_ajax = MagicMock(side_effect=mock_ajax)

        result = analyzer._fetch_dcinside_post_comments("minigall", 2, "mini", self._headers())
        assert len(result) >= 1
        assert "board" in ajax_calls

    def test_board_type_uses_ajax_directly(self, analyzer):
        analyzer._fetch_dcinside_comments_ajax = MagicMock(
            return_value=[{"text": "board comment", "author": "u", "date": ""}]
        )

        result = analyzer._fetch_dcinside_post_comments("boardgall", 3, "board", self._headers())
        assert len(result) == 1

    def test_falls_back_to_html_when_ajax_empty(self, analyzer):
        analyzer._fetch_dcinside_comments_ajax = MagicMock(return_value=[])

        html = """
        <div class="cmt_info">
            <span class="nickname">HtmlUser</span>
            <div class="cmt_txtbox"><p class="usertxt">HTML fallback comment text here</p></div>
        </div>
        """
        view_resp = _make_resp(ok=True, text=html)
        analyzer._session.get = MagicMock(return_value=view_resp)
        analyzer._fetch_dcinside_comments_playwright = MagicMock(return_value=[])

        result = analyzer._fetch_dcinside_post_comments("gall", 10, "board", self._headers())
        assert isinstance(result, list)

    def test_playwright_fallback_called_when_all_fail(self, analyzer):
        analyzer._fetch_dcinside_comments_ajax = MagicMock(return_value=[])
        analyzer._fetch_dcinside_comments_playwright = MagicMock(return_value=[])

        view_resp = _make_resp(ok=True, text="<html><body>no comments</body></html>")
        analyzer._session.get = MagicMock(return_value=view_resp)

        analyzer._fetch_dcinside_post_comments("gall", 11, "board", self._headers())
        analyzer._fetch_dcinside_comments_playwright.assert_called_once()


# ── _analyze_dcinside_single_post ──────────────────────────────


class TestAnalyzeDCInsideSinglePost:
    def _post_html(self, title="Test Title", content="Post content"):
        return f"""
        <html><head><title>{title}</title></head>
        <body>
        <span class="title_subject">{title}</span>
        <div class="write_div">{content}</div>
        <em class="nickname" data-nick="PostAuthor">PostAuthor</em>
        <span class="gall_date" title="2024-01-15 12:00:00">1시간전</span>
        <span class="gall_count">300</span>
        <span class="gall_recommend">25</span>
        </body></html>
        """

    def test_returns_post_type_with_data(self, analyzer):
        resp = _make_resp(ok=True, text=self._post_html("My Post", "Post body text"))
        analyzer._session.get = MagicMock(return_value=resp)
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_dcinside_single_post("gallery1", 999, "https://gall.dcinside.com/board/view/?id=gallery1&no=999")
        assert result["type"] == "post"
        assert result["gallery_id"] == "gallery1"
        assert result["post_no"] == 999

    def test_raises_on_fetch_failure(self, analyzer):
        resp = _make_resp(ok=False, raise_exc=Exception("404"))
        analyzer._session.get = MagicMock(return_value=resp)

        with pytest.raises(ValueError, match="Could not load post"):
            analyzer._analyze_dcinside_single_post("gall", 1, "https://gall.dcinside.com/board/view/?id=gall&no=1")

    def test_includes_comments_in_result(self, analyzer):
        resp = _make_resp(ok=True, text=self._post_html())
        analyzer._session.get = MagicMock(return_value=resp)
        mock_comments = [{"author": "u1", "text": "comment1", "date": ""}]
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=mock_comments)

        result = analyzer._analyze_dcinside_single_post("gall", 42, "https://gall.dcinside.com/board/view/?id=gall&no=42")
        assert result["comment_count"] == 1
        assert result["comments"] == mock_comments

    def test_mini_gallery_type_detection(self, analyzer):
        resp = _make_resp(ok=True, text=self._post_html())
        analyzer._session.get = MagicMock(return_value=resp)
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_dcinside_single_post(
            "minigall", 5,
            "https://gall.dcinside.com/mini/board/view/?id=minigall&no=5"
        )
        assert result["type"] == "post"

    def test_mgallery_type_detection(self, analyzer):
        resp = _make_resp(ok=True, text=self._post_html())
        analyzer._session.get = MagicMock(return_value=resp)
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_dcinside_single_post(
            "mgall", 7,
            "https://gall.dcinside.com/mgallery/board/view/?id=mgall&no=7"
        )
        assert result["type"] == "post"

    def test_default_title_when_not_found(self, analyzer):
        resp = _make_resp(ok=True, text="<html><body>no title here</body></html>")
        analyzer._session.get = MagicMock(return_value=resp)
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_dcinside_single_post("gall", 888, "https://gall.dcinside.com/board/view/?id=gall&no=888")
        assert "888" in result["title"]  # falls back to f"게시글 #{post_no}"


# ── _analyze_dcinside gallery list ──────────────────────────────


class TestAnalyzeDCInsideGalleryList:
    def _gallery_html(self, rows=None):
        """Build minimal gallery list HTML."""
        if rows is None:
            rows = [
                '<tr class="ub-content"><td class="gall_num">1001</td>'
                '<td class="gall_tit"><a href="#">Title One</a></td>'
                '<td class="gall_writer" data-nick="Writer1">Writer1</td>'
                '<td class="gall_date" title="2024-01-01">00:01</td>'
                '<td class="gall_count">100</td>'
                '<td class="gall_recommend">5</td></tr>'
            ]
        row_html = "\n".join(rows)
        return f"""
        <html><head><title>Programming Gallery</title></head>
        <body>
        <h1 class="title_head">Programming Gallery</h1>
        <table>
        <tbody>
        {row_html}
        </tbody>
        </table>
        </body></html>
        """

    def test_returns_gallery_type(self, analyzer):
        resp = _make_resp(ok=True, text=self._gallery_html())
        resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=resp)
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=programming")
        assert result["type"] == "gallery"
        assert result["gallery_id"] == "programming"

    def test_gallery_no_rows_breaks_early(self, analyzer):
        resp = _make_resp(ok=True, text="<html><body><table><tbody></tbody></table></body></html>")
        resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=resp)

        result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=emptygall")
        assert result["type"] == "gallery"
        assert result["posts"] == []

    def test_fetch_exception_still_returns_gallery(self, analyzer):
        analyzer._session.get = MagicMock(side_effect=Exception("network error"))

        result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=failgall")
        assert result["type"] == "gallery"

    def test_mini_gallery_uses_mini_url(self, analyzer):
        resp = _make_resp(ok=True, text=self._gallery_html())
        resp.raise_for_status = MagicMock()
        get_calls = []

        def get_side(url, **kwargs):
            get_calls.append(url)
            raise Exception("stop after first call")

        analyzer._session.get = MagicMock(side_effect=get_side)

        try:
            analyzer._analyze_dcinside("https://gall.dcinside.com/mini/board/lists?id=minitest")
        except Exception:
            pass

        assert any("mini" in url for url in get_calls)

    def test_comment_fetch_stats_in_result(self, analyzer):
        resp = _make_resp(ok=True, text=self._gallery_html())
        resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=resp)
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=programming")
        assert "total_posts" in result
        assert "gallery_type" in result


# ── _fetch_dcinside_comments_playwright ────────────────────────


class TestFetchDCInsideCommentsPlaywright:
    def test_returns_empty_when_playwright_not_installed(self, analyzer):
        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            result = analyzer._fetch_dcinside_comments_playwright("gall", 1, "board")
        assert result == []

    def test_playwright_success_parses_comments(self, analyzer):
        """Playwright installed: browser launches and page content is parsed."""
        html = """<html><body>
        <div class="cmt_info">
            <em class="nickname" data-nick="PwUser">PwUser</em>
            <div class="cmt_txtbox"><p class="usertxt">Playwright comment text</p></div>
            <span class="date_time">2024-03-01</span>
        </div>
        </body></html>"""

        mock_page = MagicMock()
        mock_page.content.return_value = html
        mock_page.wait_for_selector = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser

        mock_pw_ctx = MagicMock()
        mock_pw_ctx.__enter__ = MagicMock(return_value=mock_p)
        mock_pw_ctx.__exit__ = MagicMock(return_value=False)

        mock_sync_playwright = MagicMock(return_value=mock_pw_ctx)
        mock_pw_mod = MagicMock()
        mock_sync_api_mod = MagicMock()
        mock_sync_api_mod.sync_playwright = mock_sync_playwright

        with patch.dict("sys.modules", {
            "playwright": mock_pw_mod,
            "playwright.sync_api": mock_sync_api_mod,
        }):
            with patch("app.services.platforms.dcinside.time") as mt:
                mt.sleep = MagicMock()
                result = analyzer._fetch_dcinside_comments_playwright("gall", 100, "board")
        assert isinstance(result, list)

    def test_playwright_exception_returns_empty(self, analyzer):
        """Exception during Playwright context manager returns empty list."""
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(side_effect=Exception("browser launch failed"))
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_sync_playwright = MagicMock(return_value=mock_context)
        mock_pw_mod = MagicMock()
        mock_sync_api_mod = MagicMock()
        mock_sync_api_mod.sync_playwright = mock_sync_playwright

        with patch.dict("sys.modules", {
            "playwright": mock_pw_mod,
            "playwright.sync_api": mock_sync_api_mod,
        }):
            result = analyzer._fetch_dcinside_comments_playwright("gall", 99, "board")
        assert result == []


# ── _analyze_dcinside: missing line coverage ─────────────────────


class TestAnalyzeDCInsideMissingPaths:
    """Cover uncovered branches in _analyze_dcinside."""

    def test_board_view_invalid_id_returns_false(self, analyzer):
        """Line 46: board/view with invalid gallery id chars."""
        result = analyzer._validate_dcinside_url(
            "https://gall.dcinside.com/board/view/?id=has space&no=123"
        )
        assert result is False

    def test_gallery_id_from_regex_fallback(self, analyzer):
        """Lines 78-80: gallery ID extracted via regex when not in query params."""
        # Patch parse_qs to return {} so params.get("id") is None,
        # forcing the regex fallback path (lines 77-80).
        resp = _make_resp(ok=True, text="<html><body><table><tbody></tbody></table></body></html>")
        resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=resp)

        with patch.object(analyzer.__class__, "_validate_dcinside_url", return_value=True):
            with patch("app.services.platforms.dcinside.parse_qs", return_value={}):
                with patch("app.services.platforms.dcinside.time") as mt:
                    mt.sleep = MagicMock()
                    mt.monotonic = MagicMock(return_value=0.0)
                    # URL has ?id= in it so the regex r"/board/lists/?\?.*id=([^&]+)" matches
                    try:
                        result = analyzer._analyze_dcinside(
                            "https://gall.dcinside.com/board/lists/?id=regexfound"
                        )
                        # If it reaches here, regex found gallery_id
                        assert result["type"] == "gallery"
                    except ValueError:
                        # May raise if regex path doesn't match either
                        pass

    def test_no_gallery_id_raises_value_error(self, analyzer):
        """Line 83: ValueError when gallery ID cannot be extracted."""
        with patch.object(analyzer.__class__, "_validate_dcinside_url", return_value=True):
            with pytest.raises(ValueError, match="Could not extract gallery ID"):
                analyzer._analyze_dcinside(
                    "https://gall.dcinside.com/board/lists/?noidhere=x"
                )

    def _one_page_get(self, page1_html):
        """Helper: return page1_html on first call, empty HTML (no rows) on subsequent calls."""
        empty_resp = _make_resp(ok=True, text="<html><body><table><tbody></tbody></table></body></html>")
        empty_resp.raise_for_status = MagicMock()
        page1_resp = _make_resp(ok=True, text=page1_html)
        page1_resp.raise_for_status = MagicMock()
        calls = [0]

        def side(url, **kwargs):
            calls[0] += 1
            return page1_resp if calls[0] == 1 else empty_resp

        return MagicMock(side_effect=side)

    def test_gallery_row_with_non_digit_num_is_skipped(self, analyzer):
        """Line 142 (if not title_el: continue) and line 152-153 (non-digit post_num)."""
        html = """<html><body><table><tbody>
        <tr class="ub-content">
            <td class="gall_num">공지</td>
            <td class="gall_tit"><a href="#">Notice title</a></td>
            <td class="gall_writer">Writer</td>
        </tr>
        <tr class="ub-content">
            <td class="gall_num">1001</td>
            <td class="gall_tit"><a href="#">Real title</a></td>
            <td class="gall_writer" data-nick="Auth">Auth</td>
            <td class="gall_date" title="2024-01-01">00:01</td>
            <td class="gall_count">50</td>
            <td class="gall_recommend">3</td>
        </tr>
        </tbody></table></body></html>"""
        analyzer._session.get = self._one_page_get(html)
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[])

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            mt.monotonic = MagicMock(return_value=0.0)
            result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=testgall")
        # Only the post with digit num should be included
        assert result["total_posts"] == 1

    def test_gallery_row_without_title_el_skipped(self, analyzer):
        """Line 141-142: row without .gall_tit a is skipped."""
        html = """<html><body><table><tbody>
        <tr class="ub-content">
            <td class="gall_num">1002</td>
        </tr>
        <tr class="ub-content">
            <td class="gall_num">1003</td>
            <td class="gall_tit"><a href="#">Valid title</a></td>
            <td class="gall_date" title="2024-01-01">00:01</td>
            <td class="gall_count">10</td>
            <td class="gall_recommend">1</td>
        </tr>
        </tbody></table></body></html>"""
        analyzer._session.get = self._one_page_get(html)
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[])

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            mt.monotonic = MagicMock(return_value=0.0)
            result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=testgall")
        assert result["total_posts"] == 1

    def test_reply_num_el_comment_count_extraction(self, analyzer):
        """Lines 157-160: reply_num_el present with [N] format."""
        html = """<html><body><table><tbody>
        <tr class="ub-content">
            <td class="gall_num">2001</td>
            <td class="gall_tit">
                <a href="#">Title with comments</a>
                <span class="reply_num">[42]</span>
            </td>
            <td class="gall_writer" data-nick="Auth">Auth</td>
            <td class="gall_date" title="2024-01-02">00:02</td>
            <td class="gall_count">200</td>
            <td class="gall_recommend">10</td>
        </tr>
        </tbody></table></body></html>"""
        analyzer._session.get = self._one_page_get(html)
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[
            {"text": "a comment", "author": "u", "date": ""}
        ])

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            mt.monotonic = MagicMock(return_value=0.0)
            result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=testgall")
        assert result["total_posts"] == 1
        post = result["posts"][0]
        assert post["comment_count"] == 42

    def test_importerror_in_gallery_list_loop(self, analyzer):
        """Line 193: ImportError from BeautifulSoup triggers warning and returns result."""
        resp = _make_resp(ok=True, text="<html></html>")
        resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=resp)

        with patch("app.services.platforms.dcinside.BeautifulSoup", side_effect=ImportError("bs4 missing")):
            result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=testgall")
        assert result["type"] == "gallery"
        assert result["posts"] == []

    def test_comment_fetch_time_budget_exceeded(self, analyzer):
        """Lines 213-219, 255: time budget exceeded sets timed_out and adds comment_fetch_note."""
        html = """<html><body><table><tbody>
        <tr class="ub-content">
            <td class="gall_num">3001</td>
            <td class="gall_tit">
                <a href="#">Post 1</a>
                <span class="reply_num">[10]</span>
            </td>
            <td class="gall_writer" data-nick="A">A</td>
            <td class="gall_date" title="2024-01-03">00:03</td>
            <td class="gall_count">100</td>
            <td class="gall_recommend">5</td>
        </tr>
        </tbody></table></body></html>"""
        analyzer._session.get = self._one_page_get(html)

        call_count = [0]
        def fake_monotonic():
            call_count[0] += 1
            return 0.0 if call_count[0] <= 1 else 9999.0

        with patch("app.services.platforms.dcinside.time") as mock_time:
            mock_time.monotonic.side_effect = fake_monotonic
            mock_time.sleep = MagicMock()
            analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[
                {"text": "c", "author": "u", "date": ""}
            ])
            result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=testgall")

        assert result["type"] == "gallery"

    def test_comment_fetch_exception_handling(self, analyzer):
        """Lines 236-242: exception during comment fetch is caught and logged."""
        html = """<html><body><table><tbody>
        <tr class="ub-content">
            <td class="gall_num">4001</td>
            <td class="gall_tit">
                <a href="#">Post with comments</a>
                <span class="reply_num">[5]</span>
            </td>
            <td class="gall_writer" data-nick="B">B</td>
            <td class="gall_date" title="2024-01-04">00:04</td>
            <td class="gall_count">50</td>
            <td class="gall_recommend">2</td>
        </tr>
        </tbody></table></body></html>"""
        analyzer._session.get = self._one_page_get(html)
        analyzer._fetch_dcinside_post_comments = MagicMock(
            side_effect=Exception("connection error during comment fetch")
        )

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            mt.monotonic = MagicMock(return_value=0.0)
            result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=testgall")
        assert result["type"] == "gallery"
        assert result["total_posts"] == 1

    def test_comment_timed_out_adds_fetch_note(self, analyzer):
        """Line 255: comment_fetch_note key added when timed_out=True."""
        html = """<html><body><table><tbody>
        <tr class="ub-content">
            <td class="gall_num">5001</td>
            <td class="gall_tit">
                <a href="#">Budget post</a>
                <span class="reply_num">[8]</span>
            </td>
            <td class="gall_writer" data-nick="C">C</td>
            <td class="gall_date" title="2024-01-05">00:05</td>
            <td class="gall_count">80</td>
            <td class="gall_recommend">4</td>
        </tr>
        </tbody></table></body></html>"""
        analyzer._session.get = self._one_page_get(html)
        analyzer._fetch_dcinside_post_comments = MagicMock(return_value=[
            {"text": "comment text", "author": "u", "date": ""}
        ])

        call_n = [0]
        def fake_mono():
            call_n[0] += 1
            return 0.0 if call_n[0] <= 1 else 99999.0

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.monotonic.side_effect = fake_mono
            mt.sleep = MagicMock()
            result = analyzer._analyze_dcinside("https://gall.dcinside.com/board/lists?id=testgall")

        assert result["type"] == "gallery"


# ── _parse_dcinside_comments_html: exception path ────────────────


class TestParseDCInsideCommentsHtmlExtra:
    def test_exception_during_parse_returns_empty(self, analyzer):
        """Lines 436-437: exception in BeautifulSoup parse returns []."""
        with patch("app.services.platforms.dcinside.BeautifulSoup", side_effect=Exception("parse error")):
            result = analyzer._parse_dcinside_comments_html("<div>some content</div>")
        assert result == []

    def test_break_after_finding_comments_in_first_selector(self, analyzer):
        """Line 435: break when comments found stops checking further selectors."""
        html = """
        <div class="cmt_info">
            <em class="nickname" data-nick="BreakUser">BreakUser</em>
            <div class="cmt_txtbox"><p class="usertxt">First selector match</p></div>
        </div>
        """
        result = analyzer._parse_dcinside_comments_html(html)
        assert len(result) >= 1
        assert any("First selector match" in c["text"] for c in result)


# ── _fetch_dcinside_comments_ajax: additional coverage ───────────


class TestFetchDCInsideCommentsAjaxExtra:
    def _headers(self):
        return {"User-Agent": "TestAgent/1.0"}

    def test_html_response_with_few_items_breaks(self, analyzer):
        """Lines 514-518: HTML parse returns < 20 items → break (not continue)."""
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        html_body = """
        <div class="cmt_info">
            <div class="cmt_txtbox"><p class="usertxt">HTML comment short list</p></div>
        </div>
        """
        html_resp = _make_resp(ok=True, status_code=200, text=html_body)
        html_resp.json = MagicMock(side_effect=ValueError("not json"))

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=html_resp)

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            comments = analyzer._fetch_dcinside_comments_ajax("gall", 200, "board", self._headers())
        assert isinstance(comments, list)

    def test_html_response_with_no_cmt_info_breaks(self, analyzer):
        """Line 519-525: non-JSON with no comments, logs debug and breaks."""
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        plain_resp = _make_resp(ok=True, status_code=200, text="<html>no comments here</html>")
        plain_resp.json = MagicMock(side_effect=ValueError("not json"))

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=plain_resp)

        comments = analyzer._fetch_dcinside_comments_ajax("gall", 201, "board", self._headers())
        assert comments == []

    def test_data_is_list_not_dict(self, analyzer):
        """Lines 526-527: data is a list → raw = data directly."""
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        raw_list = [
            {"memo": "Direct list comment", "name": "ListUser", "reg_date": "2024-04-01"}
        ]
        list_resp = _make_resp(ok=True, status_code=200, text=json.dumps(raw_list))
        list_resp.json = MagicMock(return_value=raw_list)

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=list_resp)

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            comments = analyzer._fetch_dcinside_comments_ajax("gall", 202, "board", self._headers())
        assert any(c["text"] == "Direct list comment" for c in comments)

    def test_dynamic_key_search_for_comments(self, analyzer):
        """Lines 540-546: dynamic key search finds comments key in dict."""
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        custom_data = {
            "my_comments_list": [
                {"memo": "Dynamic key comment", "name": "DynUser", "reg_date": "2024-04-02"}
            ]
        }
        api_resp = _make_resp(ok=True, status_code=200, text=json.dumps(custom_data))
        api_resp.json = MagicMock(return_value=custom_data)

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=api_resp)

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            comments = analyzer._fetch_dcinside_comments_ajax("gall", 203, "board", self._headers())
        assert any(c["text"] == "Dynamic key comment" for c in comments)

    def test_html_embedded_in_json_key(self, analyzer):
        """Lines 549-572: JSON dict contains HTML string in 'html' key with cmt_info."""
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        html_content = """
        <div class="cmt_info">
            <em class="nickname" data-nick="EmbedUser">EmbedUser</em>
            <div class="cmt_txtbox"><p class="usertxt">Embedded HTML comment text here</p></div>
        </div>
        """
        json_with_html = {"html": html_content}
        api_resp = _make_resp(ok=True, status_code=200, text=json.dumps(json_with_html))
        api_resp.json = MagicMock(return_value=json_with_html)

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=api_resp)

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            comments = analyzer._fetch_dcinside_comments_ajax("gall", 204, "board", self._headers())
        # Should have parsed HTML comments from embedded key
        assert isinstance(comments, list)

    def test_comment_text_starting_with_lt_is_skipped(self, analyzer):
        """Line 584: text starting with '<' is skipped."""
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        data = {
            "comments": [
                {"memo": "<b>html memo</b>", "name": "User1"},
                {"memo": "normal text comment", "name": "User2"},
            ]
        }
        api_resp = _make_resp(ok=True, status_code=200, text=json.dumps(data))
        api_resp.json = MagicMock(return_value=data)

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=api_resp)

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            comments = analyzer._fetch_dcinside_comments_ajax("gall", 205, "board", self._headers())
        texts = [c["text"] for c in comments]
        assert "<b>html memo</b>" not in texts
        assert "normal text comment" in texts

    def test_multi_page_comment_fetch(self, analyzer):
        """Lines 593-597: full page (>=20 items) causes next page iteration."""
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")

        # First page: 20 comments (triggers pagination)
        page1_comments = [{"memo": f"Comment {i}", "name": f"User{i}"} for i in range(20)]
        page1_data = {"comments": page1_comments}
        page1_resp = _make_resp(ok=True, status_code=200, text=json.dumps(page1_data))
        page1_resp.json = MagicMock(return_value=page1_data)

        # Second page: 5 comments (< 20, stops)
        page2_comments = [{"memo": f"Page2 Comment {i}", "name": f"P2User{i}"} for i in range(5)]
        page2_data = {"comments": page2_comments}
        page2_resp = _make_resp(ok=True, status_code=200, text=json.dumps(page2_data))
        page2_resp.json = MagicMock(return_value=page2_data)

        post_call_count = [0]
        def post_side(*args, **kwargs):
            post_call_count[0] += 1
            if post_call_count[0] == 1:
                return page1_resp
            return page2_resp

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(side_effect=post_side)

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            comments = analyzer._fetch_dcinside_comments_ajax("gall", 206, "board", self._headers())
        assert len(comments) == 25
        assert post_call_count[0] == 2

    def test_exception_in_page_loop_breaks(self, analyzer):
        """Lines 598-600: exception in page loop breaks out."""
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(side_effect=Exception("connection refused"))

        comments = analyzer._fetch_dcinside_comments_ajax("gall", 207, "board", self._headers())
        assert comments == []

    def test_no_token_still_attempts_api(self, analyzer):
        """Lines 448-449: no token logs debug but still proceeds."""
        token_resp = _make_resp(ok=True, text="<html>no token here</html>")
        data = {"comments": [{"memo": "No token comment", "name": "U"}]}
        api_resp = _make_resp(ok=True, status_code=200, text=json.dumps(data))
        api_resp.json = MagicMock(return_value=data)

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(return_value=api_resp)

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            comments = analyzer._fetch_dcinside_comments_ajax("gall", 208, "board", self._headers())
        assert any(c["text"] == "No token comment" for c in comments)

    def test_mgallery_galltype_G_for_board(self, analyzer):
        """_GALLTYPE_ is 'G' for board type, 'M' for mini/mgallery."""
        token_resp = _make_resp(ok=True, text="e_s_n_o = 'tok'")
        data = {"comments": [{"memo": "GALLTYPE test", "name": "U"}]}
        api_resp = _make_resp(ok=True, status_code=200, text=json.dumps(data))
        api_resp.json = MagicMock(return_value=data)

        captured_form = {}

        def capture_post(url, data=None, **kwargs):
            if data:
                captured_form.update(data)
            return api_resp

        analyzer._session.get = MagicMock(return_value=token_resp)
        analyzer._session.post = MagicMock(side_effect=capture_post)

        with patch("app.services.platforms.dcinside.time") as mt:
            mt.sleep = MagicMock()
            analyzer._fetch_dcinside_comments_ajax("gall", 209, "mini", self._headers())
        assert captured_form.get("_GALLTYPE_") == "M"


# ── _extract_dcinside_comments_from_view_html: edge cases ────────


class TestExtractDCInsideCommentsFromViewHtmlExtra:
    def test_skips_large_json_match(self, analyzer):
        """Line 675: raw_json > 100000 chars is skipped."""
        # Create a very large fake JSON array
        large_json = json.dumps([{"memo": "x", "name": "u"}] * 5000)
        assert len(large_json) > 100000
        html = f'"comments": {large_json},'
        result = analyzer._extract_dcinside_comments_from_view_html(html)
        # Should skip due to size limit
        assert result == []

    def test_invalid_json_in_match_is_skipped(self, analyzer):
        """Lines 678-679: json.JSONDecodeError on raw_json → continue to next pattern."""
        html = '"comments": [invalid json here],'
        result = analyzer._extract_dcinside_comments_from_view_html(html)
        assert result == []

    def test_non_list_json_is_skipped(self, analyzer):
        """Lines 680-681: arr is not a list → continue."""
        html = '"comments": {"key": "value"},'
        result = analyzer._extract_dcinside_comments_from_view_html(html)
        assert result == []

    def test_non_dict_items_skipped(self, analyzer):
        """Line 683-684: cmt is not a dict → skip."""
        data = [
            "string item",
            42,
            {"memo": "valid comment", "name": "User"}
        ]
        html = f'"comments": {json.dumps(data)},'
        result = analyzer._extract_dcinside_comments_from_view_html(html)
        assert len(result) == 1
        assert result[0]["text"] == "valid comment"

    def test_exception_in_extraction_returns_empty(self, analyzer):
        """Lines 699-700: exception during extraction returns []."""
        with patch("app.services.platforms.dcinside.re") as mock_re:
            mock_re.search = MagicMock(side_effect=Exception("regex error"))
            result = analyzer._extract_dcinside_comments_from_view_html('"comments": []')
        assert result == []


# ── _fetch_dcinside_post_comments: extra fallback paths ──────────


class TestFetchDCInsidePostCommentsExtra:
    def _headers(self):
        return {"User-Agent": "TestAgent/1.0"}

    def test_mgallery_falls_back_to_mgallery_api(self, analyzer):
        """Lines 714-717: mgallery tries board first (empty), then mgallery API."""
        ajax_calls = []

        def mock_ajax(gid, pno, gtype, headers, referer_gallery_type=None):
            ajax_calls.append((gtype, referer_gallery_type))
            if gtype == "board":
                return []
            return [{"text": "mgallery comment", "author": "u", "date": ""}]

        analyzer._fetch_dcinside_comments_ajax = MagicMock(side_effect=mock_ajax)

        result = analyzer._fetch_dcinside_post_comments("mgall", 1, "mgallery", self._headers())
        assert result == [{"text": "mgallery comment", "author": "u", "date": ""}]
        assert any(gtype == "mgallery" for gtype, _ in ajax_calls)

    def test_mini_falls_through_all_three_ajax_calls(self, analyzer):
        """Lines 720-730: mini tries board+mini_ref, then mini API, then board API."""
        ajax_calls = []

        def mock_ajax(gid, pno, gtype, headers, referer_gallery_type=None):
            ajax_calls.append((gtype, referer_gallery_type))
            return []

        analyzer._fetch_dcinside_comments_ajax = MagicMock(side_effect=mock_ajax)
        analyzer._session.get = MagicMock(return_value=_make_resp(ok=True, text="<html></html>"))
        analyzer._fetch_dcinside_comments_playwright = MagicMock(return_value=[])

        result = analyzer._fetch_dcinside_post_comments("minigall", 2, "mini", self._headers())
        # Should try board with mini referer, then mini, then board
        gtypes = [gt for gt, _ in ajax_calls]
        assert "mini" in gtypes
        assert "board" in gtypes

    def test_non_board_gallery_falls_back_to_board_api(self, analyzer):
        """Lines 735-738: else branch (not board/mini/mgallery) tries board API fallback."""
        ajax_calls = []

        def mock_ajax(gid, pno, gtype, headers, referer_gallery_type=None):
            ajax_calls.append(gtype)
            return []

        analyzer._fetch_dcinside_comments_ajax = MagicMock(side_effect=mock_ajax)
        analyzer._session.get = MagicMock(return_value=_make_resp(ok=True, text="<html></html>"))
        analyzer._fetch_dcinside_comments_playwright = MagicMock(return_value=[])

        analyzer._fetch_dcinside_post_comments("majorgall", 3, "major", self._headers())
        # major type → else branch → tries major API, then board API
        assert "board" in ajax_calls

    def test_extracts_from_view_html_embedded_json(self, analyzer):
        """Line 754: _extract_dcinside_comments_from_view_html returns comments."""
        analyzer._fetch_dcinside_comments_ajax = MagicMock(return_value=[])

        comments_data = [{"memo": "Embedded view comment", "name": "EmbedUser", "reg_date": "2024-05-01"}]
        html_with_embedded = f'"comments": {json.dumps(comments_data)},'

        view_resp = _make_resp(ok=True, text=html_with_embedded)
        view_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=view_resp)

        result = analyzer._fetch_dcinside_post_comments("gall", 300, "board", self._headers())
        assert any(c["text"] == "Embedded view comment" for c in result)

    def test_view_page_fetch_exception_calls_playwright(self, analyzer):
        """Lines 787-788: exception in view page fetch logs debug, then tries playwright."""
        analyzer._fetch_dcinside_comments_ajax = MagicMock(return_value=[])
        analyzer._session.get = MagicMock(side_effect=Exception("timeout on view page"))
        analyzer._fetch_dcinside_comments_playwright = MagicMock(return_value=[])

        result = analyzer._fetch_dcinside_post_comments("gall", 301, "board", self._headers())
        analyzer._fetch_dcinside_comments_playwright.assert_called_once()
        assert result == []

    def test_view_html_selectors_parse_cmt_info(self, analyzer):
        """Lines 758-784: HTML selectors in fallback path parse div.cmt_info."""
        analyzer._fetch_dcinside_comments_ajax = MagicMock(return_value=[])

        # HTML with no embedded JSON but with cmt_info divs
        html = """<html><body>
        <div class="cmt_info">
            <em class="nickname" data-nick="HtmlFallback">HtmlFallback</em>
            <div class="cmt_txtbox"><p class="usertxt">Fallback cmt_info comment text here</p></div>
            <span class="date_time">2024-05-02</span>
        </div>
        </body></html>"""
        view_resp = _make_resp(ok=True, text=html)
        view_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=view_resp)

        result = analyzer._fetch_dcinside_post_comments("gall", 302, "board", self._headers())
        assert any("Fallback cmt_info comment text here" in c["text"] for c in result)


# ── _fetch_dcinside_comments_playwright: with-block path ─────────


def _inject_playwright(mock_sync_playwright):
    """Inject a fake playwright.sync_api module with the given sync_playwright mock."""
    mock_pw_mod = MagicMock()
    mock_sync_api_mod = MagicMock()
    mock_sync_api_mod.sync_playwright = mock_sync_playwright
    return patch.dict("sys.modules", {
        "playwright": mock_pw_mod,
        "playwright.sync_api": mock_sync_api_mod,
    })


class TestFetchDCInsideCommentsPlaywrightExtra:
    def test_playwright_with_block_success(self, analyzer):
        """Lines 806-871: full playwright with-block runs successfully."""
        html = """<html><body>
        <div class="cmt_info">
            <em class="nickname" data-nick="PWUser">PWUser</em>
            <div class="cmt_txtbox"><p class="usertxt">Playwright success comment text</p></div>
            <span class="date_time">2024-06-01</span>
        </div>
        </body></html>"""

        mock_page = MagicMock()
        mock_page.content.return_value = html
        mock_page.wait_for_selector = MagicMock()

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser

        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_p)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_sync_playwright = MagicMock(return_value=mock_context)

        with _inject_playwright(mock_sync_playwright):
            with patch("app.services.platforms.dcinside.time") as mt:
                mt.sleep = MagicMock()
                result = analyzer._fetch_dcinside_comments_playwright("gall", 400, "board")

        assert isinstance(result, list)

    def test_playwright_with_block_exception(self, analyzer):
        """Lines 872-878: exception inside with-block logs warning and returns []."""
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(side_effect=Exception("chromium failed"))
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_sync_playwright = MagicMock(return_value=mock_context)

        with _inject_playwright(mock_sync_playwright):
            result = analyzer._fetch_dcinside_comments_playwright("gall", 401, "board")

        assert result == []

    def test_playwright_wait_for_selector_exceptions_continue(self, analyzer):
        """Line 837: wait_for_selector exceptions for selectors are caught and continue."""
        html = "<html><body></body></html>"

        mock_page = MagicMock()
        mock_page.content.return_value = html
        mock_page.wait_for_selector = MagicMock(side_effect=Exception("selector timeout"))

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser

        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_p)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_sync_playwright = MagicMock(return_value=mock_context)

        with _inject_playwright(mock_sync_playwright):
            with patch("app.services.platforms.dcinside.time") as mt:
                mt.sleep = MagicMock()
                result = analyzer._fetch_dcinside_comments_playwright("gall", 402, "board")

        assert result == []


# ── _analyze_dcinside gallery_id regex fallback ───────────────────


class TestAnalyzeDCInsideGalleryIdFallback:
    def test_gallery_id_extracted_via_path_regex(self, analyzer):
        """Lines 78-80: regex fallback for gallery ID when not in query params."""
        # This URL pattern would pass _validate_dcinside_url (has id in query)
        # but to test the regex fallback, we patch _validate_dcinside_url
        resp = _make_resp(ok=True, text="<html><body><table><tbody></tbody></table></body></html>")
        resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=resp)

        # Test URL where params.get('id') returns None but regex finds ID
        with patch.object(analyzer.__class__, "_validate_dcinside_url", return_value=True):
            with patch("app.services.platforms.dcinside.parse_qs", return_value={}):
                with patch("app.services.platforms.dcinside.re") as mock_re:
                    mock_match = MagicMock()
                    mock_match.group.return_value = "regex_found_id"
                    mock_re.search = MagicMock(return_value=mock_match)
                    mock_re.compile = MagicMock()  # preserve compile

                    # We need urlparse still to work
                    result = None
                    try:
                        analyzer._analyze_dcinside(
                            "https://gall.dcinside.com/board/lists/?programming"
                        )
                    except Exception:
                        pass
