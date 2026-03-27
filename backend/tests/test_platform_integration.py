"""Integration tests for platform-specific analyzers with mocked HTTP."""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from app.services.platform_analyzer import PlatformAnalyzer


@pytest.fixture
def analyzer():
    with patch.dict('os.environ', {'DISABLE_SSL_VERIFY': 'false'}):
        a = PlatformAnalyzer(data_dir='/tmp/test-data')
        a._save_result = MagicMock()  # Don't write files in tests
        return a


class TestAnalyzeTelegram:
    """Tests for _analyze_telegram."""

    def test_extracts_channel_name(self, analyzer):
        html = '''
        <div class="tgme_page">
            <div class="tgme_channel_info">
                <div class="tgme_channel_info_header_title">Test Channel</div>
                <div class="tgme_channel_info_description">A test channel</div>
                <div class="tgme_channel_info_counter"><span class="counter_value">1.2K</span> subscribers</div>
            </div>
        </div>
        <div class="tgme_widget_message_wrap">
            <div class="tgme_widget_message" data-post="testchannel/123">
                <div class="tgme_widget_message_text">Hello world message</div>
                <time datetime="2025-01-01T12:00:00+00:00"></time>
            </div>
        </div>
        '''
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer._analyze_telegram('https://t.me/testchannel')
        assert result['type'] == 'channel'
        assert result['channel_name'] == 'testchannel'

    def test_telegram_403(self, analyzer):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer._analyze_telegram('https://t.me/privatechannel')
        assert result['fetch_status'] == 'blocked'

    def test_invalid_url(self, analyzer):
        with pytest.raises(ValueError, match="Could not extract"):
            analyzer._analyze_telegram('https://t.me/')


class TestAnalyzeKakao:
    """Tests for _analyze_kakao routing."""

    def test_pf_kakao_routes_to_profile(self, analyzer):
        html = '<html><head><meta property="og:title" content="Test Profile"></head><body></body></html>'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer._analyze_kakao('https://pf.kakao.com/_testid')
        assert 'profile' in result['type']

    def test_unsupported_kakao_url(self, analyzer):
        with pytest.raises(ValueError, match="Unsupported Kakao"):
            analyzer._analyze_kakao('https://developers.kakao.com/docs')


class TestAnalyzeTwitter:
    """Tests for _analyze_twitter routing."""

    def test_routes_tweet_url(self, analyzer):
        analyzer._analyze_twitter_tweet = MagicMock(return_value={'type': 'tweet'})
        result = analyzer._analyze_twitter('https://x.com/user/status/123456')
        assert result['type'] == 'tweet'
        analyzer._analyze_twitter_tweet.assert_called_once_with('user', '123456')

    def test_routes_profile_url(self, analyzer):
        analyzer._analyze_twitter_profile = MagicMock(return_value={'type': 'profile'})
        result = analyzer._analyze_twitter('https://x.com/username')
        assert result['type'] == 'profile'
        analyzer._analyze_twitter_profile.assert_called_once_with('username')

    def test_empty_username_raises(self, analyzer):
        with pytest.raises(ValueError, match="Could not extract username"):
            analyzer._analyze_twitter('https://x.com/')


class TestAnalyzeTwitterProfile:
    """Tests for _analyze_twitter_profile."""

    def test_returns_profile_info(self, analyzer):
        # Mock FxTwitter API response
        fx_resp = MagicMock()
        fx_resp.ok = True
        fx_resp.json.return_value = {
            'name': 'Test User',
            'description': 'Bio text',
            'followers': 1000,
            'following': 200,
            'tweets': 500,
            'banner': {'url': 'http://example.com/banner.jpg'},
            'avatar': {'url': 'http://example.com/avatar.jpg'},
        }
        # Mock nitter response (fallback)
        nitter_resp = MagicMock()
        nitter_resp.ok = False

        analyzer._session.get = MagicMock(side_effect=[fx_resp, nitter_resp])

        result = analyzer._analyze_twitter_profile('testuser')
        assert result['type'] == 'profile'
        assert result['username'] == 'testuser'
        assert 'title' in result


class TestAnalyzeTiktok:
    """Tests for _analyze_tiktok."""

    def test_oembed_success(self, analyzer):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            'title': 'Funny Video',
            'author_name': 'creator',
            'html': '<iframe></iframe>',
            'thumbnail_url': 'http://example.com/thumb.jpg',
            'author_url': 'http://tiktok.com/@creator',
        }
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer._analyze_tiktok('https://www.tiktok.com/@creator/video/1234567890123')
        assert result['type'] == 'video'
        assert result['title'] == 'Funny Video'

    def test_profile_url(self, analyzer):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            'author_name': 'creator',
            'author_url': 'http://tiktok.com/@creator',
        }
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer._analyze_tiktok('https://www.tiktok.com/@creator')
        assert result['type'] == 'profile'

    def test_oembed_failure_fallback(self, analyzer):
        # oEmbed fails
        fail_resp = MagicMock()
        fail_resp.ok = False
        # Fallback og:meta scrape
        html_resp = MagicMock()
        html_resp.ok = True
        html_resp.text = '<html><head><meta property="og:title" content="TikTok Video"><meta property="og:description" content="Check it out"></head></html>'

        analyzer._session.get = MagicMock(side_effect=[fail_resp, html_resp])
        result = analyzer._analyze_tiktok('https://www.tiktok.com/@user/video/9999999999999')
        assert result['title'] == 'TikTok Video'


class TestAnalyzeKakaoProfile:
    """Tests for _analyze_kakao_profile."""

    def test_extracts_og_meta(self, analyzer):
        html = '''<html><head>
            <meta property="og:title" content="Shop Profile">
            <meta property="og:description" content="Best shop">
            <meta property="og:image" content="http://example.com/img.jpg">
        </head><body></body></html>'''
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        from urllib.parse import urlparse
        result = analyzer._analyze_kakao_profile('https://pf.kakao.com/_test', urlparse('https://pf.kakao.com/_test'))
        assert 'profile' in result['type']


class TestAnalyzeKakaoStory:
    """Tests for _analyze_kakao_story."""

    def test_extracts_og_meta(self, analyzer):
        html = '''<html><head>
            <meta property="og:title" content="Story Title">
            <meta property="og:description" content="Story desc">
        </head><body></body></html>'''
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        from urllib.parse import urlparse
        result = analyzer._analyze_kakao_story('https://story.kakao.com/user', urlparse('https://story.kakao.com/user'))
        assert 'story' in result['type']


class TestAnalyzeKakaoOpenchat:
    """Tests for _analyze_kakao_openchat."""

    def test_extracts_openchat_info(self, analyzer):
        html = '''<html><head>
            <meta property="og:title" content="Open Chat Room">
            <meta property="og:description" content="Join us">
            <meta property="og:image" content="http://example.com/chat.jpg">
        </head><body></body></html>'''
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        from urllib.parse import urlparse
        result = analyzer._analyze_kakao_openchat('https://open.kakao.com/o/test', urlparse('https://open.kakao.com/o/test'))
        assert 'open' in result['type'] or 'chat' in result['type']


class TestAnalyzeInstagram:
    """Tests for _analyze_instagram."""

    def test_profile_url(self, analyzer):
        html = '''<html><head>
            <meta property="og:title" content="@testuser on Instagram">
            <meta property="og:description" content="1000 Followers, 200 Following">
            <meta property="og:image" content="http://example.com/avatar.jpg">
        </head><body></body></html>'''
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer._analyze_instagram('https://www.instagram.com/testuser')
        assert result['type'] == 'profile'
        assert 'testuser' in result.get('username', '')

    def test_post_url(self, analyzer):
        html = '''<html><head>
            <meta property="og:title" content="Photo by Test on Instagram">
            <meta property="og:description" content="Check out this photo">
        </head><body></body></html>'''
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer._analyze_instagram('https://www.instagram.com/p/ABC123/')
        assert result['type'] == 'post'

    def test_reel_url(self, analyzer):
        html = '<html><head></head><body></body></html>'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer._analyze_instagram('https://www.instagram.com/reel/ABC123/')
        assert result['type'] == 'post'

    def test_fetch_failure(self, analyzer):
        analyzer._session.get = MagicMock(side_effect=Exception("Connection error"))
        result = analyzer._analyze_instagram('https://www.instagram.com/testuser')
        assert result['type'] == 'profile'
        assert 'Instagram' in result['description']


class TestAnalyzeFacebook:
    """Tests for _analyze_facebook."""

    def test_profile_url(self, analyzer):
        result = analyzer._analyze_facebook('https://www.facebook.com/testpage')
        assert result['type'] == 'profile'
        assert result['username'] == 'testpage'
        assert '준비 중' in result['description']

    def test_fb_watch(self, analyzer):
        result = analyzer._analyze_facebook('https://fb.watch/abc123')
        assert result['type'] == 'profile'


class TestAnalyzeThreads:
    """Tests for _analyze_threads."""

    def test_post_url_html_fallback(self, analyzer):
        html = '''<html><head>
            <meta property="og:title" content="Thread post">
            <meta property="og:description" content="Thread content here">
            <meta property="og:image" content="http://example.com/img.jpg">
        </head><body>
            <script type="application/ld+json">{"text": "Thread content here", "author": {"name": "user"}}</script>
        </body></html>'''
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        # First call for HTML scrape, second for oEmbed
        oembed_resp = MagicMock()
        oembed_resp.ok = False
        analyzer._session.get = MagicMock(side_effect=[mock_resp, oembed_resp])

        result = analyzer._analyze_threads('https://www.threads.net/@user/post/abc123')
        assert 'title' in result

    def test_profile_url(self, analyzer):
        html = '''<html><head>
            <meta property="og:title" content="@threaduser">
            <meta property="og:description" content="Bio text">
        </head><body></body></html>'''
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        oembed_resp = MagicMock()
        oembed_resp.ok = False
        analyzer._session.get = MagicMock(side_effect=[mock_resp, oembed_resp])

        result = analyzer._analyze_threads('https://www.threads.net/@threaduser')
        assert 'title' in result


class TestAnalyzeFullFlow:
    """End-to-end tests for analyze() with mocked platform methods."""

    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_telegram_full_flow(self, mock_validate, analyzer):
        html = '''
        <div class="tgme_widget_message" data-post="ch/1">
            <div class="tgme_widget_message_text">좋아요 최고!</div>
            <time datetime="2025-01-01T12:00:00+00:00"></time>
        </div>
        '''
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer.analyze('https://t.me/testchannel')
        assert result['platform'] == 'telegram'
        assert 'analyzed_at' in result

    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_tiktok_full_flow(self, mock_validate, analyzer):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            'title': 'Video',
            'author_name': 'user',
            'author_url': 'http://tiktok.com/@user',
        }
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer.analyze('https://www.tiktok.com/@user/video/1234567890123')
        assert result['platform'] == 'tiktok'
        assert 'analyzed_at' in result

    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_facebook_full_flow(self, mock_validate, analyzer):
        result = analyzer.analyze('https://www.facebook.com/testpage')
        assert result['platform'] == 'facebook'
        assert '준비 중' in result['description']

    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_instagram_full_flow(self, mock_validate, analyzer):
        html = '<html><head><meta property="og:title" content="Test IG"></head><body></body></html>'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer.analyze('https://www.instagram.com/testuser')
        assert result['platform'] == 'instagram'
        assert 'analyzed_at' in result

    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_kakao_full_flow(self, mock_validate, analyzer):
        html = '<html><head><meta property="og:title" content="Kakao Test"></head><body></body></html>'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        result = analyzer.analyze('https://pf.kakao.com/_test')
        assert result['platform'] == 'kakao'

    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_threads_profile_full_flow(self, mock_validate, analyzer):
        result = analyzer.analyze('https://www.threads.net/@testuser')
        assert result['platform'] == 'threads'
        assert result['type'] == 'profile'

    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_twitter_full_flow(self, mock_validate, analyzer):
        # Mock FxTwitter
        fx_resp = MagicMock()
        fx_resp.ok = True
        fx_resp.json.return_value = {'name': 'User', 'followers': 100}
        nitter_resp = MagicMock()
        nitter_resp.ok = False
        analyzer._session.get = MagicMock(side_effect=[fx_resp, nitter_resp])

        result = analyzer.analyze('https://x.com/testuser')
        assert result['platform'] == 'twitter'


class TestTelegramBs4ImportError:
    """other_platforms.py lines 71-75: bs4 ImportError in Telegram."""

    def test_bs4_import_error_fallback(self, analyzer):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html></html>"
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)

        with patch.dict("sys.modules", {"bs4": None}):
            result = analyzer._analyze_telegram("https://t.me/testchannel")
        assert result is not None
        assert result.get("type") == "channel"


class TestAnalyzeKakaoRouting:
    """other_platforms.py lines 97, 99: story and openchat routing."""

    def test_story_url_routes_to_story(self, analyzer):
        """line 97: story.kakao.com → _analyze_kakao_story"""
        html = '<html><head><meta property="og:title" content="My Story"></head><body></body></html>'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)
        from urllib.parse import urlparse
        url = "https://story.kakao.com/someuser"
        result = analyzer._analyze_kakao(url)
        assert result["type"] == "kakao_story"

    def test_openchat_url_routes_to_openchat(self, analyzer):
        """line 99: open.kakao.com → _analyze_kakao_openchat"""
        html = '<html><head><title>Test OpenChat</title><meta property="og:description" content="desc"></head><body></body></html>'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)
        url = "https://open.kakao.com/o/gTESTroom"
        result = analyzer._analyze_kakao(url)
        assert result["type"] == "kakao_openchat"


class TestAnalyzeKakaoStoryExtra:
    """other_platforms.py lines 159, 168-169: story thumbnail and ImportError."""

    def test_story_with_thumbnail(self, analyzer):
        """line 159: og:image sets thumbnail in story_info."""
        html = (
            '<html><head>'
            '<meta property="og:title" content="Story Title">'
            '<meta property="og:description" content="Story Desc">'
            '<meta property="og:image" content="https://img.example.com/thumb.jpg">'
            '</head><body></body></html>'
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)
        from urllib.parse import urlparse
        url = "https://story.kakao.com/someuser"
        result = analyzer._analyze_kakao_story(url, urlparse(url))
        assert result["thumbnail"] == "https://img.example.com/thumb.jpg"

    def test_story_bs4_import_error(self, analyzer):
        """lines 168-169: bs4 ImportError silently ignored."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html></html>"
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)
        with patch.dict("sys.modules", {"bs4": None}):
            from urllib.parse import urlparse
            url = "https://story.kakao.com/someuser"
            result = analyzer._analyze_kakao_story(url, urlparse(url))
        assert result is not None
        assert result["type"] == "kakao_story"


class TestAnalyzeKakaoOpenchatExtra:
    """other_platforms.py lines 195, 201, 211-212."""

    def test_openchat_with_og_type_and_member_count(self, analyzer):
        """lines 195, 201: og:type and member_count extraction."""
        html = (
            '<html><head>'
            '<title>Test OpenChat 1,234명</title>'
            '<meta property="og:description" content="채팅방">'
            '<meta property="og:type" content="website">'
            '</head><body>1,234명 members</body></html>'
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)
        from urllib.parse import urlparse
        url = "https://open.kakao.com/o/gTESTroom"
        result = analyzer._analyze_kakao_openchat(url, urlparse(url))
        assert result.get("og_type") == "website"
        assert result.get("member_count") == 1234

    def test_openchat_bs4_import_error(self, analyzer):
        """lines 211-212: bs4 ImportError silently ignored."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html></html>"
        mock_resp.raise_for_status = MagicMock()
        analyzer._session.get = MagicMock(return_value=mock_resp)
        with patch.dict("sys.modules", {"bs4": None}):
            from urllib.parse import urlparse
            url = "https://open.kakao.com/o/gTESTroom"
            result = analyzer._analyze_kakao_openchat(url, urlparse(url))
        assert result is not None
        assert result["type"] == "kakao_openchat"
