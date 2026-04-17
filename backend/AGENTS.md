<!-- Parent: ../AGENTS.md -->

# AGENTS.md — Backend (Flask API)

Generated: 2026-04-08

## Quick Start

```bash
# From /backend
python -m pytest tests/ -v --cov=app --cov-fail-under=95  # Run tests
python run.py                                              # Dev (Flask)
gunicorn -b 0.0.0.0:8080 app:create_app()                # Prod (gunicorn)
```

## Directory Structure

```
backend/
  run.py                          # Flask entry point (gunicorn)
  requirements.txt
  app/
    __init__.py                   # create_app() factory; Limiter, CORS, health routes
    config.py                     # Config class — env 변수 중앙 관리
    api/
      __init__.py                 # Blueprint 정의, csrf_protect 데코레이터
      analyze.py                  # POST /api/analyze/url, GET /api/platforms
      analysis.py                 # MiroFish 브리지 + 로컬 LLM 분석
      auth.py                     # OAuth 2.0 PKCE, API key 세션
      dashboard.py                # GET /api/dashboard/stats, /api/scans
      members.py                  # GET /api/<group>/members
      vuddy.py                    # GET /api/vuddy/creators
      dcinside.py                 # GET /api/dcinside/galleries
      data.py                     # GET /api/data, /api/crawler/results
    services/
      platform_analyzer.py        # PlatformAnalyzer: URL→플랫폼 감지 및 분석
      sentiment.py                # 키워드 기반 감성 분석 유틸
      local_data.py               # 로컬 파일시스템 JSON I/O
      redis_client.py             # Redis (graceful fallback to None)
      llm_analyzer.py             # LLM 분석: OpenAI/Anthropic API
      platforms/
        youtube.py                # YouTube Data API v3
        dcinside.py               # DCInside 갤러리 스크래퍼
        reddit.py                 # Reddit API (OAuth2)
        naver_cafe.py             # 네이버 카페 크롤러
        twitter.py                # X(Twitter) API v2
        threads.py                # Meta Threads API
        other_platforms.py        # Telegram, Kakao 등
    utils/
      logger.py                   # setup_logger() / get_logger()
  tests/                          # 45개 테스트 파일, pytest, coverage ≥ 95%
```

## For AI Agents

### Configuration
- **Always** use `app/config.py` Config class for env variables
- Access via: `from app.config import Config; api_key = Config.YOUTUBE_API_KEY`
- Or directly: `os.getenv('YOUTUBE_API_KEY')`
- Never hardcode secrets

### Logging
- **Always** use `logging` module, never `print()`
- `from app.utils.logger import get_logger; logger = get_logger(__name__)`

### CSRF Protection
- **Always** apply `@csrf_protect` decorator to POST/PUT/DELETE routes
- Import: `from app.api import csrf_protect`
- Example: `@analyze_bp.route("/api/analyze/url", methods=["POST"]) @csrf_protect`

### Path Parameter Validation
- Use `_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{1,128}$')` for path IDs
- Prevents path traversal attacks
- Validate before processing: `if not _SAFE_ID_RE.match(group_id): raise ValueError(...)`

### Forbidden Patterns
- NO `eval()`, `exec()`, `pickle` usage
- NO `print()` statements (use logging)
- NO hardcoded secrets

### Redis Graceful Fallback
- All Redis calls must handle `None` client
- Example: `if redis_client: redis_client.get(...) else: load_from_disk(...)`
- System must work completely offline (local-data/ fallback)

## Testing

```bash
# Full coverage check (must be ≥ 95%)
python -m pytest tests/ -v --tb=short \
    --cov=app --cov-report=term-missing --cov-fail-under=95

# Specific test file
python -m pytest tests/test_platform_analyzer.py -v

# Coverage report (HTML)
python -m pytest tests/ --cov=app --cov-report=html
```

**Requirements:**
- 45+ test files (pytest)
- Coverage ≥ 95% mandatory
- Unit + integration + E2E tests required
- Add tests when adding new platform analyzers

## Agent Assignments

| Task | Agent |
|------|-------|
| New platform analyzer | `backend-developer` + `test-engineer` |
| API route changes | `backend-developer` |
| Flask/config refactor | `backend-developer` + `architecture` |
| LLM/OAuth integration | `backend-developer` + `security-reviewer` |
| Crawler issues | `crawler-debugger` (escalate from here) |
| Security review | `security-reviewer` |
| Test coverage gaps | `test-engineer` |

## Key Dependencies

| Package | Version | Role |
|---------|---------|------|
| Flask | ^3.0 | Web framework |
| flask-limiter | ^3.x | Rate limiting |
| flask-cors | ^4.x | CORS headers |
| requests | ^2.31 | HTTP client |
| beautifulsoup4 | ^4.12 | HTML parsing |
| redis | ^5.x | Cache (optional) |
| openai | ^1.x | OpenAI API (optional) |
| anthropic | ^0.x | Anthropic API (optional) |

See `requirements.txt` for full list and versions.

## Environment Variables (Backend-Specific)

| Variable | Required | Notes |
|----------|----------|-------|
| `YOUTUBE_API_KEY` | Yes | YouTube Data API v3 |
| `SECRET_KEY` | Prod | Flask session signing key |
| `REDIS_HOST` | No | Default: redis |
| `REDIS_PASSWORD` | No | If Redis auth required |
| `FLASK_DEBUG` | No | Default: false |
| `LOCAL_MODE` | No | Default: true (local filesystem) |
| `LOCAL_DATA_DIR` | No | Default: ./local-data |
| `NAVER_CAFE_COOKIE` | No | Sensitive — members-only content |
| `TWITTER_BEARER_TOKEN` | No | X(Twitter) API v2 |
| `THREADS_ACCESS_TOKEN` | No | Meta Threads API |
| `OPENAI_API_KEY` | No | Local LLM analysis |
| `ANTHROPIC_API_KEY` | No | Local LLM analysis |

## Security Checklist

- [ ] No hardcoded secrets (use Config/os.getenv)
- [ ] All POST/PUT/DELETE routes have `@csrf_protect`
- [ ] Path IDs validated with `_SAFE_ID_RE`
- [ ] External URLs validated (whitelist per platform)
- [ ] Redis graceful fallback implemented
- [ ] Rate limiting enabled (`flask-limiter`)
- [ ] Error messages don't leak sensitive data
- [ ] No `eval()`, `exec()`, `pickle`

## Supported Platforms (Analyzer Modules)

| Platform | Module | Notes |
|----------|--------|-------|
| YouTube | `platforms/youtube.py` | YOUTUBE_API_KEY required |
| DCInside | `platforms/dcinside.py` | Rate limit: 429 respects |
| Reddit | `platforms/reddit.py` | Optional OAuth2 |
| Naver Cafe | `platforms/naver_cafe.py` | Cookie-based (optional) |
| X (Twitter) | `platforms/twitter.py` | TWITTER_BEARER_TOKEN required |
| Threads | `platforms/threads.py` | THREADS_ACCESS_TOKEN required |
| Telegram | `platforms/other_platforms.py` | Public channels only |
| Kakao | `platforms/other_platforms.py` | Profile info only |

## Health Checks

```bash
# Flask health endpoint
curl http://localhost:8888/health
curl http://localhost:8888/api/health

# URL analysis test
curl -X POST http://localhost:8888/api/analyze/url \
     -H 'Content-Type: application/json' \
     -d '{"url":"https://www.youtube.com/watch?v=..."}'
```

## Key Code Patterns

**Config access:**
```python
from app.config import Config
api_key = Config.YOUTUBE_API_KEY
```

**Logging:**
```python
from app.utils.logger import get_logger
logger = get_logger(__name__)
logger.info("Message")
```

**CSRF protection:**
```python
from app.api import csrf_protect

@my_bp.route("/api/mutate", methods=["POST"])
@csrf_protect
def mutate(): ...
```

**Rate limiting:**
```python
from app import limiter

@my_bp.route("/api/endpoint")
@limiter.limit("30 per minute")
def endpoint(): ...
```

**Redis with fallback:**
```python
from app.services.redis_client import redis_client

if redis_client:
    value = redis_client.get(key)
else:
    value = load_from_local_data(key)
```

---

**Parent Documentation**: See `../AGENTS.md` for full project context, supported platforms, and multi-agent workflows.
