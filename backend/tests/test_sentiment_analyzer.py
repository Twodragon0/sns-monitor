"""Unit tests for SentimentAnalyzer (backend/app/services/sentiment_analyzer.py)."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from app.services.sentiment_analyzer import SentimentAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_items(*texts):
    """Build a list of item dicts from plain text strings."""
    return [{"text": t} for t in texts]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_kiwi_singleton():
    """Reset the class-level _kiwi singleton before every test."""
    original = SentimentAnalyzer._kiwi
    SentimentAnalyzer._kiwi = None
    yield
    SentimentAnalyzer._kiwi = original


@pytest.fixture()
def analyzer():
    return SentimentAnalyzer()


# ---------------------------------------------------------------------------
# analyze() – basic contracts
# ---------------------------------------------------------------------------

class TestAnalyzeEmptyInput:
    def test_empty_list_returns_total_zero(self, analyzer):
        result = analyzer.analyze([])
        assert result["total"] == 0

    def test_empty_list_returns_zero_sentiment_counts(self, analyzer):
        result = analyzer.analyze([])
        assert result["sentiment"] == {"positive": 0, "neutral": 0, "negative": 0}

    def test_empty_list_has_no_distribution_key(self, analyzer):
        """analyze([]) returns the minimal dict without distribution/keywords."""
        result = analyzer.analyze([])
        assert "distribution" not in result
        assert "top_keywords" not in result

    def test_items_with_empty_text_are_skipped(self, analyzer):
        # "" and None are filtered (falsy); "  " has len==2 so passes the guard
        # and is counted as neutral with zero keyword scores.
        result = analyzer.analyze([{"text": ""}, {"text": None}])
        assert result["total"] == 0

    def test_whitespace_only_text_counts_as_neutral(self, analyzer):
        # "  " survives the len<2 guard (len==2) and lands in neutral
        result = analyzer.analyze([{"text": "  "}])
        assert result["total"] == 1
        assert result["sentiment"]["neutral"] == 1

    def test_items_with_short_text_are_skipped(self, analyzer):
        result = analyzer.analyze([{"text": "a"}])
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# analyze() – sentiment classification
# ---------------------------------------------------------------------------

class TestAnalyzeSentimentClassification:
    def test_positive_items(self, analyzer):
        items = _make_items("정말 좋아요 최고", "good great amazing best")
        result = analyzer.analyze(items)
        assert result["sentiment"]["positive"] >= 1
        assert result["overall"] == "positive"

    def test_negative_items(self, analyzer):
        items = _make_items("진짜 싫어요 최악", "bad worst hate terrible")
        result = analyzer.analyze(items)
        assert result["sentiment"]["negative"] >= 1
        assert result["overall"] == "negative"

    def test_neutral_items(self, analyzer):
        items = _make_items("오늘 날씨가 맑습니다", "the weather today is cloudy")
        result = analyzer.analyze(items)
        assert result["overall"] == "neutral"

    def test_mixed_sentiment_single_item(self, analyzer):
        """One item with equal positive and negative scores → neutral."""
        items = _make_items("좋아요 싫어요")
        result = analyzer.analyze(items)
        # equal scores → neutral bucket
        assert result["sentiment"]["neutral"] >= 1

    def test_mixed_positive_and_negative_items(self, analyzer):
        items = _make_items("좋아요 최고", "싫어요 최악", "그냥 보통")
        result = analyzer.analyze(items)
        assert result["total"] == 3
        assert sum(result["sentiment"].values()) == 3

    def test_overall_equals_dominant_bucket(self, analyzer):
        items = _make_items("좋아요", "최고", "좋다", "싫어")
        result = analyzer.analyze(items)
        dominant = max(result["sentiment"], key=lambda k: result["sentiment"][k])
        assert result["overall"] == dominant

    def test_distribution_sums_to_one(self, analyzer):
        items = _make_items("좋아요", "싫어요", "보통이야")
        result = analyzer.analyze(items)
        total = sum(result["distribution"].values())
        assert abs(total - 1.0) < 0.01

    def test_distribution_keys_present(self, analyzer):
        items = _make_items("좋아요")
        result = analyzer.analyze(items)
        assert set(result["distribution"].keys()) == {"positive", "neutral", "negative"}

    def test_top_keywords_in_result(self, analyzer):
        items = _make_items("좋아요 좋아요 좋아요")
        result = analyzer.analyze(items)
        assert "top_keywords" in result
        assert isinstance(result["top_keywords"], list)

    def test_top_keywords_max_20(self, analyzer):
        # 25 unique words – result must not exceed 20 entries
        text = " ".join([f"단어{i}단어" for i in range(25)])
        result = analyzer.analyze([{"text": text}])
        assert len(result["top_keywords"]) <= 20

    def test_top_keywords_have_word_and_count(self, analyzer):
        items = _make_items("안녕하세요 안녕하세요")
        result = analyzer.analyze(items)
        if result["top_keywords"]:
            kw = result["top_keywords"][0]
            assert "word" in kw
            assert "count" in kw

    def test_stopwords_excluded_from_keywords(self, analyzer):
        items = _make_items("갤러리 답글 댓글")
        result = analyzer.analyze(items)
        words = [kw["word"] for kw in result["top_keywords"]]
        for sw in ("갤러리", "답글", "댓글"):
            assert sw not in words

    def test_items_missing_text_key_are_skipped(self, analyzer):
        items = [{"score": 5}, {"score": 3}]
        result = analyzer.analyze(items)
        assert result["total"] == 0

    def test_total_matches_classified_items(self, analyzer):
        items = _make_items("좋아요", "싫어요", "오늘 날씨 보통이야")
        result = analyzer.analyze(items)
        assert result["total"] == sum(result["sentiment"].values())

    def test_community_slang_positive(self, analyzer):
        items = _make_items("개추 꿀잼 레전드")
        result = analyzer.analyze(items)
        assert result["sentiment"]["positive"] >= 1

    def test_community_slang_negative(self, analyzer):
        items = _make_items("비추 노잼 쓰레기")
        result = analyzer.analyze(items)
        assert result["sentiment"]["negative"] >= 1

    def test_english_positive(self, analyzer):
        items = _make_items("awesome cool wonderful excellent")
        result = analyzer.analyze(items)
        assert result["overall"] == "positive"

    def test_english_negative(self, analyzer):
        items = _make_items("terrible awful boring ugly")
        result = analyzer.analyze(items)
        assert result["overall"] == "negative"


# ---------------------------------------------------------------------------
# _extract_keywords()
# ---------------------------------------------------------------------------

class TestExtractKeywords:
    def test_regex_fallback_extracts_korean(self, analyzer):
        """With no Kiwi available the regex path returns Korean words."""
        SentimentAnalyzer._kiwi = False
        words = analyzer._extract_keywords("안녕하세요 오늘 날씨")
        assert isinstance(words, list)
        # regex: [가-힣]{2,}
        assert all(isinstance(w, str) for w in words)

    def test_regex_fallback_extracts_english(self, analyzer):
        SentimentAnalyzer._kiwi = False
        words = analyzer._extract_keywords("hello world foo bar")
        assert "hello" in words
        assert "world" in words

    def test_regex_fallback_ignores_short_english(self, analyzer):
        SentimentAnalyzer._kiwi = False
        words = analyzer._extract_keywords("hi ok go test")
        # only [a-zA-Z]{3,} -> "test" passes, "hi"/"ok"/"go" don't
        assert "hi" not in words
        assert "test" in words

    def test_regex_fallback_empty_text(self, analyzer):
        SentimentAnalyzer._kiwi = False
        words = analyzer._extract_keywords("")
        assert words == []

    def test_kiwi_tokenize_exception_falls_back_to_regex(self, analyzer):
        """Cover lines 143-146: Kiwi tokenize raises → regex fallback."""
        mock_kiwi = MagicMock()
        mock_kiwi.tokenize.side_effect = RuntimeError("tokenize error")
        SentimentAnalyzer._kiwi = mock_kiwi
        # Should not raise; returns regex results
        words = analyzer._extract_keywords("안녕하세요 hello world")
        assert isinstance(words, list)

    def test_kiwi_tokenize_exception_returns_regex_results(self, analyzer):
        """After Kiwi failure the regex fallback still extracts tokens."""
        mock_kiwi = MagicMock()
        mock_kiwi.tokenize.side_effect = ValueError("bad input")
        SentimentAnalyzer._kiwi = mock_kiwi
        words = analyzer._extract_keywords("good morning")
        assert "good" in words
        assert "morning" in words

    def test_with_mock_kiwi_filters_pos_tags(self, analyzer):
        """Kiwi path: only tokens with POS in _KEYWORD_POS and len >= 2 kept."""
        token_nng = MagicMock()
        token_nng.form = "스트리머"
        token_nng.tag = "NNG"
        token_jx = MagicMock()
        token_jx.form = "에서"
        token_jx.tag = "JX"  # not in _KEYWORD_POS
        mock_kiwi = MagicMock()
        mock_kiwi.tokenize.return_value = [token_nng, token_jx]
        SentimentAnalyzer._kiwi = mock_kiwi
        words = analyzer._extract_keywords("스트리머에서")
        assert "스트리머" in words
        assert "에서" not in words

    def test_kiwi_filters_short_foreign_sl_tokens(self, analyzer):
        """SL (foreign) tokens require len >= 3."""
        token_sl_short = MagicMock()
        token_sl_short.form = "ab"
        token_sl_short.tag = "SL"
        token_sl_long = MagicMock()
        token_sl_long.form = "abc"
        token_sl_long.tag = "SL"
        mock_kiwi = MagicMock()
        mock_kiwi.tokenize.return_value = [token_sl_short, token_sl_long]
        SentimentAnalyzer._kiwi = mock_kiwi
        words = analyzer._extract_keywords("abcab")
        assert "ab" not in words
        assert "abc" in words


# ---------------------------------------------------------------------------
# _get_kiwi() – lazy initialization
# ---------------------------------------------------------------------------

class TestGetKiwi:
    def test_returns_none_when_kiwipiepy_unavailable(self, analyzer):
        """Cover lines 129-131: ImportError path sets _kiwi = False, returns None."""
        with patch.dict(sys.modules, {"kiwipiepy": None}):
            with patch("builtins.__import__", side_effect=_import_raise_for_kiwi):
                result = SentimentAnalyzer._get_kiwi()
        assert result is None
        assert SentimentAnalyzer._kiwi is False

    def test_returns_cached_false_as_none_on_second_call(self):
        """Once _kiwi is False subsequent calls return None without re-importing."""
        SentimentAnalyzer._kiwi = False
        result = SentimentAnalyzer._get_kiwi()
        assert result is None

    def test_returns_existing_kiwi_instance(self):
        """If _kiwi is already set it is returned directly."""
        mock_kiwi = MagicMock()
        SentimentAnalyzer._kiwi = mock_kiwi
        result = SentimentAnalyzer._get_kiwi()
        assert result is mock_kiwi

    def test_add_user_word_failure_is_logged_not_raised(self):
        """Cover lines 125-126: add_user_word exception is caught and logged."""
        mock_kiwi_instance = MagicMock()
        mock_kiwi_instance.add_user_word.side_effect = Exception("word add error")
        mock_kiwi_class = MagicMock(return_value=mock_kiwi_instance)
        mock_module = MagicMock()
        mock_module.Kiwi = mock_kiwi_class

        with patch.dict(sys.modules, {"kiwipiepy": mock_module}):
            with patch("app.services.sentiment_analyzer.logger") as mock_logger:
                result = SentimentAnalyzer._get_kiwi()

        # Should succeed and store the kiwi instance despite add_user_word failures
        assert result is mock_kiwi_instance
        assert SentimentAnalyzer._kiwi is mock_kiwi_instance
        # debug was called for each word that failed
        assert mock_logger.debug.called

    def test_kiwi_loads_successfully_and_is_cached(self):
        """Happy path: Kiwi instantiated and cached as class singleton."""
        mock_kiwi_instance = MagicMock()
        mock_kiwi_class = MagicMock(return_value=mock_kiwi_instance)
        mock_module = MagicMock()
        mock_module.Kiwi = mock_kiwi_class

        with patch.dict(sys.modules, {"kiwipiepy": mock_module}):
            result = SentimentAnalyzer._get_kiwi()

        assert result is mock_kiwi_instance
        assert SentimentAnalyzer._kiwi is mock_kiwi_instance


# ---------------------------------------------------------------------------
# analyze() – Kiwi tokenize exception in main loop (lines 193-194)
# ---------------------------------------------------------------------------

class TestAnalyzeKiwiException:
    def test_kiwi_tokenize_exception_in_analyze_does_not_raise(self, analyzer):
        """Cover lines 193-194: Kiwi tokenize error during analyze loop is swallowed."""
        mock_kiwi = MagicMock()
        mock_kiwi.tokenize.side_effect = RuntimeError("kiwi boom")
        SentimentAnalyzer._kiwi = mock_kiwi
        items = _make_items("정말 좋아요 최고야")
        result = analyzer.analyze(items)
        # The item is still processed via keyword-only scoring
        assert result["total"] >= 0

    def test_kiwi_tokenize_exception_falls_back_to_keyword_scoring(self, analyzer):
        """When Kiwi raises, keyword scoring still classifies the item."""
        mock_kiwi = MagicMock()
        mock_kiwi.tokenize.side_effect = Exception("fail")
        SentimentAnalyzer._kiwi = mock_kiwi
        items = _make_items("좋아요 최고 amazing best great")
        result = analyzer.analyze(items)
        assert result["sentiment"]["positive"] >= 1

    def test_kiwi_tokenize_exception_neutral_item_still_counted(self, analyzer):
        mock_kiwi = MagicMock()
        mock_kiwi.tokenize.side_effect = ValueError("bad")
        SentimentAnalyzer._kiwi = mock_kiwi
        items = _make_items("오늘 날씨가 맑습니다")
        result = analyzer.analyze(items)
        assert result["total"] == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_items_with_only_stopwords_produce_no_keywords(self, analyzer):
        SentimentAnalyzer._kiwi = False
        items = _make_items("갤러리 보기 다음 이전")
        result = analyzer.analyze(items)
        # stopwords filtered → no keywords in top list
        words = [kw["word"] for kw in result["top_keywords"]]
        for sw in ("갤러리", "보기", "다음", "이전"):
            assert sw not in words

    def test_large_input_total_accurate(self, analyzer):
        SentimentAnalyzer._kiwi = False
        items = _make_items(*["좋아요 최고" for _ in range(100)])
        result = analyzer.analyze(items)
        assert result["total"] == 100

    def test_single_positive_item_overall_positive(self, analyzer):
        SentimentAnalyzer._kiwi = False
        result = analyzer.analyze([{"text": "great amazing wonderful"}])
        assert result["overall"] == "positive"

    def test_text_lowercased_for_matching(self, analyzer):
        """Keywords are uppercased in input but matching is case-insensitive."""
        SentimentAnalyzer._kiwi = False
        items = [{"text": "GOOD GREAT AMAZING"}]
        result = analyzer.analyze(items)
        # .lower() applied in analyze() before keyword matching
        assert result["sentiment"]["positive"] >= 1

    def test_item_without_text_key_skipped_gracefully(self, analyzer):
        SentimentAnalyzer._kiwi = False
        items = [{"content": "some text"}, {"text": "좋아요 최고"}]
        result = analyzer.analyze(items)
        # Only the item with "text" key processed
        assert result["total"] == 1


# ---------------------------------------------------------------------------
# Helper: selective ImportError for kiwipiepy
# ---------------------------------------------------------------------------

_original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__


def _import_raise_for_kiwi(name, *args, **kwargs):
    if name == "kiwipiepy":
        raise ImportError("kiwipiepy not installed")
    return _original_import(name, *args, **kwargs)
