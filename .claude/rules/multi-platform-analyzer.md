---
description: SNS Monitor multi-platform social media analyzer rules
globs: ["backend/**/*.py", "frontend/**/*.{js,jsx}", "crawlers/**/*.py", "docker/**/*"]
---

# Architecture

- Frontend: React 18 (port 3000) — Recharts, Axios
- Backend: Flask (port 8080) — Python 3.11
- Storage: Redis (cache) + local filesystem (fallback)
- Crawlers: YouTube, DCInside, Reddit, Telegram, Kakao (2-hour interval)

# Security (Hard Rules)

- No hardcoded secrets — `os.getenv()` only
- Validate ALL external input (whitelist approach)
- Logging module ONLY (no print statements)
- NO `eval()`, `exec()`, `pickle` — ever
- YouTube API key required for full functionality

# Development

- Quick start: `docker-compose up -d --build`
- Tests: `make test` (pytest for crawlers)
- Lint: `make lint` (Helm chart linting)
- Clean: `make clean`
- Dashboard: http://localhost:3000
- API health: http://localhost:8080/health

# API Endpoints

- `POST /api/analyze/url` — analyze any social media URL
- `GET /api/platforms` — list supported platforms
- `GET /api/health` — health check
- `GET /api/dashboard/stats` — aggregated statistics

# Environment

- `YOUTUBE_API_KEY` — required for YouTube analysis
- `LOCAL_MODE=true` — default; local JSON storage
- `REDIS_HOST=redis` — Redis connection
- `FLASK_DEBUG=false` — never true in production

# Infrastructure (Optional)

- K8s: `k8s/` manifests
- Helm: `helm/` charts
- Terraform: `terraform/` IaC
- Chrome extension: `chrome-extension/`
