<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-08 -->

# AGENTS.md — Crawlers

## Purpose

Periodic data collection via Docker CronJobs (2-hour intervals) for YouTube, DCInside, and Naver Cafe platforms. Each crawler runs independently and stores results in `local-data/` as JSON.

## Directory Structure

```
crawlers/
  youtube/
    crawler.py                # YouTube Data API v3 crawler
    optimized_youtube_api.py  # Batch API calls + caching
    local_storage.py          # JSON persistence
    run_crawler.py            # Entry point
    requirements.txt
  dcinside/
    crawler.py                # DCInside gallery scraper
    requirements.txt
  naver_cafe/
    crawler.py                # Naver Cafe crawler (cookie auth)
    requirements.txt
  common/
    local_storage.py          # Shared filesystem utilities
    timezone_utils.py         # KST/UTC conversion
```

## Key Components

**YouTube Crawler** (`youtube/`):
- Uses YouTube Data API v3 (YOUTUBE_API_KEY required)
- Optimized batch calls to reduce quota consumption
- Stores video stats, comment sentiment, channel metrics in `local-data/youtube/`
- Graceful quota exhaustion handling

**DCInside Crawler** (`dcinside/`):
- Scrapes gallery posts via HTML parsing
- Rate limiting: respects 429 responses (1-2 min backoff)
- Stores gallery metadata, post lists, sentiment in `local-data/dcinside/`

**Naver Cafe Crawler** (`naver_cafe/`):
- Members-only content requires `NAVER_CAFE_COOKIE` (sensitive, never log/commit)
- Cookie refresh mechanism for session persistence
- Stores cafe posts, member activity in `local-data/naver_cafe/`

**Common Utilities** (`common/`):
- `local_storage.py`: Atomic JSON write, read-with-fallback
- `timezone_utils.py`: KST/UTC conversion for timestamp normalization

## Agent Routing

For crawler issues, use `crawler-debugger` agent:

| Issue | Agent | Action |
|-------|-------|--------|
| Rate limit (429), auth failure, parse error | `crawler-debugger` | Diagnose + structured report |
| P0 security (secret exposure) | `crawler-debugger` → `security-reviewer` | Immediate escalation |
| New platform crawler | `sns-monitor-lead` → `backend-developer` | Feature implementation |

**When to delegate to crawler-debugger:**
```
- Crawler fails with 429, 401, or timeout
- JSON output corrupted or missing fields
- API quota exceeded or API schema change
- Cookie session expired (Naver Cafe)
```

## Environment Variables

| Variable | Crawler | Description |
|----------|---------|-------------|
| `YOUTUBE_API_KEY` | youtube | API key from https://console.cloud.google.com/apis/credentials |
| `NAVER_CAFE_COOKIE` | naver_cafe | Login cookie for member-only content (sensitive) |
| `LOCAL_DATA_DIR` | all | Data storage path (default: ./local-data) |
| `LOG_LEVEL` | all | Python logging level (default: INFO) |

## Testing

```bash
# Test individual crawler (from crawlers/ dir)
python youtube/run_crawler.py        # Requires YOUTUBE_API_KEY
python -m pytest dcinside/crawler.py -v
python -m pytest naver_cafe/crawler.py -v

# Test via Docker (from project root)
docker-compose --profile crawlers up -d
docker-compose logs youtube-crawler
docker-compose logs dcinside-crawler
docker-compose logs naver-cafe-crawler
```

## Security Rules

- **P0**: Never log `NAVER_CAFE_COOKIE` — treat as secret credential
- **P0**: No hardcoded API keys — use environment variables only
- **P0**: Validate all scraped URLs and IDs before storing (whitelist by platform)
- Rate limit respectfully: backoff on 429, don't hammer APIs
- Local data files (`local-data/`) must never contain unencrypted secrets
