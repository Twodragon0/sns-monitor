# Scripts Directory

This directory contains utility scripts for development, monitoring, and data management.

## Active Scripts

### Monitoring & Data Collection

- **monitor_top_posts.py** - Monitor top posts from various platforms
- **set_naver_cookie.py** - Set `NAVER_CAFE_COOKIE` in `.env` from paste/clipboard/browser

### Data Management

- **s3_sync.py** - Sync local data to/from S3 (used by CronJob)
- **migrate_local_to_s3.py** - Migrate local data to S3

### Deployment

- **deploy-k8s.sh** - Deploy to Kubernetes cluster

## Archive

The `archive/` subdirectory contains one-time data collection and migration scripts that were used during initial setup. These scripts are kept for reference but are not needed for regular operation:

- `collect_*.py` - One-time data collection scripts
- `update_*.py` - One-time data migration scripts
- `add_*.py` - One-time data addition scripts
- `crawl_*.py` - Experimental crawler scripts

## Usage Examples

### Monitoring

```bash
# Monitor top posts
python3 scripts/monitor_top_posts.py

# Set NAVER_CAFE_COOKIE from pasted cookie/cURL text
python3 scripts/set_naver_cookie.py

# Set NAVER_CAFE_COOKIE from clipboard
python3 scripts/set_naver_cookie.py --clipboard

# Recommended: apply from clipboard and restart API in one step
python3 scripts/set_naver_cookie.py --clipboard --restart-api

# Optional: read cookie directly from local browser profile
pip install browser-cookie3
python3 scripts/set_naver_cookie.py --from-browser chrome

# Auto-probe latest article IDs and retry single-post verification
python3 scripts/test_naver_cafe.py "https://cafe.naver.com/f-e/cafes/31581843/menus/0?viewType=L" --show-fetch-diagnostics --auto-find-article

# Tune menu scan range and candidate count (cache enabled by default)
python3 scripts/test_naver_cafe.py "https://cafe.naver.com/f-e/cafes/31581843/menus/0?viewType=L" \
  --show-fetch-diagnostics --auto-find-article --menu-range 1-80 --max-candidates 20

# Strict success mode: require comment collection
python3 scripts/test_naver_cafe.py "https://cafe.naver.com/f-e/cafes/31581843/menus/0?viewType=L" \
  --show-fetch-diagnostics --auto-find-article --require-comments
```

### S3 Sync

```bash
# Backup local data to S3
python3 scripts/s3_sync.py

# Restore from S3
SYNC_MODE=restore python3 scripts/s3_sync.py

# Dry run
DRY_RUN=true python3 scripts/s3_sync.py
```

## Script Categories

| Category | Scripts | Purpose |
|----------|---------|---------|
| **Monitoring** | `monitor_*.py` | Data collection and monitoring |
| **Data Sync** | `s3_sync.py`, `migrate_*.py` | Data backup and migration |
| **Deployment** | `deploy-k8s.sh` | Kubernetes deployment |

## Notes

- All scripts should be run from the project root directory
- Environment variables may be required (check script headers)
- Some scripts require API keys (YouTube, etc.)
- Archive scripts are preserved for historical reference only

---

**Last Updated**: 2026-03-10
