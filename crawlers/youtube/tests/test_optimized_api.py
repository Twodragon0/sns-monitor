"""
Tests for optimized_youtube_api.py

Covers:
- get_cache_key: deterministic SHA-256 cache key generation
- get_from_cache / save_to_cache: Redis path and fallback-when-unavailable
- execute_with_retry_and_cache: quota tracking, retry logic, quota warning,
  error categorisation (403-quota, 403-commentsDisabled, 403-forbidden,
  429, 400, 404, generic)
- reset_api_stats: stats reset to zero
- print_api_stats: runs without error; does not crash on all-zero stats
- get_videos_batch: batching logic
- detect_comment_country: language detection
- is_vtuber_comment: keyword matching
"""

import hashlib
import json
import os
import sys
import importlib
import unittest
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Path setup: run from repo root OR from crawlers/youtube directly
# ---------------------------------------------------------------------------
_YOUTUBE_DIR = os.path.join(os.path.dirname(__file__), "..")
if _YOUTUBE_DIR not in sys.path:
    sys.path.insert(0, _YOUTUBE_DIR)

# ---------------------------------------------------------------------------
# The module imports redis at module level and tries to connect.  We must
# stub both 'redis' and 'googleapiclient.errors' before the first import.
# ---------------------------------------------------------------------------
_fake_redis_mod = MagicMock()
_fake_redis_instance = MagicMock()
_fake_redis_instance.ping.side_effect = Exception("redis not available in tests")
_fake_redis_mod.Redis.return_value = _fake_redis_instance

_fake_http_error_class = type("HttpError", (Exception,), {})

with patch.dict(
    "sys.modules",
    {
        "redis": _fake_redis_mod,
        "googleapiclient": MagicMock(),
        "googleapiclient.errors": MagicMock(HttpError=_fake_http_error_class),
    },
):
    import optimized_youtube_api as yt_api
    # Force REDIS_AVAILABLE to False so all tests start clean
    yt_api.REDIS_AVAILABLE = False
    yt_api.redis_client = None

# Grab the real HttpError substitute used inside the module
HttpError = _fake_http_error_class


def _make_http_error(status, reason=None):
    """Build a fake HttpError that matches the shape crawler.py expects."""
    err = HttpError(f"HTTP {status}")
    err.resp = MagicMock()
    err.resp.status = status
    error_body = {"error": {"errors": [{"reason": reason or ""}]}}
    err.content = json.dumps(error_body).encode()
    return err


# ---------------------------------------------------------------------------
# Helper: reset module-level stats before every test
# ---------------------------------------------------------------------------
def _reset():
    yt_api.reset_api_stats()


class TestGetCacheKey(unittest.TestCase):
    """get_cache_key produces a stable, order-independent SHA-256 key."""

    def test_returns_string_with_api_name_prefix(self):
        key = yt_api.get_cache_key("search", {"q": "test"})
        self.assertIsInstance(key, str)
        self.assertTrue(key.startswith("youtube_api:search:"))

    def test_key_is_deterministic_for_same_params(self):
        k1 = yt_api.get_cache_key("videos", {"id": "abc", "part": "snippet"})
        k2 = yt_api.get_cache_key("videos", {"id": "abc", "part": "snippet"})
        self.assertEqual(k1, k2)

    def test_key_differs_for_different_params(self):
        k1 = yt_api.get_cache_key("videos", {"id": "abc"})
        k2 = yt_api.get_cache_key("videos", {"id": "xyz"})
        self.assertNotEqual(k1, k2)

    def test_key_is_order_independent(self):
        k1 = yt_api.get_cache_key("channels", {"part": "id", "forHandle": "test"})
        k2 = yt_api.get_cache_key("channels", {"forHandle": "test", "part": "id"})
        self.assertEqual(k1, k2)

    def test_hash_segment_is_sha256_hex(self):
        params = {"q": "hello"}
        key = yt_api.get_cache_key("search", params)
        hash_part = key.split(":")[-1]
        # SHA-256 hex digest is always 64 characters
        self.assertEqual(len(hash_part), 64)
        # Must be valid hex
        int(hash_part, 16)

    def test_different_api_names_produce_different_keys_for_same_params(self):
        k1 = yt_api.get_cache_key("search", {"q": "hi"})
        k2 = yt_api.get_cache_key("videos", {"q": "hi"})
        self.assertNotEqual(k1, k2)


class TestCacheWithRedisUnavailable(unittest.TestCase):
    """When REDIS_AVAILABLE is False both cache helpers are no-ops."""

    def setUp(self):
        yt_api.REDIS_AVAILABLE = False
        yt_api.redis_client = None
        _reset()

    def test_get_from_cache_returns_none_when_redis_unavailable(self):
        result = yt_api.get_from_cache("search", {"q": "test"})
        self.assertIsNone(result)

    def test_save_to_cache_is_noop_when_redis_unavailable(self):
        # Must not raise, must not call redis
        yt_api.save_to_cache("search", {"q": "test"}, {"items": []})

    def test_cache_miss_does_not_increment_cache_hits(self):
        _reset()
        yt_api.get_from_cache("search", {"q": "miss"})
        self.assertEqual(yt_api.api_stats["search"]["cache_hits"], 0)


class TestCacheWithRedisAvailable(unittest.TestCase):
    """When REDIS_AVAILABLE is True the helpers delegate to redis_client."""

    def setUp(self):
        self._mock_redis = MagicMock()
        yt_api.REDIS_AVAILABLE = True
        yt_api.redis_client = self._mock_redis
        _reset()

    def tearDown(self):
        yt_api.REDIS_AVAILABLE = False
        yt_api.redis_client = None

    def test_get_from_cache_returns_none_on_cache_miss(self):
        self._mock_redis.get.return_value = None
        result = yt_api.get_from_cache("videos", {"id": "abc"})
        self.assertIsNone(result)

    def test_get_from_cache_returns_parsed_json_on_hit(self):
        payload = {"items": [{"id": "v1"}]}
        self._mock_redis.get.return_value = json.dumps(payload)
        result = yt_api.get_from_cache("videos", {"id": "abc"})
        self.assertEqual(result, payload)

    def test_get_from_cache_increments_cache_hits_on_hit(self):
        _reset()
        self._mock_redis.get.return_value = json.dumps({"items": []})
        yt_api.get_from_cache("search", {"q": "hit"})
        self.assertEqual(yt_api.api_stats["search"]["cache_hits"], 1)

    def test_save_to_cache_calls_setex_with_correct_ttl(self):
        data = {"items": []}
        yt_api.save_to_cache("commentThreads", {"videoId": "v1"}, data)
        self._mock_redis.setex.assert_called_once()
        args = self._mock_redis.setex.call_args[0]
        # args: (key, ttl, json_string)
        self.assertEqual(args[1], yt_api.CACHE_TTL["commentThreads"])

    def test_get_from_cache_returns_none_on_redis_exception(self):
        self._mock_redis.get.side_effect = Exception("redis down")
        result = yt_api.get_from_cache("search", {"q": "x"})
        self.assertIsNone(result)

    def test_save_to_cache_silently_handles_redis_exception(self):
        self._mock_redis.setex.side_effect = Exception("redis down")
        # Must not raise
        yt_api.save_to_cache("search", {"q": "x"}, {})


class TestResetApiStats(unittest.TestCase):
    """reset_api_stats resets every counter to zero."""

    def test_all_stat_fields_are_zero_after_reset(self):
        # Dirty the stats first
        for api in yt_api.api_stats:
            yt_api.api_stats[api]["calls"] = 99
            yt_api.api_stats[api]["quota"] = 99
            yt_api.api_stats[api]["errors"] = 99
            yt_api.api_stats[api]["cache_hits"] = 99

        yt_api.reset_api_stats()

        for api, stats in yt_api.api_stats.items():
            for field in ("calls", "quota", "errors", "cache_hits"):
                self.assertEqual(stats[field], 0, f"{api}.{field} should be 0 after reset")

    def test_reset_preserves_all_expected_api_keys(self):
        yt_api.reset_api_stats()
        expected_keys = {"search", "videos", "channels", "commentThreads", "playlistItems"}
        self.assertEqual(set(yt_api.api_stats.keys()), expected_keys)


class TestPrintApiStats(unittest.TestCase):
    """print_api_stats must not raise under any stats state."""

    def test_does_not_raise_with_all_zero_stats(self):
        _reset()
        yt_api.print_api_stats()  # must not raise

    def test_does_not_raise_with_nonzero_stats(self):
        _reset()
        yt_api.api_stats["search"]["calls"] = 5
        yt_api.api_stats["search"]["quota"] = 500
        yt_api.api_stats["search"]["cache_hits"] = 2
        yt_api.api_stats["search"]["errors"] = 1
        yt_api.print_api_stats()  # must not raise


class TestExecuteWithRetryAndCache(unittest.TestCase):
    """execute_with_retry_and_cache: quota tracking, error handling, retry."""

    def setUp(self):
        yt_api.REDIS_AVAILABLE = False
        yt_api.redis_client = None
        _reset()

    def _call(self, api_call, api_name="videos", params=None, max_retries=0):
        return yt_api.execute_with_retry_and_cache(
            api_call,
            api_name,
            params or {"id": "v1"},
            max_retries=max_retries,
            backoff_base=0,   # zero backoff so tests don't sleep
        )

    # --- happy path ---

    @patch("time.sleep")
    def test_successful_call_increments_calls_and_quota(self, mock_sleep):
        _reset()
        mock_api = MagicMock(return_value={"items": []})
        self._call(mock_api, api_name="videos")
        self.assertEqual(yt_api.api_stats["videos"]["calls"], 1)
        self.assertEqual(yt_api.api_stats["videos"]["quota"], yt_api.QUOTA_COSTS["videos"])

    @patch("time.sleep")
    def test_successful_call_returns_api_result(self, mock_sleep):
        payload = {"items": [{"id": "v1"}]}
        mock_api = MagicMock(return_value=payload)
        result = self._call(mock_api)
        self.assertEqual(result, payload)

    # --- quota warning ---

    @patch("time.sleep")
    def test_logs_quota_warning_when_threshold_exceeded(self, mock_sleep):
        _reset()
        # Push search quota just past the threshold (default 8000)
        yt_api.api_stats["search"]["quota"] = 7999

        mock_api = MagicMock(return_value={"items": []})
        with patch.object(yt_api.logger, "warning") as mock_warn:
            with patch.dict(os.environ, {"YOUTUBE_QUOTA_WARN_THRESHOLD": "8000"}):
                self._call(mock_api, api_name="videos")
        # Warning was emitted at least once mentioning quota
        warned = any("quota" in str(c).lower() for c in mock_warn.call_args_list)
        self.assertTrue(warned, "Expected a quota warning log")

    # --- 403 quota exceeded ---

    @patch("time.sleep")
    def test_403_quota_exceeded_raises_after_max_retries(self, mock_sleep):
        err = _make_http_error(403, "quotaExceeded")
        mock_api = MagicMock(side_effect=err)
        with self.assertRaises(Exception) as ctx:
            self._call(mock_api, api_name="search", max_retries=1)
        self.assertIn("quota exceeded", str(ctx.exception).lower())

    @patch("time.sleep")
    def test_403_daily_limit_exceeded_raises_after_max_retries(self, mock_sleep):
        err = _make_http_error(403, "dailyLimitExceeded")
        mock_api = MagicMock(side_effect=err)
        with self.assertRaises(Exception) as ctx:
            self._call(mock_api, api_name="search", max_retries=1)
        self.assertIn("quota exceeded", str(ctx.exception).lower())

    # --- 403 comments disabled ---

    @patch("time.sleep")
    def test_403_comments_disabled_returns_none(self, mock_sleep):
        err = _make_http_error(403, "commentsDisabled")
        mock_api = MagicMock(side_effect=err)
        result = self._call(mock_api, api_name="commentThreads")
        self.assertIsNone(result)

    # --- 403 permanent access denial ---

    @patch("time.sleep")
    def test_403_forbidden_reason_raises_immediately(self, mock_sleep):
        err = _make_http_error(403, "forbidden")
        mock_api = MagicMock(side_effect=err)
        with self.assertRaises(HttpError):
            self._call(mock_api, api_name="search", max_retries=3)
        # Should not retry — called exactly once
        mock_api.assert_called_once()

    @patch("time.sleep")
    def test_403_key_invalid_raises_immediately(self, mock_sleep):
        err = _make_http_error(403, "keyInvalid")
        mock_api = MagicMock(side_effect=err)
        with self.assertRaises(HttpError):
            self._call(mock_api, api_name="search", max_retries=3)
        mock_api.assert_called_once()

    # --- 429 rate limit ---

    @patch("time.sleep")
    def test_429_raises_exception_after_max_retries(self, mock_sleep):
        err = _make_http_error(429)
        mock_api = MagicMock(side_effect=err)
        with self.assertRaises(Exception) as ctx:
            self._call(mock_api, api_name="search", max_retries=1)
        self.assertIn("rate limit", str(ctx.exception).lower())

    # --- 400 bad request ---

    @patch("time.sleep")
    def test_400_raises_immediately_without_retry(self, mock_sleep):
        err = _make_http_error(400, "invalidChannelId")
        mock_api = MagicMock(side_effect=err)
        with self.assertRaises(HttpError):
            self._call(mock_api, api_name="channels", max_retries=3)
        mock_api.assert_called_once()

    # --- 404 not found ---

    @patch("time.sleep")
    def test_404_returns_none(self, mock_sleep):
        err = _make_http_error(404)
        mock_api = MagicMock(side_effect=err)
        result = self._call(mock_api, api_name="videos")
        self.assertIsNone(result)

    # --- generic retry ---

    @patch("time.sleep")
    def test_generic_http_error_retries_and_eventually_raises(self, mock_sleep):
        err = _make_http_error(500)
        mock_api = MagicMock(side_effect=err)
        with self.assertRaises(HttpError):
            self._call(mock_api, max_retries=2)
        # Called once for initial attempt + 2 retries = 3 total
        self.assertEqual(mock_api.call_count, 3)

    @patch("time.sleep")
    def test_non_http_exception_retries_and_eventually_raises(self, mock_sleep):
        mock_api = MagicMock(side_effect=ValueError("network error"))
        with self.assertRaises(ValueError):
            self._call(mock_api, max_retries=2)
        self.assertEqual(mock_api.call_count, 3)

    # --- error stat tracking ---

    @patch("time.sleep")
    def test_http_error_increments_errors_stat(self, mock_sleep):
        _reset()
        err = _make_http_error(500)
        mock_api = MagicMock(side_effect=err)
        with self.assertRaises(HttpError):
            self._call(mock_api, api_name="videos", max_retries=0)
        self.assertGreater(yt_api.api_stats["videos"]["errors"], 0)

    # --- cache integration ---

    @patch("time.sleep")
    def test_returns_cached_result_without_calling_api(self, mock_sleep):
        cached = {"items": [{"id": "cached"}]}
        mock_api = MagicMock(return_value={"items": [{"id": "fresh"}]})

        yt_api.REDIS_AVAILABLE = True
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached)
        yt_api.redis_client = mock_redis

        try:
            result = self._call(mock_api, api_name="videos", params={"id": "v1"})
            self.assertEqual(result, cached)
            mock_api.assert_not_called()
        finally:
            yt_api.REDIS_AVAILABLE = False
            yt_api.redis_client = None


class TestQuotaCosts(unittest.TestCase):
    """QUOTA_COSTS dict matches the documented YouTube API v3 values."""

    def test_search_costs_100_quota_units(self):
        self.assertEqual(yt_api.QUOTA_COSTS["search"], 100)

    def test_videos_costs_1_quota_unit(self):
        self.assertEqual(yt_api.QUOTA_COSTS["videos"], 1)

    def test_channels_costs_1_quota_unit(self):
        self.assertEqual(yt_api.QUOTA_COSTS["channels"], 1)

    def test_comment_threads_costs_1_quota_unit(self):
        self.assertEqual(yt_api.QUOTA_COSTS["commentThreads"], 1)

    def test_playlist_items_costs_1_quota_unit(self):
        self.assertEqual(yt_api.QUOTA_COSTS["playlistItems"], 1)


class TestDetectCommentCountry(unittest.TestCase):
    """detect_comment_country classifies text language correctly."""

    def test_returns_kr_for_korean_text(self):
        result = yt_api.detect_comment_country("안녕하세요 반갑습니다")
        self.assertEqual(result, "KR")

    def test_returns_jp_for_hiragana_text(self):
        result = yt_api.detect_comment_country("こんにちは よろしく")
        self.assertEqual(result, "JP")

    def test_returns_jp_for_katakana_text(self):
        result = yt_api.detect_comment_country("コンニチハ ヨロシク")
        self.assertEqual(result, "JP")

    def test_returns_us_for_english_text(self):
        result = yt_api.detect_comment_country("Hello world this is great")
        self.assertEqual(result, "US")

    def test_returns_unknown_for_empty_string(self):
        result = yt_api.detect_comment_country("")
        self.assertEqual(result, "Unknown")

    def test_returns_unknown_for_none(self):
        result = yt_api.detect_comment_country(None)
        self.assertEqual(result, "Unknown")

    def test_returns_unknown_for_only_numbers_and_symbols(self):
        result = yt_api.detect_comment_country("12345 !!! @@@")
        self.assertEqual(result, "Unknown")


class TestIsVtuberComment(unittest.TestCase):
    """is_vtuber_comment detects VTuber-related author names."""

    def test_returns_true_for_vtuber_keyword(self):
        self.assertTrue(yt_api.is_vtuber_comment("VTuber Fan"))

    def test_returns_true_for_virtual_keyword(self):
        self.assertTrue(yt_api.is_vtuber_comment("Virtual Singer"))

    def test_returns_true_for_korean_keyword(self):
        self.assertTrue(yt_api.is_vtuber_comment("버튜버 채널"))

    def test_returns_true_for_avatar_keyword(self):
        self.assertTrue(yt_api.is_vtuber_comment("avatar user"))

    def test_returns_false_for_regular_username(self):
        self.assertFalse(yt_api.is_vtuber_comment("John Smith"))

    def test_returns_false_for_empty_string(self):
        self.assertFalse(yt_api.is_vtuber_comment(""))

    def test_returns_false_for_none(self):
        self.assertFalse(yt_api.is_vtuber_comment(None))

    def test_case_insensitive_matching(self):
        self.assertTrue(yt_api.is_vtuber_comment("VTUBER CHANNEL"))


class TestGetVideosBatch(unittest.TestCase):
    """get_videos_batch splits large ID lists into batches of <=50."""

    def setUp(self):
        yt_api.REDIS_AVAILABLE = False
        yt_api.redis_client = None
        _reset()

    @patch("time.sleep")
    def test_single_batch_for_fewer_than_50_ids(self, mock_sleep):
        mock_youtube = MagicMock()
        mock_youtube.videos.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "v1"}]
        }

        with patch.object(yt_api, "execute_with_retry_and_cache") as mock_exec:
            mock_exec.return_value = {"items": [{"id": "v1"}]}
            videos = yt_api.get_videos_batch(mock_youtube, ["v1", "v2", "v3"])

        self.assertEqual(mock_exec.call_count, 1)

    @patch("time.sleep")
    def test_two_batches_for_51_ids(self, mock_sleep):
        mock_youtube = MagicMock()
        video_ids = [f"v{i}" for i in range(51)]

        with patch.object(yt_api, "execute_with_retry_and_cache") as mock_exec:
            mock_exec.return_value = {"items": []}
            yt_api.get_videos_batch(mock_youtube, video_ids)

        self.assertEqual(mock_exec.call_count, 2)

    @patch("time.sleep")
    def test_returns_empty_list_for_empty_input(self, mock_sleep):
        mock_youtube = MagicMock()
        result = yt_api.get_videos_batch(mock_youtube, [])
        self.assertEqual(result, [])

    @patch("time.sleep")
    def test_batch_ids_are_comma_joined(self, mock_sleep):
        mock_youtube = MagicMock()
        with patch.object(yt_api, "execute_with_retry_and_cache") as mock_exec:
            mock_exec.return_value = {"items": []}
            yt_api.get_videos_batch(mock_youtube, ["v1", "v2"])

        called_params = mock_exec.call_args[0][2]  # positional arg: params
        self.assertIn(",", called_params["id"])
        self.assertIn("v1", called_params["id"])
        self.assertIn("v2", called_params["id"])

    @patch("time.sleep")
    def test_errors_in_one_batch_do_not_stop_other_batches(self, mock_sleep):
        mock_youtube = MagicMock()
        video_ids = [f"v{i}" for i in range(60)]

        call_results = [Exception("batch 1 failed"), {"items": [{"id": "v50"}]}]

        with patch.object(yt_api, "execute_with_retry_and_cache") as mock_exec:
            mock_exec.side_effect = call_results
            result = yt_api.get_videos_batch(mock_youtube, video_ids)

        # Second batch succeeded
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "v50")


if __name__ == "__main__":
    unittest.main()
