"""Tests for sentiment analysis utility functions."""

import pytest
from app.services.sentiment import (
    calculate_sentiment_from_comments,
    detect_comment_sentiment,
    calculate_sentiment_distribution,
    get_overall_sentiment,
    extract_comment_sentiment,
    _detect_reply_sentiment,
    _calculate_sentiment_from_samples,
    _simple_sentiment_analysis,
)


class TestCalculateSentimentFromComments:
    def test_empty_list_returns_none(self):
        assert calculate_sentiment_from_comments([], 0) is None

    def test_none_returns_none(self):
        assert calculate_sentiment_from_comments(None, 0) is None

    def test_positive_dominant(self):
        samples = [
            {'sentiment': 'positive'},
            {'sentiment': 'positive'},
            {'sentiment': 'positive'},
            {'sentiment': 'negative'},
        ]
        result = calculate_sentiment_from_comments(samples, 100)
        assert result is not None
        assert result['sentiment'] == 'positive'
        assert result['sentiment_distribution']['positive'] == 0.75
        assert result['sentiment_distribution']['negative'] == 0.25
        assert result['sentiment_distribution']['neutral'] == 0.0
        assert result['overall_score'] == 75

    def test_negative_dominant(self):
        samples = [
            {'sentiment': 'negative'},
            {'sentiment': 'negative'},
            {'sentiment': 'negative'},
            {'sentiment': 'positive'},
        ]
        result = calculate_sentiment_from_comments(samples, 50)
        assert result['sentiment'] == 'negative'
        assert result['overall_score'] == 25

    def test_neutral_when_tied(self):
        samples = [
            {'sentiment': 'positive'},
            {'sentiment': 'negative'},
        ]
        result = calculate_sentiment_from_comments(samples, 2)
        assert result['sentiment'] == 'neutral'

    def test_summary_contains_total_comments(self):
        samples = [{'sentiment': 'positive'}]
        result = calculate_sentiment_from_comments(samples, 999)
        assert '999' in result['summary']

    def test_returns_expected_keys(self):
        samples = [{'sentiment': 'neutral'}]
        result = calculate_sentiment_from_comments(samples, 1)
        assert 'sentiment' in result
        assert 'sentiment_distribution' in result
        assert 'summary' in result
        assert 'keywords' in result
        assert 'trends' in result
        assert 'insights' in result
        assert 'overall_score' in result

    def test_missing_sentiment_key_treated_as_neutral(self):
        samples = [{'text': 'no sentiment field'}]
        result = calculate_sentiment_from_comments(samples, 1)
        assert result['sentiment'] == 'neutral'
        assert result['sentiment_distribution']['neutral'] == 1.0


class TestDetectCommentSentiment:
    def test_empty_string_returns_neutral(self):
        assert detect_comment_sentiment('') == 'neutral'

    def test_none_returns_neutral(self):
        assert detect_comment_sentiment(None) == 'neutral'

    def test_positive_korean_word(self):
        assert detect_comment_sentiment('정말 좋아요') == 'positive'

    def test_positive_emoji(self):
        assert detect_comment_sentiment('너무 좋다 👍') == 'positive'

    def test_negative_korean_word(self):
        assert detect_comment_sentiment('최악이에요') == 'negative'

    def test_negative_emoji(self):
        assert detect_comment_sentiment('실망이야 😢') == 'negative'

    def test_neutral_text(self):
        assert detect_comment_sentiment('오늘 날씨가 맑습니다') == 'neutral'

    def test_positive_takes_priority_over_negative(self):
        # positive word checked first; if found, returns positive
        result = detect_comment_sentiment('좋아 안좋아')
        assert result == 'positive'


class TestCalculateSentimentDistribution:
    def test_empty_dict_returns_zeros(self):
        result = calculate_sentiment_distribution({})
        assert result == {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}

    def test_none_returns_zeros(self):
        result = calculate_sentiment_distribution(None)
        assert result == {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}

    def test_zero_total_returns_zeros(self):
        result = calculate_sentiment_distribution({'positive': 0, 'negative': 0, 'neutral': 0})
        assert result == {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}

    def test_normalizes_values(self):
        result = calculate_sentiment_distribution({'positive': 3, 'negative': 1, 'neutral': 0})
        assert result['positive'] == 0.75
        assert result['negative'] == 0.25
        assert result['neutral'] == 0.0

    def test_partial_keys(self):
        result = calculate_sentiment_distribution({'positive': 1})
        assert result['positive'] == 1.0
        assert result['negative'] == 0.0
        assert result['neutral'] == 0.0

    def test_sum_is_one(self):
        dist = {'positive': 10, 'negative': 5, 'neutral': 5}
        result = calculate_sentiment_distribution(dist)
        total = result['positive'] + result['negative'] + result['neutral']
        assert abs(total - 1.0) < 0.01


class TestGetOverallSentiment:
    def test_none_returns_neutral(self):
        assert get_overall_sentiment(None) == 'neutral'

    def test_empty_dict_returns_neutral(self):
        # max of empty dict raises, but function checks falsy first
        assert get_overall_sentiment({}) == 'neutral'

    def test_positive_dominant(self):
        assert get_overall_sentiment({'positive': 0.7, 'negative': 0.1, 'neutral': 0.2}) == 'positive'

    def test_negative_dominant(self):
        assert get_overall_sentiment({'positive': 0.1, 'negative': 0.8, 'neutral': 0.1}) == 'negative'

    def test_neutral_dominant(self):
        assert get_overall_sentiment({'positive': 0.1, 'negative': 0.1, 'neutral': 0.8}) == 'neutral'


class TestExtractCommentSentiment:
    def test_uses_comment_sentiment_field(self):
        comment = {'sentiment': 'positive', 'text': ''}
        assert extract_comment_sentiment(comment, '') == 'positive'

    def test_ignores_is_vtuber_field(self):
        """is_vtuber is not a sentiment value; should fall back to text detection."""
        comment = {'is_vtuber': 'negative', 'text': ''}
        assert extract_comment_sentiment(comment, '') == 'neutral'

    def test_falls_back_to_text_detection(self):
        comment = {}
        assert extract_comment_sentiment(comment, '최고야') == 'positive'

    def test_falls_back_to_neutral_when_no_signal(self):
        comment = {}
        assert extract_comment_sentiment(comment, '그냥 평범한 텍스트') == 'neutral'


class TestDetectReplySentiment:
    def test_positive_word(self):
        assert _detect_reply_sentiment('정말 좋은 방송이었어요') == 'positive'

    def test_negative_word(self):
        assert _detect_reply_sentiment('완전 최악') == 'negative'

    def test_neutral_text(self):
        assert _detect_reply_sentiment('안녕하세요') == 'neutral'

    def test_emoji_positive(self):
        assert _detect_reply_sentiment('😊') == 'positive'

    def test_emoji_negative(self):
        assert _detect_reply_sentiment('😡') == 'negative'


class TestCalculateSentimentFromSamples:
    def test_empty_returns_defaults(self):
        dist, sentiment, score = _calculate_sentiment_from_samples([])
        assert dist == {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}
        assert sentiment == 'neutral'
        assert score == 50

    def test_none_returns_defaults(self):
        dist, sentiment, score = _calculate_sentiment_from_samples(None)
        assert sentiment == 'neutral'
        assert score == 50

    def test_positive_dominant(self):
        samples = [
            {'sentiment': 'positive'},
            {'sentiment': 'positive'},
            {'sentiment': 'negative'},
        ]
        dist, sentiment, score = _calculate_sentiment_from_samples(samples)
        assert sentiment == 'positive'
        assert dist['positive'] == round(2 / 3, 2)
        assert score == 66

    def test_negative_dominant(self):
        samples = [{'sentiment': 'negative'}, {'sentiment': 'negative'}]
        dist, sentiment, score = _calculate_sentiment_from_samples(samples)
        assert sentiment == 'negative'
        assert score == 0

    def test_neutral_when_tied(self):
        samples = [{'sentiment': 'positive'}, {'sentiment': 'negative'}]
        _, sentiment, _ = _calculate_sentiment_from_samples(samples)
        assert sentiment == 'neutral'

    def test_missing_sentiment_counts_as_neutral(self):
        samples = [{'text': 'no sentiment'}]
        dist, sentiment, score = _calculate_sentiment_from_samples(samples)
        assert dist['neutral'] == 1.0
        assert sentiment == 'neutral'
        assert score == 0


class TestSimpleSentimentAnalysis:
    def test_empty_list_returns_none(self):
        assert _simple_sentiment_analysis([]) is None

    def test_positive_items(self):
        items = [
            {'text': '정말 좋아요 great amazing'},
            {'text': '최고입니다 best'},
        ]
        result = _simple_sentiment_analysis(items)
        assert result is not None
        assert result['total'] == 2
        assert result['sentiment']['positive'] >= 1
        assert result['overall'] == 'positive'

    def test_negative_items(self):
        items = [
            {'text': '정말 싫어요 hate terrible'},
            {'text': '최악입니다 worst'},
        ]
        result = _simple_sentiment_analysis(items)
        assert result['sentiment']['negative'] >= 1
        assert result['overall'] == 'negative'

    def test_neutral_items(self):
        items = [{'text': 'ordinary text here'}]
        result = _simple_sentiment_analysis(items)
        assert result['overall'] == 'neutral'

    def test_returns_expected_keys(self):
        items = [{'text': '좋아요'}]
        result = _simple_sentiment_analysis(items)
        assert 'total' in result
        assert 'sentiment' in result
        assert 'overall' in result
        assert 'top_keywords' in result

    def test_keywords_extracted(self):
        items = [
            {'text': 'hello world hello'},
            {'text': 'hello there'},
        ]
        result = _simple_sentiment_analysis(items)
        words = [kw['word'] for kw in result['top_keywords']]
        assert 'hello' in words

    def test_mixed_positive_negative_item_not_double_counted(self):
        items = [{'text': '좋아요 싫어요'}]
        result = _simple_sentiment_analysis(items)
        # both words present: neither pos nor neg incremented
        assert result['sentiment']['positive'] == 0
        assert result['sentiment']['negative'] == 0

    def test_top_keywords_max_15(self):
        items = [{'text': ' '.join([f'word{i}' for i in range(50)])}]
        result = _simple_sentiment_analysis(items)
        assert len(result['top_keywords']) <= 15
