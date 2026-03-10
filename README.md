# SNS Monitor

Multi-platform social media content analyzer with sentiment analysis.

[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docs.docker.com/compose/)

## Features

- **URL Analyzer** - Paste any URL to analyze content and sentiment
- **Multi-platform** - YouTube, DCInside, Reddit, Telegram, Kakao
- **Sentiment Analysis** - Automatic Korean/English sentiment detection with charts
- **Dashboard** - Real-time monitoring with aggregated statistics
- **Periodic Crawling** - Optional CronJob crawlers for continuous data collection

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/your-org/sns-monitor.git
cd sns-monitor
cp .env.example .env
# Edit .env → set YOUTUBE_API_KEY

# 2. Run
docker-compose up -d --build

# 3. Open
# Dashboard: http://localhost:3000
# URL Analyzer: http://localhost:3000/analyze
# API: http://localhost:8080/health
```

**Only requirement:** Docker and a [YouTube API key](https://console.cloud.google.com/apis/credentials).

## Supported Platforms

| Platform | URL Pattern | What's Analyzed |
|----------|------------|----------------|
| YouTube | `youtube.com/watch?v=`, `youtu.be/`, `@channel` | Video comments, channel stats |
| DCInside | `gall.dcinside.com` | Gallery posts, sentiment |
| Reddit | `reddit.com/r/` | Subreddit posts, comments |
| Telegram | `t.me/channel` | Public channel messages |
| Kakao | `pf.kakao.com`, `story.kakao.com` | Profile information |

## Architecture

```
Frontend (React :3000)
  ↓ /api/*
API Backend (Flask :8080)
  ├── /api/analyze/url    → Platform Analyzer (URL-based)
  ├── /api/platforms      → Supported platforms list
  ├── /api/dashboard/*    → Dashboard data
  └── /api/dcinside/*     → Gallery data
  ↓
Redis (cache) + local-data/ (JSON storage)
  ↑
CronJob Crawlers (optional, every 2 hours)
```

## API Usage

```bash
# Analyze a YouTube video
curl -X POST http://localhost:8080/api/analyze/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# Analyze a Reddit subreddit
curl -X POST http://localhost:8080/api/analyze/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.reddit.com/r/programming"}'

# List supported platforms
curl http://localhost:8080/api/platforms
```

## Project Structure

```
├── backend/                  # Flask API server
│   ├── app.py                # Application entry point
│   ├── api_handlers.py       # REST API route handlers
│   ├── platform_analyzer.py  # Multi-platform URL analyzer
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

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `YOUTUBE_API_KEY` | Yes | [YouTube Data API v3 key](https://console.cloud.google.com/apis/credentials) |
| `LOCAL_MODE` | No | Use local filesystem (default: `true`) |
| `REDIS_HOST` | No | Redis hostname (default: `redis`) |
| `FLASK_DEBUG` | No | Enable debug mode (default: `false`) |

## Optional: Periodic Crawlers

```bash
# Start crawlers alongside the main services
docker-compose --profile crawlers up -d

# Crawlers collect data every 2 hours from configured channels
```

## License

MIT
