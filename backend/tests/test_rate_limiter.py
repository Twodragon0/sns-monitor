"""Unit tests for RateLimiterService (backend/app/services/rate_limiter.py)."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.rate_limiter import RateLimiterService, KST


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def svc():
    """RateLimiterService with no Redis (in-memory mode)."""
    return RateLimiterService()


@pytest.fixture()
def mock_redis():
    """Reusable mock Redis client."""
    return MagicMock()


@pytest.fixture()
def svc_redis(mock_redis):
    """RateLimiterService backed by a mock Redis client."""
    return RateLimiterService(redis_client=mock_redis)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_no_redis_client_stores_none(self):
        s = RateLimiterService()
        assert s._redis is None

    def test_redis_client_stored(self, mock_redis):
        s = RateLimiterService(redis_client=mock_redis)
        assert s._redis is mock_redis

    def test_redis_client_can_be_any_object(self):
        obj = object()
        s = RateLimiterService(redis_client=obj)
        assert s._redis is obj


# ---------------------------------------------------------------------------
# window()
# ---------------------------------------------------------------------------

class TestWindow:
    def test_youtube_returns_daily_window(self, svc):
        win = svc.window("youtube")
        # YYYY-MM-DD
        assert len(win) == 10
        parts = win.split("-")
        assert len(parts) == 3

    def test_naver_search_returns_daily_window(self, svc):
        win = svc.window("naver_search")
        assert len(win) == 10

    def test_reddit_returns_10min_window(self, svc):
        win = svc.window("reddit")
        # e.g. "2024-01-15T14:3"  (date + T + HH:slot)
        assert "T" in win

    def test_reddit_window_contains_date_prefix(self, svc):
        win = svc.window("reddit")
        date_part = win.split("T")[0]
        parts = date_part.split("-")
        assert len(parts) == 3

    def test_reddit_slot_is_minute_div_10(self, svc):
        """Slot value should be minute // 10 (0-5)."""
        fake_now = datetime(2024, 6, 15, 14, 37, tzinfo=KST)  # minute=37 → slot=3
        with patch("app.services.rate_limiter.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.strftime = datetime.strftime
            win = svc.window("reddit")
        assert win == "2024-06-15T14:3"

    def test_daily_window_matches_kst_date(self, svc):
        fake_now = datetime(2024, 6, 15, 23, 0, tzinfo=KST)
        with patch("app.services.rate_limiter.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.strftime = datetime.strftime
            win = svc.window("youtube")
        assert win == "2024-06-15"

    def test_unknown_service_returns_daily_window(self, svc):
        """Unknown services fall back to daily (daily is the default)."""
        win = svc.window("unknown_service")
        assert "T" not in win
        assert len(win) == 10

    def test_two_calls_same_minute_return_same_window(self, svc):
        w1 = svc.window("youtube")
        w2 = svc.window("youtube")
        assert w1 == w2


# ---------------------------------------------------------------------------
# get() – in-memory fallback
# ---------------------------------------------------------------------------

class TestGetInMemory:
    def test_get_returns_zero_initially(self, svc):
        assert svc.get("youtube") == 0

    def test_get_returns_zero_for_naver(self, svc):
        assert svc.get("naver_search") == 0

    def test_get_returns_zero_for_reddit(self, svc):
        assert svc.get("reddit") == 0

    def test_get_returns_zero_for_unknown_service(self, svc):
        assert svc.get("nonexistent") == 0

    def test_get_after_increment_returns_count(self, svc):
        svc.increment("youtube")
        assert svc.get("youtube") == 1

    def test_get_returns_zero_after_window_change(self, svc):
        """When the window changes, get() sees a stale window and returns 0."""
        svc.increment("youtube")
        # Simulate window change by directly mutating the stored window key
        svc._mem_youtube = {"window": "1999-01-01", "count": 99}
        # window() now returns today's date, which differs from the stale key
        assert svc.get("youtube") == 0


# ---------------------------------------------------------------------------
# get() – Redis path
# ---------------------------------------------------------------------------

class TestGetRedis:
    def test_get_redis_returns_integer_value(self, svc_redis, mock_redis):
        mock_redis.get.return_value = b"42"
        assert svc_redis.get("youtube") == 42

    def test_get_redis_returns_zero_when_key_missing(self, svc_redis, mock_redis):
        mock_redis.get.return_value = None
        assert svc_redis.get("youtube") == 0

    def test_get_redis_returns_zero_on_exception(self, svc_redis, mock_redis):
        mock_redis.get.side_effect = ConnectionError("redis down")
        assert svc_redis.get("youtube") == 0

    def test_get_redis_logs_on_exception(self, svc_redis, mock_redis):
        mock_redis.get.side_effect = RuntimeError("timeout")
        with patch("app.services.rate_limiter.logger") as mock_log:
            svc_redis.get("youtube")
        mock_log.debug.assert_called_once()

    def test_get_redis_uses_correct_key_format(self, svc_redis, mock_redis):
        mock_redis.get.return_value = None
        win = svc_redis.window("youtube")
        svc_redis.get("youtube")
        expected_key = f"sns:youtube:count:{win}"
        mock_redis.get.assert_called_with(expected_key)

    def test_get_redis_string_value_parsed(self, svc_redis, mock_redis):
        mock_redis.get.return_value = "7"
        assert svc_redis.get("naver_search") == 7

    def test_get_redis_falls_back_to_memory_on_exception(self, svc_redis, mock_redis):
        """After Redis failure, in-memory fallback is consulted."""
        mock_redis.get.side_effect = Exception("broken")
        # Pre-seed in-memory state with current window
        win = svc_redis.window("youtube")
        svc_redis._mem_youtube = {"window": win, "count": 5}
        result = svc_redis.get("youtube")
        assert result == 5


# ---------------------------------------------------------------------------
# increment() – in-memory fallback
# ---------------------------------------------------------------------------

class TestIncrementInMemory:
    def test_increment_increases_count(self, svc):
        svc.increment("youtube")
        assert svc.get("youtube") == 1

    def test_increment_multiple_times(self, svc):
        for _ in range(5):
            svc.increment("youtube")
        assert svc.get("youtube") == 5

    def test_increment_different_services_independent(self, svc):
        svc.increment("youtube")
        svc.increment("naver_search")
        svc.increment("naver_search")
        assert svc.get("youtube") == 1
        assert svc.get("naver_search") == 2

    def test_increment_resets_on_window_change(self, svc):
        """When the stored window is stale, counter resets to 1 on first increment."""
        svc._mem_youtube = {"window": "1999-01-01", "count": 999}
        svc.increment("youtube")
        assert svc.get("youtube") == 1

    def test_increment_unknown_service_uses_default_ttl(self, svc):
        """Unknown services get ttl=90000 (default) without raising."""
        svc.increment("unknown_svc")
        # No error, counter stored
        assert svc.get("unknown_svc") == 1

    def test_increment_creates_mem_attr(self, svc):
        assert not hasattr(svc, "_mem_reddit")
        svc.increment("reddit")
        assert hasattr(svc, "_mem_reddit")

    def test_increment_preserves_window_key_in_attr(self, svc):
        win = svc.window("youtube")
        svc.increment("youtube")
        assert svc._mem_youtube["window"] == win
        assert svc._mem_youtube["count"] == 1


# ---------------------------------------------------------------------------
# increment() – Redis path
# ---------------------------------------------------------------------------

class TestIncrementRedis:
    def test_increment_calls_pipeline(self, svc_redis, mock_redis):
        pipe = MagicMock()
        mock_redis.pipeline.return_value = pipe
        pipe.execute.return_value = [1, True]
        svc_redis.increment("youtube")
        mock_redis.pipeline.assert_called_once()
        pipe.incr.assert_called_once()
        pipe.expire.assert_called_once()
        pipe.execute.assert_called_once()

    def test_increment_redis_uses_correct_key(self, svc_redis, mock_redis):
        pipe = MagicMock()
        mock_redis.pipeline.return_value = pipe
        pipe.execute.return_value = [1, True]
        win = svc_redis.window("youtube")
        svc_redis.increment("youtube")
        expected_key = f"sns:youtube:count:{win}"
        pipe.incr.assert_called_with(expected_key)

    def test_increment_redis_sets_ttl(self, svc_redis, mock_redis):
        pipe = MagicMock()
        mock_redis.pipeline.return_value = pipe
        pipe.execute.return_value = [1, True]
        win = svc_redis.window("youtube")
        svc_redis.increment("youtube")
        expected_key = f"sns:youtube:count:{win}"
        pipe.expire.assert_called_with(expected_key, 90000)

    def test_increment_redis_reddit_ttl(self, svc_redis, mock_redis):
        pipe = MagicMock()
        mock_redis.pipeline.return_value = pipe
        pipe.execute.return_value = [1, True]
        win = svc_redis.window("reddit")
        svc_redis.increment("reddit")
        expected_key = f"sns:reddit:count:{win}"
        pipe.expire.assert_called_with(expected_key, 660)

    def test_increment_redis_exception_falls_back_to_memory(self, svc_redis, mock_redis):
        mock_redis.pipeline.side_effect = Exception("pipe broken")
        svc_redis.increment("youtube")
        # Redis is bypassed; verify via memory fallback (remove redis)
        svc_redis._redis = None
        assert svc_redis.get("youtube") == 1

    def test_increment_redis_logs_on_exception(self, svc_redis, mock_redis):
        mock_redis.pipeline.side_effect = RuntimeError("crash")
        with patch("app.services.rate_limiter.logger") as mock_log:
            svc_redis.increment("youtube")
        mock_log.debug.assert_called_once()

    def test_increment_redis_partial_pipeline_result_logs_warning(self, svc_redis, mock_redis):
        """Partial pipeline result (results[0] is None) triggers a warning log."""
        pipe = MagicMock()
        mock_redis.pipeline.return_value = pipe
        pipe.execute.return_value = [None, True]
        with patch("app.services.rate_limiter.logger") as mock_log:
            svc_redis.increment("youtube")
        mock_log.warning.assert_called_once()

    def test_increment_redis_none_results_logs_warning(self, svc_redis, mock_redis):
        pipe = MagicMock()
        mock_redis.pipeline.return_value = pipe
        pipe.execute.return_value = None
        with patch("app.services.rate_limiter.logger") as mock_log:
            svc_redis.increment("youtube")
        mock_log.warning.assert_called_once()

    def test_increment_redis_short_results_logs_warning(self, svc_redis, mock_redis):
        pipe = MagicMock()
        mock_redis.pipeline.return_value = pipe
        pipe.execute.return_value = [1]  # only one element, need 2
        with patch("app.services.rate_limiter.logger") as mock_log:
            svc_redis.increment("youtube")
        mock_log.warning.assert_called_once()


# ---------------------------------------------------------------------------
# check()
# ---------------------------------------------------------------------------

class TestCheck:
    def test_check_returns_true_when_within_limit(self, svc):
        allowed, count, limit = svc.check("youtube")
        assert allowed is True
        assert count == 0
        assert limit == 10000

    def test_check_returns_false_when_limit_reached(self, svc):
        with patch.object(svc, "get", return_value=10000):
            allowed, count, limit = svc.check("youtube")
        assert allowed is False
        assert count == 10000

    def test_check_naver_search_limit(self, svc):
        allowed, count, limit = svc.check("naver_search")
        assert limit == 25000

    def test_check_reddit_limit(self, svc):
        allowed, count, limit = svc.check("reddit")
        assert limit == 600

    def test_check_unknown_service_uses_high_default_limit(self, svc):
        allowed, count, limit = svc.check("mystery_api")
        assert limit == 999999
        assert allowed is True

    def test_check_reflects_current_count(self, svc):
        svc.increment("youtube")
        svc.increment("youtube")
        allowed, count, limit = svc.check("youtube")
        assert count == 2
        assert allowed is True

    def test_check_just_below_limit_allowed(self, svc):
        with patch.object(svc, "get", return_value=9999):
            allowed, count, limit = svc.check("youtube")
        assert allowed is True

    def test_check_just_above_limit_denied(self, svc):
        with patch.object(svc, "get", return_value=10001):
            allowed, count, limit = svc.check("youtube")
        assert allowed is False

    def test_check_returns_three_tuple(self, svc):
        result = svc.check("youtube")
        assert len(result) == 3


# ---------------------------------------------------------------------------
# get_usage()
# ---------------------------------------------------------------------------

class TestGetUsage:
    def test_get_usage_returns_all_three_services(self, svc):
        usage = svc.get_usage(
            naver_configured=True,
            youtube_configured=True,
            reddit_configured=True,
        )
        assert set(usage.keys()) == {"naver_search", "youtube", "reddit"}

    def test_get_usage_configured_flag_naver(self, svc):
        usage = svc.get_usage(
            naver_configured=False,
            youtube_configured=True,
            reddit_configured=True,
        )
        assert usage["naver_search"]["configured"] is False
        assert usage["youtube"]["configured"] is True

    def test_get_usage_configured_flag_youtube(self, svc):
        usage = svc.get_usage(
            naver_configured=True,
            youtube_configured=False,
            reddit_configured=True,
        )
        assert usage["youtube"]["configured"] is False

    def test_get_usage_configured_flag_reddit(self, svc):
        usage = svc.get_usage(
            naver_configured=True,
            youtube_configured=True,
            reddit_configured=False,
        )
        assert usage["reddit"]["configured"] is False

    def test_get_usage_storage_memory(self, svc):
        usage = svc.get_usage(
            naver_configured=True, youtube_configured=True, reddit_configured=True
        )
        for svc_name in ("naver_search", "youtube", "reddit"):
            assert usage[svc_name]["storage"] == "memory"

    def test_get_usage_storage_redis(self, svc_redis):
        usage = svc_redis.get_usage(
            naver_configured=True, youtube_configured=True, reddit_configured=True
        )
        for svc_name in ("naver_search", "youtube", "reddit"):
            assert usage[svc_name]["storage"] == "redis"

    def test_get_usage_daily_limit_values(self, svc):
        usage = svc.get_usage(
            naver_configured=True, youtube_configured=True, reddit_configured=True
        )
        assert usage["naver_search"]["daily_limit"] == 25000
        assert usage["youtube"]["daily_limit"] == 10000
        assert usage["reddit"]["daily_limit"] == 600

    def test_get_usage_used_today_starts_zero(self, svc):
        usage = svc.get_usage(
            naver_configured=True, youtube_configured=True, reddit_configured=True
        )
        for svc_name in ("naver_search", "youtube", "reddit"):
            assert usage[svc_name]["used_today"] == 0

    def test_get_usage_remaining_equals_limit_minus_used(self, svc):
        svc.increment("youtube")
        svc.increment("youtube")
        usage = svc.get_usage(
            naver_configured=True, youtube_configured=True, reddit_configured=True
        )
        assert usage["youtube"]["used_today"] == 2
        assert usage["youtube"]["remaining"] == 10000 - 2

    def test_get_usage_remaining_never_negative(self, svc):
        """remaining = max(0, limit - count) so it can't go below 0."""
        with patch.object(svc, "get", return_value=99999):
            usage = svc.get_usage(
                naver_configured=True, youtube_configured=True, reddit_configured=True
            )
        for svc_name in ("naver_search", "youtube", "reddit"):
            assert usage[svc_name]["remaining"] >= 0

    def test_get_usage_window_label_daily(self, svc):
        usage = svc.get_usage(
            naver_configured=True, youtube_configured=True, reddit_configured=False
        )
        assert usage["youtube"]["window"] == "일일"
        assert usage["naver_search"]["window"] == "일일"

    def test_get_usage_window_label_10min(self, svc):
        usage = svc.get_usage(
            naver_configured=True, youtube_configured=True, reddit_configured=True
        )
        assert usage["reddit"]["window"] == "10분"

    def test_get_usage_date_field_is_today(self, svc):
        today = datetime.now(KST).strftime("%Y-%m-%d")
        usage = svc.get_usage(
            naver_configured=True, youtube_configured=True, reddit_configured=True
        )
        for svc_name in ("naver_search", "youtube", "reddit"):
            assert usage[svc_name]["date"] == today

    def test_get_usage_required_fields_present(self, svc):
        required = {"configured", "daily_limit", "used_today", "remaining", "window", "date", "storage"}
        usage = svc.get_usage(
            naver_configured=True, youtube_configured=True, reddit_configured=True
        )
        for svc_name in ("naver_search", "youtube", "reddit"):
            assert required == set(usage[svc_name].keys())


# ---------------------------------------------------------------------------
# In-memory counter expiration via window timestamps
# ---------------------------------------------------------------------------

class TestInMemoryWindowExpiration:
    def test_stale_window_resets_on_increment(self, svc):
        """Counter stored under yesterday's window resets when incremented today."""
        svc._mem_naver_search = {"window": "2000-01-01", "count": 500}
        svc.increment("naver_search")
        assert svc.get("naver_search") == 1

    def test_stale_window_returns_zero_on_get(self, svc):
        svc._mem_naver_search = {"window": "2000-01-01", "count": 500}
        assert svc.get("naver_search") == 0

    def test_correct_window_preserves_count_on_get(self, svc):
        win = svc.window("naver_search")
        svc._mem_naver_search = {"window": win, "count": 123}
        assert svc.get("naver_search") == 123

    def test_correct_window_accumulates_on_increment(self, svc):
        win = svc.window("youtube")
        svc._mem_youtube = {"window": win, "count": 10}
        svc.increment("youtube")
        assert svc.get("youtube") == 11

    def test_reddit_10min_window_expiry(self, svc):
        """Simulates minute-slot rollover for Reddit 10-min window."""
        fake_old = datetime(2024, 6, 15, 14, 5, tzinfo=KST)   # slot 0
        fake_new = datetime(2024, 6, 15, 14, 15, tzinfo=KST)  # slot 1

        with patch("app.services.rate_limiter.datetime") as mock_dt:
            mock_dt.now.return_value = fake_old
            mock_dt.strftime = datetime.strftime
            svc.increment("reddit")

        with patch("app.services.rate_limiter.datetime") as mock_dt:
            mock_dt.now.return_value = fake_new
            mock_dt.strftime = datetime.strftime
            count = svc.get("reddit")

        # New slot → stale window → count = 0
        assert count == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_rate_key_template_format(self):
        """_RATE_KEY_TPL produces the expected key string."""
        tpl = RateLimiterService._RATE_KEY_TPL
        key = tpl.format(service="youtube", window="2024-06-15")
        assert key == "sns:youtube:count:2024-06-15"

    def test_api_limits_contains_expected_services(self):
        limits = RateLimiterService._API_LIMITS
        assert "youtube" in limits
        assert "naver_search" in limits
        assert "reddit" in limits

    def test_youtube_api_limit_is_10000(self):
        assert RateLimiterService._API_LIMITS["youtube"]["limit"] == 10000

    def test_naver_api_limit_is_25000(self):
        assert RateLimiterService._API_LIMITS["naver_search"]["limit"] == 25000

    def test_reddit_api_limit_is_600(self):
        assert RateLimiterService._API_LIMITS["reddit"]["limit"] == 600

    def test_reddit_window_is_10min(self):
        assert RateLimiterService._API_LIMITS["reddit"]["window"] == "10min"

    def test_youtube_window_is_daily(self):
        assert RateLimiterService._API_LIMITS["youtube"]["window"] == "daily"

    def test_multiple_services_isolated(self, svc):
        for _ in range(3):
            svc.increment("youtube")
        for _ in range(7):
            svc.increment("naver_search")
        assert svc.get("youtube") == 3
        assert svc.get("naver_search") == 7
        assert svc.get("reddit") == 0

    def test_redis_get_exception_falls_back_silently(self, svc_redis, mock_redis):
        mock_redis.get.side_effect = TimeoutError("timeout")
        result = svc_redis.get("youtube")
        assert result == 0  # no exception raised

    def test_redis_incr_exception_falls_back_silently(self, svc_redis, mock_redis):
        mock_redis.pipeline.side_effect = OSError("connection reset")
        # Should not raise
        svc_redis.increment("youtube")

    def test_check_count_matches_get(self, svc):
        svc.increment("reddit")
        svc.increment("reddit")
        svc.increment("reddit")
        _, count, _ = svc.check("reddit")
        assert count == svc.get("reddit") == 3
