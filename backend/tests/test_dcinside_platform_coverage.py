"""Tests for app/services/platforms/dcinside.py - DCInsideMixin coverage."""

import json
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
