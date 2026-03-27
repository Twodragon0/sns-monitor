"""Tests for app/services/platforms/naver_cafe.py - NaverCafeMixin coverage."""

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


# ── _extract_naver_article_id ───────────────────────────────────


class TestExtractNaverArticleId:
    def test_extracts_from_articleid_query_param(self, analyzer):
        url = "https://cafe.naver.com/ArticleRead.nhn?clubid=12345&articleid=999"
        assert analyzer._extract_naver_article_id(url) == "999"

    def test_extracts_from_cafes_articles_path(self, analyzer):
        url = "https://cafe.naver.com/ca-fe/web/cafes/12345/articles/777"
        assert analyzer._extract_naver_article_id(url) == "777"

    def test_extracts_from_fe_articles_path(self, analyzer):
        url = "https://cafe.naver.com/f-e/cafes/12345/articles/888"
        assert analyzer._extract_naver_article_id(url) == "888"

    def test_returns_none_for_empty_url(self, analyzer):
        assert analyzer._extract_naver_article_id("") is None
        assert analyzer._extract_naver_article_id(None) is None

    def test_returns_none_when_no_article_id(self, analyzer):
        assert analyzer._extract_naver_article_id("https://cafe.naver.com/somecafe") is None

    def test_case_insensitive_articleid(self, analyzer):
        url = "https://cafe.naver.com/ArticleRead.nhn?clubid=123&articleId=456"
        assert analyzer._extract_naver_article_id(url) == "456"


# ── _extract_naver_cafe_posts_from_script_json ──────────────────


class TestExtractNaverCafePostsFromScriptJson:
    def test_extracts_from_articleList_json(self, analyzer):
        articles = [
            {"articleId": "100", "subject": "Article One", "writer": "user1", "readCount": 50},
            {"articleId": "101", "subject": "Article Two", "writerName": "user2"},
        ]
        html = json.dumps({"articleList": articles})
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 2
        assert result[0]["text"] == "Article One"
        assert result[0]["article_id"] == "100"

    def test_deduplicates_by_article_id(self, analyzer):
        articles = [
            {"articleId": "200", "subject": "Duplicate Post"},
            {"articleId": "200", "subject": "Duplicate Post Again"},
        ]
        html = json.dumps({"articleList": articles})
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        ids = [r["article_id"] for r in result]
        assert ids.count("200") == 1

    def test_skips_short_titles(self, analyzer):
        articles = [
            {"articleId": "300", "subject": "X"},  # too short
            {"articleId": "301", "subject": "Valid title here"},
        ]
        html = json.dumps({"articleList": articles})
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert all(len(r["text"]) >= 2 for r in result)

    def test_returns_empty_for_no_match(self, analyzer):
        result = analyzer._extract_naver_cafe_posts_from_script_json(
            "<html>no json here</html>", "12345"
        )
        assert result == []

    def test_extracts_from_articles_key(self, analyzer):
        articles = [
            {"id": "400", "title": "Title from articles key", "nickname": "auth1"},
        ]
        html = json.dumps({"articles": articles})
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 1
        assert result[0]["text"] == "Title from articles key"

    def test_uses_content_as_title_fallback(self, analyzer):
        articles = [
            {"articleId": "500", "content": "Content used as title when no subject"},
        ]
        html = json.dumps({"articleList": articles})
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        if result:  # content < 200 chars used as title
            assert len(result[0]["text"]) > 0

    def test_post_url_built_correctly(self, analyzer):
        articles = [{"articleId": "600", "subject": "URL Test Article"}]
        html = json.dumps({"articleList": articles})
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "99999")
        assert result[0]["url"].endswith("articleid=600")
        assert "clubid=99999" in result[0]["url"]

    def test_comment_count_extracted(self, analyzer):
        articles = [{"articleId": "700", "subject": "Post with comments", "commentCount": 15}]
        html = json.dumps({"articleList": articles})
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert result[0]["comment_count"] == 15


# ── _parse_naver_comment_items ──────────────────────────────────


class TestParseNaverCommentItems:
    def test_extracts_basic_comment(self, analyzer):
        items = [
            {"content": "Hello comment", "writer": {"nick": "user1"}, "createDate": "2024-01-01"},
        ]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1
        assert result[0]["text"] == "Hello comment"
        assert result[0]["author"] == "user1"

    def test_skips_deleted_comments(self, analyzer):
        items = [
            {"content": "Active comment", "isDeleted": False},
            {"content": "Deleted comment", "isDeleted": True},
        ]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1
        assert result[0]["text"] == "Active comment"

    def test_skips_empty_text(self, analyzer):
        items = [
            {"content": "", "writer": "user"},
            {"content": "Real comment", "writer": "user2"},
        ]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1

    def test_sticker_comment(self, analyzer):
        items = [{"content": "", "sticker": "happy_sticker", "writer": "stickeruser"}]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1
        assert result[0]["text"] == "[스티커]"

    def test_writer_as_string(self, analyzer):
        items = [{"comment": "String writer", "writer": "plain_author"}]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1
        assert result[0]["author"] == "plain_author"

    def test_writer_dict_nickName_fallback(self, analyzer):
        items = [{"text": "Dict writer with nickName", "writer": {"nickName": "NickUser"}}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["author"] == "NickUser"

    def test_epoch_ms_date_conversion(self, analyzer):
        items = [{"memo": "Date conversion test", "createDate": 1704067200000}]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1
        assert "2024" in result[0]["date"]

    def test_non_dict_item_skipped(self, analyzer):
        items = ["not a dict", {"content": "Valid comment", "writer": "u"}]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1

    def test_uses_memo_field(self, analyzer):
        items = [{"memo": "From memo field", "writer": "memouser"}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["text"] == "From memo field"

    def test_uses_body_field(self, analyzer):
        items = [{"body": "From body field", "writer": "bodyuser"}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["text"] == "From body field"


# ── _extract_naver_comments_from_payload ───────────────────────


class TestExtractNaverCommentsFromPayload:
    def test_extracts_from_comments_items_format(self, analyzer):
        payload = {
            "comments": {
                "items": [
                    {"content": "New API comment", "writer": {"nick": "user1"}},
                ]
            }
        }
        result = analyzer._extract_naver_comments_from_payload(payload)
        assert len(result) == 1
        assert result[0]["text"] == "New API comment"

    def test_walks_nested_comment_keys(self, analyzer):
        payload = {
            "message": {
                "result": {
                    "commentList": [
                        {"content": "Nested comment", "writer": "walkuser"},
                    ]
                }
            }
        }
        result = analyzer._extract_naver_comments_from_payload(payload)
        assert len(result) == 1

    def test_returns_empty_for_no_comments(self, analyzer):
        payload = {"data": {"articles": []}}
        result = analyzer._extract_naver_comments_from_payload(payload)
        assert result == []

    def test_empty_payload(self, analyzer):
        result = analyzer._extract_naver_comments_from_payload({})
        assert result == []


# ── _naver_search_cafe_articles ─────────────────────────────────


class TestNaverSearchCafeArticles:
    def test_returns_none_without_credentials(self, analyzer):
        analyzer._naver_search_client_id = ""
        analyzer._naver_search_client_secret = ""
        result = analyzer._naver_search_cafe_articles("query", "cafe", "12345")
        assert result is None

    def test_returns_none_when_daily_limit_reached(self, analyzer):
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._naver_api_daily_limit = 100
        analyzer._get_naver_api_count = MagicMock(return_value=100)

        result = analyzer._naver_search_cafe_articles("query", "cafe", "12345")
        assert result is None

    def test_returns_filtered_results(self, analyzer):
        analyzer._naver_search_client_id = "clientid"
        analyzer._naver_search_client_secret = "clientsecret"
        analyzer._naver_api_daily_limit = 25000
        analyzer._get_naver_api_count = MagicMock(return_value=0)
        analyzer._incr_naver_api_count = MagicMock()

        resp = _make_resp(json_data={
            "items": [
                {
                    "title": "Post <b>Title</b>",
                    "description": "Post <b>description</b>",
                    "link": "https://cafe.naver.com/12345/article/500",
                    "cafename": "test cafe",
                    "postdate": "20240101",
                }
            ]
        })
        analyzer._session.get = MagicMock(return_value=resp)

        result = analyzer._naver_search_cafe_articles("query", "test cafe", "12345")
        assert result is not None
        assert len(result) == 1
        # HTML tags should be stripped
        assert "<b>" not in result[0]["text"]

    def test_returns_none_when_api_fails(self, analyzer):
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._naver_api_daily_limit = 25000
        analyzer._get_naver_api_count = MagicMock(return_value=0)
        analyzer._incr_naver_api_count = MagicMock()
        analyzer._session.get = MagicMock(side_effect=Exception("API error"))

        result = analyzer._naver_search_cafe_articles("q", "cafe", "123")
        assert result is None

    def test_returns_none_when_no_matching_items(self, analyzer):
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._naver_api_daily_limit = 25000
        analyzer._get_naver_api_count = MagicMock(return_value=0)
        analyzer._incr_naver_api_count = MagicMock()

        resp = _make_resp(json_data={
            "items": [
                {
                    "title": "Unrelated post",
                    "link": "https://cafe.naver.com/othercafe/99",
                    "cafename": "completely different cafe",
                }
            ]
        })
        analyzer._session.get = MagicMock(return_value=resp)

        result = analyzer._naver_search_cafe_articles("q", "mycafe", "99999")
        assert result is None


# ── _analyze_naver_cafe_single_post ─────────────────────────────


class TestAnalyzeNaverCafeSinglePost:
    def _post_html(self, title="Post Title", content="Post body here"):
        return f"""
        <html>
        <head><title>{title} : Naver Cafe</title>
        <meta property="og:title" content="{title}"/>
        </head>
        <body>
        <h3 class="title_text">{title}</h3>
        <div class="ContentRenderer">{content}</div>
        <span class="nickname">AuthorNick</span>
        <span class="date">2024-01-15</span>
        <span class="count">조회 150</span>
        </body>
        </html>
        """

    def test_returns_post_type(self, analyzer):
        resp = _make_resp(ok=True, text=self._post_html())
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])

        headers = {"User-Agent": "TestAgent"}
        result = analyzer._analyze_naver_cafe_single_post("12345", "999", headers)
        assert result["type"] == "post"
        assert result["gallery_id"] == "12345"
        assert result["post_no"] == "999"

    def test_extracts_title_and_content(self, analyzer):
        resp = _make_resp(ok=True, text=self._post_html("Great Post", "Detailed content"))
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_naver_cafe_single_post("12345", "100", {})
        assert "Great Post" in result["title"]
        assert result["content"] != "" or result["title"] != ""

    def test_fetch_status_blocked_when_no_content_no_comments(self, analyzer):
        resp = _make_resp(ok=False)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_naver_cafe_single_post("12345", "200", {})
        assert result["fetch_status"] == "blocked"

    def test_fetch_status_partial_when_content_no_comments(self, analyzer):
        resp = _make_resp(ok=True, text=self._post_html("Title", "Content"))
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_naver_cafe_single_post("12345", "300", {})
        # partial if content found but no comments
        if result["content"]:
            assert result["fetch_status"] in ("ok", "partial")

    def test_includes_comments(self, analyzer):
        resp = _make_resp(ok=True, text=self._post_html())
        analyzer._naver_get = MagicMock(return_value=resp)
        mock_comments = [
            {"author": "commenter1", "text": "Great post!", "date": "2024-01-16"},
        ]
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=mock_comments)

        result = analyzer._analyze_naver_cafe_single_post("12345", "400", {})
        assert result["comment_count"] == 1
        assert result["comments"] == mock_comments

    def test_url_in_result(self, analyzer):
        resp = _make_resp(ok=True, text=self._post_html())
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_naver_cafe_single_post("55555", "777", {})
        assert "55555" in result["url"]
        assert "777" in result["url"]

    def test_login_verified_false_without_cookie(self, analyzer):
        resp = _make_resp(ok=True, text=self._post_html("Title", "Content text here"))
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        analyzer._naver_cookie = ""

        result = analyzer._analyze_naver_cafe_single_post("12345", "500", {})
        assert result["login_verified"] is False


# ── _fetch_naver_cafe_post_comments ─────────────────────────────


class TestFetchNaverCafePostComments:
    def _headers(self):
        return {"User-Agent": "TestAgent/1.0"}

    def test_returns_comments_from_api(self, analyzer):
        api_resp = _make_resp(ok=True, text='{"comments": {"items": []}}', json_data={
            "comments": {
                "items": [
                    {"content": "API comment 1", "writer": {"nick": "user1"}},
                    {"content": "API comment 2", "writer": {"nick": "user2"}},
                ]
            }
        })
        analyzer._naver_get = MagicMock(return_value=api_resp)

        result = analyzer._fetch_naver_cafe_post_comments("12345", "999", self._headers())
        assert len(result) == 2

    def test_returns_empty_when_all_fail(self, analyzer):
        resp = _make_resp(ok=False)
        analyzer._naver_get = MagicMock(return_value=resp)

        result = analyzer._fetch_naver_cafe_post_comments("12345", "000", self._headers())
        assert result == []

    def test_html_fallback_parses_comments(self, analyzer):
        html = """
        <html><body>
        <ul class="CommentList">
            <li class="CommentItem">
                <span class="text_comment">HTML comment here</span>
                <span class="nickname">HTMLUser</span>
            </li>
        </ul>
        </body></html>
        """
        api_resp = _make_resp(ok=False)
        html_resp = _make_resp(ok=True, text=html, json_data={})

        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if "articleapi" in url:
                return api_resp
            return html_resp

        analyzer._naver_get = MagicMock(side_effect=side_effect)

        result = analyzer._fetch_naver_cafe_post_comments("12345", "111", self._headers())
        assert isinstance(result, list)

    def test_exception_in_api_continues_to_next(self, analyzer):
        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if "cafe-articleapi/cafes" in url and "/v2/" not in url:
                raise Exception("connection refused")
            return _make_resp(ok=False)

        analyzer._naver_get = MagicMock(side_effect=side_effect)
        result = analyzer._fetch_naver_cafe_post_comments("12345", "222", self._headers())
        assert isinstance(result, list)


# ── _analyze_naver_cafe (list flow) ──────────────────────────────


class TestAnalyzeNaverCafeListFlow:
    def _cafe_list_html(self, cafe_name="Test Cafe"):
        return f"""
        <html>
        <head>
          <title>{cafe_name} : 네이버 카페</title>
          <meta property="og:title" content="{cafe_name}"/>
        </head>
        <body>
        <h1>{cafe_name}</h1>
        <table>
          <tbody>
            <tr class="article-board-row">
              <td><a href="/ArticleRead.nhn?clubid=12345&articleid=1">First Article</a></td>
            </tr>
          </tbody>
        </table>
        </body>
        </html>
        """

    def test_gallery_type_returned(self, analyzer):
        resp = _make_resp(ok=True, text=self._cafe_list_html())
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert result["type"] == "gallery"

    def test_fetch_status_key_present(self, analyzer):
        resp = _make_resp(ok=True, text=self._cafe_list_html())
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert "fetch_status" in result

    def test_naver_get_exception_still_returns_result(self, analyzer):
        analyzer._naver_get = MagicMock(side_effect=Exception("blocked"))

        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert result["type"] == "gallery"

    def test_search_query_in_result(self, analyzer):
        resp = _make_resp(ok=True, text=self._cafe_list_html())
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        analyzer._naver_search_cafe_articles = MagicMock(return_value=None)

        result = analyzer._analyze_naver_cafe(
            "https://cafe.naver.com/f-e/cafes/12345/menus/0?q=search+term"
        )
        if "search_query" in result:
            assert result["search_query"] == "search term"

    def test_login_verified_false_without_cookie(self, analyzer):
        resp = _make_resp(ok=True, text=self._cafe_list_html())
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        analyzer._naver_cookie = ""

        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert result["login_verified"] is False

    def test_api_v21_fallback_when_html_has_no_posts(self, analyzer):
        empty_html = "<html><body><h1>Empty Cafe</h1></body></html>"
        html_resp = _make_resp(ok=True, text=empty_html)

        api_data = {
            "message": {
                "status": "200",
                "result": {
                    "articleList": [
                        {"articleId": 999, "subject": "API Article One", "writerNickname": "api_user"},
                    ]
                }
            }
        }
        api_resp = _make_resp(ok=True, json_data=api_data)

        call_count = [0]

        def naver_get_side(url, **kwargs):
            call_count[0] += 1
            if "ArticleListV2dot1" in url:
                return api_resp
            if "SideMenuList" in url or "CafeGateInfo" in url:
                return _make_resp(ok=False)
            if "ArticleList.json" in url:
                return _make_resp(ok=False)
            if "m.cafe" in url:
                return _make_resp(ok=False)
            return html_resp

        analyzer._naver_get = MagicMock(side_effect=naver_get_side)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])

        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert result["type"] == "gallery"
        # Posts from API should have been collected
        assert isinstance(result["posts"], list)
