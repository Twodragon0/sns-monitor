# Scripts Directory

This directory contains utility scripts for development, monitoring, and data management.

## Active Scripts

### Monitoring & Data Collection

- **monitor_top_posts.py** - Monitor top posts from various platforms

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
