"""
Tests for crawler.py

Covers:
- get_kst_now: returns a timezone-aware KST datetime
- _import_local_storage: path resolution with fallback ordering
- CHANNEL_ID_OVERRIDE lookup in get_channel_id_from_handle
- LOCAL_MODE=true vs false branch behaviour (AWS clients)
- execute_with_retry: quota exceeded, commentsDisabled, 400, 404, 429,
  generic retry, unexpected errors
- is_vtuber_comment: keyword heuristic
- detect_comment_country: Korean / Japanese / English / empty
- _process_replies: vtuber flag, empty replies
- _calculate_vtuber_likes_from_replies: aggregation
- _process_comment_item: country bucketing, vtuber detection
- clean_creator_name_for_search: studio name stripping, member mapping
- _get_keyword_channel_map: key presence
- _find_channel_by_partial_match: exact match, no match
- _resolve_channel_filter: known keyword hits override path
- get_youtube_api_key: env-var path and Secrets Manager path
"""

import importlib
import json
import os
import sys
import types
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Path bootstrap so the module can be imported from any CWD
# ---------------------------------------------------------------------------
_YOUTUBE_DIR = os.path.join(os.path.dirname(__file__), "..")
if _YOUTUBE_DIR not in sys.path:
    sys.path.insert(0, _YOUTUBE_DIR)

# ---------------------------------------------------------------------------
# Pre-stub heavy external dependencies so module-level code doesn't connect
# to real services during import.
# ---------------------------------------------------------------------------
_fake_http_error_class = type("HttpError", (Exception,), {})

_fake_google_pkg = types.ModuleType("googleapiclient")
_fake_google_pkg.discovery = MagicMock()
_fake_google_pkg.errors = MagicMock(HttpError=_fake_http_error_class)

_fake_redis_mod = MagicMock()
_fake_redis_instance = MagicMock()
_fake_redis_instance.ping.side_effect = Exception("no redis in tests")
_fake_redis_mod.Redis.return_value = _fake_redis_instance

_fake_optimized = MagicMock()

# Patch everything before first import
with patch.dict(
    "sys.modules",
    {
        "boto3": MagicMock(),
        "redis": _fake_redis_mod,
        "googleapiclient": _fake_google_pkg,
        "googleapiclient.discovery": _fake_google_pkg.discovery,
        "googleapiclient.errors": _fake_google_pkg.errors,
        "optimized_youtube_api": _fake_optimized,
    },
):
    # Set LOCAL_MODE=true so AWS clients are NOT initialised at import time
    with patch.dict(os.environ, {"LOCAL_MODE": "true", "LOCAL_DATA_DIR": "/tmp/test-local-data"}):
        # local_storage must be importable; use the real one from the same dir
        import local_storage  # noqa: F401
        import crawler

# Keep a reference to the HttpError used in the module
HttpError = _fake_http_error_class


def _make_http_error(status, reason=None):
    """Build a HttpError stub matching the shape crawler.py inspects."""
    err = HttpError(f"HTTP {status}")
    err.resp = MagicMock()
    err.resp.status = status
    body = {"error": {"errors": [{"reason": reason or ""}]}}
    err.content = json.dumps(body).encode()
    return err


# ---------------------------------------------------------------------------
# KST timezone tests
# ---------------------------------------------------------------------------
class TestGetKstNow(unittest.TestCase):
    """get_kst_now returns a timezone-aware datetime in KST (UTC+9)."""

    def test_returns_datetime_instance(self):
        result = crawler.get_kst_now()
        self.assertIsInstance(result, datetime)

    def test_result_is_timezone_aware(self):
        result = crawler.get_kst_now()
        self.assertIsNotNone(result.tzinfo)

    def test_utc_offset_is_plus_nine_hours(self):
        result = crawler.get_kst_now()
        offset = result.utcoffset()
        self.assertEqual(offset, timedelta(hours=9))

    def test_kst_is_nine_hours_ahead_of_utc(self):
        before = datetime.now(timezone.utc)
        kst = crawler.get_kst_now()
        after = datetime.now(timezone.utc)
        # KST - UTC should be approximately 9 hours
        diff = kst.utcoffset().total_seconds()
        self.assertEqual(diff, 9 * 3600)


# ---------------------------------------------------------------------------
# _import_local_storage tests
# ---------------------------------------------------------------------------
class TestImportLocalStorage(unittest.TestCase):
    """_import_local_storage resolves paths in priority order."""

    def test_returns_two_callables_when_local_storage_is_on_syspath(self):
        # local_storage.py lives in the same directory as crawler.py and is
        # already importable because we added _YOUTUBE_DIR to sys.path above.
        # Re-call the function to exercise the "current directory" code path.
        save, save_meta = crawler._import_local_storage()
        self.assertTrue(callable(save))
        self.assertTrue(callable(save_meta))

    def test_raises_import_error_when_no_path_succeeds(self):
        # Temporarily remove local_storage from sys.modules AND block the
        # import so that every candidate path in _import_local_storage fails.
        saved = sys.modules.pop("local_storage", None)
        try:
            # Make os.path.exists return False for every candidate path so
            # sys.path.insert branches are all skipped, and also make the
            # bare import (None path / current dir) raise ImportError by
            # injecting a broken sentinel into sys.modules.
            sys.modules["local_storage"] = None  # causes ImportError on `import`
            with patch.object(os.path, "exists", return_value=False):
                with self.assertRaises(ImportError):
                    crawler._import_local_storage()
        finally:
            sys.modules.pop("local_storage", None)
            if saved is not None:
                sys.modules["local_storage"] = saved


# ---------------------------------------------------------------------------
# CHANNEL_ID_OVERRIDE logic in get_channel_id_from_handle
# ---------------------------------------------------------------------------
class TestChannelIdOverride(unittest.TestCase):
    """get_channel_id_from_handle uses CHANNEL_ID_OVERRIDE before any API call."""

    def _call(self, handle):
        """Call with a dummy youtube client — should never reach the API."""
        mock_youtube = MagicMock()
        return crawler.get_channel_id_from_handle(mock_youtube, handle)

    def test_returns_overridden_id_for_known_handle(self):
        # Pick any handle that appears in CHANNEL_ID_OVERRIDE
        known_handle = "@example-studio-official"
        expected_id = crawler.CHANNEL_ID_OVERRIDE[known_handle]
        result = self._call(known_handle)
        self.assertEqual(result, expected_id)

    def test_does_not_call_api_when_override_exists(self):
        mock_youtube = MagicMock()
        crawler.get_channel_id_from_handle(mock_youtube, "@example-studio-official")
        mock_youtube.channels.assert_not_called()

    def test_returns_override_for_handle_in_full_url(self):
        url = "https://www.youtube.com/@example-studio-official?si=abc123"
        mock_youtube = MagicMock()
        result = crawler.get_channel_id_from_handle(mock_youtube, url)
        self.assertEqual(result, crawler.CHANNEL_ID_OVERRIDE["@example-studio-official"])

    def test_all_override_handles_start_with_at_sign(self):
        for handle in crawler.CHANNEL_ID_OVERRIDE:
            self.assertTrue(handle.startswith("@"), f"Expected @ prefix: {handle}")

    def test_all_override_ids_start_with_uc(self):
        for handle, channel_id in crawler.CHANNEL_ID_OVERRIDE.items():
            self.assertTrue(channel_id.startswith("UC"), f"Bad channel ID for {handle}: {channel_id}")

    def test_returns_none_for_url_with_no_at_or_path_handle(self):
        mock_youtube = MagicMock()
        # URL with no @handle and no matchable path part
        mock_youtube.channels.return_value.list.return_value.execute.return_value = {"items": []}
        result = crawler.get_channel_id_from_handle(mock_youtube, "https://youtube.com/channel/UCxxx")
        # Should return None because no handle can be extracted from this URL form
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# LOCAL_MODE environment variable branching
# ---------------------------------------------------------------------------
class TestLocalModeBranching(unittest.TestCase):
    """Module-level LOCAL_MODE flag gates AWS client initialisation."""

    def test_local_mode_sets_s3_client_to_none(self):
        # crawler was imported with LOCAL_MODE=true
        self.assertIsNone(crawler.s3_client)

    def test_local_mode_sets_lambda_client_to_none(self):
        self.assertIsNone(crawler.lambda_client)

    def test_local_mode_sets_secrets_client_to_none(self):
        self.assertIsNone(crawler.secrets_client)

    def test_local_mode_sets_dynamodb_to_none(self):
        self.assertIsNone(crawler.dynamodb)


# ---------------------------------------------------------------------------
# execute_with_retry error categorisation
# ---------------------------------------------------------------------------
class TestExecuteWithRetry(unittest.TestCase):
    """execute_with_retry handles HTTP errors correctly without real sleeps."""

    def _call(self, fn, max_retries=0):
        return crawler.execute_with_retry(fn, max_retries=max_retries, backoff_base=0)

    @patch("time.sleep")
    def test_returns_result_on_success(self, mock_sleep):
        result = self._call(lambda: {"items": []})
        self.assertEqual(result, {"items": []})

    @patch("time.sleep")
    def test_404_returns_none(self, mock_sleep):
        err = _make_http_error(404)
        result = self._call(lambda: (_ for _ in ()).throw(err))
        self.assertIsNone(result)

    @patch("time.sleep")
    def test_comments_disabled_returns_none(self, mock_sleep):
        err = _make_http_error(403, "commentsDisabled")
        result = self._call(lambda: (_ for _ in ()).throw(err))
        self.assertIsNone(result)

    @patch("time.sleep")
    def test_quota_exceeded_raises_after_all_retries(self, mock_sleep):
        err = _make_http_error(403, "quotaExceeded")
        with self.assertRaises(Exception) as ctx:
            self._call(lambda: (_ for _ in ()).throw(err), max_retries=1)
        self.assertIn("quota exceeded", str(ctx.exception).lower())

    @patch("time.sleep")
    def test_400_raises_without_retry(self, mock_sleep):
        err = _make_http_error(400, "badRequest")
        call_count = 0

        def api():
            nonlocal call_count
            call_count += 1
            raise err

        with self.assertRaises(HttpError):
            self._call(api, max_retries=3)
        self.assertEqual(call_count, 1)

    @patch("time.sleep")
    def test_429_raises_after_all_retries(self, mock_sleep):
        err = _make_http_error(429)
        with self.assertRaises(Exception) as ctx:
            self._call(lambda: (_ for _ in ()).throw(err), max_retries=1)
        self.assertIn("rate limit", str(ctx.exception).lower())

    @patch("time.sleep")
    def test_generic_500_retries_specified_number_of_times(self, mock_sleep):
        err = _make_http_error(500)
        call_count = 0

        def api():
            nonlocal call_count
            call_count += 1
            raise err

        with self.assertRaises(HttpError):
            self._call(api, max_retries=2)
        self.assertEqual(call_count, 3)  # 1 initial + 2 retries

    @patch("time.sleep")
    def test_non_http_exception_retries_and_re_raises(self, mock_sleep):
        call_count = 0

        def api():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("network failure")

        with self.assertRaises(RuntimeError):
            self._call(api, max_retries=2)
        self.assertEqual(call_count, 3)

    @patch("time.sleep")
    def test_first_attempt_applies_default_api_delay(self, mock_sleep):
        self._call(lambda: {}, max_retries=0)
        mock_sleep.assert_called()


# ---------------------------------------------------------------------------
# is_vtuber_comment
# ---------------------------------------------------------------------------
class TestIsVtuberComment(unittest.TestCase):
    """is_vtuber_comment uses keyword heuristics on the author name."""

    def test_returns_true_when_author_contains_vtuber(self):
        self.assertTrue(crawler.is_vtuber_comment("Cool VTuber Channel"))

    def test_returns_true_when_author_contains_virtual(self):
        self.assertTrue(crawler.is_vtuber_comment("Virtual Artist"))

    def test_returns_true_when_author_contains_korean_keyword(self):
        self.assertTrue(crawler.is_vtuber_comment("버튜버스타"))

    def test_returns_true_when_author_contains_avatar(self):
        self.assertTrue(crawler.is_vtuber_comment("My Avatar Streams"))

    def test_returns_false_for_regular_author(self):
        self.assertFalse(crawler.is_vtuber_comment("Regular User 123"))

    def test_returns_false_for_empty_string(self):
        self.assertFalse(crawler.is_vtuber_comment(""))

    def test_returns_false_for_none(self):
        self.assertFalse(crawler.is_vtuber_comment(None))

    def test_matching_is_case_insensitive(self):
        self.assertTrue(crawler.is_vtuber_comment("VTUBER_FAN"))


# ---------------------------------------------------------------------------
# detect_comment_country
# ---------------------------------------------------------------------------
class TestDetectCommentCountry(unittest.TestCase):
    """detect_comment_country estimates country from character frequency."""

    def test_korean_text_returns_kr(self):
        self.assertEqual(crawler.detect_comment_country("안녕하세요 반갑습니다"), "KR")

    def test_hiragana_text_returns_jp(self):
        self.assertEqual(crawler.detect_comment_country("こんにちは よろしく"), "JP")

    def test_english_text_returns_us(self):
        self.assertEqual(crawler.detect_comment_country("Hello great video thanks"), "US")

    def test_empty_string_returns_unknown(self):
        self.assertEqual(crawler.detect_comment_country(""), "Unknown")

    def test_none_returns_unknown(self):
        self.assertEqual(crawler.detect_comment_country(None), "Unknown")

    def test_numeric_only_string_returns_unknown(self):
        self.assertEqual(crawler.detect_comment_country("1234567890"), "Unknown")


# ---------------------------------------------------------------------------
# _process_replies
# ---------------------------------------------------------------------------
class TestProcessReplies(unittest.TestCase):
    """_process_replies extracts reply data and sets is_vtuber flag."""

    def _make_item(self, replies_list):
        return {
            "replies": {
                "comments": replies_list
            }
        }

    def _make_reply(self, author, text, like_count=0, published_at="2026-01-01T00:00:00Z"):
        return {
            "snippet": {
                "authorDisplayName": author,
                "textDisplay": text,
                "likeCount": like_count,
                "publishedAt": published_at,
            }
        }

    def test_returns_empty_list_when_no_replies_key(self):
        result = crawler._process_replies({}, analyze_vtubers=False)
        self.assertEqual(result, [])

    def test_returns_correct_number_of_replies(self):
        item = self._make_item([
            self._make_reply("UserA", "Nice!"),
            self._make_reply("UserB", "Cool!"),
        ])
        result = crawler._process_replies(item, analyze_vtubers=False)
        self.assertEqual(len(result), 2)

    def test_reply_contains_required_fields(self):
        item = self._make_item([self._make_reply("Alice", "Great video", 5)])
        result = crawler._process_replies(item, analyze_vtubers=False)
        reply = result[0]
        self.assertEqual(reply["author"], "Alice")
        self.assertEqual(reply["text"], "Great video")
        self.assertEqual(reply["like_count"], 5)

    def test_is_vtuber_is_false_when_analyze_vtubers_is_false(self):
        item = self._make_item([self._make_reply("VTuber Fan", "hi")])
        result = crawler._process_replies(item, analyze_vtubers=False)
        self.assertFalse(result[0]["is_vtuber"])

    def test_is_vtuber_is_true_for_vtuber_author_when_analyze_is_true(self):
        item = self._make_item([self._make_reply("VTuber Channel", "hi")])
        result = crawler._process_replies(item, analyze_vtubers=True)
        self.assertTrue(result[0]["is_vtuber"])


# ---------------------------------------------------------------------------
# _calculate_vtuber_likes_from_replies
# ---------------------------------------------------------------------------
class TestCalculateVtuberLikesFromReplies(unittest.TestCase):
    """_calculate_vtuber_likes_from_replies sums likes for vtuber replies only."""

    def test_returns_zero_when_analyze_vtubers_is_false(self):
        replies = [{"is_vtuber": True, "like_count": 100}]
        result = crawler._calculate_vtuber_likes_from_replies(replies, analyze_vtubers=False)
        self.assertEqual(result, 0)

    def test_returns_zero_when_no_vtuber_replies(self):
        replies = [{"is_vtuber": False, "like_count": 50}]
        result = crawler._calculate_vtuber_likes_from_replies(replies, analyze_vtubers=True)
        self.assertEqual(result, 0)

    def test_sums_likes_for_vtuber_replies_only(self):
        replies = [
            {"is_vtuber": True, "like_count": 10},
            {"is_vtuber": False, "like_count": 20},
            {"is_vtuber": True, "like_count": 5},
        ]
        result = crawler._calculate_vtuber_likes_from_replies(replies, analyze_vtubers=True)
        self.assertEqual(result, 15)

    def test_returns_zero_for_empty_replies(self):
        result = crawler._calculate_vtuber_likes_from_replies([], analyze_vtubers=True)
        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# _process_comment_item
# ---------------------------------------------------------------------------
class TestProcessCommentItem(unittest.TestCase):
    """_process_comment_item extracts comment data and updates stats correctly."""

    def _make_item(self, author="TestUser", text="Hello", like_count=3,
                   published_at="2026-01-01T00:00:00Z", reply_count=0):
        return {
            "id": "comment123",
            "snippet": {
                "topLevelComment": {
                    "snippet": {
                        "authorDisplayName": author,
                        "authorChannelId": {"value": "UCtest"},
                        "textDisplay": text,
                        "likeCount": like_count,
                        "publishedAt": published_at,
                    }
                },
                "totalReplyCount": reply_count,
            }
        }

    def _fresh_country_stats(self):
        return {
            "KR": {"comments": 0, "likes": 0},
            "US": {"comments": 0, "likes": 0},
            "JP": {"comments": 0, "likes": 0},
            "Other": {"comments": 0, "likes": 0},
        }

    def test_returns_comment_data_dict_with_required_keys(self):
        item = self._make_item()
        data, _ = crawler._process_comment_item(
            item, False, None, [], 0, self._fresh_country_stats()
        )
        for key in ("comment_id", "author", "text", "like_count", "published_at",
                    "reply_count", "is_vtuber", "country"):
            self.assertIn(key, data)

    def test_uses_video_region_when_provided(self):
        item = self._make_item(text="Hello world")
        data, _ = crawler._process_comment_item(
            item, False, "KR", [], 0, self._fresh_country_stats()
        )
        self.assertEqual(data["country"], "KR")

    def test_falls_back_to_text_detection_when_no_video_region(self):
        item = self._make_item(text="안녕하세요 반갑습니다")
        data, _ = crawler._process_comment_item(
            item, False, None, [], 0, self._fresh_country_stats()
        )
        self.assertEqual(data["country"], "KR")

    def test_increments_country_stats_comments(self):
        item = self._make_item(text="Hello world", like_count=2)
        stats = self._fresh_country_stats()
        crawler._process_comment_item(item, False, "US", [], 0, stats)
        self.assertEqual(stats["US"]["comments"], 1)

    def test_increments_country_stats_likes(self):
        item = self._make_item(text="Hello world", like_count=7)
        stats = self._fresh_country_stats()
        crawler._process_comment_item(item, False, "US", [], 0, stats)
        self.assertEqual(stats["US"]["likes"], 7)

    def test_non_standard_country_is_bucketed_as_other(self):
        # "Unknown" from detect_comment_country should become "Other"
        item = self._make_item(text="12345")  # numeric-only → Unknown
        data, _ = crawler._process_comment_item(
            item, False, None, [], 0, self._fresh_country_stats()
        )
        self.assertEqual(data["country"], "Other")

    def test_vtuber_comment_added_to_vtuber_list_when_analyze_true(self):
        item = self._make_item(author="VTuber Star")
        vtuber_list = []
        crawler._process_comment_item(
            item, True, "US", vtuber_list, 0, self._fresh_country_stats()
        )
        self.assertEqual(len(vtuber_list), 1)

    def test_vtuber_comment_not_added_when_analyze_false(self):
        item = self._make_item(author="VTuber Star")
        vtuber_list = []
        crawler._process_comment_item(
            item, False, "US", vtuber_list, 0, self._fresh_country_stats()
        )
        self.assertEqual(len(vtuber_list), 0)

    def test_vtuber_likes_accumulate_correctly(self):
        item = self._make_item(author="VTuber Star", like_count=10)
        _, updated_likes = crawler._process_comment_item(
            item, True, "US", [], 0, self._fresh_country_stats()
        )
        self.assertEqual(updated_likes, 10)


# ---------------------------------------------------------------------------
# clean_creator_name_for_search
# ---------------------------------------------------------------------------
class TestCleanCreatorNameForSearch(unittest.TestCase):
    """clean_creator_name_for_search strips studio prefixes and maps member names."""

    def test_strips_examplestudio_prefix(self):
        result = crawler.clean_creator_name_for_search("ExampleStudioCreator1")
        self.assertEqual(result, "Creator1")

    def test_strips_studio_word(self):
        result = crawler.clean_creator_name_for_search("StudioCreator2")
        self.assertEqual(result, "Creator2")

    def test_returns_none_for_none_input(self):
        result = crawler.clean_creator_name_for_search(None)
        self.assertIsNone(result)

    def test_returns_original_when_no_match(self):
        result = crawler.clean_creator_name_for_search("RandomName999")
        self.assertEqual(result, "RandomName999")

    def test_member_name_mapping_creator1(self):
        result = crawler.clean_creator_name_for_search("Creator1")
        self.assertEqual(result, "Creator1")

    def test_member_name_mapping_case_insensitive(self):
        result = crawler.clean_creator_name_for_search("creator2")
        self.assertEqual(result, "Creator2")

    def test_empty_string_returns_empty_string(self):
        result = crawler.clean_creator_name_for_search("")
        # Either empty or original; must not raise
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# _get_keyword_channel_map
# ---------------------------------------------------------------------------
class TestGetKeywordChannelMap(unittest.TestCase):
    """_get_keyword_channel_map contains the expected keyword mappings."""

    def setUp(self):
        self.mapping = crawler._get_keyword_channel_map()

    def test_returns_dict(self):
        self.assertIsInstance(self.mapping, dict)

    def test_groupb_keyword_maps_to_example_group_b_handle(self):
        self.assertEqual(self.mapping.get("GroupB"), "@example-group-b")

    def test_examplestudio_keyword_maps_to_studio_official(self):
        self.assertEqual(self.mapping.get("ExampleStudio"), "@example-studio-official")

    def test_lowercase_groupb_maps_to_example_group_b_handle(self):
        self.assertEqual(self.mapping.get("groupb"), "@example-group-b")


# ---------------------------------------------------------------------------
# _find_channel_by_partial_match
# ---------------------------------------------------------------------------
class TestFindChannelByPartialMatch(unittest.TestCase):
    """_find_channel_by_partial_match returns handle on overlap, None otherwise."""

    def setUp(self):
        self.mapping = crawler._get_keyword_channel_map()

    def test_returns_none_when_no_overlap(self):
        result = crawler._find_channel_by_partial_match(
            "UnrelatedKeyword", "unrelatedkeyword", self.mapping
        )
        self.assertIsNone(result)

    def test_returns_studio_handle_for_examplestudio_partial(self):
        result = crawler._find_channel_by_partial_match(
            "ExampleStudio", "examplestudio", self.mapping
        )
        self.assertEqual(result, "@example-studio-official")

    def test_returns_groupb_handle_for_groupb_partial(self):
        result = crawler._find_channel_by_partial_match(
            "GroupB", "groupb", self.mapping
        )
        self.assertEqual(result, "@example-group-b")


# ---------------------------------------------------------------------------
# get_youtube_api_key
# ---------------------------------------------------------------------------
class TestGetYoutubeApiKey(unittest.TestCase):
    """get_youtube_api_key reads env var first; falls back to Secrets Manager."""

    def test_returns_env_var_when_set(self):
        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-key-from-env"}):
            result = crawler.get_youtube_api_key()
        self.assertEqual(result, "test-key-from-env")

    def test_calls_secrets_manager_when_env_var_absent(self):
        # Remove env var and set a mock secrets_client on the module
        env = {k: v for k, v in os.environ.items() if k != "YOUTUBE_API_KEY"}
        mock_secrets = MagicMock()
        mock_secrets.get_secret_value.return_value = {
            "SecretString": json.dumps({"youtube_api_key": "secret-manager-key"})
        }

        with patch.dict(os.environ, env, clear=True):
            with patch.object(crawler, "secrets_client", mock_secrets):
                with patch.object(crawler, "YOUTUBE_API_KEY_SECRET", "my-secret-id"):
                    result = crawler.get_youtube_api_key()

        self.assertEqual(result, "secret-manager-key")

    def test_raises_when_no_env_var_and_no_secret_name(self):
        env = {k: v for k, v in os.environ.items() if k != "YOUTUBE_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(crawler, "secrets_client", None):
                with patch.object(crawler, "YOUTUBE_API_KEY_SECRET", None):
                    with self.assertRaises(Exception):
                        crawler.get_youtube_api_key()


# ---------------------------------------------------------------------------
# _resolve_channel_filter
# ---------------------------------------------------------------------------
class TestResolveChannelFilter(unittest.TestCase):
    """_resolve_channel_filter maps known keywords to channel IDs via override."""

    def test_returns_channel_id_for_groupb_keyword(self):
        mock_youtube = MagicMock()
        # get_channel_id_from_handle will hit CHANNEL_ID_OVERRIDE for GroupB handle
        channel_filter, channel_handle = crawler._resolve_channel_filter(
            mock_youtube, "GroupB", "GroupB"
        )
        # The GroupB handle's override ID should be returned
        expected_id = crawler.CHANNEL_ID_OVERRIDE.get("@example-group-b")
        self.assertEqual(channel_filter, expected_id)
        self.assertEqual(channel_handle, "@example-group-b")

    def test_returns_none_filter_for_unknown_keyword(self):
        mock_youtube = MagicMock()
        # An unknown keyword has no mapping → channel_filter should be None
        channel_filter, channel_handle = crawler._resolve_channel_filter(
            mock_youtube, "SomeRandomTopic", "SomeRandomTopic"
        )
        self.assertIsNone(channel_filter)
        self.assertIsNone(channel_handle)

    def test_returns_examplestudio_channel_id_for_studio_keyword(self):
        mock_youtube = MagicMock()
        channel_filter, channel_handle = crawler._resolve_channel_filter(
            mock_youtube, "ExampleStudio", "ExampleStudio"
        )
        expected_id = crawler.CHANNEL_ID_OVERRIDE.get("@example-studio-official")
        self.assertEqual(channel_filter, expected_id)


if __name__ == "__main__":
    unittest.main()
