# AGENTS.md — SNS Monitor (Current)

## Quick Start for Agents

```bash
# 환경 설정
cp .env.example .env           # YOUTUBE_API_KEY 필수 설정

# 실행
docker-compose up -d --build          # 전체 스택 시작 (redis, api-backend, frontend)
docker-compose --profile crawlers up -d  # 크롤러 포함 (youtube, dcinside, naver-cafe)
docker-compose --profile analysis up -d  # MiroFish AI 분석 서비스 포함

# 접근 포인트
# Frontend:  http://localhost:3080
# Backend:   http://localhost:8888
# Health:    http://localhost:8888/health  또는  /api/health

# 검증
make test    # backend/tests/ pytest (coverage ≥ 95% 필요)
make lint    # Helm chart 린팅 (helm/sns-monitor)
make build   # Docker 이미지 빌드 (api-backend, frontend, youtube/dcinside/naver-cafe crawlers)
make clean   # Docker 이미지 및 볼륨 정리
```

## Tech Stack

| Layer       | Tech                                       | Port |
|-------------|---------------------------------------------|------|
| Frontend    | React 19, Recharts, Axios, Vite             | 3080 |
| Backend     | Python 3.11, Flask, flask-limiter, flask-cors | 8888 (→ 8080 내부) |
| Cache       | Redis 7 (optional, graceful fallback)        | 6379 |
| AI Analysis | MiroFish (optional, `--profile analysis`)   | 5001 |
| Infra       | Docker Compose (local), K8s + Helm (optional) | — |

## Directory Structure

```
backend/
  run.py                          # Flask entry point (gunicorn)
  app/
    __init__.py                   # create_app() factory; Limiter, CORS, health routes
    config.py                     # Config class — 모든 env 변수 중앙 관리
    api/
      __init__.py                 # Blueprint 정의, csrf_protect 데코레이터
      analyze.py                  # POST /api/analyze/url, POST /api/analyze/summarize, GET /api/platforms
      analysis.py                 # MiroFish 브리지 + 로컬 LLM 분석 (다수 엔드포인트)
      auth.py                     # OAuth 2.0 PKCE (Anthropic/OpenAI), API key 세션, /callback
      dashboard.py                # GET /api/dashboard/stats, /api/scans, /api/channels
      members.py                  # GET /api/<group>/members, /api/<group>/channel (group-a,b,c)
      vuddy.py                    # GET /api/vuddy/creators
      dcinside.py                 # GET /api/dcinside/galleries, /api/dcinside/gallery-posts
      data.py                     # GET /api/data, /api/crawler/results, /api/twitter/search
    services/
      platform_analyzer.py        # PlatformAnalyzer: URL→플랫폼 감지 및 분석 디스패처
      sentiment.py                # 키워드 기반 감성 분석 유틸리티
      local_data.py               # 로컬 파일시스템 JSON I/O
      redis_client.py             # Redis (graceful fallback to None)
      llm_analyzer.py             # LLM 분석: OpenAI/Anthropic API, OAuth 토큰, CLI 폴백
      platforms/
        youtube.py                # YouTube Data API v3 분석기
        dcinside.py               # DCInside 갤러리 스크래퍼
        reddit.py                 # Reddit API (OAuth2) 분석기
        naver_cafe.py             # 네이버 카페 크롤러 (쿠키 지원)
        twitter.py                # X(Twitter) API v2 분석기
        threads.py                # Meta Threads API 분석기
        other_platforms.py        # Telegram, Kakao 등 기타 플랫폼
    utils/
      logger.py                   # setup_logger() / get_logger()
  tests/                          # 45개 테스트 파일, pytest, coverage ≥ 95%
  requirements.txt

crawlers/                         # Docker CronJob 수집기 (2시간 주기)
  youtube/
    crawler.py                    # YouTube Data API v3 크롤러
    optimized_youtube_api.py      # 최적화된 API 호출 (배치, 캐싱)
    local_storage.py              # local-data/ JSON 저장
    run_crawler.py                # 크롤러 진입점
  dcinside/
    crawler.py                    # DCInside 갤러리 스크래퍼
  naver_cafe/
    crawler.py                    # 네이버 카페 크롤러
  common/
    local_storage.py              # 공유 스토리지 유틸리티
    timezone_utils.py             # KST/UTC 변환

frontend/
  src/
    App.jsx                       # 메인 앱: lazy routing (Dashboard, CreatorDetail, AnalysisTab)
    config.js                     # API_BASE 설정 (VITE_API_URL 또는 same-origin)
    contexts/
      AuthContext.jsx             # OAuth/API key 인증 상태 관리
    components/
      Dashboard.jsx               # 메인 모니터링 대시보드
      Dashboard.css
      URLAnalyzer.jsx             # URL 입력 + 감성 차트 + AI 분석
      URLAnalyzer.css
      AnalysisTab.jsx             # MiroFish/LLM 수집 데이터 분석 탭 (/analysis)
      CreatorDetail.jsx           # 크리에이터 상세 페이지
      EmptyState.jsx / .css       # 빈 상태 컴포넌트
      ErrorBoundary.jsx           # React 에러 경계
      LoadingSkeleton.jsx / .css  # 로딩 스켈레톤 UI
      Toast.jsx / .css            # 토스트 알림 (ToastContainer, useToast)
      analysis-tab/
        AnalysisWidgets.jsx       # 분석 위젯 모음
        AuthPanel.jsx             # OAuth 로그인/API key 입력 패널
        ResultPanels.jsx          # 분석 결과 표시 패널
      dashboard/
        AnalysisResult.jsx        # 대시보드 분석 결과 컴포넌트
        MonitorPanels.jsx         # 모니터링 패널
      url-analyzer/
        ResultComponents.jsx      # URL 분석 결과 컴포넌트
    constants/
      platforms.js                # 지원 플랫폼 상수 목록
    utils/
      analysis.js                 # 분석 유틸리티 함수

docker/
  Dockerfile.api                  # Flask 백엔드 이미지
  Dockerfile.frontend             # React (Vite 빌드 + nginx) 이미지
  Dockerfile.crawler              # DCInside 크롤러 이미지
  Dockerfile.youtube-crawler      # YouTube 크롤러 이미지
  Dockerfile.naver-crawler        # 네이버 카페 크롤러 이미지
  nginx.conf                      # API 백엔드용 nginx
  nginx-frontend.conf             # 프론트엔드용 nginx (/api 프록시 → 8888)
  entrypoint.local.sh

helm/sns-monitor/                 # Kubernetes Helm 차트 (optional)
k8s/                              # Raw K8s 매니페스트 (optional)
terraform/                        # AWS 인프라 (S3, pod-identity 등, optional)
scripts/                          # 유틸리티 스크립트
  deploy-k8s.sh
  monitor_top_posts.py
  seed_sample_data.py
  set_naver_cookie.py
  naver_cookie_helper.html
chrome-extension/                 # 브라우저 확장 (YouTube, Twitter 콘텐츠 스크립트)
  manifest.json
  content-youtube.js
  content-twitter.js
  popup.html / popup.js
local-data/                       # 런타임 JSON 스토리지 (Docker volume mount)
```

## Supported Platforms

| Platform    | URL Pattern                            | 분석기 모듈                  | 비고 |
|-------------|----------------------------------------|-----------------------------|------|
| YouTube     | youtube.com, youtu.be                  | `platforms/youtube.py`      | YOUTUBE_API_KEY 필수 |
| DCInside    | gall.dcinside.com                      | `platforms/dcinside.py`     | Rate limit: 429 준수 |
| Reddit      | reddit.com/r/                          | `platforms/reddit.py`       | REDDIT_CLIENT_ID/SECRET 권장 |
| Telegram    | t.me/                                  | `platforms/other_platforms.py` | 공개 채널만 |
| Kakao       | pf.kakao.com, story.kakao.com          | `platforms/other_platforms.py` | 프로필 정보만 |
| Naver Cafe  | cafe.naver.com                         | `platforms/naver_cafe.py`   | NAVER_CAFE_COOKIE 권장 |
| X (Twitter) | twitter.com, x.com                     | `platforms/twitter.py`      | TWITTER_BEARER_TOKEN 필요 |
| Threads     | threads.net                            | `platforms/threads.py`      | THREADS_ACCESS_TOKEN 필요 |

## Agent Roles

### Project Agents (`.claude/agents/`)

| Agent 파일             | Model  | 역할 |
|------------------------|--------|------|
| `sns-monitor-lead.md`  | sonnet | 프로젝트 리드, 기능 조율, 아키텍처 결정 |
| `architect.md`         | sonnet | React+Flask 아키텍처, 플랫폼 분석기 설계, Redis 캐싱 전략 |
| `crawler-debugger.md`  | sonnet | 크롤러 파싱/API 장애 디버깅 |
| `frontend-developer.md`| sonnet | React 19 대시보드, URL 분석 UI, Recharts 시각화 |
| `backend-developer.md` | sonnet | Flask API, 플랫폼 분석기, Redis 통합, LLM 연동 |
| `infra-engineer.md`    | sonnet | Docker, K8s, Terraform, Helm 인프라 |
| `security-reviewer.md` | sonnet | API 보안, CSRF, OAuth, 입력 검증, 시크릿 관리 |
| `test-engineer.md`     | sonnet | pytest (coverage ≥ 95%), API 테스트, 크롤러 검증 |

### Multi-Agent Workflow Patterns

- **플랫폼 추가**: `sns-monitor-lead` → `architect` + `backend-developer` + `test-engineer` (병렬) → `security-reviewer`
- **크롤러 장애**: `crawler-debugger` → `backend-developer` → `test-engineer`
- **UI 개선**: `frontend-developer` → `architect` → `test-engineer`
- **인프라 변경**: `infra-engineer` → `security-reviewer` → `test-engineer`
- **LLM/OAuth 이슈**: `backend-developer` + `security-reviewer` → `test-engineer`

### `sns-monitor-lead` (sonnet)
기능 추가, 버그 수정, 아키텍처 결정 담당 리드. 새 기능은 `spec.md` 확인 후 진행.
- Frontend + Backend + Crawler 서브태스크로 분해하여 실행
- 포트/서비스명 변경 시 docker-compose.yml 일관성 검증
- 크롤러 이슈는 `crawler-debugger`에 위임

### `crawler-debugger` (sonnet)
크롤러 장애(rate limit, 인증 실패, 파싱 오류) 진단 및 수정.
- 진단 후 구조화된 리포트 생성
- P0 보안 이슈(시크릿 노출) 즉시 보고

**위임 규칙:**
- 크롤러 rate limit / auth / parsing 오류 → `crawler-debugger`
- 기능 구현, 리팩터링 → `sns-monitor-lead`

## Coding Conventions

**Python (Backend/Crawlers):**
```python
# 설정은 app/config.py의 Config class만 사용
from app.config import Config
api_key = Config.YOUTUBE_API_KEY  # 또는 os.getenv() 직접 사용

# 로깅: logging 모듈 사용, print() 금지
import logging
logger = logging.getLogger(__name__)

# CSRF 보호: mutating 엔드포인트에 @csrf_protect 필수
@analyze_bp.route("/api/analyze/url", methods=["POST"])
@limiter.limit("30 per minute")
@csrf_protect
def analyze_url(): ...

# 경로 ID 검증: _SAFE_ID_RE 패턴 사용
_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{1,128}$')

# 금지: eval(), exec(), pickle
```

**React (Frontend):**
```jsx
// ES modules, named imports, React 19
import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../config';

// API 호출은 API_BASE + /api/* (Docker에서는 same-origin)
const response = await axios.post(`${API_BASE}/api/analyze/url`, { url });

// 인증 상태: useAuth() hook 사용
import { useAuth } from '../contexts/AuthContext';
```

## Testing

```bash
# 백엔드 테스트 (coverage ≥ 95% 필수)
cd backend && python -m pytest tests/ -v --tb=short \
    --cov=app --cov-report=term-missing --cov-fail-under=95

# 또는 Makefile
make test

# 헬스 체크
curl http://localhost:8888/health
curl http://localhost:8888/api/health

# URL 분석 테스트
curl -X POST http://localhost:8888/api/analyze/url \
     -H 'Content-Type: application/json' \
     -d '{"url":"https://www.youtube.com/watch?v=..."}'
```

- 백엔드 변경 시: `make test` 통과 필수 (45개 테스트 파일)
- Docker 변경 시: `docker-compose up -d --build` 후 `/health` 확인
- 새 플랫폼 분석기 추가 시: `backend/tests/test_platform_analyzer.py` 및 관련 테스트 추가

## Security Rules

- **P0**: 시크릿 하드코딩 금지. `os.getenv()` / `Config.*` / K8s Secrets만 사용
- **P0**: `NAVER_CAFE_COOKIE`는 민감 자격증명 — 로그 출력 및 커밋 금지
- **P0**: `SECRET_KEY` 미설정 시 세션이 재시작마다 초기화됨 — 프로덕션에서 필수 설정
- CSRF: `@csrf_protect` 데코레이터를 모든 POST/PUT/DELETE 라우트에 적용
- 모든 외부 URL 입력: 플랫폼별 화이트리스트 패턴으로 검증
- 경로 파라미터: `_SAFE_ID_RE` 패턴으로 path traversal 방지
- `eval()`, `exec()`, `pickle` 사용 금지
- Redis 없이도 동작해야 함 (graceful fallback 유지)
- Rate limiting: `flask-limiter` (기본 200/분, 엔드포인트별 세분화)

## Key API Endpoints

```
# 헬스
GET  /health
GET  /api/health

# URL 분석
POST /api/analyze/url           {"url": "https://..."}
POST /api/analyze/summarize     {"result": {...}}  ← MiroFish/LLM/로컬 폴백
GET  /api/platforms

# 대시보드
GET  /api/dashboard/stats
GET  /api/scans
GET  /api/channels

# DCInside
GET  /api/dcinside/galleries
GET  /api/dcinside/gallery-posts

# 그룹 멤버
GET  /api/group-a/members  (또는 group-b, group-c)
GET  /api/group-a/channel

# Vuddy 크리에이터
GET  /api/vuddy/creators

# 데이터
GET  /api/data
GET  /api/crawler/results
GET  /api/twitter/search

# 인증 (OAuth 2.0 PKCE)
GET  /api/auth/me
GET  /api/auth/anthropic       ← Claude OAuth 시작
GET  /api/auth/openai          ← OpenAI OAuth 시작
GET  /callback                 ← OAuth 콜백 (Claude Code 패턴)
GET  /auth/callback            ← OpenAI 콜백 (OpenCode 패턴)
POST /api/auth/apikey          {"provider": "anthropic"|"openai", "api_key": "sk-..."}
POST /api/auth/logout

# AI 분석 (MiroFish 브리지)
GET  /api/analysis/status
GET  /api/analysis/sources
POST /api/analysis/transform
POST /api/analysis/graph/build
GET  /api/analysis/graph/task/<task_id>
GET  /api/analysis/graph/data/<graph_id>
POST /api/analysis/report/generate
GET  /api/analysis/report/<report_id>
POST /api/analysis/report/chat
GET  /api/analysis/projects

# AI 분석 (로컬 LLM — Claude/OpenAI API 직접 호출)
GET  /api/analysis/llm/status
POST /api/analysis/ai-summary
POST /api/analysis/ai-chat
POST /api/analysis/ai-url-analyze
POST /api/analysis/ai-url-chat

# 로컬 분석 (오프라인 가능)
POST /api/analysis/local-summary
GET  /api/analysis/trend        ?type=dcinside&id=<gallery_id>
GET  /api/analysis/compare
POST /api/analysis/report/generate-daily
GET  /api/analysis/reports
GET  /api/analysis/reports/<date>
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `YOUTUBE_API_KEY` | 필수 | YouTube Data API v3 키 |
| `SECRET_KEY` | 프로덕션 필수 | Flask 세션 서명 키 (미설정 시 재시작마다 랜덤 생성) |
| `REDIS_HOST` | 선택 | Redis 호스트명 (기본: redis) |
| `REDIS_PASSWORD` | 선택 | Redis 비밀번호 |
| `FLASK_DEBUG` | 선택 | Flask 디버그 모드 (기본: false) |
| `LOCAL_MODE` | 선택 | 로컬 파일시스템 모드 (기본: true) |
| `LOCAL_DATA_DIR` | 선택 | 데이터 저장 경로 (기본: ./local-data) |
| `NAVER_CAFE_COOKIE` | 선택 | 네이버 로그인 쿠키 (members-only 콘텐츠 수집 필요) |
| `NAVER_CAFE_PROXY_URL` | 선택 | 네이버 카페 프록시 URL |
| `NAVER_SEARCH_CLIENT_ID` | 선택 | 네이버 Open API Client ID |
| `NAVER_SEARCH_CLIENT_SECRET` | 선택 | 네이버 Open API Client Secret |
| `TWITTER_BEARER_TOKEN` | 선택 | Twitter API v2 Bearer Token |
| `THREADS_ACCESS_TOKEN` | 선택 | Meta Threads API 액세스 토큰 |
| `REDDIT_CLIENT_ID` | 선택 | Reddit OAuth2 앱 Client ID |
| `REDDIT_CLIENT_SECRET` | 선택 | Reddit OAuth2 앱 Client Secret |
| `OPENAI_API_KEY` | 선택 | OpenAI API 키 (로컬 LLM 분석) |
| `ANTHROPIC_API_KEY` | 선택 | Anthropic API 키 (로컬 LLM 분석) |
| `LLM_PROVIDER` | 선택 | LLM 제공자 강제 지정: "openai" 또는 "anthropic" |
| `LLM_MODEL` | 선택 | LLM 모델명 오버라이드 |
| `OPENAI_OAUTH_CLIENT_ID` | 선택 | OpenAI OAuth 클라이언트 ID |
| `ANTHROPIC_OAUTH_CLIENT_ID` | 선택 | Anthropic OAuth 클라이언트 ID |
| `AUTH_REQUIRED_FOR_ANALYSIS` | 선택 | AI 분석 엔드포인트 인증 필수화 (기본: false) |
| `MIROFISH_ENDPOINT` | 선택 | MiroFish AI 서비스 URL (기본: http://mirofish:5001) |
| `CORS_ORIGINS` | 선택 | 허용 CORS 오리진 (콤마 구분) |
| `FRONTEND_URL` | 선택 | OAuth 콜백 후 프론트엔드 리다이렉트 URL |
| `GOOGLE_API_KEY` | 선택 | Google/Gemini API 키 |

> **참고**: 상세 기술 명세는 `spec.md` 참조. 신규 플랫폼 추가 전 반드시 확인.
