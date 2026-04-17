"""
Shared sentiment analysis utilities.

Extracted from api_handlers.py to be reusable by Blueprint modules.
"""

import logging

logger = logging.getLogger(__name__)

__all__ = [
    'calculate_sentiment_from_comments',
    'detect_comment_sentiment',
    'calculate_sentiment_distribution',
    'get_overall_sentiment',
    'extract_comment_sentiment',
    '_detect_reply_sentiment',
    '_calculate_sentiment_from_samples',
    '_simple_sentiment_analysis',
]


def calculate_sentiment_from_comments(comment_samples, total_comments):
    """댓글 샘플에서 감성 분석 결과 계산"""
    if not comment_samples:
        return None

    total = len(comment_samples)
    if total == 0:
        return None

    positive_count = sum(1 for c in comment_samples if c.get('sentiment') == 'positive')
    negative_count = sum(1 for c in comment_samples if c.get('sentiment') == 'negative')
    neutral_count = total - positive_count - negative_count

    if positive_count > negative_count and positive_count > neutral_count:
        sentiment = 'positive'
    elif negative_count > positive_count and negative_count > neutral_count:
        sentiment = 'negative'
    else:
        sentiment = 'neutral'

    return {
        'sentiment': sentiment,
        'sentiment_distribution': {
            'positive': round(positive_count / total, 2),
            'negative': round(negative_count / total, 2),
            'neutral': round(neutral_count / total, 2)
        },
        'summary': f"총 {total_comments}개의 댓글이 수집되었습니다. 감성 분석 결과: 긍정 {int((positive_count / total) * 100)}%, 중립 {int((neutral_count / total) * 100)}%, 부정 {int((negative_count / total) * 100)}%",
        'keywords': [],
        'trends': [],
        'insights': [],
        'overall_score': int((positive_count / total) * 100)
    }


def detect_comment_sentiment(comment_text):
    """댓글 텍스트에서 감성 분석"""
    if not comment_text:
        return 'neutral'

    text_lower = comment_text.lower()
    positive_words = ['좋', '최고', '사랑', '감사', '고마', '훌륭', '멋', '대박', '완벽', '👍', '❤', '💕', '😊', '😍']
    negative_words = ['안좋', '최악', '싫', '별로', '실망', '나쁘', '문제', '불만', '😢', '😡', '👎']

    if any(word in text_lower for word in positive_words):
        return 'positive'
    if any(word in text_lower for word in negative_words):
        return 'negative'
    return 'neutral'


def calculate_sentiment_distribution(sentiment_dist):
    """감성 분포 계산"""
    if not sentiment_dist:
        return {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}

    total_sentiment = sum(sentiment_dist.values())
    if total_sentiment == 0:
        return {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}

    return {
        'positive': round(sentiment_dist.get('positive', 0) / total_sentiment, 2),
        'negative': round(sentiment_dist.get('negative', 0) / total_sentiment, 2),
        'neutral': round(sentiment_dist.get('neutral', 0) / total_sentiment, 2)
    }


def get_overall_sentiment(sentiment_dist):
    """전체 감성 결정"""
    if not sentiment_dist:
        return 'neutral'
    return max(sentiment_dist, key=sentiment_dist.get)


def extract_comment_sentiment(comment, comment_text):
    """댓글에서 감성 분석 추출 (중첩 if 제거)"""
    sentiment = comment.get('sentiment')
    if sentiment:
        return sentiment
    return detect_comment_sentiment(comment_text)


def _detect_reply_sentiment(reply_text):
    """댓글 텍스트에서 감성 분석. detect_comment_sentiment에 위임."""
    return detect_comment_sentiment(reply_text)


def _calculate_sentiment_from_samples(comment_samples):
    """댓글 샘플에서 감성 분포 계산"""
    if not comment_samples:
        return {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'neutral', 50

    total = len(comment_samples)
    positive_count = sum(1 for c in comment_samples if c.get('sentiment') == 'positive')
    negative_count = sum(1 for c in comment_samples if c.get('sentiment') == 'negative')
    neutral_count = total - positive_count - negative_count

    if total == 0:
        return {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'neutral', 50

    sentiment_distribution = {
        'positive': round(positive_count / total, 2),
        'negative': round(negative_count / total, 2),
        'neutral': round(neutral_count / total, 2)
    }

    if positive_count > negative_count and positive_count > neutral_count:
        overall_sentiment = 'positive'
    elif negative_count > positive_count and negative_count > neutral_count:
        overall_sentiment = 'negative'
    else:
        overall_sentiment = 'neutral'

    positive_ratio = positive_count / total if total > 0 else 0
    calculated_score = int(positive_ratio * 100)

    return sentiment_distribution, overall_sentiment, calculated_score


def _simple_sentiment_analysis(items):
    """간단한 감성 분석. SentimentAnalyzer로 위임 (Kiwi 기반, 더 정확한 결과)."""
    if not items:
        return None
    from .sentiment_analyzer import SentimentAnalyzer
    return SentimentAnalyzer().analyze(items)
