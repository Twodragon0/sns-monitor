# AGENTS.md — Utility Scripts

<!-- Parent: ../AGENTS.md -->
Generated: 2026-04-08

## Overview

Standalone scripts for testing, debugging, data seeding, and deployment. Not part of the main application; used for validation and administrative tasks.

## Scripts

### deploy-k8s.sh

Kubernetes deployment automation script.

**Usage**:
```bash
./scripts/deploy-k8s.sh [namespace] [environment] [component]
# Examples:
./scripts/deploy-k8s.sh platform dev all
./scripts/deploy-k8s.sh platform prod backend
./scripts/deploy-k8s.sh platform prod frontend
```

**Arguments**:
- `namespace` (default: `platform`) — K8s namespace
- `environment` (default: `dev`) — `dev`, `prod`, `production` (selects values.yaml or values-production.yaml)
- `component` (default: `all`) — `all`, `backend`, `frontend`

**Steps**:
1. Verify kubeconfig
2. Confirm/create namespace
3. Build frontend (if needed)
4. Rollout restart backend OR Helm install (if not exists)
5. Rollout restart frontend OR Helm install (if not exists)
6. Verify pods, services, deployments

**For agents**: Run before K8s updates; validates kubeconfig and namespace setup.

### seed_sample_data.py

Populate local-data/ with sample YouTube/DCInside content for testing.

**Usage**:
```bash
python scripts/seed_sample_data.py [--youtube] [--dcinside] [--output path]
```

**Output**: Creates JSON files in `local-data/youtube/channels/` and `local-data/dcinside/`

**For agents**: Run after Docker setup to test dashboard without API keys.

### monitor_top_posts.py

Monitor trending posts from YouTube, DCInside, Twitter.

**Usage**:
```bash
python scripts/monitor_top_posts.py [--platform youtube|dcinside|twitter] [--days N]
```

**For agents**: Manual post monitoring; used for testing sentiment analysis.

### set_naver_cookie.py

Helper to set Naver Cafe login cookie for member-only content access.

**Usage**:
```bash
python scripts/set_naver_cookie.py --cookie "your_naver_cookie_here"
```

**Output**: Stores cookie in environment or `.env` file

**For agents**: Required for Naver Cafe crawler to access restricted posts.

### naver_cookie_helper.html

Browser bookmarklet HTML to extract Naver login cookie.

**Usage**: Open in browser, run bookmarklet, copy cookie from console

**For agents**: Simplifies cookie extraction without developer tools.

### test_naver_cafe.py

Unit tests for Naver Cafe crawler.

**Usage**:
```bash
python scripts/test_naver_cafe.py
# Or with pytest:
pytest scripts/test_naver_cafe.py -v
```

**Tests**:
- Cookie validation
- URL parsing
- Member list scraping
- Post fetching

**For agents**: Run to verify Naver integration before deployment.

### test_dcinside_comment.py

Unit tests for DCInside gallery scraper.

**Usage**:
```bash
python scripts/test_dcinside_comment.py
# Or with pytest:
pytest scripts/test_dcinside_comment.py -v
```

**Tests**:
- Gallery enumeration
- Post scraping
- Comment extraction
- Rate limit handling

**For agents**: Validates DCInside parser; run when scraper logic changes.

## Testing Workflow

1. **Local validation**:
   ```bash
   pytest scripts/test_naver_cafe.py -v
   pytest scripts/test_dcinside_comment.py -v
   ```

2. **Data seeding**:
   ```bash
   python scripts/seed_sample_data.py --youtube --dcinside
   docker-compose up -d
   curl http://localhost:8888/api/dashboard/stats
   ```

3. **K8s deployment**:
   ```bash
   ./scripts/deploy-k8s.sh platform dev all
   kubectl logs -n platform -l app.kubernetes.io/instance=sns-monitor -f
   ```

## Environment Variables (for scripts)

| Variable | Usage |
|----------|-------|
| `YOUTUBE_API_KEY` | `seed_sample_data.py`, `monitor_top_posts.py` |
| `NAVER_CAFE_COOKIE` | `test_naver_cafe.py`, `set_naver_cookie.py` |
| `KUBECONFIG` | `deploy-k8s.sh` (defaults to ~/.kube/config) |

## Common Tasks

**Test DCInside scraper**:
```bash
pytest scripts/test_dcinside_comment.py::test_parse_gallery -v
```

**Extract Naver cookie**:
```bash
# Use naver_cookie_helper.html in browser, then:
python scripts/set_naver_cookie.py --cookie "NID_AUT=..."
```

**Seed data for testing**:
```bash
python scripts/seed_sample_data.py --youtube --output ./local-data
docker-compose up -d api-backend frontend
curl http://localhost:8888/api/dashboard/stats | jq .
```

**Deploy to K8s staging**:
```bash
./scripts/deploy-k8s.sh platform staging all
```

## Related Files

- `backend/tests/` — Integration tests (45+ test files)
- `helm/sns-monitor/` — Helm deployment chart
- `docker-compose.yml` — Local dev environment
- `CLAUDE.md` — Configuration and environment setup
