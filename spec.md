# SNS 모니터링 시스템 - 기술 명세서 (Technical Specification)

> **Version:** 2.0.0  
> **Last Updated:** 2025-01-XX  
> **Status:** Production Ready  
> **Maintainer:** DevSecOps Team

---

## 목차 (Table of Contents)

1. [프로젝트 개요](#1-프로젝트-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [기능 명세](#3-기능-명세)
4. [데이터 모델](#4-데이터-모델)
5. [API 명세](#5-api-명세)
6. [UI/UX 명세](#6-uiux-명세)
7. [보안 요구사항](#7-보안-요구사항)
8. [성능 및 확장성](#8-성능-및-확장성)
9. [운영 및 모니터링](#9-운영-및-모니터링)
10. [비용 최적화](#10-비용-최적화)
11. [트레이드오프 및 제약사항](#11-트레이드오프-및-제약사항)
12. [향후 개선 계획](#12-향후-개선-계획)

---

## 1. 프로젝트 개요

### 1.1 목적

SNS 모니터링 시스템은 VTuber/Creator의 소셜 미디어 활동을 자동으로 수집, 분석, 시각화하는 통합 플랫폼입니다. YouTube, DCInside 등 다양한 플랫폼에서 크리에이터 관련 데이터를 수집하여 실시간 대시보드로 제공합니다.

### 1.2 핵심 가치 제안

- **자동화된 데이터 수집**: 크롤러가 주기적으로 데이터를 수집하여 수동 작업 최소화
- **실시간 모니터링**: 크리에이터의 활동, 댓글, 트렌드를 실시간으로 추적
- **비용 효율성**: 월 $100-110 수준의 운영 비용으로 안정적인 서비스 제공
- **확장 가능한 아키텍처**: Kubernetes 기반으로 트래픽 증가에 대응 가능

### 1.3 주요 사용자

- **VTuber 매니저**: 크리에이터의 소셜 미디어 활동 모니터링
- **팬 커뮤니티**: 크리에이터 관련 트렌드 및 댓글 분석
- **마케팅 팀**: 크리에이터 관련 키워드 및 감성 분석

### 1.4 기술 스택

```
Frontend:     React 18.2.0, Axios, ReCharts
Backend:      Python 3.11, Flask, boto3
Storage:      Redis (Cache), EBS PVC (5Gi), S3 (Backup)
Container:    Docker, Kubernetes (EKS)
Infrastructure: Terraform, Helm
CI/CD:        GitHub Actions
Monitoring:   CloudWatch (계획), Prometheus (계획)
```

---

## 2. 시스템 아키텍처

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Internet                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS (443)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              AWS EKS Cluster (your-cluster)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         Nginx Ingress Controller                        │   │
│  │         (TLS Termination, Rate Limiting)                │   │
│  └────────────────────┬────────────────────────────────────┘   │
│                       │                                          │
│  ┌────────────────────▼────────────┐  ┌──────────────────────┐ │
│  │  Frontend (React)               │  │  API Backend (Flask) │ │
│  │  Port: 3000                    │  │  Port: 8080         │ │
│  │  Replicas: 1-3                 │  │  Replicas: 1-3      │ │
│  └─────────────────────────────────┘  └──────────┬───────────┘ │
│                                                    │             │
│                    ┌───────────────────────────────┼───────────┐ │
│                    │                               │           │ │
│  ┌─────────────────▼──────┐  ┌───────────────────▼──────┐   │ │
│  │  Redis (Cache)         │  │  PVC (local-data)       │   │ │
│  │  Port: 6379            │  │  Size: 5-50Gi           │   │ │
│  │  Memory: 100MB         │  │  StorageClass: gp3     │   │ │
│  └────────────────────────┘  └───────────────────┬──────┘   │ │
│                                                    │           │ │
│  ┌─────────────────────────────────────────────────┼─────────┐ │
│  │         CronJobs (Scheduled)                    │         │ │
│  │  ┌──────────────┐  ┌──────────────┐            │         │ │
│  │  │ YouTube      │  │ DCInside     │────────────┘         │ │
│  │  │ Crawler      │  │ Crawler      │                       │ │
│  │  │ (2 hours)    │  │ (2 hours)    │                       │ │
│  │  └──────────────┘  └──────────────┘                       │ │
│  │                                                             │ │
│  │  ┌──────────────┐  ┌──────────────┐                       │ │
│  │  │ S3 Sync      │  │ Night Scaler │                       │ │
│  │  │ (6 hours)    │──│ (22:00-07:00)│                       │ │
│  │  └──────┬───────┘  └──────────────┘                       │ │
│  └─────────┼──────────────────────────────────────────────────┘ │
└────────────┼─────────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────┐
│  AWS S3                      │
│  Bucket: sns-monitor-data-*  │
│  Encryption: AES256          │
│  Tiering: Intelligent-Tiering│
└──────────────────────────────┘
```

### 2.2 데이터 흐름

#### 2.2.1 크롤링 데이터 흐름

```
YouTube API / DCInside Website
         │
         ▼
CronJob Crawlers (매 2시간)
         │
         ▼
PVC (local-data) - JSON 파일 저장
         │
         ├──► API Backend (읽기)
         ├──► S3 Sync (백업, 매 6시간)
         └──► Redis (캐싱)
```

#### 2.2.2 사용자 요청 흐름

```
User Request
     │
     ▼
Ingress (nginx)
     │
     ├──► Frontend (React)
     │         │
     │         └──► API Backend
     │                   │
     │                   ├──► Redis (Cache Check)
     │                   │         │
     │                   │    Hit ─┘
     │                   │
     │                   └──► PVC (File Read)
     │                             │
     │                             └──► JSON Response
```

### 2.3 네트워크 아키텍처

```
VPC (10.0.0.0/16)
├── Public Subnet (10.0.1.0/24)
│   ├── NAT Gateway
│   └── Internet Gateway
└── Private Subnet (10.0.2.0/24)
    └── EKS Nodes (t3.medium)
        ├── Frontend Pods
        ├── API Backend Pods
        ├── Redis Pods
        └── CronJob Pods
```

---

## 3. 기능 명세

### 3.1 YouTube 크롤러

#### 3.1.1 기능

- **채널 모니터링**: 지정된 YouTube 채널의 통계 수집
  - 구독자 수
  - 총 조회수
  - 총 영상 수
  - 최신 영상 목록

- **댓글 수집**: 각 영상의 댓글 및 좋아요 수집
  - 댓글 텍스트
  - 작성자 정보
  - 좋아요/답글 수
  - 타임스탬프 댓글 필터링 (노래 목록, 챕터 제외)

- **키워드 검색**: 특정 키워드로 영상 검색 및 분석

#### 3.1.2 모니터링 대상 채널

채널 목록은 Helm values 또는 환경 변수로 설정합니다:

```yaml
channels:
  - "@YourChannelHandle1"
  - "@YourChannelHandle2"
  - "@YourChannelHandle3"
```

#### 3.1.3 실행 스케줄

- **기본**: 매 2시간 (`0 */2 * * *`)
- **API 쿼터 관리**: YouTube Data API v3 일일 할당량 고려
- **재시도 전략**: 지수 백오프 (1초, 2초, 4초, 최대 3회)

#### 3.1.4 데이터 저장 형식

```json
{
  "channel_id": "UC...",
  "channel_title": "Your Channel Name",
  "channel_handle": "@YourChannelHandle",
  "subscriber_count": 123456,
  "view_count": 12345678,
  "video_count": 123,
  "videos": [
    {
      "video_id": "dQw4w9WgXcQ",
      "title": "Video Title",
      "published_at": "2025-01-01T00:00:00Z",
      "view_count": 12345,
      "like_count": 123,
      "comment_count": 45,
      "comments": [
        {
          "author": "User Name",
          "text": "Comment text",
          "like_count": 5,
          "published_at": "2025-01-01T01:00:00Z",
          "sentiment": "positive"
        }
      ]
    }
  ],
  "crawled_at": "2025-01-01T02:00:00Z"
}
```

### 3.2 DCInside 크롤러

#### 3.2.1 기능

- **갤러리 모니터링**: 지정된 DCInside 갤러리 게시글 수집
  - 인기 게시글 자동 선택 (조회수 + 추천수 기반)
  - 최소 10개 게시글 보장
  - 키워드 필터링

- **댓글 수집**: 각 게시글의 모든 댓글 수집
  - 댓글 텍스트
  - 작성자 정보
  - 추천/비추천 수

- **감성 분석**: 게시글 및 댓글의 긍정/부정/중립 분류
  - 키워드 기반 감성 분석
  - 통계 제공

#### 3.2.2 모니터링 대상 갤러리

갤러리 목록은 Helm values 또는 환경 변수로 설정합니다:

```yaml
galleries:
  - your-gallery-id-1
  - your-gallery-id-2
```

#### 3.2.3 실행 스케줄

- **기본**: 매 2시간 (`0 */2 * * *`)
- **도구**: Playwright (Chromium)
- **타임아웃**: 5분/갤러리

#### 3.2.4 데이터 저장 형식

```json
{
  "gallery_id": "your-gallery-id",
  "gallery_name": "Your Gallery Name",
  "crawled_at": "2025-01-01T02:00:00Z",
  "total_posts": 10,
  "total_comments": 123,
  "positive_count": 80,
  "negative_count": 20,
  "posts": [
    {
      "post_id": "12345678",
      "title": "Post Title",
      "author": "Author Name",
      "views": 1234,
      "recommends": 56,
      "comments": [
        {
          "author": "Commenter",
          "text": "Comment text",
          "sentiment": "positive"
        }
      ]
    }
  ]
}
```

### 3.3 API Backend

#### 3.3.1 주요 기능

- **REST API 제공**: 프론트엔드에서 필요한 데이터 제공
- **캐싱**: Redis를 통한 응답 캐싱 (TTL: 5분)
- **데이터 집계**: 크롤링 데이터를 분석하여 통계 제공
- **Health Check**: 서비스 상태 확인

#### 3.3.2 API 엔드포인트

| Method | Endpoint | 설명 | 캐싱 |
|--------|----------|------|------|
| GET | `/api/health` | 헬스체크 | 없음 |
| GET | `/api/vuddy/creators` | 크리에이터 목록 | 5분 |
| GET | `/api/youtube/channels` | YouTube 채널 데이터 | 5분 |
| GET | `/api/youtube/channels/{handle}` | 특정 채널 상세 | 5분 |
| GET | `/api/dcinside/{gallery_id}` | DCInside 갤러리 데이터 | 5분 |
| GET | `/api/crawler/results` | 크롤러 실행 결과 | 1분 |

### 3.4 Frontend

#### 3.4.1 주요 기능

- **대시보드**: 전체 크리에이터 통계 및 트렌드 표시
- **크리에이터 상세**: 개별 크리에이터의 상세 정보
- **실시간 업데이트**: 주기적 폴링으로 최신 데이터 표시
- **반응형 디자인**: 모바일, 태블릿, 데스크톱 지원

#### 3.4.2 주요 컴포넌트

| 컴포넌트 | 경로 | 설명 |
|----------|------|------|
| Dashboard | `/` | 메인 대시보드 |
| CreatorDetail | `/creator/:id` | 크리에이터 상세 페이지 |

#### 3.4.3 UI/UX 기능

- **로딩 상태**: 스켈레톤 UI로 로딩 중 콘텐츠 구조 미리보기
- **에러 처리**: EmptyState 컴포넌트로 명확한 에러 메시지
- **사용자 피드백**: Toast 메시지로 액션 결과 알림
- **접근성**: 키보드 네비게이션, ARIA 라벨, 스크린 리더 지원

---

## 4. 데이터 모델

### 4.1 저장소 구조

#### 4.1.1 PVC (local-data)

```
/app/local-data/
├── youtube/
│   ├── channels/
│   │   └── {channel_id}/
│   │       └── {timestamp}.json
│   └── keywords/
│       └── {keyword}/
│           └── {timestamp}.json
├── dcinside/
│   └── {gallery_id}/
│       └── {timestamp}.json
├── metadata/
│   └── crawler_metadata.json
└── vuddy/
    └── comprehensive_analysis/
        └── {creator_name}.json
```

#### 4.1.2 S3 백업 구조

```
s3://sns-monitor-data-{account-id}/
├── data/
│   ├── youtube/
│   │   ├── channels/
│   │   └── keywords/
│   ├── dcinside/
│   │   └── {gallery_id}/
│   └── metadata/
└── raw-data/              # raw data storage
    ├── youtube/
    └── dcinside/
```

### 4.2 데이터 보존 정책

- **PVC**: 최대 5-50Gi (설정 가능)
- **S3 Lifecycle**:
  - 30일 후: STANDARD → STANDARD_IA
  - 60일 후: STANDARD_IA → GLACIER
  - 180일 후: raw-data 삭제
  - 365일 후: 분석 데이터 삭제

### 4.3 캐시 정책

- **Redis TTL**:
  - 채널 데이터: 5분
  - 갤러리 데이터: 5분
  - 크롤러 결과: 1분
- **캐시 무효화**: 크롤러 실행 후 관련 키 삭제

---

## 5. API 명세

### 5.1 Health Check

```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T00:00:00Z",
  "version": "2.0.0"
}
```

### 5.2 크리에이터 목록

```http
GET /api/vuddy/creators
```

**Response:**
```json
{
  "creators": [
    {
      "name": "Creator Name",
      "youtube_channel": "@YourChannelHandle",
      "subscriber_count": 123456,
      "last_updated": "2025-01-01T00:00:00Z"
    }
  ]
}
```

### 5.3 YouTube 채널 데이터

```http
GET /api/youtube/channels?handle=@YourChannelHandle
```

**Response:**
```json
{
  "channel_id": "UC...",
  "channel_title": "Your Channel Name",
  "channel_handle": "@YourChannelHandle",
  "subscriber_count": 123456,
  "view_count": 12345678,
  "video_count": 123,
  "videos": [...],
  "crawled_at": "2025-01-01T02:00:00Z"
}
```

### 5.4 DCInside 갤러리 데이터

```http
GET /api/dcinside/your-gallery-id
```

**Response:**
```json
{
  "gallery_id": "your-gallery-id",
  "gallery_name": "Your Gallery Name",
  "total_posts": 10,
  "total_comments": 123,
  "positive_count": 80,
  "negative_count": 20,
  "posts": [...],
  "crawled_at": "2025-01-01T02:00:00Z"
}
```

---

## 6. UI/UX 명세

### 6.1 디자인 원칙

- **명확성**: 정보를 명확하고 직관적으로 표시
- **일관성**: 일관된 디자인 패턴 및 컴포넌트 사용
- **접근성**: WCAG 2.1 AA 수준 준수
- **반응형**: 모바일 우선 설계

### 6.2 주요 UI 컴포넌트

#### 6.2.1 LoadingSkeleton

- **용도**: 데이터 로딩 중 콘텐츠 구조 미리보기
- **타입**:
  - `CardSkeleton`: 카드 형태 로딩
  - `StatCardSkeleton`: 통계 카드 로딩
  - `TableSkeleton`: 테이블 로딩

#### 6.2.2 EmptyState

- **용도**: 빈 상태 또는 에러 상태 표시
- **타입**:
  - `EmptyStateNoData`: 데이터 없음
  - `EmptyStateError`: 에러 발생
  - `EmptyStateLoading`: 로딩 중

#### 6.2.3 Toast

- **용도**: 사용자 액션에 대한 피드백
- **타입**: success, error, warning, info
- **자동 사라짐**: 5초 후 자동 제거

### 6.3 반응형 브레이크포인트

```css
/* 모바일 */
@media (max-width: 480px) { ... }

/* 태블릿 */
@media (min-width: 481px) and (max-width: 768px) { ... }

/* 데스크톱 */
@media (min-width: 769px) { ... }
```

### 6.4 접근성 요구사항

- **키보드 네비게이션**: 모든 기능을 키보드만으로 사용 가능
- **ARIA 라벨**: 스크린 리더를 위한 의미 있는 라벨
- **색상 대비**: WCAG AA 수준 (4.5:1 이상)
- **포커스 표시**: 명확한 포커스 인디케이터

---

## 7. 보안 요구사항

### 7.1 인프라 보안

#### 7.1.1 S3 보안

- ✅ **서버 사이드 암호화**: AES256
- ✅ **퍼블릭 액세스 차단**: `block_public_acls = true`
- ✅ **HTTPS 강제**: `aws:SecureTransport` 조건
- ✅ **암호화 없는 업로드 차단**: 버킷 정책

#### 7.1.2 Pod Identity

- ✅ **IRSA 대신 Pod Identity 사용**: 최신 모범 사례
- ✅ **최소 권한 원칙**: S3 접근만 허용
- ✅ **자동 자격 증명 로테이션**: Pod Identity Agent

#### 7.1.3 Network Policy

- ⚠️ **현재 상태**: 활성화됨 (`enabled: true`)
- ✅ **Pod 간 통신 제한**: 필요한 통신만 허용
- ✅ **Ingress Controller만 허용**: 외부 접근 제어

### 7.2 컨테이너 보안

#### 7.2.1 Pod Security Context

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault
```

#### 7.2.2 Container Security Context

```yaml
containerSecurityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false  # ⚠️ 개선 필요: true로 변경 권장
  capabilities:
    drop:
      - ALL
```

### 7.3 애플리케이션 보안

#### 7.3.1 입력 검증

- ✅ **API 파라미터 검증**: 화이트리스트 방식
- ✅ **SQL Injection 방지**: 파라미터 바인딩 사용
- ⚠️ **환경 변수 검증**: 앱 시작 시점 검증 추가 필요

#### 7.3.2 로깅 보안

- ⚠️ **민감 정보 마스킹**: API 키, 토큰 마스킹 필요
- ✅ **구조화된 로깅**: JSON 형식 로그
- ⚠️ **프로덕션 로그 레벨**: DEBUG 레벨 제거 필요

### 7.4 CI/CD 보안

#### 7.4.1 GitHub Actions

- ✅ **OIDC 인증**: GitHub OIDC Provider 사용
- ✅ **최소 권한**: `contents: read`, `packages: read`
- ✅ **Secrets 관리**: GitHub Secrets 사용
- ✅ **Pull Request 배포 차단**: `workflow_dispatch`만 허용

---

## 8. 성능 및 확장성

### 8.1 성능 목표

| 메트릭 | 목표 | 현재 |
|--------|------|------|
| API 응답 시간 (p95) | < 500ms | ~300ms |
| API 응답 시간 (p99) | < 1s | ~800ms |
| 프론트엔드 로딩 시간 | < 2s | ~1.5s |
| 크롤러 실행 시간 | < 5분 | ~3분 |

### 8.2 확장성 전략

#### 8.2.1 수평 확장

- **HPA (Horizontal Pod Autoscaler)**:
  - 현재: 비활성화
  - 활성화 시: minReplicas=1, maxReplicas=2
  - 트리거: CPU 사용률 80%

#### 8.2.2 리소스 제한

```yaml
# Frontend
resources:
  requests:
    cpu: 25m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 256Mi

# API Backend
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 256Mi
```

### 8.3 캐싱 전략

- **Redis 캐싱**: API 응답 캐싱 (TTL: 5분)
- **브라우저 캐싱**: 정적 자산 캐싱 (Cache-Control)
- **CDN**: CloudFront 사용 고려 (향후)

### 8.4 병목 지점

1. **PVC I/O**: JSON 파일 읽기/쓰기
   - **해결책**: 데이터베이스 마이그레이션 고려 (DynamoDB, PostgreSQL)

2. **크롤러 실행 시간**: 여러 채널/갤러리 순차 처리
   - **해결책**: 병렬 처리, 작업 큐 도입

3. **API 응답 시간**: 대용량 데이터 조회
   - **해결책**: 페이지네이션, 데이터 집계 최적화

---

## 9. 운영 및 모니터링

### 9.1 Health Check

#### 9.1.1 Liveness Probe

```yaml
livenessProbe:
  httpGet:
    path: /api/health
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 30
  timeoutSeconds: 5
  failureThreshold: 3
```

#### 9.1.2 Readiness Probe

```yaml
readinessProbe:
  httpGet:
    path: /api/health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

### 9.2 로깅

#### 9.2.1 로그 형식

```json
{
  "timestamp": "2025-01-01T00:00:00Z",
  "level": "INFO",
  "service": "api-backend",
  "message": "Request processed",
  "request_id": "abc123",
  "duration_ms": 150,
  "status_code": 200
}
```

#### 9.2.2 로그 레벨

- **개발**: DEBUG
- **프로덕션**: INFO
- **에러**: ERROR

### 9.3 모니터링 (계획)

#### 9.3.1 메트릭 수집

- **Prometheus**: 애플리케이션 메트릭
- **CloudWatch**: AWS 리소스 메트릭
- **Grafana**: 대시보드 시각화

#### 9.3.2 알람 설정

- **API 에러율**: 5% 이상 시 알람
- **크롤러 실패**: 연속 3회 실패 시 알람
- **디스크 사용률**: 80% 이상 시 알람
- **메모리 사용률**: 90% 이상 시 알람

### 9.4 백업 및 복구

#### 9.4.1 백업 전략

- **S3 자동 동기화**: 매 6시간
- **PVC 스냅샷**: 수동 (필요 시)
- **데이터베이스 백업**: DynamoDB Point-in-Time Recovery (향후)

#### 9.4.2 복구 절차

1. S3에서 데이터 복원
2. PVC 재마운트
3. Pod 재시작
4. 데이터 검증

---

## 10. 비용 최적화

### 10.1 현재 비용 구조

| 항목 | 월 비용 (USD) | 비고 |
|------|--------------|------|
| EKS Control Plane | $73 | 고정 비용 |
| EC2 (t3.medium x1) | ~$30 | 온디맨드 |
| EBS gp3 (10Gi) | ~$1 | 스토리지 |
| S3 Intelligent-Tiering | ~$1 | 데이터 백업 |
| Data Transfer | ~$5 | 아웃바운드 |
| **합계** | **~$110** | |

### 10.2 비용 절감 전략

#### 10.2.1 야간 스케일 다운

- **스케줄**: 22:00-07:00 KST (평일만)
- **절감액**: ~$10-15/월
- **구현 상태**: ⚠️ CronJob 템플릿 필요

#### 10.2.2 크롤러 스케줄 최적화

- **현재**: 매 2시간
- **최적화**: 필요 시에만 실행 (이벤트 기반)
- **절감액**: ~$5/월

#### 10.2.3 S3 Lifecycle 정책

- **30일 후**: STANDARD → STANDARD_IA (50% 절감)
- **60일 후**: STANDARD_IA → GLACIER (80% 절감)
- **절감액**: ~$5-10/월

### 10.3 비용 모니터링

- **AWS Cost Explorer**: 월별 비용 추적
- **비용 알람**: 예산 초과 시 알림
- **태그 기반 비용 분석**: 리소스별 비용 추적

---

## 11. 트레이드오프 및 제약사항

### 11.1 트레이드오프

#### 11.1.1 실시간성 vs 비용

- **현재**: 2시간마다 크롤링 (비용 절감 우선)
- **대안**: 실시간 알림 (Webhook, EventBridge)
- **트레이드오프**: 실시간성 증가 → 비용 증가 (~$20-30/월)

#### 11.1.2 데이터 정확도 vs 수집 속도

- **현재**: 정확한 데이터 수집 우선
- **대안**: 빠른 수집, 일부 오류 허용
- **트레이드오프**: 속도 증가 → 정확도 감소

#### 11.1.3 기능 범위 vs 개발 속도

- **현재**: 핵심 기능 우선 구현
- **대안**: 풍부한 기능 포함
- **트레이드오프**: 기능 증가 → 개발 시간 증가

### 11.2 제약사항

#### 11.2.1 기술적 제약

- **YouTube API 쿼터**: 일일 10,000 유닛 제한
- **DCInside 크롤링**: robots.txt 준수 필요
- **PVC 용량**: 최대 50Gi (확장 가능)

#### 11.2.2 운영 제약

- **EKS Private Endpoint**: 수동 배포 필요
- **모니터링 부재**: Prometheus/CloudWatch 설정 필요
- **백업 검증**: 수동 검증 필요

#### 11.2.3 비용 제약

- **월 예산**: ~$110
- **확장 시**: 트래픽 증가에 따른 비용 증가

---

## 12. 향후 개선 계획

### 12.1 단기 개선 (1-2개월)

#### 12.1.1 보안 강화

- [ ] **readOnlyRootFilesystem 활성화**: API Backend 컨테이너
- [ ] **환경 변수 검증**: 앱 시작 시점 필수 변수 검증
- [ ] **로그 마스킹**: 민감 정보 마스킹 함수 추가
- [ ] **NetworkPolicy 세분화**: 특정 네임스페이스만 허용

#### 12.1.2 모니터링 구축

- [ ] **Prometheus 설정**: 메트릭 수집
- [ ] **Grafana 대시보드**: 시각화
- [ ] **알람 설정**: 에러율, 리소스 사용률

#### 12.1.3 운영 효율성

- [ ] **야간 스케일 다운 구현**: CronJob 템플릿 생성
- [ ] **로깅 표준화**: 구조화된 로깅 적용
- [ ] **백업 검증 자동화**: 스크립트 작성

### 12.2 중기 개선 (3-6개월)

#### 12.2.1 성능 최적화

- [ ] **데이터베이스 마이그레이션**: DynamoDB 또는 PostgreSQL
- [ ] **병렬 크롤링**: 여러 채널/갤러리 동시 처리
- [ ] **API 페이지네이션**: 대용량 데이터 조회 최적화

#### 12.2.2 기능 확장

- [ ] **실시간 알림**: Webhook, EventBridge 통합
- [ ] **다크 모드**: 사용자 테마 선택
- [ ] **데이터 내보내기**: CSV, PDF 리포트

#### 12.2.3 사용자 경험

- [ ] **오프라인 지원**: Service Worker 통합
- [ ] **국제화**: 다국어 지원
- [ ] **성능 모니터링**: Web Vitals 측정

### 12.3 장기 개선 (6개월 이상)

#### 12.3.1 아키텍처 개선

- [ ] **마이크로서비스 분리**: 크롤러, 분석기 독립 서비스
- [ ] **이벤트 기반 아키텍처**: EventBridge, SQS 통합
- [ ] **멀티 리전 배포**: 고가용성 향상

#### 12.3.2 AI/ML 기능

- [ ] **감성 분석 고도화**: Bedrock Claude 통합
- [ ] **트렌드 예측**: 머신러닝 모델
- [ ] **자동 요약**: 댓글 자동 요약

#### 12.3.3 플랫폼 확장

- [ ] **추가 플랫폼**: Twitter, Instagram, TikTok
- [ ] **Chrome Extension**: 브라우저 확장 프로그램
- [ ] **모바일 앱**: React Native 앱

---

## 부록

### A. 용어 정의

- **VTuber**: 버추얼 유튜버
- **Creator**: 크리에이터
- **PVC**: PersistentVolumeClaim (Kubernetes)
- **HPA**: Horizontal Pod Autoscaler
- **IRSA**: IAM Roles for Service Accounts
- **Pod Identity**: EKS Pod Identity

### B. 참고 문서

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - 시스템 아키텍처 상세
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - 배포 가이드
- [architecture-security-review.md](docs/architecture-security-review.md) - 보안 검토 보고서
- [ui-ux-summary.md](docs/ui-ux-summary.md) - UI/UX 개선 요약
- [cost-optimization.md](docs/cost-optimization.md) - 비용 최적화 가이드

### C. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 2.0.0 | 2025-01-XX | 초기 스펙 작성 |
| | | - 프로젝트 개요 및 아키텍처 정의 |
| | | - 기능 명세 상세화 |
| | | - 보안 요구사항 정리 |
| | | - 향후 개선 계획 수립 |

---

**작성자**: DevSecOps Team  
**검토자**: Platform Team  
**승인자**: Engineering Lead
