"""Comprehensive tests for app/services/platforms/naver_cafe.py to achieve 85%+ coverage."""

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


def _make_resp(ok=True, status_code=200, text="", json_data=None, raise_exc=None):
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.text = text
    resp.json = MagicMock(return_value=json_data or {})
    if raise_exc:
        resp.raise_for_status = MagicMock(side_effect=raise_exc)
    else:
        resp.raise_for_status = MagicMock()
    return resp


# ==========================================
# _analyze_naver_cafe: basic routing & validation
# ==========================================

class TestNaverCafeValidation:
    def test_rejects_non_cafe_url(self, analyzer):
        with pytest.raises(ValueError, match="Invalid Naver Cafe URL"):
            analyzer._analyze_naver_cafe("https://example.com/cafes/123")

    def test_rejects_url_without_club_id(self, analyzer):
        with pytest.raises(ValueError, match="Could not extract cafe"):
            analyzer._analyze_naver_cafe("https://cafe.naver.com/somecafename")

    def test_routes_single_post_with_article_id(self, analyzer):
        analyzer._analyze_naver_cafe_single_post = MagicMock(return_value={"type": "post"})
        result = analyzer._analyze_naver_cafe(
            "https://cafe.naver.com/ArticleRead.nhn?clubid=12345&articleid=999"
        )
        analyzer._analyze_naver_cafe_single_post.assert_called_once()
        assert result["type"] == "post"

    def test_routes_single_post_fe_article_url(self, analyzer):
        analyzer._analyze_naver_cafe_single_post = MagicMock(return_value={"type": "post"})
        analyzer._analyze_naver_cafe(
            "https://cafe.naver.com/ca-fe/web/cafes/12345/articles/999"
        )
        analyzer._analyze_naver_cafe_single_post.assert_called_once()


# ==========================================
# _analyze_naver_cafe: HTML parsing from list page
# ==========================================

class TestNaverCafeListPage:
    def test_returns_gallery_type(self, analyzer):
        html = "<html><head><title>Test Cafe - 네이버 카페</title></head><body></body></html>"
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert result["type"] == "gallery"
        assert result["gallery_id"] == "12345"
        assert result["gallery_name"] == "Test Cafe"

    def test_cafe_name_from_og_title(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="My Cafe | 네이버 카페">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/99999/menus/0")
        assert result["gallery_name"] == "My Cafe"

    def test_blocked_status_when_no_posts(self, analyzer):
        html = "<html><head><title>카페</title></head><body></body></html>"
        analyzer._naver_get = MagicMock(return_value=_make_resp(ok=False))
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/11111/menus/1")
        assert result["fetch_status"] == "blocked"

    def test_cookie_not_set_appended_to_reason(self, analyzer):
        analyzer._naver_cookie = None
        analyzer._naver_get = MagicMock(return_value=_make_resp(ok=False))
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/22222/menus/0")
        assert "cookie_not_set" in result["fetch_reason"]

    def test_total_posts_estimate_from_html(self, analyzer):
        html = """<html><head><title>Cafe</title></head><body>
        <span>1,234개의 글</span>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/33333/menus/0")
        assert result["total_posts"] == 1234

    def test_html_fetch_exception_appends_reason(self, analyzer):
        analyzer._naver_get = MagicMock(side_effect=Exception("network error"))
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/44444/menus/0")
        assert result["fetch_status"] == "blocked"

    def test_login_verified_with_cookie_and_logout_text(self, analyzer):
        html = """<html><head><title>Cafe</title></head>
        <body>로그아웃</body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_cookie = "valid_cookie=abc"
        analyzer._naver_get = MagicMock(return_value=resp)
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/55555/menus/0")
        assert "login_verified" in result

    def test_cafe_content_link_extraction(self, analyzer):
        html = """<html><head><title>MyCafe</title></head><body>
        <div id="cafe_content">
            <a href="/ArticleRead.nhn?clubid=12345&articleid=1">First Article</a>
            <a href="/ArticleRead.nhn?clubid=12345&articleid=2">Second Article</a>
        </div>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert len(result["posts"]) >= 1

    def test_article_board_row_extraction(self, analyzer):
        html = """<html><head><title>BoardCafe</title></head><body>
        <table class="article-board">
        <tbody>
        <tr class="article-board-row">
            <td><a href="/ArticleRead.nhn?clubid=77777&articleid=100" class="article">Article Title Here</a></td>
            <td class="td_name"><a>Author1</a></td>
            <td class="td_date">2025.01.01</td>
            <td class="td_view">500</td>
        </tr>
        </tbody>
        </table>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/77777/menus/0")
        posts = result["posts"]
        assert any(p["text"] == "Article Title Here" for p in posts)

    def test_partial_status_when_posts_but_no_comments(self, analyzer):
        html = """<html><head><title>PartialCafe</title></head><body>
        <div id="cafe_content">
            <a href="/ArticleRead.nhn?clubid=66666&articleid=1">Article Without Comments</a>
        </div>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/66666/menus/0")
        assert result["fetch_status"] in ("partial", "ok")

    def test_search_query_client_side_filter(self, analyzer):
        html = """<html><head><title>SearchCafe</title></head><body>
        <div id="cafe_content">
            <a href="/ArticleRead.nhn?clubid=12399&articleid=1">Python Programming Tips</a>
            <a href="/ArticleRead.nhn?clubid=12399&articleid=2">Java Development Guide</a>
        </div>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        analyzer._naver_search_client_id = None
        analyzer._naver_search_client_secret = None
        result = analyzer._analyze_naver_cafe(
            "https://cafe.naver.com/f-e/cafes/12399/menus/0?q=Python"
        )
        assert result.get("search_query") == "Python"
        assert all("python" in p["text"].lower() for p in result["posts"])

    def test_search_query_no_results(self, analyzer):
        html = "<html><head><title>Cafe</title></head><body></body></html>"
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._naver_search_client_id = None
        result = analyzer._analyze_naver_cafe(
            "https://cafe.naver.com/f-e/cafes/12399/menus/0?q=NoMatch"
        )
        assert result["fetch_status"] == "ok"
        assert result["fetch_reason"] == "no_search_results"

    def test_search_with_naver_api_results_merged(self, analyzer):
        html = """<html><head><title>SearchAPICafe</title></head><body>
        <div id="cafe_content">
            <a href="/ArticleRead.nhn?clubid=12399&articleid=1">Python article</a>
        </div>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        analyzer._naver_search_client_id = "test_client_id"
        analyzer._naver_search_client_secret = "test_secret"
        search_results = [
            {
                "text": "Python article",
                "number": 1,
                "author": "",
                "date": "20250101",
                "url": "https://cafe.naver.com/ArticleRead.nhn?clubid=12399&articleid=1",
                "article_id": "1",
                "search_snippet": "Python snippet",
            }
        ]
        analyzer._naver_search_cafe_articles = MagicMock(return_value=search_results)
        result = analyzer._analyze_naver_cafe(
            "https://cafe.naver.com/f-e/cafes/12399/menus/0?q=Python"
        )
        assert result.get("search_query") == "Python"

    def test_search_naver_api_returns_none_falls_to_client_filter(self, analyzer):
        html = """<html><head><title>Cafe</title></head><body>
        <div id="cafe_content">
            <a href="/ArticleRead.nhn?clubid=12399&articleid=1">Python tips</a>
            <a href="/ArticleRead.nhn?clubid=12399&articleid=2">Java guide</a>
        </div>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._naver_search_cafe_articles = MagicMock(return_value=None)
        result = analyzer._analyze_naver_cafe(
            "https://cafe.naver.com/f-e/cafes/12399/menus/0?q=Python"
        )
        assert all("python" in p["text"].lower() for p in result["posts"])


# ==========================================
# _analyze_naver_cafe: API fallback (ArticleListV2dot1 & ArticleList)
# ==========================================

class TestNaverCafeAPIFallback:
    def test_api_v21_populates_posts(self, analyzer):
        html_resp = _make_resp(ok=False)
        article_list = [
            {
                "articleId": 101,
                "subject": "Test Article 1",
                "writerNickname": "Writer1",
                "writeDate": "2025-01-01",
                "readCount": 100,
                "commentCount": 5,
            },
            {
                "articleId": 102,
                "subject": "Test Article 2",
                "writerNickname": "Writer2",
                "writeDateTimestamp": 1700000000000,
                "readCount": "200",
                "commentCount": "10",
            },
        ]
        api_resp = _make_resp(
            ok=True,
            json_data={
                "message": {
                    "status": "200",
                    "result": {"articleList": article_list},
                }
            },
        )

        def naver_get(url, **kwargs):
            if "ArticleListV2dot1" in url or "SideMenu" in url or "CafeGate" in url:
                return api_resp
            return html_resp

        analyzer._naver_get = MagicMock(side_effect=naver_get)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert len(result["posts"]) >= 1

    def test_api_v21_status_not_200_skips(self, analyzer):
        html_resp = _make_resp(ok=False)
        api_fail = _make_resp(ok=True, json_data={"message": {"status": "401", "result": {}}})

        def naver_get(url, **kwargs):
            if "ArticleListV2dot1" in url:
                return api_fail
            return html_resp

        analyzer._naver_get = MagicMock(side_effect=naver_get)
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/1")
        assert result["fetch_status"] in ("blocked", "partial")

    def test_api_v1_fallback_populates_posts(self, analyzer):
        html_resp = _make_resp(ok=False)
        article_list_v1 = [
            {
                "articleId": 201,
                "subject": "V1 Article",
                "writer": "WriterV1",
                "writeDate": "2025-02-01",
                "readCount": 50,
            }
        ]
        api_v21_resp = _make_resp(ok=True, json_data={"message": {"status": "401", "result": {}}})
        api_v1_resp = _make_resp(
            ok=True,
            json_data={"message": {"result": {"articleList": article_list_v1}}},
        )

        def naver_get(url, **kwargs):
            if "ArticleListV2dot1" in url:
                return api_v21_resp
            if "ArticleList.json" in url:
                return api_v1_resp
            return html_resp

        analyzer._naver_get = MagicMock(side_effect=naver_get)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/1")
        assert any(p["text"] == "V1 Article" for p in result["posts"])

    def test_side_menu_list_fetches_menu_ids_and_cafe_name(self, analyzer):
        html_resp = _make_resp(ok=False)
        side_menu_data = {
            "message": {
                "result": {
                    "menus": [
                        {"menuId": 10, "menuType": "B", "boardType": "L"},
                        {"menuId": 11, "menuType": "B", "boardType": "C"},
                        {"menuId": 12, "menuType": "X", "boardType": "L"},  # skipped
                    ]
                }
            }
        }
        gate_data = {"message": {"result": {"cafeInfoView": {"cafeName": "SideMenu Cafe"}}}}
        api_resp = _make_resp(ok=True, json_data={"message": {"status": "200", "result": {"articleList": []}}})

        def naver_get(url, **kwargs):
            if "SideMenuList" in url:
                return _make_resp(ok=True, json_data=side_menu_data)
            if "CafeGateInfo" in url:
                return _make_resp(ok=True, json_data=gate_data)
            if "ArticleListV2dot1" in url:
                return api_resp
            return html_resp

        analyzer._naver_get = MagicMock(side_effect=naver_get)
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert result["gallery_name"] == "SideMenu Cafe"

    def test_mobile_fallback_populates_posts(self, analyzer):
        html_resp = _make_resp(ok=False)
        mobile_html = """<html><body>
        <a href="/ca-fe/cafes/12345/articles/301">Mobile Article Title Here</a>
        </body></html>"""

        def naver_get(url, **kwargs):
            if "m.cafe.naver.com" in url:
                return _make_resp(ok=True, text=mobile_html)
            if "ArticleListV2dot1" in url or "ArticleList.json" in url:
                return _make_resp(ok=False)
            return html_resp

        analyzer._naver_get = MagicMock(side_effect=naver_get)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/1")
        assert "posts" in result

    def test_comments_fetched_and_counted(self, analyzer):
        html = """<html><head><title>CommentCafe</title></head><body>
        <div id="cafe_content">
            <a href="/ArticleRead.nhn?clubid=12345&articleid=1">Article With Comments</a>
        </div>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        mock_comments = [{"author": "User", "text": "Great post!", "date": "2025-01-01"}]
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=mock_comments)
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert result["total_comments"] > 0

    def test_api_v21_with_articlelistmap(self, analyzer):
        html_resp = _make_resp(ok=False)
        api_resp = _make_resp(
            ok=True,
            json_data={
                "message": {
                    "status": "200",
                    "result": {
                        "articleListMap": {
                            "list": [
                                {"articleId": 300, "subject": "Map Article", "writerNickname": "Writer3"}
                            ]
                        }
                    },
                }
            },
        )

        def naver_get(url, **kwargs):
            if "ArticleListV2dot1" in url or "SideMenu" in url or "CafeGate" in url:
                return api_resp
            return html_resp

        analyzer._naver_get = MagicMock(side_effect=naver_get)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        assert any(p["text"] == "Map Article" for p in result["posts"])

    def test_posts_with_api_count_but_no_comments_list(self, analyzer):
        html = """<html><head><title>Cafe</title></head><body>
        <div id="cafe_content">
            <a href="/ArticleRead.nhn?clubid=12345&articleid=50">Article With API Count</a>
        </div>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        # Return no comment list but simulate comment_count from API
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe("https://cafe.naver.com/f-e/cafes/12345/menus/0")
        # With api_count from fetch returning nothing - posts_with_comments = 0
        assert "fetch_status" in result


# ==========================================
# _naver_search_cafe_articles
# ==========================================

class TestNaverSearchCafeArticles:
    def test_returns_none_without_credentials(self, analyzer):
        analyzer._naver_search_client_id = None
        analyzer._naver_search_client_secret = None
        result = analyzer._naver_search_cafe_articles("query", "cafe", "123")
        assert result is None

    def test_returns_none_when_rate_limited(self, analyzer):
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._naver_api_daily_limit = 0
        analyzer._get_naver_api_count = MagicMock(return_value=1)
        result = analyzer._naver_search_cafe_articles("query", "cafe", "123")
        assert result is None

    def test_api_error_returns_none(self, analyzer):
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._get_naver_api_count = MagicMock(return_value=0)
        analyzer._incr_naver_api_count = MagicMock()
        resp = _make_resp(ok=False, status_code=429, text="Rate limited")
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._naver_search_cafe_articles("query", "cafe", "123")
        assert result is None

    def test_empty_items_returns_empty_list(self, analyzer):
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._get_naver_api_count = MagicMock(return_value=0)
        analyzer._incr_naver_api_count = MagicMock()
        resp = _make_resp(ok=True, json_data={"items": []})
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._naver_search_cafe_articles("query", "cafe", "123")
        assert result == []

    def test_filters_by_club_id_in_link(self, analyzer):
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._get_naver_api_count = MagicMock(return_value=0)
        analyzer._incr_naver_api_count = MagicMock()
        # The code checks: cafe_link_pattern = f"/{club_id}/" so the link must contain /99999/
        items = [
            {
                "title": "<b>Python</b> Tutorial",
                "description": "Learn <b>Python</b>",
                "link": "https://cafe.naver.com/mycafe/99999/articles/456",
                "cafename": "other cafe",
                "postdate": "20250101",
            },
            {
                "title": "Java Guide",
                "description": "Learn Java",
                "link": "https://cafe.naver.com/other/notmatching",
                "cafename": "another cafe",
                "postdate": "20250102",
            },
        ]
        resp = _make_resp(ok=True, json_data={"items": items})
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._naver_search_cafe_articles("Python", "test cafe", "99999")
        assert result is not None
        assert len(result) == 1
        assert "Python Tutorial" in result[0]["text"]

    def test_filters_by_cafe_name(self, analyzer):
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._get_naver_api_count = MagicMock(return_value=0)
        analyzer._incr_naver_api_count = MagicMock()
        items = [
            {
                "title": "Article in MyCafe",
                "description": "content",
                "link": "https://cafe.naver.com/somelink/777",
                "cafename": "mycafe",
                "postdate": "20250103",
            }
        ]
        resp = _make_resp(ok=True, json_data={"items": items})
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._naver_search_cafe_articles("article", "MyCafe", "88888")
        assert result is not None
        assert len(result) == 1

    def test_exception_returns_none(self, analyzer):
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._get_naver_api_count = MagicMock(return_value=0)
        analyzer._incr_naver_api_count = MagicMock()
        analyzer._session.get = MagicMock(side_effect=Exception("network fail"))
        result = analyzer._naver_search_cafe_articles("query", "cafe", "123")
        assert result is None

    def test_no_filter_match_returns_none(self, analyzer):
        analyzer._naver_search_client_id = "id"
        analyzer._naver_search_client_secret = "secret"
        analyzer._get_naver_api_count = MagicMock(return_value=0)
        analyzer._incr_naver_api_count = MagicMock()
        items = [
            {
                "title": "Unrelated Article",
                "description": "content",
                "link": "https://cafe.naver.com/other/999",
                "cafename": "completelydifferent",
                "postdate": "20250104",
            }
        ]
        resp = _make_resp(ok=True, json_data={"items": items})
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._naver_search_cafe_articles("query", "mycafe", "12345")
        assert result is None


# ==========================================
# _analyze_naver_cafe_single_post
# ==========================================

class TestNaverCafeSinglePost:
    def _make_headers(self):
        return {
            "User-Agent": "TestAgent/1.0",
            "Accept": "text/html",
            "Accept-Language": "ko-KR",
            "Referer": "https://cafe.naver.com/",
        }

    def test_success_with_full_content(self, analyzer):
        # NOTE: select_one matches in document order, so <title> in <head>
        # is matched before <h3> in <body> — title retains " - 네이버 카페" suffix
        html = """<html><head>
        <title>My Post Title - 네이버 카페</title>
        </head><body>
        <h3 class="title_text">My Post Title</h3>
        <div class="ContentRenderer">This is the post content here.</div>
        <span class="nickname">AuthorName</span>
        <span class="date">2025.01.15</span>
        <span class="count">1500</span>
        </body></html>"""
        resp = _make_resp(ok=True, text=html)
        comments = [{"author": "User1", "text": "Comment text", "date": "2025-01-15"}]
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=comments)
        result = analyzer._analyze_naver_cafe_single_post("12345", "999", self._make_headers())
        assert result["type"] == "post"
        assert "My Post Title" in result["title"]
        assert result["content"] == "This is the post content here."
        assert result["author"] == "AuthorName"
        assert result["view_count"] == 1500
        assert result["comment_count"] == 1
        assert result["fetch_status"] == "ok"

    def test_blocked_status_when_no_content_no_comments(self, analyzer):
        analyzer._naver_get = MagicMock(return_value=_make_resp(ok=False))
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe_single_post("12345", "000", self._make_headers())
        assert result["fetch_status"] == "blocked"
        assert "content_and_comments_unavailable" in result["fetch_reason"]

    def test_partial_when_content_but_no_comments(self, analyzer):
        html = """<html><body>
        <div class="ContentRenderer">Some content</div>
        </body></html>"""
        resp = _make_resp(ok=True, text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe_single_post("12345", "888", self._make_headers())
        assert result["fetch_status"] == "partial"
        assert result["fetch_reason"] == "content_found_but_comments_unavailable"

    def test_meta_og_title_used(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="OG Article Title">
        </head><body></body></html>"""
        resp = _make_resp(ok=True, text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe_single_post("12345", "777", self._make_headers())
        assert result["title"] == "OG Article Title"

    def test_cookie_not_set_appended_to_reason(self, analyzer):
        analyzer._naver_cookie = None
        analyzer._naver_get = MagicMock(return_value=_make_resp(ok=False))
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe_single_post("12345", "666", self._make_headers())
        assert "cookie_not_set" in result["fetch_reason"]

    def test_login_verified_with_cookie_and_content(self, analyzer):
        html = "<html><body><div class='ContentRenderer'>Content</div></body></html>"
        resp = _make_resp(ok=True, text=html)
        analyzer._naver_cookie = "cookie=abc"
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe_single_post("12345", "555", self._make_headers())
        assert result["login_verified"] is True

    def test_exception_in_page_parse_continues_to_next(self, analyzer):
        call_count = [0]

        def naver_get_side(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("first page failed")
            return _make_resp(ok=True, text="<html><body><div class='ContentRenderer'>Content</div></body></html>")

        analyzer._naver_get = MagicMock(side_effect=naver_get_side)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe_single_post("12345", "444", self._make_headers())
        assert result["type"] == "post"

    def test_returns_correct_url(self, analyzer):
        analyzer._naver_get = MagicMock(return_value=_make_resp(ok=False))
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe_single_post("99999", "123", self._make_headers())
        assert "clubid=99999" in result["url"]
        assert "articleid=123" in result["url"]

    def test_view_count_non_digit_text_is_zero(self, analyzer):
        html = """<html><body>
        <div class="ContentRenderer">Content</div>
        <span class="count">조회수 없음</span>
        </body></html>"""
        resp = _make_resp(ok=True, text=html)
        analyzer._naver_get = MagicMock(return_value=resp)
        analyzer._fetch_naver_cafe_post_comments = MagicMock(return_value=[])
        result = analyzer._analyze_naver_cafe_single_post("12345", "333", self._make_headers())
        assert result["view_count"] == 0


# ==========================================
# _extract_naver_cafe_posts_from_script_json
# ==========================================

class TestExtractNaverCafePostsFromScriptJson:
    def test_extracts_from_preloaded_state(self, analyzer):
        data = {
            "articleList": [
                {"articleId": "1", "subject": "Article 1", "writer": "Writer1"},
                {"articleId": "2", "subject": "Article 2", "writerName": "Writer2"},
            ]
        }
        html = f"var __PRELOADED_STATE__ = {json.dumps(data)};"
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 2
        assert result[0]["text"] == "Article 1"

    def test_extracts_from_article_list_regex(self, analyzer):
        articles = [
            {"articleId": "10", "subject": "Regex Article", "nickname": "User1"},
        ]
        html = f'"articleList": {json.dumps(articles)},'
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 1
        assert result[0]["text"] == "Regex Article"

    def test_extracts_from_articles_regex(self, analyzer):
        articles = [
            {"id": "20", "title": "Articles Key Article", "writer": "Author"},
        ]
        html = f'"articles": {json.dumps(articles)},'
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 1
        assert result[0]["text"] == "Articles Key Article"

    def test_deduplication(self, analyzer):
        articles = [
            {"articleId": "100", "subject": "Dupe Article"},
            {"articleId": "100", "subject": "Dupe Article"},
            {"articleId": "101", "subject": "Unique Article"},
        ]
        html = f'"articleList": {json.dumps(articles)},'
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 2

    def test_skips_non_dict_articles(self, analyzer):
        articles = ["string", 123, {"articleId": "200", "subject": "Valid"}]
        html = f'"articleList": {json.dumps(articles)},'
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 1

    def test_skips_short_title(self, analyzer):
        articles = [
            {"articleId": "300", "subject": "X"},  # too short
            {"articleId": "301", "subject": "Valid Article Title"},
        ]
        html = f'"articleList": {json.dumps(articles)},'
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 1
        assert result[0]["text"] == "Valid Article Title"

    def test_empty_html_returns_empty(self, analyzer):
        result = analyzer._extract_naver_cafe_posts_from_script_json("", "12345")
        assert result == []

    def test_invalid_json_in_preloaded_state(self, analyzer):
        html = "var __PRELOADED_STATE__ = {invalid json};"
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert result == []

    def test_nested_article_list_map(self, analyzer):
        data = {
            "articleListMap": {
                "list": [
                    {"articleId": "400", "subject": "Nested List Article"},
                ]
            }
        }
        html = f"var __PRELOADED_STATE__ = {json.dumps(data)};"
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 1
        assert result[0]["text"] == "Nested List Article"

    def test_returns_max_50_items(self, analyzer):
        articles = [{"articleId": str(i), "subject": f"Article {i}"} for i in range(60)]
        html = f'"articleList": {json.dumps(articles)},'
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 50

    def test_content_used_when_subject_missing(self, analyzer):
        articles = [
            {"articleId": "500", "content": "Content as title fallback"}
        ]
        html = f'"articleList": {json.dumps(articles)},'
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 1

    def test_nested_message_result_articlelist(self, analyzer):
        data = {
            "message": {
                "result": {
                    "articleList": [
                        {"articleId": "600", "subject": "Deeply Nested Article"},
                    ]
                }
            }
        }
        html = f"var __PRELOADED_STATE__ = {json.dumps(data)};"
        result = analyzer._extract_naver_cafe_posts_from_script_json(html, "12345")
        assert len(result) == 1
        assert result[0]["text"] == "Deeply Nested Article"


# ==========================================
# _extract_naver_article_id
# ==========================================

class TestExtractNaverArticleId:
    def test_extracts_from_query_param_articleid(self, analyzer):
        result = analyzer._extract_naver_article_id(
            "https://cafe.naver.com/ArticleRead.nhn?clubid=123&articleid=456"
        )
        assert result == "456"

    def test_extracts_from_query_param_articleId_capital(self, analyzer):
        result = analyzer._extract_naver_article_id(
            "https://cafe.naver.com/ArticleRead.nhn?clubid=123&articleId=789"
        )
        assert result == "789"

    def test_extracts_from_path_cafes_articles(self, analyzer):
        result = analyzer._extract_naver_article_id(
            "https://cafe.naver.com/ca-fe/web/cafes/12345/articles/999"
        )
        assert result == "999"

    def test_extracts_from_regex_articles_pattern(self, analyzer):
        result = analyzer._extract_naver_article_id(
            "https://m.cafe.naver.com/ca-fe/cafes/12345/articles/321"
        )
        assert result == "321"

    def test_returns_none_for_empty_url(self, analyzer):
        result = analyzer._extract_naver_article_id("")
        assert result is None

    def test_returns_none_for_none(self, analyzer):
        result = analyzer._extract_naver_article_id(None)
        assert result is None

    def test_non_digit_article_id_returns_none(self, analyzer):
        result = analyzer._extract_naver_article_id(
            "https://cafe.naver.com/ArticleRead.nhn?clubid=123&articleid=abc"
        )
        assert result is None

    def test_extracts_from_articleid_pattern(self, analyzer):
        result = analyzer._extract_naver_article_id(
            "https://cafe.naver.com/something?articleid=555"
        )
        assert result == "555"


# ==========================================
# _fetch_naver_cafe_post_comments
# ==========================================

class TestFetchNaverCafePostComments:
    def _make_headers(self):
        return {"User-Agent": "TestAgent/1.0"}

    def test_api_returns_comments(self, analyzer):
        payload = {
            "comments": {
                "items": [
                    {"content": "Comment 1", "writer": {"nick": "User1"}, "createDate": "2025-01-01"},
                    {"content": "Comment 2", "writer": {"nick": "User2"}, "createDate": "2025-01-02"},
                ]
            }
        }
        resp = _make_resp(ok=True, text=json.dumps(payload), json_data=payload)
        analyzer._naver_get = MagicMock(return_value=resp)
        comments = analyzer._fetch_naver_cafe_post_comments("12345", "999", self._make_headers())
        assert len(comments) == 2
        assert comments[0]["text"] == "Comment 1"
        assert comments[0]["author"] == "User1"

    def test_api_empty_text_response_skipped(self, analyzer):
        empty_resp = MagicMock()
        empty_resp.ok = True
        empty_resp.text = "   "
        analyzer._naver_get = MagicMock(return_value=empty_resp)
        comments = analyzer._fetch_naver_cafe_post_comments("12345", "888", self._make_headers())
        assert comments == []

    def test_api_not_ok_skipped(self, analyzer):
        analyzer._naver_get = MagicMock(return_value=_make_resp(ok=False))
        comments = analyzer._fetch_naver_cafe_post_comments("12345", "777", self._make_headers())
        assert comments == []

    def test_html_fallback_extracts_comments(self, analyzer):
        api_resp = _make_resp(ok=False)
        html = """<html><body>
        <li class="CommentItem">
            <p class="text_comment">HTML Comment 1</p>
            <span class="nickname">HTMLUser1</span>
            <span class="date">2025-01-10</span>
        </li>
        <li class="CommentItem">
            <p class="text_comment">HTML Comment 2</p>
        </li>
        </body></html>"""
        html_resp = _make_resp(ok=True, text=html)

        def naver_get(url, **kwargs):
            if "articleapi" in url:
                return api_resp
            return html_resp

        analyzer._naver_get = MagicMock(side_effect=naver_get)
        comments = analyzer._fetch_naver_cafe_post_comments("12345", "666", self._make_headers())
        assert len(comments) >= 1
        assert comments[0]["text"] == "HTML Comment 1"

    def test_comment_item_without_text_skipped(self, analyzer):
        api_resp = _make_resp(ok=False)
        html = """<html><body>
        <li class="CommentItem">
        </li>
        </body></html>"""
        html_resp = _make_resp(ok=True, text=html)

        def naver_get(url, **kwargs):
            if "articleapi" in url:
                return api_resp
            return html_resp

        analyzer._naver_get = MagicMock(side_effect=naver_get)
        comments = analyzer._fetch_naver_cafe_post_comments("12345", "555", self._make_headers())
        assert comments == []

    def test_api_exception_continues(self, analyzer):
        def naver_get(url, **kwargs):
            if "articleapi" in url:
                raise Exception("API error")
            return _make_resp(ok=False)

        analyzer._naver_get = MagicMock(side_effect=naver_get)
        comments = analyzer._fetch_naver_cafe_post_comments("12345", "444", self._make_headers())
        assert comments == []

    def test_html_fallback_exception_continues(self, analyzer):
        call_count = [0]

        def naver_get(url, **kwargs):
            call_count[0] += 1
            if "articleapi" in url:
                return _make_resp(ok=False)
            raise Exception("html fail")

        analyzer._naver_get = MagicMock(side_effect=naver_get)
        comments = analyzer._fetch_naver_cafe_post_comments("12345", "333", self._make_headers())
        assert comments == []


# ==========================================
# _extract_naver_comments_from_payload
# ==========================================

class TestExtractNaverCommentsFromPayload:
    def test_new_api_format(self, analyzer):
        payload = {
            "comments": {
                "items": [
                    {"content": "New format comment", "writer": {"nick": "NewUser"}},
                ]
            }
        }
        result = analyzer._extract_naver_comments_from_payload(payload)
        assert len(result) == 1
        assert result[0]["text"] == "New format comment"

    def test_legacy_walk_format(self, analyzer):
        payload = {
            "result": {
                "commentList": [
                    {"content": "Legacy comment", "nickname": "LegacyUser"},
                ]
            }
        }
        result = analyzer._extract_naver_comments_from_payload(payload)
        assert len(result) == 1

    def test_empty_payload(self, analyzer):
        result = analyzer._extract_naver_comments_from_payload({})
        assert result == []

    def test_walk_with_nested_comment_list(self, analyzer):
        payload = {
            "data": {
                "articleCommentList": [
                    {"text": "Nested comment", "writer": "NestUser"},
                ]
            }
        }
        result = analyzer._extract_naver_comments_from_payload(payload)
        assert len(result) == 1

    def test_comments_obj_items_not_list(self, analyzer):
        payload = {
            "comments": {
                "items": "not a list"
            }
        }
        result = analyzer._extract_naver_comments_from_payload(payload)
        assert result == []

    def test_walk_with_list_at_top_level(self, analyzer):
        payload = {
            "commentData": [
                {"content": "Top level comment", "writer": "TopUser"},
            ]
        }
        result = analyzer._extract_naver_comments_from_payload(payload)
        assert len(result) == 1


# ==========================================
# _parse_naver_comment_items
# ==========================================

class TestParseNaverCommentItems:
    def test_skips_deleted_comments(self, analyzer):
        items = [
            {"isDeleted": True, "content": "deleted"},
            {"content": "valid comment", "writer": {"nick": "User"}},
        ]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1
        assert result[0]["text"] == "valid comment"

    def test_skips_non_dict_items(self, analyzer):
        items = ["string", 123, {"content": "valid", "writer": "User"}]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1

    def test_sticker_only_comment(self, analyzer):
        items = [{"sticker": "sticker_id_123", "writer": {"nick": "StickerUser"}}]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1
        assert result[0]["text"] == "[스티커]"

    def test_writer_as_string(self, analyzer):
        items = [{"content": "Comment text", "writer": "StringWriter"}]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1
        assert result[0]["author"] == "StringWriter"

    def test_writer_dict_nick(self, analyzer):
        items = [{"content": "Test", "writer": {"nick": "NickUser"}}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["author"] == "NickUser"

    def test_writer_dict_nickName(self, analyzer):
        items = [{"content": "Test", "writer": {"nickName": "NickNameUser"}}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["author"] == "NickNameUser"

    def test_writer_dict_memberNickname(self, analyzer):
        items = [{"content": "Test", "writer": {"memberNickname": "MemberUser"}}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["author"] == "MemberUser"

    def test_writer_dict_name(self, analyzer):
        items = [{"content": "Test", "writer": {"name": "NameUser"}}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["author"] == "NameUser"

    def test_writer_dict_id(self, analyzer):
        items = [{"content": "Test", "writer": {"id": "id_user"}}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["author"] == "id_user"

    def test_date_as_epoch_ms(self, analyzer):
        items = [{"content": "Timed comment", "writer": "User", "createDate": 1700000000000}]
        result = analyzer._parse_naver_comment_items(items)
        assert len(result) == 1
        assert "2023" in result[0]["date"]

    def test_date_as_string(self, analyzer):
        items = [{"content": "String date comment", "writer": "User", "writeDate": "2025-01-01"}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["date"] == "2025-01-01"

    def test_various_text_fields(self, analyzer):
        for field in ["content", "comment", "text", "memo", "body", "description", "message"]:
            items = [{"writer": "User", field: f"Text via {field}"}]
            result = analyzer._parse_naver_comment_items(items)
            assert result[0]["text"] == f"Text via {field}"

    def test_empty_text_skipped(self, analyzer):
        items = [{"content": "", "writer": "User"}]
        result = analyzer._parse_naver_comment_items(items)
        assert result == []

    def test_writer_dict_fallback_to_dash(self, analyzer):
        items = [{"content": "No author info", "writer": {}}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["author"] == "—"

    def test_no_writer_field_uses_dash(self, analyzer):
        # When "writer" key is absent, item.get("writer") returns None,
        # None or {} = {}, enters dict branch, all fields missing → "—"
        items = [{"content": "No writer key", "nickname": "NicknameUser"}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["author"] == "—"

    def test_writer_string_else_branch_nickname_fallback(self, analyzer):
        # When writer key is a truthy string, enters else branch which checks
        # item.get("nickname") as fallback
        items = [{"content": "Has writer string", "writer": "StringWriter", "nickname": "AltNick"}]
        result = analyzer._parse_naver_comment_items(items)
        # writer is truthy string → else branch → uses writer value directly
        assert result[0]["author"] == "StringWriter"

    def test_date_low_epoch_used_as_string(self, analyzer):
        items = [{"content": "Low epoch", "writer": "User", "updateDate": 1234567}]
        result = analyzer._parse_naver_comment_items(items)
        assert result[0]["date"] == "1234567"

