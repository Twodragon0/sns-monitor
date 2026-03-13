# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SNS Monitor - A multi-platform social media content analyzer. Paste any URL from YouTube, DCInside, Reddit, Telegram, or Kakao to analyze content and sentiment.

**Tech Stack:**
- Frontend: React 18 with Recharts, Axios
- Backend: Python 3.11 with Flask
- Storage: Redis (cache), local filesystem
- Infrastructure: Docker, Kubernetes (optional), Terraform (optional), Helm (optional)

## Quick Start (Docker)

```bash
# 1. Setup
cp .env.example .env
# Edit .env → set YOUTUBE_API_KEY (get from https://console.cloud.google.com/apis/credentials)

# 2. Run
docker-compose up -d --build

# 3. Access
# Dashboard: http://localhost:3080
# URL Analyzer: http://localhost:3080
# API Health: http://localhost:8888/health

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
User → Frontend (host :3080)
         ↓ /api/*
       API Backend (host :8888)
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
- `*Detail.jsx` - Creator detail pages (one per monitored creator)

**API Endpoints:**
- `POST /api/analyze/url` - Analyze any supported URL `{"url": "https://..."}`
- `GET /api/platforms` - List supported platforms
- `GET /api/health` - Health check
- `GET /api/dashboard/stats` - Dashboard statistics
- `GET /api/dcinside/galleries` - DCInside gallery data
- `GET /api/{group}/members` - Creator group members
- **수집 데이터 분석·요약 (MiroFish):** `app/api/analysis.py` - `GET /api/analysis/status`, `GET /api/analysis/sources`, `POST /api/analysis/transform`, `POST /api/analysis/graph/build`, `GET /api/analysis/graph/task/<id>`, `GET /api/analysis/graph/data/<id>`, `POST /api/analysis/report/chat`. Frontend: `/analysis` (AnalysisTab.jsx). 대시보드 전체 개요 탭에서 「수집 데이터 분석·요약」 카드로 진입.

### Supported Platforms (URL Analysis)

| Platform | URL Pattern | Analysis |
|----------|------------|----------|
| YouTube | youtube.com, youtu.be | Video comments, channel stats |
| DCInside | gall.dcinside.com | Gallery posts, sentiment |
| Reddit | reddit.com/r/ | Subreddit/post comments |
| Telegram | t.me/ | Public channel messages |
| Kakao | pf.kakao.com, story.kakao.com | Profile info |
| Naver Cafe | cafe.naver.com (f-e/cafes/ID/menus/0, ArticleRead.nhn) | Cafe posts and comments (NAVER_CAFE_COOKIE recommended) |

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

## Centralized Hourly Automation

- Central scheduler and pull runner: `$HOME/Desktop/.twodragon0/bin/hourly-opencode-git-pull.sh`
- Central OpenClaw cron registration: `$HOME/Desktop/.twodragon0/bin/install-system-cron.sh`
- Central prompt: `$HOME/Desktop/.twodragon0/openclaw_ultrawork_prompt.md`
- Central repo registry: `$HOME/Desktop/.twodragon0/repos.list`
- Use `$HOME`-based paths for user portability across machines.
- Per-repo OpenClaw/OpenCode cron scripts are not used.
