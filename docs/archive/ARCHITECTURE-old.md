# SNS Monitoring System - Architecture & Cost Analysis

## 📋 목차
- [시스템 개요](#시스템-개요)
- [아키텍처](#아키텍처)
- [기술 스택](#기술-스택)
- [데이터 플로우](#데이터-플로우)
- [비용 분석](#비용-분석)
- [배포 구성](#배포-구성)

---

## 시스템 개요

SNS Monitoring System은 다양한 플랫폼(YouTube, SOOP, Vuddy 등)에서 크리에이터 데이터를 수집, 분석하여 통합 대시보드로 제공하는 시스템입니다.

### 주요 기능
- ✅ YouTube 채널 통계 수집 (구독자, 조회수, 동영상 수)
- ✅ YouTube 댓글 수집 및 감성 분석
- ✅ 국가별 팬층 분석 (한국, 미국, 일본)
- ✅ SOOP 플랫폼 정보 통합
- ✅ 실시간 대시보드 제공
- ✅ 크리에이터별 상세 분석

### 지원 플랫폼
- YouTube (API v3)
- SOOP (구 아프리카TV)
- Vuddy
- Twitter/X (준비 중)
- Instagram (준비 중)
- Facebook (준비 중)
- Telegram (준비 중)
- Threads (준비 중)

---

## 아키텍처

### 전체 시스템 구성도

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  React Frontend (Port 3000)                              │  │
│  │  - Dashboard (모든 크리에이터)                             │  │
│  │  - AkaiV Studio Detail Page                              │  │
│  │  - BARABARA Detail Page                                  │  │
│  │  - Cache Busting & Real-time Updates                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                          API Layer                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  API Backend (Port 8080)                                 │  │
│  │  - Lambda Function Handler (Python)                      │  │
│  │  - RESTful API Endpoints                                 │  │
│  │  - Data Aggregation & Processing                         │  │
│  │  - Health Check & Monitoring                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Collection Layer                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ YouTube        │  │ SOOP           │  │ Vuddy          │   │
│  │ Crawler        │  │ Crawler        │  │ Crawler        │   │
│  │ (Port 5000)    │  │                │  │                │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ Twitter        │  │ Instagram      │  │ Facebook       │   │
│  │ Crawler        │  │ Crawler        │  │ Crawler        │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│  ┌────────────────┐  ┌────────────────┐                       │
│  │ Telegram       │  │ Threads        │                       │
│  │ Crawler        │  │ Crawler        │                       │
│  └────────────────┘  └────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Data Storage Layer                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Local File System (JSON)                                │  │
│  │  - vuddy-creators.json (9 creators)                      │  │
│  │  - akaiv-studio-members.json (5 members)                 │  │
│  │  - Backup files (.backup, .backup_*)                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Redis Cache (Port 6379)                                 │  │
│  │  - YouTube API Response Caching                          │  │
│  │  - 15-minute TTL                                         │  │
│  │  - Quota Optimization                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  DynamoDB (Local)                                        │  │
│  │  - Scan History                                          │  │
│  │  - User Preferences                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services Layer                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ YouTube API v3 │  │ LocalStack     │  │ LLM Analyzer   │   │
│  │ (Google)       │  │ (AWS Mock)     │  │ (GPT/Claude)   │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 컴포넌트 상세

#### 1. Frontend (React)
- **기술**: React 18, React Router, Axios
- **포트**: 3000
- **주요 기능**:
  - 크리에이터 대시보드 (메인 페이지)
  - AkaiV Studio 상세 페이지
  - BARABARA, IVNIT, SKOSHISM 상세 페이지
  - 실시간 데이터 업데이트
  - Cache-busting 구현

#### 2. API Backend (Python)
- **기술**: Python 3.11, Flask-like Lambda Handler
- **포트**: 8080
- **주요 엔드포인트**:
  - `GET /api/health` - Health Check
  - `GET /api/vuddy/creators` - 모든 크리에이터 조회
  - `GET /api/akaiv-studio/members` - AkaiV Studio 멤버 조회
  - `GET /api/dashboard/stats` - 대시보드 통계
  - `GET /api/scans` - 스캔 이력
  - `GET /api/channels` - 채널 목록

#### 3. YouTube Crawler
- **기술**: Python 3.11, google-api-python-client
- **포트**: 5000 (내부)
- **주요 기능**:
  - YouTube API v3 호출
  - 채널 통계 수집 (구독자, 조회수, 동영상 수)
  - 댓글 수집 및 분석
  - 국가별 분류 (정규식 기반)
  - 감성 분석 (키워드 기반)
  - Redis 캐싱으로 Quota 최적화

#### 4. Data Storage
- **JSON Files**: 로컬 파일 시스템에 저장
  - `vuddy-creators.json`: 전체 크리에이터 데이터
  - `akaiv-studio-members.json`: AkaiV Studio 멤버만
- **Redis**: YouTube API 응답 캐싱
- **DynamoDB**: 스캔 이력 및 메타데이터

---

## 기술 스택

### Backend
- **Language**: Python 3.11
- **Framework**: Flask-like Lambda Handler
- **APIs**:
  - google-api-python-client (YouTube API v3)
  - boto3 (AWS SDK)
- **Caching**: Redis 7
- **Database**: DynamoDB (Local)

### Frontend
- **Framework**: React 18
- **Routing**: React Router 6
- **HTTP Client**: Axios
- **Styling**: CSS3, Vuddy.io Theme

### Infrastructure
- **Container**: Docker & Docker Compose
- **Orchestration**: Docker Compose
- **Services**:
  - Frontend: Node 18
  - API Backend: Python 3.11
  - YouTube Crawler: Python 3.11
  - Redis: redis:7-alpine
  - DynamoDB: amazon/dynamodb-local
  - LocalStack: localstack/localstack

### External APIs
- **YouTube Data API v3**: 크리에이터 데이터 수집
- **Quota**: 10,000 units/day (free tier)

---

## 데이터 플로우

### 1. 데이터 수집 플로우

```
User Request
    │
    ▼
[수동 실행] collect_all_creators_stats.py
    │
    ├─► YouTube API v3
    │   ├─► 채널 검색 (search.list) - 100 units
    │   ├─► 채널 통계 (channels.list) - 1 unit
    │   ├─► 동영상 목록 (playlistItems.list) - 1 unit
    │   └─► 댓글 수집 (commentThreads.list) - 1 unit per call
    │
    ├─► Redis Cache 확인
    │   └─► Cache Hit: API 호출 생략 (Quota 절약)
    │
    ▼
[데이터 저장] vuddy-creators.json
    │
    ├─► 백업 생성 (.backup_*)
    ├─► 통계 업데이트 (subscribers, views, videos)
    ├─► 댓글 분석 (sentiment, country)
    └─► 분석 요약 생성
    │
    ▼
[동기화] akaiv-studio-members.json
    │
    └─► AkaiV Studio 멤버만 추출
```

### 2. API 요청 플로우

```
Frontend Request (http://localhost:3000/api/vuddy/creators)
    │
    ▼
[Frontend Proxy] → API Backend (http://api-backend:8080)
    │
    ▼
[API Handler] lambda_function.py
    │
    ├─► Local Mode 확인
    ├─► vuddy-creators.json 로드
    ├─► 데이터 변환 및 필터링
    └─► JSON 응답 생성
    │
    ▼
Frontend Display
    │
    ├─► 대시보드: 9개 크리에이터 카드
    ├─► AkaiV Studio: 5개 멤버 상세
    └─► 통계, 댓글, 분석 표시
```

### 3. 댓글 수집 및 분석 플로우

```
[YouTube API] commentThreads.list
    │
    ▼
[댓글 데이터 수집]
    │
    ├─► 작성자, 텍스트, 좋아요 수, 작성일
    ├─► 최대 30개/동영상 (Quota 최적화)
    └─► Redis 캐싱 (15분)
    │
    ▼
[국가 분류]
    │
    ├─► 한글 ([가-힣]) → KR
    ├─► 일본어 ([ぁ-んァ-ヶー一-龯]) → JP
    └─► 기타 → US
    │
    ▼
[감성 분석]
    │
    ├─► Positive Keywords: 좋아, 최고, 사랑, 대박, good, great, love...
    ├─► Negative Keywords: 싫어, 별로, 실망, bad, hate, terrible...
    └─► Neutral: 기타
    │
    ▼
[통계 집계]
    │
    ├─► 국가별 댓글 수 및 좋아요 수
    ├─► 감성 분포 (positive/neutral/negative)
    └─► 댓글 샘플 저장 (상위 20개)
```

---

## 비용 분석

### 1. YouTube API v3 비용

#### Quota 사용량 (크리에이터 1명 기준)
| API 호출 | Units | 빈도 | 총 Units |
|---------|-------|------|----------|
| search.list (채널 검색) | 100 | 1회 | 100 |
| channels.list (통계) | 1 | 1회 | 1 |
| playlistItems.list (동영상) | 1 | 1회 | 1 |
| commentThreads.list | 1 | 5회 (5개 동영상) | 5 |
| videos.list (동영상 통계) | 1 | 1회 (5개 동영상) | 1 |
| **합계** | - | - | **108 units** |

#### 전체 시스템 Quota 사용량 (1회 수집 기준)
- **9개 크리에이터**: 108 × 9 = **972 units**
- **Daily Quota**: 10,000 units (무료)
- **가능한 수집 횟수**: 10,000 / 972 = **10.3회/일**

#### Redis 캐싱으로 Quota 절약
- **Cache Hit Rate**: ~80% (15분 TTL 기준)
- **실제 Quota 사용**: 972 × 0.2 = **194.4 units/회**
- **가능한 수집 횟수**: 10,000 / 194.4 = **51.4회/일**

#### 비용 계산 (무료 Quota 초과 시)
- **추가 10,000 units**: 무료 (Google Cloud Console에서 신청)
- **유료 전환**: 필요 없음 (현재 사용량 < 무료 한도)

### 2. 인프라 비용

#### 로컬 개발 환경 (현재)
| 항목 | 비용 |
|-----|------|
| Docker Desktop | 무료 (개인 사용) |
| 로컬 컴퓨팅 | 무료 (개발 PC) |
| **총 비용** | **$0/월** |

#### AWS 배포 시 예상 비용 (월간)
| 서비스 | 스펙 | 비용 |
|--------|------|------|
| EC2 (t3.medium) | 2 vCPU, 4GB RAM | $30 |
| ECS Fargate | 0.5 vCPU, 1GB RAM × 3 태스크 | $25 |
| ElastiCache (Redis) | cache.t3.micro | $12 |
| DynamoDB | On-demand (1GB) | $0.25 |
| S3 | 1GB 저장 | $0.02 |
| CloudWatch Logs | 1GB/월 | $0.50 |
| Application Load Balancer | - | $16 |
| **총 비용** | - | **~$84/월** |

#### 비용 최적화 옵션
1. **EC2 Reserved Instance**: 30-40% 절감 → **$50-60/월**
2. **Fargate Spot**: 70% 절감 → **$40-50/월**
3. **Self-Hosted (VPS)**: DigitalOcean/Vultr → **$12-24/월**

### 3. 외부 서비스 비용

| 서비스 | 플랜 | 비용 |
|--------|------|------|
| YouTube API v3 | 무료 (10,000 units/day) | $0 |
| SOOP API | 미사용 (웹 스크래핑 검토 중) | $0 |
| GPT-4 API (분석용, 미래) | $0.03/1K tokens | 예상 $10-20/월 |
| **총 비용** | - | **$0-20/월** |

### 4. 총 비용 요약

| 환경 | 월간 비용 | 연간 비용 |
|-----|----------|----------|
| **로컬 개발** | $0 | $0 |
| **AWS 배포 (최적화)** | $50-60 | $600-720 |
| **VPS 배포** | $12-24 | $144-288 |
| **외부 API** | $0-20 | $0-240 |

**추천 배포 방식**: VPS (DigitalOcean/Vultr) + Docker
- **비용**: $12-24/월
- **장점**: 간단한 배포, 낮은 비용, 충분한 성능
- **단점**: 수동 관리 필요, 확장성 제한

---

## 배포 구성

### 로컬 개발 환경 (현재)

```bash
# 서비스 시작
docker-compose up -d

# 서비스 확인
docker ps

# 로그 확인
docker logs sns-monitor-api-backend
docker logs sns-monitor-frontend

# 서비스 중지
docker-compose down
```

**접속 주소**:
- Frontend: http://localhost:3000
- API Backend: http://localhost:8080
- Redis: localhost:6379
- DynamoDB: http://localhost:8000

### 프로덕션 배포 권장사항

#### Option 1: VPS (DigitalOcean/Vultr)

```bash
# 1. VPS 설정
apt update && apt upgrade -y
apt install docker.io docker-compose git -y

# 2. 코드 클론
git clone <repository-url>
cd sns-monitoring-system

# 3. 환경 변수 설정
cp .env.example .env
# YouTube API 키 설정

# 4. 프로덕션 빌드
docker-compose -f docker-compose.prod.yml up -d

# 5. Nginx 리버스 프록시 설정
apt install nginx -y
# nginx.conf 설정

# 6. SSL 인증서 (Let's Encrypt)
apt install certbot python3-certbot-nginx -y
certbot --nginx -d yourdomain.com
```

**비용**: $12-24/월 (4GB RAM 권장)

#### Option 2: AWS ECS Fargate

```bash
# 1. ECR 이미지 푸시
aws ecr create-repository --repository-name sns-monitor-frontend
aws ecr create-repository --repository-name sns-monitor-api-backend

docker build -t sns-monitor-frontend ./frontend
docker tag sns-monitor-frontend:latest <account-id>.dkr.ecr.<region>.amazonaws.com/sns-monitor-frontend:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/sns-monitor-frontend:latest

# 2. ECS 태스크 정의 생성
aws ecs register-task-definition --cli-input-json file://task-definition.json

# 3. ECS 서비스 생성
aws ecs create-service --cli-input-json file://service-definition.json

# 4. ALB 설정
aws elbv2 create-load-balancer --name sns-monitor-alb

# 5. Route 53 DNS 설정
aws route53 change-resource-record-sets --hosted-zone-id <zone-id> --change-batch file://dns-config.json
```

**비용**: $50-60/월 (최적화 시)

### 모니터링 설정

```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## 데이터 구조

### vuddy-creators.json 구조

```json
{
  "platform": "vuddy",
  "group": "Vuddy Creators",
  "timestamp": "2025-11-20T14:25:00+09:00",
  "total_creators": 9,
  "creators": [
    {
      "name": "크리에이터 이름",
      "youtube_channel": "@handle",
      "total_comments": 150,
      "total_likes": 2040,
      "total_blog_posts": 12,
      "total_google_results": 76,
      "statistics": {
        "subscribers": 52800,
        "total_views": 12072548,
        "video_count": 268
      },
      "sentiment_distribution": {
        "positive": 0.25,
        "negative": 0.0,
        "neutral": 0.75
      },
      "country_stats": {
        "KR": {"comments": 147, "likes": 2000},
        "US": {"comments": 3, "likes": 40},
        "JP": {"comments": 0, "likes": 0}
      },
      "comment_samples": [
        {
          "text": "댓글 내용",
          "author": "작성자",
          "like_count": 15,
          "published_at": "2024-12-31T11:39:18Z",
          "country": "KR",
          "sentiment": "positive",
          "video_id": "video_id",
          "video_title": "동영상 제목",
          "video_url": "https://www.youtube.com/watch?v=..."
        }
      ],
      "videos": [
        {
          "video_id": "video_id",
          "title": "동영상 제목",
          "url": "https://www.youtube.com/watch?v=...",
          "view_count": 12291,
          "like_count": 456,
          "comment_count": 30
        }
      ],
      "platform_links": [
        {"platform": "YouTube", "url": "https://www.youtube.com/@handle"},
        {"platform": "SOOP", "url": "https://www.sooplive.co.kr/station/id"}
      ],
      "soop_analysis": {
        "soop_url": "https://www.sooplive.co.kr/station/id",
        "soop_id": "id",
        "platform": "SOOP (구 아프리카TV)",
        "status": "active",
        "streaming_schedule": {
          "regular_schedule": "주중 저녁 시간대"
        },
        "content_type": ["노래 방송", "게임 방송", "토크 방송"]
      },
      "analysis": {
        "sentiment": "neutral",
        "summary": "크리에이터 분석 요약..."
      }
    }
  ]
}
```

---

## 보안 고려사항

### API 키 관리
- ✅ `.env` 파일 사용 (Git에서 제외)
- ✅ Docker Secrets 사용 (프로덕션)
- ⚠️ 코드에 하드코딩된 API 키 제거 필요

### 권장 보안 강화
1. **API Rate Limiting**: 무단 사용 방지
2. **CORS 설정**: 허용된 도메인만 접근
3. **HTTPS 강제**: SSL/TLS 인증서
4. **Input Validation**: SQL Injection 등 방지
5. **Authentication**: JWT 토큰 기반 인증

---

## 향후 개선 사항

### 기능 개선
- [ ] 실시간 데이터 업데이트 (WebSocket)
- [ ] 자동 스케줄링 (Cron Job)
- [ ] GPT/Claude를 활용한 고급 분석
- [ ] SOOP API 연동 (공식 API 출시 시)
- [ ] 다국어 지원 (영어, 일본어)
- [ ] PDF 리포트 생성

### 인프라 개선
- [ ] CI/CD 파이프라인 (GitHub Actions)
- [ ] 로그 집중화 (ELK Stack)
- [ ] 메트릭 수집 (Prometheus + Grafana)
- [ ] 자동 백업 (S3 또는 B2)
- [ ] Blue-Green 배포

### 비용 최적화
- [ ] Redis Cluster → Redis Standalone (개발 환경)
- [ ] DynamoDB → SQLite (로컬 개발)
- [ ] CloudFront CDN (정적 파일)
- [ ] S3 Lifecycle Policy (오래된 백업 삭제)

---

## 문의 및 지원

**프로젝트**: SNS Monitoring System
**버전**: 1.0.0
**최종 업데이트**: 2025-11-21

**기술 스택**:
- Frontend: React 18, Axios, React Router
- Backend: Python 3.11, Flask-like Lambda
- Database: Redis, DynamoDB, JSON Files
- APIs: YouTube Data API v3
- Infrastructure: Docker, Docker Compose

**개발 환경**:
- Node.js: 18.x
- Python: 3.11
- Docker: 20.x+
- Docker Compose: 2.x+

---

## 라이선스

이 프로젝트는 내부 사용 목적으로 개발되었습니다.
