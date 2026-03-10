# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SNS Monitor - A multi-platform social media content analyzer. Paste any URL from YouTube, DCInside, Reddit, Telegram, or Kakao to analyze content and sentiment.

**Tech Stack:**
- Frontend: React 18 with Recharts, Axios
- Backend: Python 3.11 with Flask
- Storage: Redis (cache), local filesystem
- Infrastructure: Docker, Kubernetes (optional), Terraform (optional), Helm (optional)

## Quick Start (Local)

```bash
# 1. Setup
cp .env.example .env
# Edit .env → set YOUTUBE_API_KEY (get from https://console.cloud.google.com/apis/credentials)

# 2. Run (only Docker required)
docker-compose up -d --build

# 3. Access
# Dashboard: http://localhost:3000
# URL Analyzer: http://localhost:3000/analyze
# API Health: http://localhost:8080/health

# 4. Optional: Run crawlers for periodic data collection
docker-compose --profile crawlers up -d
```

## Common Commands

```bash
make build                # Build all Docker images
make test                 # Run pytest for crawlers
make lint                 # Lint Helm chart
make clean                # Clean up Docker images and volumes
```

## Architecture

```
User → Frontend (React :3000)
         ↓ /api/*
       API Backend (Flask :8080)
         ├── Platform Analyzer (URL-based analysis)
         ├── Redis (cache, optional)
         └── local-data/ (JSON storage)
              ↑
       CronJob Crawlers (optional, every 2 hours)
```

### Project Structure

```
├── backend/                  # Flask API server
│   ├── run.py                # Entry point
│   ├── api_handlers.py       # Legacy API route handlers
│   ├── app/
│   │   ├── __init__.py       # Flask app factory (create_app)
│   │   ├── config.py         # Centralized configuration
│   │   ├── api/
│   │   │   ├── analyze.py    # /api/analyze/url, /api/platforms
│   │   │   └── legacy.py     # Bridge to api_handlers
│   │   ├── services/
│   │   │   ├── platform_analyzer.py  # Multi-platform URL analyzer
│   │   │   └── redis_client.py       # Redis with graceful fallback
│   │   └── utils/
│   │       └── logger.py     # Logging configuration
│   └── requirements.txt      # Python dependencies
├── crawlers/                 # Periodic data collection
│   ├── youtube/              # YouTube Data API crawler
│   ├── dcinside/             # DCInside gallery scraper
│   └── common/               # Shared utilities
├── frontend/                 # React 18 dashboard
│   └── src/components/
│       ├── URLAnalyzer.jsx   # URL analysis UI
│       ├── Dashboard.jsx     # Main dashboard
│       └── *Detail.jsx       # Creator detail pages
├── docker/                   # Dockerfiles
├── helm/                     # Kubernetes Helm chart (optional)
├── terraform/                # AWS infrastructure (optional)
└── docker-compose.yml        # Local development
```

### Key Components

**Backend** (`backend/`):
- `run.py` - Entry point, creates Flask app via factory
- `app/__init__.py` - Flask app factory (`create_app()`)
- `app/config.py` - Centralized configuration (Config class)
- `app/api/analyze.py` - URL analysis routes
- `app/api/legacy.py` - Bridge to legacy api_handlers
- `app/services/platform_analyzer.py` - Multi-platform URL analyzer
- `api_handlers.py` - Legacy API handlers (dashboard, members, galleries)

**Frontend** (`frontend/src/components/`):
- `URLAnalyzer.jsx` - URL input and analysis results with sentiment charts
- `Dashboard.jsx` - Main monitoring dashboard
- Detail pages: `ArchiveStudioDetail`, `BarabaraDetail`, `PsyChordDetail`, `SkoshismDetail`

**API Endpoints:**
- `POST /api/analyze/url` - Analyze any supported URL `{"url": "https://..."}`
- `GET /api/platforms` - List supported platforms
- `GET /api/health` - Health check
- `GET /api/dashboard/stats` - Dashboard statistics
- `GET /api/dcinside/galleries` - DCInside gallery data
- `GET /api/{group}/members` - Creator group members

### Supported Platforms (URL Analysis)

| Platform | URL Pattern | Analysis |
|----------|------------|----------|
| YouTube | youtube.com, youtu.be | Video comments, channel stats |
| DCInside | gall.dcinside.com | Gallery posts, sentiment |
| Reddit | reddit.com/r/ | Subreddit/post comments |
| Telegram | t.me/ | Public channel messages |
| Kakao | pf.kakao.com, story.kakao.com | Profile info |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `YOUTUBE_API_KEY` | Yes | YouTube Data API v3 key |
| `LOCAL_MODE` | No | Use local filesystem (default: true) |
| `REDIS_HOST` | No | Redis hostname (default: redis) |
| `FLASK_DEBUG` | No | Enable Flask debug mode (default: false) |

## Security Requirements

- No hardcoded secrets - use `os.getenv()`, K8s Secrets, environment variables
- Validate all external input (whitelist approach)
- Use `logging` module instead of `print()` in Python
- No `eval()`, `exec()`, `pickle`
