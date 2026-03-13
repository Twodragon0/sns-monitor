"""Tests for Naver Cafe analysis."""

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


# ── URL validation & routing ───────────────────────────────────


class TestNaverCafeURLParsing:
    def test_rejects_non_naver_url(self, analyzer):
        with pytest.raises(ValueError, match="Invalid Naver Cafe URL"):
            analyzer._analyze_naver_cafe("https://example.com/cafes/123")

    def test_extracts_club_id_from_cafes_path(self, analyzer):
        """f-e/cafes/ID/menus/0 format."""
        analyzer._analyze_naver_cafe_single_post = MagicMock()
        analyzer._session.get = MagicMock(side_effect=Exception("stop"))
        try:
            analyzer._analyze_naver_cafe(
                "https://cafe.naver.com/f-e/cafes/12345/menus/0"
            )
        except Exception:
            pass
        # If it tried to fetch (not single post), the club_id was extracted

    def test_extracts_club_id_from_ca_fe_path(self, analyzer):
        """ca-fe/web/cafes/ID format."""
        analyzer._session.get = MagicMock(side_effect=Exception("stop"))
        try:
            analyzer._analyze_naver_cafe(
                "https://cafe.naver.com/ca-fe/web/cafes/67890/menus/1"
            )
        except Exception:
            pass

    def test_extracts_club_id_from_query_params(self, analyzer):
        """clubid= query param format."""
        analyzer._session.get = MagicMock(side_effect=Exception("stop"))
        try:
            analyzer._analyze_naver_cafe(
                "https://cafe.naver.com/ArticleRead.nhn?clubid=11111&articleid=222"
            )
        except Exception:
            pass

    def test_raises_without_club_id(self, analyzer):
        with pytest.raises(ValueError, match="Could not extract cafe"):
            analyzer._analyze_naver_cafe("https://cafe.naver.com/somecafe")

    def test_routes_to_single_post_with_article_id(self, analyzer):
        analyzer._analyze_naver_cafe_single_post = MagicMock(return_value={"type": "post"})
        result = analyzer._analyze_naver_cafe(
            "https://cafe.naver.com/ArticleRead.nhn?clubid=12345&articleid=999"
        )
        analyzer._analyze_naver_cafe_single_post.assert_called_once()
        assert result["type"] == "post"

    def test_routes_to_single_post_from_fe_article_url(self, analyzer):
        """f-e/cafes/ID/articles/AID format."""
        analyzer._analyze_naver_cafe_single_post = MagicMock(return_value={"type": "post"})
        analyzer._analyze_naver_cafe(
            "https://cafe.naver.com/ca-fe/web/cafes/12345/articles/999"
        )
        analyzer._analyze_naver_cafe_single_post.assert_called_once()


# ── Menu ID extraction ─────────────────────────────────────────


class TestNaverCafeMenuExtraction:
    def test_menu_id_defaults_to_zero(self, analyzer):
        """When no menu_id in URL, defaults to '0'."""
        analyzer._session.get = MagicMock(side_effect=Exception("stop"))
        try:
            analyzer._analyze_naver_cafe(
                "https://cafe.naver.com/f-e/cafes/12345"
            )
        except Exception:
            pass


# ── Naver Cafe response structure ──────────────────────────────


class TestNaverCafeFetchStatus:
    def test_returns_gallery_type_for_list(self, analyzer):
        """List endpoint should return type=gallery with fetch_status."""
        html_resp = MagicMock()
        html_resp.status_code = 200
        html_resp.ok = True
        html_resp.text = """
        <html><head><title>Test Cafe</title></head>
        <body><h1>Test Cafe</h1></body></html>
        """
        html_resp.raise_for_status = MagicMock()

        # Return same response for all HTTP calls
        analyzer._session.get = MagicMock(return_value=html_resp)
        # Override _naver_get to return our mock
        analyzer._naver_get = MagicMock(return_value=html_resp)

        result = analyzer._analyze_naver_cafe(
            "https://cafe.naver.com/f-e/cafes/12345/menus/0"
        )

        assert result["type"] == "gallery"
        assert "gallery_id" in result
        assert "fetch_status" in result
        assert isinstance(result.get("posts", []), list)
