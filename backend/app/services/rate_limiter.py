"""
Rate limiter service with Redis-backed storage and in-memory fallback.
Extracted from PlatformAnalyzer to separate concerns.
"""

import logging
import os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class RateLimiterService:
    """Unified rate limit tracking for external API calls.

    Uses Redis when available, falls back to in-memory counters.
    Supports daily windows (YouTube, Naver) and 10-minute windows (Reddit).
    """

    _RATE_KEY_TPL = "sns:{service}:count:{window}"

    _API_LIMITS = {
        "naver_search": {"limit": 25000, "window": "daily", "ttl": 90000},
        "youtube": {"limit": 10000, "window": "daily", "ttl": 90000},
        "reddit": {"limit": 600, "window": "10min", "ttl": 660},
    }

    def __init__(self, redis_client=None):
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def window(self, service: str) -> str:
        """Return the current window key for the given service."""
        cfg = self._API_LIMITS.get(service, {})
        if cfg.get("window") == "10min":
            now = datetime.now(KST)
            slot = now.minute // 10
            return f"{now.strftime('%Y-%m-%d')}T{now.hour:02d}:{slot}"
        return datetime.now(KST).strftime("%Y-%m-%d")

    def get(self, service: str) -> int:
        """Get current call count for a service."""
        win = self.window(service)
        if self._redis:
            try:
                val = self._redis.get(
                    self._RATE_KEY_TPL.format(service=service, window=win)
                )
                return int(val) if val else 0
            except Exception as e:
                logger.debug("Redis rate_get failed for %s: %s", service, e)
        # In-memory fallback
        mem = getattr(self, f"_mem_{service}", None) or {"window": "", "count": 0}
        if mem["window"] != win:
            return 0
        return mem["count"]

    def increment(self, service: str) -> None:
        """Increment call count for a service."""
        win = self.window(service)
        ttl = self._API_LIMITS.get(service, {}).get("ttl", 90000)
        if self._redis:
            try:
                rkey = self._RATE_KEY_TPL.format(service=service, window=win)
                pipe = self._redis.pipeline()
                pipe.incr(rkey)
                pipe.expire(rkey, ttl)
                results = pipe.execute()
                if results is None or len(results) < 2 or results[0] is None:
                    logger.warning(
                        "Redis pipeline partial failure for rate key %s: %s",
                        rkey,
                        results,
                    )
                return
            except Exception as e:
                logger.debug("Redis rate_incr failed for %s: %s", service, e)
        # In-memory fallback
        key = f"_mem_{service}"
        mem = getattr(self, key, None) or {"window": "", "count": 0}
        if mem["window"] != win:
            mem = {"window": win, "count": 0}
        mem["count"] += 1
        setattr(self, key, mem)

    def check(self, service: str):
        """Check if service is within rate limit. Returns (allowed, count, limit)."""
        cfg = self._API_LIMITS.get(service, {})
        limit = cfg.get("limit", 999999)
        count = self.get(service)
        return count < limit, count, limit

    def get_usage(self, *, naver_configured: bool, youtube_configured: bool, reddit_configured: bool) -> dict:
        """Return API usage stats for all rate-limited services."""
        today = datetime.now(KST).strftime("%Y-%m-%d")
        storage = "redis" if self._redis else "memory"

        def _build(service: str, configured: bool) -> dict:
            cfg = self._API_LIMITS[service]
            count = self.get(service)
            limit = cfg["limit"]
            window_label = "일일" if cfg["window"] == "daily" else "10분"
            return {
                "configured": configured,
                "daily_limit": limit,
                "used_today": count,
                "remaining": max(0, limit - count),
                "window": window_label,
                "date": today,
                "storage": storage,
            }

        return {
            "naver_search": _build("naver_search", naver_configured),
            "youtube": _build("youtube", youtube_configured),
            "reddit": _build("reddit", reddit_configured),
        }
