"""Tests for PlatformAnalyzer: detect_platform, _analyze_sentiment, analyze, list_platforms."""

import pytest
from unittest.mock import patch, MagicMock
from app.services.platform_analyzer import PlatformAnalyzer


@pytest.fixture
def analyzer():
    with patch.dict('os.environ', {'DISABLE_SSL_VERIFY': 'false'}):
        return PlatformAnalyzer(data_dir='/tmp/test-data')


class TestDetectPlatform:
    """Tests for detect_platform across all supported platforms."""

    def test_youtube_watch(self, analyzer):
        assert analyzer.detect_platform('https://www.youtube.com/watch?v=abc123') == 'youtube'

    def test_youtube_short(self, analyzer):
        assert analyzer.detect_platform('https://youtu.be/abc123') == 'youtube'

    def test_youtube_channel(self, analyzer):
        assert analyzer.detect_platform('https://www.youtube.com/@channel') == 'youtube'

    def test_dcinside(self, analyzer):
        assert analyzer.detect_platform('https://gall.dcinside.com/board/lists?id=test') == 'dcinside'

    def test_reddit_subreddit(self, analyzer):
        assert analyzer.detect_platform('https://www.reddit.com/r/python') == 'reddit'

    def test_reddit_old(self, analyzer):
        assert analyzer.detect_platform('https://old.reddit.com/r/python') == 'reddit'

    def test_telegram(self, analyzer):
        assert analyzer.detect_platform('https://t.me/channel_name') == 'telegram'

    def test_kakao_open(self, analyzer):
        assert analyzer.detect_platform('https://open.kakao.com/o/test') == 'kakao'

    def test_kakao_pf(self, analyzer):
        assert analyzer.detect_platform('https://pf.kakao.com/test') == 'kakao'

    def test_twitter(self, analyzer):
        assert analyzer.detect_platform('https://twitter.com/user/status/123') == 'twitter'

    def test_x_com(self, analyzer):
        assert analyzer.detect_platform('https://x.com/user/status/123') == 'twitter'

    def test_naver_cafe(self, analyzer):
        assert analyzer.detect_platform('https://cafe.naver.com/mycafe') == 'naver_cafe'

    def test_instagram(self, analyzer):
        assert analyzer.detect_platform('https://www.instagram.com/p/abc123') == 'instagram'

    def test_facebook(self, analyzer):
        assert analyzer.detect_platform('https://www.facebook.com/page') == 'facebook'

    def test_threads(self, analyzer):
        assert analyzer.detect_platform('https://www.threads.net/@user/post/abc') == 'threads'

    def test_tiktok(self, analyzer):
        assert analyzer.detect_platform('https://www.tiktok.com/@user/video/123') == 'tiktok'

    def test_unknown_platform(self, analyzer):
        assert analyzer.detect_platform('https://unknown-site.com/page') is None

    def test_empty_url(self, analyzer):
        assert analyzer.detect_platform('') is None


class TestAnalyzeSentiment:
    """Tests for _analyze_sentiment."""

    def test_empty_items(self, analyzer):
        result = analyzer._analyze_sentiment([])
        assert result['total'] == 0
        assert result['sentiment']['positive'] == 0
        assert result['sentiment']['neutral'] == 0
        assert result['sentiment']['negative'] == 0

    def test_positive_items(self, analyzer):
        items = [
            {'text': '정말 좋아요 최고 대박'},
            {'text': '너무 좋다 감사합니다 응원합니다'},
            {'text': '최고의 영상이네요 축하합니다'},
        ]
        result = analyzer._analyze_sentiment(items)
        assert result['total'] == 3
        assert result['sentiment']['positive'] >= 2
        assert result['overall'] == 'positive'

    def test_negative_items(self, analyzer):
        items = [
            {'text': '최악 싫어요 별로'},
            {'text': '짜증나 실망이다 나쁜'},
            {'text': '진짜 쓰레기 같은 영상'},
        ]
        result = analyzer._analyze_sentiment(items)
        assert result['total'] == 3
        assert result['sentiment']['negative'] >= 1

    def test_neutral_items(self, analyzer):
        items = [
            {'text': '오늘 날씨가 좋네요'},
            {'text': '이것은 일반적인 텍스트입니다'},
        ]
        result = analyzer._analyze_sentiment(items)
        assert result['total'] == 2

    def test_short_text_skipped(self, analyzer):
        items = [{'text': 'a'}]
        result = analyzer._analyze_sentiment(items)
        assert result['total'] == 0

    def test_none_text(self, analyzer):
        items = [{'text': None}]
        result = analyzer._analyze_sentiment(items)
        assert result['total'] == 0

    def test_keywords_extracted(self, analyzer):
        items = [
            {'text': '파이썬 프로그래밍 파이썬 개발 파이썬 최고'},
        ]
        result = analyzer._analyze_sentiment(items)
        assert 'top_keywords' in result

    def test_distribution_sums_to_one(self, analyzer):
        items = [
            {'text': '좋아요 최고'},
            {'text': '싫어요 별로'},
            {'text': '그냥 보통이에요'},
        ]
        result = analyzer._analyze_sentiment(items)
        if result['total'] > 0:
            dist = result['distribution']
            total = dist['positive'] + dist['neutral'] + dist['negative']
            assert abs(total - 1.0) < 0.01


class TestAnalyze:
    """Tests for analyze() main entry point."""

    @patch.object(PlatformAnalyzer, '_analyze_youtube')
    @patch.object(PlatformAnalyzer, '_save_result')
    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_youtube_analysis(self, mock_validate, mock_save, mock_yt, analyzer):
        mock_yt.return_value = {'title': 'Test Video', 'comments': []}
        result = analyzer.analyze('https://www.youtube.com/watch?v=test123')
        assert result['platform'] == 'youtube'
        assert result['title'] == 'Test Video'
        assert 'analyzed_at' in result
        mock_save.assert_called_once()

    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_unsupported_platform_raises(self, mock_validate, analyzer):
        with pytest.raises(ValueError, match="Unsupported platform"):
            analyzer.analyze('https://unknown-site.com/page')

    @patch.object(PlatformAnalyzer, '_analyze_dcinside')
    @patch.object(PlatformAnalyzer, '_save_result')
    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_dcinside_analysis(self, mock_validate, mock_save, mock_dc, analyzer):
        mock_dc.return_value = {'gallery_id': 'test', 'posts': [{'text': '좋아요'}]}
        result = analyzer.analyze('https://gall.dcinside.com/board/lists?id=test')
        assert result['platform'] == 'dcinside'

    @patch.object(PlatformAnalyzer, '_analyze_reddit')
    @patch.object(PlatformAnalyzer, '_save_result')
    @patch.object(PlatformAnalyzer, '_validate_url_host')
    def test_reddit_analysis(self, mock_validate, mock_save, mock_reddit, analyzer):
        mock_reddit.return_value = {'subreddit': 'python', 'comments': []}
        result = analyzer.analyze('https://www.reddit.com/r/python')
        assert result['platform'] == 'reddit'


class TestCollectSentimentItems:
    """Tests for _collect_sentiment_items."""

    def test_youtube_with_comments(self, analyzer):
        result = {'comments': [{'text': 'great'}]}
        items = analyzer._collect_sentiment_items('youtube', result)
        assert len(items) == 1
        assert items[0]['text'] == 'great'

    def test_dcinside_post_with_content_and_comments(self, analyzer):
        result = {
            'type': 'post',
            'content': 'Post body text',
            'comments': [{'text': 'comment1'}],
        }
        items = analyzer._collect_sentiment_items('dcinside', result)
        assert len(items) == 2
        assert items[0]['text'] == 'Post body text'

    def test_dcinside_gallery_with_posts(self, analyzer):
        result = {
            'type': 'gallery',
            'posts': [
                {'text': 'post1', 'comments': [{'text': 'c1'}]},
                {'text': 'post2', 'comments': []},
            ],
        }
        items = analyzer._collect_sentiment_items('dcinside', result)
        assert len(items) == 3  # post1 + c1 + post2

    def test_naver_cafe_gallery(self, analyzer):
        result = {
            'type': 'gallery',
            'posts': [{'text': 'cafe post', 'comments': [{'text': 'reply'}]}],
        }
        items = analyzer._collect_sentiment_items('naver_cafe', result)
        assert len(items) == 2

    def test_threads_post(self, analyzer):
        result = {
            'type': 'post',
            'content': 'Thread content',
            'replies': [{'text': 'reply1'}],
        }
        items = analyzer._collect_sentiment_items('threads', result)
        assert len(items) == 2

    def test_empty_result(self, analyzer):
        items = analyzer._collect_sentiment_items('youtube', {})
        assert items == []

    def test_replies_fallback(self, analyzer):
        result = {'replies': [{'text': 'r1'}, {'text': 'r2'}]}
        items = analyzer._collect_sentiment_items('twitter', result)
        assert len(items) == 2


class TestRateLimiting:
    """Tests for rate limiting helpers."""

    def test_rate_get_returns_zero_initially(self, analyzer):
        count = analyzer._rate_get('youtube')
        assert count == 0

    def test_rate_incr_and_get(self, analyzer):
        analyzer._rate_incr('youtube')
        analyzer._rate_incr('youtube')
        count = analyzer._rate_get('youtube')
        assert count == 2

    def test_rate_check_allowed(self, analyzer):
        allowed, count, limit = analyzer._rate_check('youtube')
        assert allowed is True
        assert count == 0
        assert limit == 10000

    def test_rate_window_daily(self, analyzer):
        window = analyzer._rate_window('youtube')
        assert len(window) == 10  # YYYY-MM-DD

    def test_rate_window_10min(self, analyzer):
        window = analyzer._rate_window('reddit')
        assert 'T' in window


class TestExtractKeywords:
    """Tests for _extract_keywords."""

    def test_extract_from_korean(self, analyzer):
        words = analyzer._extract_keywords('파이썬 프로그래밍은 재미있다')
        assert isinstance(words, list)

    def test_extract_from_empty(self, analyzer):
        words = analyzer._extract_keywords('')
        assert isinstance(words, list)
        assert len(words) == 0


class TestListPlatforms:
    """Tests for list_platforms and get_api_usage."""

    def test_list_platforms_returns_list(self, analyzer):
        platforms = analyzer.list_platforms()
        assert isinstance(platforms, list)
        assert len(platforms) >= 6
        names = [p['id'] for p in platforms]
        assert 'youtube' in names
        assert 'dcinside' in names
        assert 'reddit' in names
        assert 'telegram' in names
        assert 'twitter' in names
        assert 'naver_cafe' in names
        assert 'tiktok' in names

    def test_list_platforms_has_examples(self, analyzer):
        platforms = analyzer.list_platforms()
        for p in platforms:
            assert 'examples' in p
            assert 'description' in p
            assert len(p['examples']) >= 1

    def test_get_api_usage(self, analyzer):
        usage = analyzer.get_api_usage()
        assert isinstance(usage, dict)
        assert 'youtube' in usage or 'naver_search' in usage

    def test_get_api_usage_structure(self, analyzer):
        usage = analyzer.get_api_usage()
        for service, info in usage.items():
            assert 'daily_limit' in info or 'remaining' in info
