# Scripts Directory

This directory contains utility scripts for development, testing, monitoring, and data management.

## 🚀 Active Production Scripts

### Development & Testing

- **start_local_api.py** - Start local API server for development
- **test_local.py** - Test local setup and API endpoints
- **start_local_api_docker.sh** - Start local API server using Docker
- **start_local_dev.sh** - Start local development environment

### Monitoring & Data Collection

- **monitor_dcinside.py** - Monitor DCInside galleries and collect posts/comments
- **monitor_top_posts.py** - Monitor top posts from various platforms
- **schedule-dcinside-crawl.sh** - Schedule DCInside crawler execution

### Data Management

- **s3_sync.py** - Sync local data to/from S3 (used by CronJob)
- **migrate_local_to_s3.py** - Migrate local data to S3

### Data Update Scripts

These scripts update creator/member data and may be run periodically:

- **update_akaiv_members.py** - Update AkaiV Studio members data
- **update_barabara_members.py** - Update BARABARA members data
- **update_skoshism_data.py** - Update SKOSHISM data
- **update_skoshism_summary.py** - Update SKOSHISM summary
- **update_all_members_json.py** - Update all members JSON files
- **update_video_published_dates.py** - Update video published dates from YouTube API

## 📦 Archive

The `archive/` subdirectory contains one-time data collection and migration scripts that were used during initial setup. These scripts are kept for reference but are not needed for regular operation:

- `collect_*.py` - One-time YouTube data collection scripts
- `update_*.py` - One-time data migration scripts  
- `add_*.py` - One-time data addition scripts
- `crawl_*.py` - Experimental crawler scripts
- `test_*.py` - One-time test scripts

These scripts have already been executed and the data is now managed through the main application.

## 📋 Usage Examples

### Local Development

```bash
# Start local API server
python3 scripts/start_local_api.py

# Test local setup
python3 scripts/test_local.py

# Start with Docker
./scripts/start_local_api_docker.sh
```

### Monitoring

```bash
# Monitor DCInside galleries
python3 scripts/monitor_dcinside.py --galleries akaiv ivnit

# Monitor top posts
python3 scripts/monitor_top_posts.py
```

### Data Updates

```bash
# Update all members data
python3 scripts/update_all_members_json.py

# Update specific creator
python3 scripts/update_akaiv_members.py
python3 scripts/update_skoshism_data.py
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

## 🔧 Script Categories

| Category | Scripts | Purpose |
|----------|---------|---------|
| **Development** | `start_local_*.py/sh` | Local development setup |
| **Testing** | `test_local.py` | Test and verify setup |
| **Monitoring** | `monitor_*.py` | Data collection and monitoring |
| **Data Updates** | `update_*.py` | Update creator/member data |
| **Data Sync** | `s3_sync.py`, `migrate_*.py` | Data backup and migration |
| **Scheduling** | `schedule-*.sh` | Cron job scripts |

## 📝 Notes

- All scripts should be run from the project root directory
- Environment variables may be required (check script headers)
- Some scripts require API keys (YouTube, etc.)
- Archive scripts are preserved for historical reference only

---

**Last Updated**: 2025-12-29
