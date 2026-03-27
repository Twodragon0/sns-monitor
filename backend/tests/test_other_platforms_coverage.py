"""Comprehensive tests for app/services/platforms/other_platforms.py to achieve 85%+ coverage."""

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
# Telegram
# ==========================================

class TestAnalyzeTelegram:
    def test_invalid_url_raises(self, analyzer):
        with pytest.raises(ValueError, match="Could not extract Telegram"):
            analyzer._analyze_telegram("https://t.me/")

    def test_403_returns_blocked(self, analyzer):
        resp = _make_resp(status_code=403)
        resp.status_code = 403
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_telegram("https://t.me/privatechannel")
        assert result["fetch_status"] == "blocked"
        assert result["fetch_reason"] == "telegram_403_forbidden"
        assert result["channel_name"] == "privatechannel"

    def test_success_with_full_html(self, analyzer):
        html = """
        <html><body>
        <div class="tgme_channel_info_header_title">My Channel</div>
        <div class="tgme_channel_info_description">A great channel</div>
        <div class="tgme_channel_info_counter"><span class="counter_value">5K</span></div>
        <div class="tgme_widget_message_wrap">
            <div class="tgme_widget_message_text">Hello world</div>
            <a class="tgme_widget_message_date"><time datetime="2025-01-01T00:00:00"></time></a>
            <span class="tgme_widget_message_views">100</span>
        </div>
        <div class="tgme_widget_message_wrap">
            <div class="tgme_widget_message_text">Another message</div>
        </div>
        </body></html>
        """
        resp = _make_resp(status_code=200, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_telegram("https://t.me/s/mychannel")
        assert result["type"] == "channel"
        assert result["channel_name"] == "mychannel"
        assert result["title"] == "My Channel"
        assert result["description"] == "A great channel"
        assert result["subscriber_count"] == "5K"
        assert result["total_messages"] == 2

    def test_success_with_minimal_html(self, analyzer):
        """Missing optional elements still returns a valid result."""
        resp = _make_resp(status_code=200, text="<html><body></body></html>")
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_telegram("https://t.me/channel123")
        assert result["type"] == "channel"
        assert result["channel_name"] == "channel123"
        assert result["total_messages"] == 0

    def test_message_without_text_el_is_skipped(self, analyzer):
        html = """
        <html><body>
        <div class="tgme_widget_message_wrap">
        </div>
        </body></html>
        """
        resp = _make_resp(status_code=200, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_telegram("https://t.me/chan")
        assert result["total_messages"] == 0

    def test_message_with_date_and_views(self, analyzer):
        html = """
        <html><body>
        <div class="tgme_widget_message_wrap">
            <div class="tgme_widget_message_text">Post text</div>
            <a class="tgme_widget_message_date"><time datetime="2024-06-01T10:00:00+00:00"></time></a>
            <span class="tgme_widget_message_views">50</span>
        </div>
        </body></html>
        """
        resp = _make_resp(status_code=200, text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_telegram("https://t.me/newchan")
        assert len(result["posts"]) == 1
        assert result["posts"][0]["date"] == "2024-06-01T10:00:00+00:00"
        assert result["posts"][0]["views"] == "50"


# ==========================================
# Kakao
# ==========================================

class TestAnalyzeKakao:
    def test_pf_kakao_routes_to_profile(self, analyzer):
        html = """<html><head>
        <title>Test Brand</title>
        <meta name="description" content="Brand desc">
        <meta property="og:image" content="https://example.com/img.jpg">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_kakao("https://pf.kakao.com/_testbrand")
        assert result["type"] == "kakao_profile"
        assert result["title"] == "Test Brand"
        assert result["description"] == "Brand desc"
        assert result["thumbnail"] == "https://example.com/img.jpg"
        assert len(result["posts"]) == 1

    def test_pf_kakao_no_title_or_description(self, analyzer):
        html = "<html><head></head><body></body></html>"
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_kakao("https://pf.kakao.com/_test")
        assert result["type"] == "kakao_profile"
        assert result["posts"] == []

    def test_story_kakao_routes_to_story(self, analyzer):
        html = """<html><head>
        <title>Story Title</title>
        <meta property="og:description" content="Story about us">
        <meta property="og:image" content="https://example.com/story.jpg">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_kakao("https://story.kakao.com/someuser")
        assert result["type"] == "kakao_story"
        assert result["title"] == "Story Title"
        assert result["description"] == "Story about us"
        assert len(result["posts"]) == 1

    def test_story_kakao_no_content(self, analyzer):
        html = "<html><head></head><body></body></html>"
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_kakao("https://story.kakao.com/noone")
        assert result["type"] == "kakao_story"
        assert result["posts"] == []

    def test_openchat_kakao_with_member_count(self, analyzer):
        html = """<html><head>
        <title>My Open Chat</title>
        <meta property="og:description" content="Join us">
        <meta property="og:image" content="https://example.com/oc.jpg">
        <meta property="og:type" content="website">
        </head><body>현재 1,234명이 참여 중입니다.</body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_kakao("https://open.kakao.com/o/gABCDEF")
        assert result["type"] == "kakao_openchat"
        assert result["member_count"] == 1234
        assert result["og_type"] == "website"
        assert len(result["posts"]) == 1

    def test_openchat_no_content(self, analyzer):
        html = "<html><head></head><body></body></html>"
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_kakao("https://open.kakao.com/o/gXYZ")
        assert result["type"] == "kakao_openchat"
        assert result["posts"] == []

    def test_unsupported_kakao_url_raises(self, analyzer):
        with pytest.raises(ValueError, match="Unsupported Kakao"):
            analyzer._analyze_kakao("https://developers.kakao.com/docs")


# ==========================================
# Instagram
# ==========================================

class TestAnalyzeInstagram:
    def test_profile_url_structure(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="testuser on Instagram">
        <meta property="og:description" content="Profile description">
        <meta property="og:image" content="https://example.com/profile.jpg">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_instagram("https://www.instagram.com/testuser/")
        assert result["type"] == "profile"
        assert result["username"] == "testuser"
        assert result["title"] == "testuser on Instagram"
        assert result["description"] == "Profile description"

    def test_post_url_structure(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="Post Title">
        <meta property="og:description" content="Post description here">
        <meta property="og:image" content="https://example.com/post.jpg">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_instagram("https://www.instagram.com/p/ABC123/")
        assert result["type"] == "post"
        assert result["username"] == "p"
        assert len(result["posts"]) == 1
        assert result["posts"][0]["text"] == "Post description here"

    def test_reel_url_structure(self, analyzer):
        html = "<html><head></head><body></body></html>"
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_instagram("https://www.instagram.com/reel/XYZ999/")
        assert result["type"] == "post"
        assert "Reel" in result["title"]

    def test_fetch_failure_returns_fallback(self, analyzer):
        analyzer._session.get = MagicMock(side_effect=Exception("Connection error"))
        result = analyzer._analyze_instagram("https://www.instagram.com/failuser/")
        assert result["type"] == "profile"
        assert "Instagram이 비로그인 요청을 제한" in result["description"]
        assert len(result["posts"]) == 1
        assert result["posts"][0]["text"] == "원문에서 확인"

    def test_og_title_updates_username(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="John Doe on Instagram">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_instagram("https://www.instagram.com/johndoe/")
        assert result["username"] == "John Doe"

    def test_profile_with_no_meta(self, analyzer):
        html = "<html><head></head><body></body></html>"
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_instagram("https://www.instagram.com/nocontentuser/")
        assert result["type"] == "profile"
        assert result["description"] == "Instagram URL 분석은 og:meta/oEmbed로 제한됩니다. 댓글 수집은 공식 API가 필요합니다."

    def test_unknown_path_username(self, analyzer):
        html = "<html><head></head><body></body></html>"
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_instagram("https://www.instagram.com/")
        assert result["username"] == "unknown"

    def test_post_oembed_fallback_success(self, analyzer):
        """oEmbed fallback when og meta found but no description."""
        # First call (og:meta): no description
        html_no_desc = """<html><head>
        <meta property="og:title" content="Some Post">
        </head><body></body></html>"""
        # oEmbed response
        oembed_data = {
            "title": "oEmbed Title",
            "author_name": "oembed_user",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "html": "<blockquote>Post content</blockquote>",
        }
        og_resp = _make_resp(text=html_no_desc)
        oembed_resp = _make_resp(json_data=oembed_data)
        oembed_resp.ok = True

        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if "oembed" in url or "api.instagram" in url:
                return oembed_resp
            return og_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._analyze_instagram("https://www.instagram.com/p/TESTPOST/")
        assert result["type"] == "post"

    def test_post_oembed_fallback_exception(self, analyzer):
        """oEmbed fallback exception is silently ignored."""
        html_no_desc = """<html><head>
        <meta property="og:title" content="Some Post">
        </head><body></body></html>"""

        og_resp = _make_resp(text=html_no_desc)

        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if "oembed" in url or "api.instagram" in url:
                raise Exception("oEmbed timeout")
            return og_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._analyze_instagram("https://www.instagram.com/p/FAILPOST/")
        assert result["type"] == "post"


# ==========================================
# Facebook
# ==========================================

class TestAnalyzeFacebook:
    def test_facebook_returns_placeholder(self, analyzer):
        result = analyzer._analyze_facebook("https://www.facebook.com/somepage/")
        assert result["type"] == "profile"
        assert result["username"] == "somepage"
        assert "준비 중" in result["description"]

    def test_facebook_empty_path(self, analyzer):
        result = analyzer._analyze_facebook("https://www.facebook.com/")
        assert result["type"] == "profile"
        assert result["username"] == "unknown"


# ==========================================
# TikTok
# ==========================================

class TestAnalyzeTikTok:
    def test_profile_url_oembed_success(self, analyzer):
        oembed_data = {
            "title": "TikTok Profile",
            "author_name": "creator123",
            "html": "<blockquote>embed</blockquote>",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "author_url": "https://tiktok.com/@creator123",
        }
        resp = _make_resp(json_data=oembed_data)
        resp.ok = True
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_tiktok("https://www.tiktok.com/@creator123")
        assert result["type"] == "profile"
        assert result["title"] == "TikTok Profile"
        assert result["description"] == "TikTok @creator123"

    def test_video_url_oembed_success(self, analyzer):
        oembed_data = {
            "title": "Funny Video",
            "author_name": "funnyuser",
            "html": "<embed>...</embed>",
            "thumbnail_url": "https://example.com/vid.jpg",
            "author_url": "https://tiktok.com/@funnyuser",
        }
        resp = _make_resp(json_data=oembed_data)
        resp.ok = True
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_tiktok(
            "https://www.tiktok.com/@funnyuser/video/12345678901234"
        )
        assert result["type"] == "video"
        assert result["title"] == "Funny Video"

    def test_oembed_failure_falls_back_to_og_meta(self, analyzer):
        html = (
            '<meta property="og:title" content="OG Title"> '
            '<meta property="og:description" content="OG Desc"> '
            '<meta property="og:image" content="https://example.com/img.jpg">'
        )
        oembed_resp = _make_resp(ok=False, status_code=403)
        og_resp = _make_resp(ok=True, text=html)

        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if "oembed" in url:
                return oembed_resp
            return og_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._analyze_tiktok("https://www.tiktok.com/@user/video/99999999999999")
        assert result["type"] == "video"
        assert result["title"] == "OG Title"
        assert result["description"] == "OG Desc"
        assert result["thumbnail"] == "https://example.com/img.jpg"

    def test_oembed_exception_og_meta_fallback(self, analyzer):
        html = '<meta property="og:title" content="Fallback Title">'
        og_resp = _make_resp(ok=True, text=html)

        def side_effect(url, **kwargs):
            if "oembed" in url:
                raise Exception("network error")
            return og_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._analyze_tiktok("https://www.tiktok.com/@user2")
        assert result["title"] == "Fallback Title"

    def test_both_fail_returns_default_description_profile(self, analyzer):
        def side_effect(url, **kwargs):
            raise Exception("all fail")

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._analyze_tiktok("https://www.tiktok.com/@someuser")
        assert "프로필" in result["description"]

    def test_both_fail_returns_default_description_video(self, analyzer):
        def side_effect(url, **kwargs):
            raise Exception("all fail")

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._analyze_tiktok(
            "https://www.tiktok.com/@someuser/video/11111111111111"
        )
        assert "동영상" in result["description"]

    def test_oembed_ok_false_triggers_fallback(self, analyzer):
        oembed_resp = _make_resp(ok=False, status_code=404)
        og_html = '<meta property="og:description" content="fallback desc">'
        og_resp = _make_resp(ok=True, text=og_html)

        def side_effect(url, **kwargs):
            if "oembed" in url:
                return oembed_resp
            return og_resp

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._analyze_tiktok("https://www.tiktok.com/@creator/video/22222222222222")
        assert result["description"] == "fallback desc"

    def test_og_meta_fallback_exception_still_returns(self, analyzer):
        def side_effect(url, **kwargs):
            if "oembed" in url:
                raise Exception("oembed fail")
            raise Exception("og fail too")

        analyzer._session.get = MagicMock(side_effect=side_effect)
        result = analyzer._analyze_tiktok("https://www.tiktok.com/@x/video/33333333333333")
        assert result["type"] == "video"
        assert "description" in result

    def test_url_stripped_of_query_params(self, analyzer):
        oembed_data = {"title": "Clean URL", "author_name": "user"}
        resp = _make_resp(json_data=oembed_data, ok=True)
        resp.ok = True
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_tiktok(
            "https://www.tiktok.com/@user?refer=embed&is_from_webapp=1"
        )
        assert "?" not in result["url"]


# ==========================================
# Vuddy
# ==========================================

class TestAnalyzeVuddy:
    def test_creator_page(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="Creator Name">
        <meta property="og:description" content="Creator bio">
        <meta property="og:image" content="https://example.com/creator.jpg">
        </head><body>
        <div class="product-card"><h3>Product A</h3></div>
        <div class="product-card"><h3>Product B</h3></div>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/creator/creator_id123")
        assert result["type"] == "creator"
        assert result["creator_id"] == "creator_id123"
        assert result["title"] == "Creator Name"
        assert result["description"] == "Creator bio"
        assert result["thumbnail"] == "https://example.com/creator.jpg"

    def test_product_page(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="Product XYZ">
        <meta property="og:description" content="A great product">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/product/999")
        assert result["type"] == "product"
        assert result["title"] == "Product XYZ"

    def test_store_page(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="Store Name">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/store/mystore")
        assert result["type"] == "store"

    def test_goods_page(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="Goods Page">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/goods/item1")
        assert result["type"] == "product"

    def test_next_data_extraction(self, analyzer):
        next_data = {
            "props": {
                "pageProps": {
                    "creator": {
                        "name": "NextJS Creator",
                        "description": "NextJS bio",
                        "profileImageUrl": "https://example.com/next.jpg",
                        "followerCount": 1000,
                    },
                    "products": [
                        {"id": "p1", "name": "Product 1", "creatorName": "Creator A"},
                        {"id": "p2", "name": "Product 2", "creatorName": "Creator A"},
                    ],
                }
            }
        }
        html = f"""<html><head></head><body>
        <script id="__NEXT_DATA__">{json.dumps(next_data)}</script>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/creator/nextcreator")
        assert result["title"] == "NextJS Creator"
        assert result["description"] == "NextJS bio"
        assert result["follower_count"] == 1000
        assert len(result["posts"]) == 2

    def test_next_data_nested_under_data(self, analyzer):
        next_data = {
            "props": {
                "pageProps": {
                    "data": {
                        "creator": {
                            "name": "Nested Creator",
                            "description": "Nested desc",
                            "profileImageUrl": "",
                        },
                        "products": [
                            {"id": "p3", "title": "Nested Product"},
                        ],
                    }
                }
            }
        }
        html = f"""<html><head></head><body>
        <script id="__NEXT_DATA__">{json.dumps(next_data)}</script>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/creator/nestedone")
        assert result["title"] == "Nested Creator"

    def test_fallback_card_extraction(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="Vuddy Shop">
        </head><body>
        <div class="product-card"><h3 class="title">Item 1</h3></div>
        <div class="product-card"><h4 class="name">Item 2</h4></div>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/")
        assert len(result["posts"]) >= 1

    def test_summary_post_from_description(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="Vuddy Page">
        <meta property="og:description" content="Some description for summary">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/unknownpath")
        # Should create summary post from description
        assert len(result["posts"]) >= 1
        assert result["posts"][0]["text"] == "Some description for summary"

    def test_fetch_exception_returns_error_description(self, analyzer):
        analyzer._session.get = MagicMock(side_effect=Exception("network error"))
        result = analyzer._analyze_vuddy("https://vuddy.io/creator/broken")
        assert result["description"] == "Vuddy 페이지를 불러오지 못했습니다."

    def test_total_posts_count(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="Multi Product Page">
        <meta property="og:description" content="desc">
        </head><body>
        <div class="item"><h3>P1</h3></div>
        <div class="item"><h3>P2</h3></div>
        <div class="item"><h3>P3</h3></div>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/products")
        assert result["total_posts"] == len(result["posts"])

    def test_creator_page_without_creator_id(self, analyzer):
        """Creator path without second segment."""
        html = """<html><head>
        <meta property="og:title" content="Creators List">
        </head><body></body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/creator")
        assert result["type"] == "creator"
        assert "creator_id" not in result

    def test_next_data_invalid_json_skipped(self, analyzer):
        html = """<html><head>
        <meta property="og:title" content="Bad JSON">
        </head><body>
        <script id="__NEXT_DATA__">INVALID JSON HERE</script>
        </body></html>"""
        resp = _make_resp(text=html)
        analyzer._session.get = MagicMock(return_value=resp)
        result = analyzer._analyze_vuddy("https://vuddy.io/creator/test")
        assert result["title"] == "Bad JSON"
