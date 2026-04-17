# AGENTS.md — Docker Containers

<!-- Parent: ../AGENTS.md -->
Generated: 2026-04-08

## Overview

SNS Monitor runs 4 main services as Docker containers. Backend listens on port 8080 internally, exposed as 8888 externally. Frontend builds with Vite, served by nginx on 3080.

## Service Architecture

| Service | Dockerfile | Port (Internal) | Port (External) | Runtime |
|---------|-----------|-----------------|-----------------|---------|
| API Backend | Dockerfile.api | 8080 | 8888 (nginx) | Python 3.11, Flask, gunicorn |
| Frontend | Dockerfile.frontend | 3000 | 3080 (nginx) | Node 20, React 19, Vite |
| YouTube Crawler | Dockerfile.youtube-crawler | — | — | Python 3.11, CronJob |
| DCInside Crawler | Dockerfile.crawler | — | — | Python 3.11, CronJob |
| Naver Crawler | Dockerfile.naver-crawler | — | — | Python 3.11, CronJob |
| Redis | official image | 6379 | 6379 | Cache (optional, graceful fallback) |

## Dockerfile.api

**Base**: python:3.11-slim-bookworm

**Key points**:
- Installs Python dependencies from `backend/requirements.txt`
- Creates directory structure: `/app/local-data/`, `/app/logs/`
- Installs Playwright Chromium for DCInside fallback scraping
- Non-root user: `appuser`
- Exposes: 8080
- Healthcheck: `GET /health` every 30s
- CMD: `python run.py` (gunicorn entry)

**For agents**: Modify requirements.txt, then rebuild: `docker-compose build api-backend`

## Dockerfile.frontend

**Base**: node:20-alpine (build stage) → nginx:1.25-alpine (runtime)

**Build stage**:
- Installs npm dependencies
- Builds with Vite: `npm run build`
- Output: `dist/` (SPA with index.html, assets/)

**Runtime stage**:
- Copies nginx.conf and dist/ files
- Exposes: 3000 (note: external mapping to 3080)
- CMD: nginx

**For agents**: Modify React code, rebuild: `docker-compose build frontend`. Vite HMR disabled in Docker.

## Dockerfile.youtube-crawler & Dockerfile.crawler

**Base**: python:3.11-slim-bookworm

**Purpose**: Scheduled crawlers run as CronJobs in K8s or periodic containers in Docker Compose.

- YouTube: Uses `YOUTUBE_API_KEY`, stores to `/app/local-data/youtube/channels/`
- DCInside: Scrapes galleries, stores to `/app/local-data/dcinside/`
- Naver: Uses `NAVER_CAFE_COOKIE`, stores cafe data

**For agents**: No exposed ports. Triggered by schedule, logs to stdout/stderr.

## nginx.conf & nginx-frontend.conf

**nginx.conf**: Reverse proxy for API backend (port 8888 → 8080)

**nginx-frontend.conf**: Serves React SPA, proxies /api/* to backend

**Key routing**:
```
/ → static SPA files (dist/)
/api/* → http://api-backend:8080/api/*
```

**For agents**: Modify listen port, upstream URL, or cache headers in these files.

## entrypoint.local.sh

Entry script for local development. Typically sets environment and starts services.

## Key Commands

```bash
# Build all images
docker-compose build

# Start all services
docker-compose up -d --build

# Start with crawlers
docker-compose --profile crawlers up -d

# View logs
docker-compose logs -f api-backend
docker-compose logs -f frontend

# Health check
curl http://localhost:8888/health
curl http://localhost:3080

# Stop all
docker-compose down -v
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Backend returns 502 | Flask not responding | Check: `docker-compose logs api-backend` |
| Frontend blank page | Vite build failed | Rebuild: `docker-compose build frontend` |
| Crawler timeout | Rate limit or auth | Verify: `YOUTUBE_API_KEY`, `NAVER_CAFE_COOKIE` |
| nginx permission denied | Non-root temp paths | Check: /tmp/ writable, check logs in /tmp/nginx-error.log |

## Related Files

- `docker-compose.yml` — Service definitions and port mappings
- `backend/requirements.txt` — Python dependencies
- `frontend/package.json` — Node dependencies
- `helm/sns-monitor/` — K8s deployment (optional production)
