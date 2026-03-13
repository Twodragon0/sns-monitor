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

## Quick Start (Docker)

```bash
# 1. Clone and configure
git clone https://github.com/your-org/sns-monitor.git
cd sns-monitor
cp .env.example .env
# Edit .env → set YOUTUBE_API_KEY

# 2. Run (Docker only)
docker-compose up -d --build

# 3. Open
# Dashboard: http://localhost:3080
# URL Analyzer: http://localhost:3080
# API: http://localhost:8888/health
```

**Requirements:** Docker, Docker Compose, and a [YouTube API key](https://console.cloud.google.com/apis/credentials).

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
Frontend (host :3080 → container :3000)
  ↓ /api/*
API Backend (host :8888 → container :8080)
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
curl -X POST http://localhost:8888/api/analyze/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# Analyze a Reddit subreddit
curl -X POST http://localhost:8888/api/analyze/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.reddit.com/r/programming"}'

# List supported platforms
curl http://localhost:8888/api/platforms
```

## Project Structure

```
├── backend/                  # Flask API server (app factory pattern)
│   ├── run.py                # Entry point
│   ├── app/                  # Flask application package
│   │   ├── api/              # Route blueprints (analyze, legacy)
│   │   ├── services/         # Business logic (platform_analyzer, redis)
│   │   └── utils/            # Logging, helpers
│   ├── api_handlers.py       # Legacy API route handlers
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
| `DISABLE_SSL_VERIFY` | No | Disable outbound TLS verification (`false` recommended) |
| `MIROFISH_SSL_VERIFY` | No | TLS verification for MiroFish summarize call (default: `true`) |

## Optional: Periodic Crawlers

```bash
# Start crawlers alongside the main services
docker-compose --profile crawlers up -d

# Crawlers collect data every 2 hours from configured channels
```

## Security Scanning Operations

- Automatic code scanning uses GitHub Code Scanning default setup.
- `.github/workflows/codeql.yml` is reserved for manual advanced scans only (`workflow_dispatch`).
- Trigger manual advanced CodeQL only when one of these is true:
  - repository-level CodeQL query pack/config change needs verification
  - unusual language/extractor issue needs deeper diagnostics than default setup
  - release/security audit requires explicit advanced-scan evidence
- Do not require manual advanced CodeQL on every PR; use default setup for routine gating.

## 수집 데이터 분석·요약 (MiroFish)

크롤러로 수집한 YouTube·DCInside 데이터를 **MiroFish** AI로 분석·요약할 수 있습니다.

**"MiroFish service is not running" / Offline 이 나올 때:** 아래 1~3을 완료한 뒤 `docker-compose --profile analysis up -d` 로 MiroFish 서비스를 기동하세요.

1. **MiroFish 프로젝트 준비**  
   MiroFish는 별도 저장소(예: `~/Desktop/mirofish`)에 두고, Docker 빌드 컨텍스트로 지정합니다.
   - 저장소가 없다면 클론 후 해당 경로를 `MIROFISH_CONTEXT`에 넣습니다.

2. **환경 설정**
   ```bash
   # .env 또는 환경변수 (mirofish 프로젝트 경로)
   export MIROFISH_CONTEXT=/path/to/mirofish   # 예: /Users/yong/Desktop/mirofish 또는 ./mirofish

   # OpenAI OAuth 사용 시: API 키 불필요. 로그인한 사용자의 토큰이 MiroFish로 전달됩니다.
   # (선택) .env.mirofish 에 LLM_API_KEY 등 고정 키를 넣으면 OAuth 미로그인 환경에서도 동작 가능
   ```

3. **실행**
   ```bash
   docker-compose up -d --build
   docker-compose --profile analysis up -d   # MiroFish 서비스 기동
   ```

4. **사용**
   - 대시보드 → **전체 개요** 탭 하단 **「수집 데이터 분석 · 요약」** → **분석 페이지로 이동**
   - 또는 브라우저에서 `http://localhost:3080/analysis` 접속
   - **Select Data Sources**에서 YouTube 채널·DCInside 갤러리 선택 후 **Analyze** → 엔티티 그래프 구축 후 AI 채팅으로 인사이트 질의

수집 데이터는 `local-data/`에 있으며, MiroFish 컨테이너에는 `./local-data`가 `/app/sns-data`로 읽기 전용 마운트됩니다.

### OpenAI OAuth로 API 키 없이 MiroFish 사용 (권장)

**LLM_API_KEY, ZEP_API_KEY 없이** OpenAI(OAuth) 로그인만으로 GPT 기반 분석을 사용할 수 있습니다. 백엔드가 로그인 사용자의 액세스 토큰을 MiroFish로 전달합니다.

1. **환경 변수** (`.env` 또는 docker-compose)
   - `AUTH_REQUIRED_FOR_ANALYSIS=true` 로 설정 시 분석·MiroFish는 로그인 필수
   - `OPENAI_OAUTH_CLIENT_ID`, `OPENAI_OAUTH_CLIENT_SECRET`, `OAUTH_REDIRECT_URI`
   - `OAUTH_AUTHORIZE_URL`, `OAUTH_TOKEN_URL` (OpenAI IdP 주소)
   - `FRONTEND_URL`, `SECRET_KEY`, `CORS_ORIGINS`

2. **동작**
   - 사용자가 「OpenAI(GPT)로 로그인」 → 백엔드 세션에 액세스 토큰 저장
   - MiroFish 호출 시 `Authorization: Bearer <token>` 전달 → MiroFish는 이 토큰으로 OpenAI API 호출 (GPT 등)
   - `.env.mirofish` 의 LLM_API_KEY/ZEP_API_KEY 는 선택 사항 (OAuth 미사용 시에만 필요)

## Verify DCInside/Naver Cafe in Docker

```bash
# Optional: improve Naver Cafe collection stability
# 1) authenticated browser cookie string
export NAVER_CAFE_COOKIE='NID_AUT=...; NID_SES=...; ...'
# 2) optional corporate proxy
export NAVER_CAFE_PROXY_URL='http://proxy.company.local:8080'
# export NAVER_CAFE_PROXY_USERNAME='your_user'
# export NAVER_CAFE_PROXY_PASSWORD='your_pass'

# API/Frontend start
docker-compose up -d --build

# Analyze DCInside post (includes post body + comments when available)
curl -X POST http://localhost:8888/api/analyze/url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://gall.dcinside.com/board/view/?id=baseball_new11&no=123456"}'

# Analyze Naver Cafe list (includes posts + comments for sampled articles when available)
curl -X POST http://localhost:8888/api/analyze/url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://cafe.naver.com/f-e/cafes/31093618/menus/0?viewType=L"}'

# Analyze Naver Cafe single post and check fetch_status/fetch_reason
curl -X POST http://localhost:8888/api/analyze/url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://cafe.naver.com/ArticleRead.nhn?clubid=31093618&articleid=1"}'

# Cleanup
docker-compose down
```

- Frontend result page: `http://localhost:3080`
- API health: `http://localhost:8888/health`

## Troubleshooting

### `Unchecked runtime.lastError: The message port closed before a response was received`

브라우저 **확장 프로그램**(React DevTools, 광고 차단, 비밀번호 관리자 등)에서 나는 메시지입니다. 앱 코드 오류가 아니며, 무시해도 되거나 해당 확장을 끄면 사라질 수 있습니다.

### `POST /api/analyze/url net::ERR_CONNECTION_REFUSED` (또는 `/api/channels`, `/api/dcinside/galleries` 등)

**원인:** 프론트는 `localhost:3080`으로 요청하고, 3080의 nginx가 `/api/*`를 백엔드 컨테이너로 프록시합니다. **백엔드(API) 컨테이너가 떠 있지 않으면** 연결 거부가 납니다.

**해결:**

```bash
# 컨테이너 상태 확인
docker-compose ps

# 모두 떠 있도록 실행 (백엔드·프론트·Redis)
docker-compose up -d --build

# API 직접 확인
curl http://localhost:8888/health
```

브라우저에서 3080이 아니라 **직접 8888**로 API를 쓰는 구성이면, CORS/프록시 설정을 확인하세요. 기본 구성에서는 **3080만 사용**하고, 3080이 8888로 프록시합니다.

### 네이버 카페 분석이 안 될 때

- **로그인 필요 카페:** 포스팅·댓글 수집을 위해 `.env`에 `NAVER_CAFE_COOKIE`를 설정해야 합니다.
  - **쿠키 복사:** 브라우저에서 cafe.naver.com 로그인 후 **개발자 도구(F12) → Application → Storage → Cookies → `https://cafe.naver.com`** (또는 `https://nid.naver.com`)에서 `NID_AUT`, `NID_SES` 등 필요한 항목의 Name=Value를 복사해 `; `로 이어 붙입니다. (또는 Network 탭에서 cafe.naver.com 요청 선택 → Headers → Request Headers → Cookie 전체 복사)
  - **기본 운영 절차(권장):** `python3 scripts/set_naver_cookie.py --clipboard --restart-api`
  - **설정(붙여넣기):** `python3 scripts/set_naver_cookie.py` 실행 후, 쿠키 문자열/Copy as cURL/Copy as fetch 텍스트를 그대로 붙여넣고 `Ctrl-D`.
  - **설정(클립보드):** `python3 scripts/set_naver_cookie.py --clipboard`
  - **설정(브라우저 직접 읽기, 옵션):** `pip install browser-cookie3` 후 `python scripts/set_naver_cookie.py --from-browser chrome`
  - **자동 재기동:** `--restart-api`를 붙이면 반영 후 `api-backend`를 자동 재기동합니다.
- **URL 형식:** 게시글 목록은 `https://cafe.naver.com/f-e/cafes/카페ID/menus/0` 형태, 단일 글은 `ArticleRead.nhn?clubid=...&articleid=...` 형태를 지원합니다.
- **자동 단건 재시도:** 목록 URL이 빈 결과일 때 최신 게시글 번호를 자동 탐지해 단건 검증하려면

```bash
python3 scripts/test_naver_cafe.py "https://cafe.naver.com/f-e/cafes/31581843/menus/0?viewType=L" --show-fetch-diagnostics --auto-find-article

# 탐지 범위/후보 수 조절 + 성공 article_id 캐시 재사용
python3 scripts/test_naver_cafe.py "https://cafe.naver.com/f-e/cafes/31581843/menus/0?viewType=L" \
  --show-fetch-diagnostics --auto-find-article --menu-range 1-80 --max-candidates 20

# 댓글까지 실제 수집된 경우만 성공으로 판정
python3 scripts/test_naver_cafe.py "https://cafe.naver.com/f-e/cafes/31581843/menus/0?viewType=L" \
  --show-fetch-diagnostics --auto-find-article --require-comments
```

- **주기 수집(크롤러):** `NAVER_CAFE_URLS`에 카페 목록 URL을 쉼표로 구분해 넣고, `docker-compose --profile crawlers up -d`로 naver-cafe-crawler를 실행하면 분석 API를 호출해 결과를 `local-data/naver_cafe/{카페ID}/`에 저장합니다.
- **프록시:** 회사 방화벽 등이 있으면 `NAVER_CAFE_PROXY_URL`(및 계정 필요 시 username/password)을 설정합니다.
- **TLS 검사 환경:** 사내 SSL 검사로 인증서 체인이 깨지는 환경이면 `NAVER_CAFE_DISABLE_SSL_VERIFY=true`를 임시로 사용해 네이버 요청만 검증 우회할 수 있습니다.

### Instagram / Facebook / Threads 분석

현재 **URL 인식만** 되고, 실제 수집·감성 분석은 **준비 중**입니다. 인스타그램 URL을 넣으면 "Instagram URL 분석은 현재 준비 중입니다" 안내가 나오며, YouTube·DCInside·네이버 카페·Reddit·X(Twitter) 등은 정상 분석됩니다.

## License

MIT
