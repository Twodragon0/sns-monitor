# SNS Monitor - Architecture

## Overview

SNS Monitor analyzes social media content from multiple platforms via URL input. It provides sentiment analysis, keyword extraction, and aggregated statistics through a React dashboard.

## System Architecture

```
┌──────────────────────────────────────────────────┐
│                    Frontend                       │
│              React 18 (Nginx :3000)               │
│                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │  Dashboard   │  │ URL Analyzer │  │  Detail   │ │
│  │              │  │              │  │  Pages    │ │
│  └──────────────┘  └──────────────┘  └──────────┘ │
└───────────────────────┬──────────────────────────┘
                        │ /api/*
┌───────────────────────▼──────────────────────────┐
│                  API Backend                      │
│               Flask (Python :8080)                │
│                                                   │
│  ┌──────────────────┐  ┌────────────────────────┐ │
│  │  API Handlers     │  │  Platform Analyzer     │ │
│  │  (api_handlers)   │  │  YouTube | DCInside    │ │
│  │  Dashboard stats  │  │  Reddit  | Telegram    │ │
│  │  Members data     │  │  Kakao   | Sentiment   │ │
│  └──────────────────┘  └────────────────────────┘ │
└───────┬───────────────────────────┬──────────────┘
        │                           │
   ┌────▼─────┐              ┌─────▼──────┐
   │  Redis    │              │ local-data/ │
   │  (cache)  │              │   (JSON)    │
   └──────────┘              └─────▲──────┘
                                   │
                        ┌──────────┴──────────┐
                        │  CronJob Crawlers    │
                        │  YouTube | DCInside  │
                        │  (optional, 2h)      │
                        └─────────────────────┘
```

## Project Structure

```
sns-monitor/
├── backend/                    # Flask API server
│   ├── app.py                  # Entry point, route setup
│   ├── api_handlers.py         # API route handlers (dashboard, members, galleries)
│   ├── platform_analyzer.py    # Multi-platform URL analyzer with sentiment
│   └── requirements.txt        # Python dependencies
├── crawlers/                   # Periodic data collection services
│   ├── youtube/                # YouTube Data API v3 crawler
│   ├── dcinside/               # DCInside gallery scraper (Playwright)
│   └── common/                 # Shared utilities (storage, timezone)
├── frontend/                   # React 18 SPA
│   └── src/
│       ├── App.js              # Custom pathname-based routing
│       └── components/         # UI components
├── docker/                     # Dockerfiles and nginx config
├── helm/sns-monitor/           # Kubernetes Helm chart
├── k8s/                        # Raw Kubernetes manifests
├── terraform/                  # AWS infrastructure (optional)
├── scripts/                    # Utility scripts
└── docker-compose.yml          # Local development orchestration
```

## Data Flow

### URL Analysis (On-demand)
1. User enters URL in frontend
2. Frontend POSTs to `/api/analyze/url`
3. `PlatformAnalyzer.detect_platform()` identifies platform from URL
4. Platform-specific analyzer fetches content (API or scraping)
5. `_analyze_sentiment()` runs keyword-based sentiment analysis
6. Results saved to `local-data/analysis/{platform}/` and returned

### Periodic Crawling (Optional)
1. CronJob crawlers run every 2 hours
2. YouTube crawler uses Data API v3 to fetch channel/video data
3. DCInside crawler uses Playwright for browser-based scraping
4. Data written to `local-data/` as JSON files
5. API backend reads from `local-data/` for dashboard stats

## Key Design Decisions

- **No react-router**: Custom pathname-based routing in App.js for simplicity
- **Lambda handler adapter**: `api_handlers.py` uses Lambda event format internally, proxied by Flask `app.py` for backward compatibility
- **Lazy imports**: Platform analyzer and Redis are lazily initialized
- **Graceful degradation**: Works without Redis, crawlers are optional
- **Local-first storage**: JSON files on disk, no database required
