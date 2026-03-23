# AGENTS.md — SNS Monitor (Current)

## Quick Start for Agents

```bash
# 환경 설정
cp .env.example .env           # YOUTUBE_API_KEY 필수 설정

# 실행
docker-compose up -d --build   # 전체 스택 시작
docker-compose --profile crawlers up -d  # 크롤러 포함

# 접근 포인트
# Frontend:  http://localhost:3080
# Backend:   http://localhost:8888
# Health:    http://localhost:8888/health

# 검증
make test    # pytest (크롤러 단위 테스트)
make lint    # Helm chart 린팅
make build   # 이미지 빌드
make clean   # 정리
```

## Tech Stack

| Layer     | Tech                          | Port |
|-----------|-------------------------------|------|
| Frontend  | React 18, Recharts, Axios     | 3080 |
| Backend   | Python 3.11, Flask            | 8888 |
| Cache     | Redis (optional, graceful fallback) | 6379 |
| Infra     | Docker Compose (local), K8s + Helm (optional) | — |

## Directory Structure

```
backend/
  run.py                    # Flask entry point
  app/__init__.py           # create_app() factory
  app/config.py             # Config class (centralized)
  app/api/analyze.py        # POST /api/analyze/url
  app/api/analysis.py       # MiroFish analysis API
  app/services/platform_analyzer.py  # 플랫폼 디스패처
  app/services/redis_client.py       # Redis (graceful fallback)
  api_handlers.py           # Legacy handlers
crawlers/
  youtube/                  # YouTube Data API v3
  dcinside/                 # DCInside gallery scraper
  common/                   # 공유 유틸리티
frontend/src/components/
  URLAnalyzer.jsx           # URL 입력 + 감성 차트
  Dashboard.jsx             # 메인 대시보드
  AnalysisTab.jsx           # MiroFish 수집 데이터 분석
  *Detail.jsx               # 크리에이터 상세 페이지
```

## Supported Platforms

| Platform   | URL Pattern                | Notes                          |
|------------|----------------------------|--------------------------------|
| YouTube    | youtube.com, youtu.be      | API key required               |
| DCInside   | gall.dcinside.com          | Rate limit: respect 429        |
| Reddit     | reddit.com/r/              | 1 req/sec max                  |
| Telegram   | t.me/                      | Public channels only           |
| Kakao      | pf.kakao.com               | Profile info only              |
| Naver Cafe | cafe.naver.com             | `NAVER_CAFE_COOKIE` for members-only |

## Agent Roles

### `sns-monitor-lead` (sonnet)
기능 추가, 버그 수정, 아키텍처 결정 담당 리드. 새 기능은 `spec.md` 확인 후 진행.
- Frontend + Backend + Crawler 서브태스크로 분해하여 실행
- 포트/서비스명 변경 시 docker-compose.yml 일관성 검증
- 크롤러 이슈는 `crawler-debugger`에 위임

### `crawler-debugger` (haiku, read-only)
크롤러 장애(rate limit, 인증 실패, 파싱 오류) 진단 전용. 파일 수정 불가.
- 진단 후 구조화된 리포트 생성 → sns-monitor-lead가 수정 적용
- P0 보안 이슈(시크릿 노출) 즉시 보고

**위임 규칙:**
- 크롤러 rate limit / auth / parsing 오류 → `crawler-debugger`
- 기능 구현, 리팩터링 → `sns-monitor-lead`

## Coding Conventions

**Python (Backend/Crawlers):**
```python
# 설정은 app/config.py의 Config class 사용
from app.config import Config

# 환경변수는 반드시 os.getenv()
api_key = os.getenv("YOUTUBE_API_KEY")

# 로깅: logging 모듈 사용, print() 금지
import logging
logger = logging.getLogger(__name__)

# 금지: eval(), exec(), pickle
```

**React (Frontend):**
```jsx
// ES modules, named imports
import { useState, useEffect } from 'react';
import axios from 'axios';

// API 호출은 /api/* 경로 (proxy → port 8888)
const response = await axios.post('/api/analyze/url', { url });
```

## Testing

```bash
make test    # crawlers/ pytest 실행
# 백엔드 라우트 수동 확인:
curl http://localhost:8888/health
curl -X POST http://localhost:8888/api/analyze/url -d '{"url":"..."}'
```

- 백엔드 변경 시: `make test` 통과 필수
- Docker 변경 시: `docker-compose up -d --build` 후 health check 확인

## Security Rules

- **P0**: 시크릿 하드코딩 금지. `os.getenv()` 또는 K8s Secrets만 사용
- **P0**: `NAVER_CAFE_COOKIE`는 민감 자격증명 — 로그 출력 및 커밋 금지
- 모든 외부 URL 입력: 플랫폼별 화이트리스트 패턴으로 검증
- `eval()`, `exec()`, `pickle` 사용 금지
- Redis 없이도 동작해야 함 (graceful fallback 유지)

## Key API Endpoints

```
POST /api/analyze/url        {"url": "https://..."}
GET  /api/platforms
GET  /api/health
GET  /api/dashboard/stats
GET  /api/dcinside/galleries
GET  /api/{group}/members
GET  /api/analysis/status    (MiroFish)
POST /api/analysis/transform (MiroFish)
```

> **참고**: 상세 기술 명세는 `spec.md` 참조. 신규 플랫폼 추가 전 반드시 확인.
