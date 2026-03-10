# SNS Monitoring System - Architecture Documentation

> **Version:** 1.2.0
> **Last Updated:** 2025-12-29
> **Maintainer:** Platform Team
> 
> **주요 변경사항 (v1.2.0):**
> - IRSA에서 Pod Identity로 마이그레이션 완료
> - ServiceAccount annotation 불필요
> - 보안 강화 및 관리 간소화

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Component Details](#3-component-details)
4. [Data Flow](#4-data-flow)
5. [Infrastructure](#5-infrastructure)
6. [Build & Deployment](#6-build--deployment)
7. [Cost Optimization](#7-cost-optimization)
8. [Security](#8-security)
9. [Monitoring & Operations](#9-monitoring--operations)

---

## 1. Overview

SNS Monitoring System은 크리에이터 및 커뮤니티의 소셜 미디어 활동을 모니터링하고 분석하는 시스템입니다.

### 1.1 주요 기능

| 기능 | 설명 |
|------|------|
| YouTube 모니터링 | 채널 구독자, 조회수, 댓글 수집 |
| DCInside 크롤링 | 갤러리 게시글 및 댓글 수집 |
| 실시간 대시보드 | React 기반 웹 대시보드 |
| 데이터 백업 | S3 자동 동기화 |

### 1.2 기술 스택

```
Frontend:    React 18, Axios, ReCharts
Backend:     Python 3.11, Flask, boto3
Database:    Redis (Cache), EBS PVC (Storage), S3 (Backup)
Container:   Docker, Kubernetes (EKS)
IaC:         Terraform, Helm
CI/CD:       GitHub Actions
```

### 1.3 프로젝트 구조

```
sns-monitoring-system/
├── frontend/                 # React 프론트엔드
│   ├── src/components/       # React 컴포넌트
│   └── build/                # 빌드 결과물
├── lambda/                   # 백엔드 서비스
│   ├── api-backend/          # REST API 서버
│   ├── youtube-crawler/      # YouTube 크롤러
│   ├── dcinside-crawler/     # DCInside 크롤러
│   └── common/               # 공통 유틸리티
├── docker/                   # Dockerfile 모음
├── helm/sns-monitor/         # Helm 차트
│   ├── templates/            # K8s 매니페스트 템플릿
│   └── values.yaml           # 기본 설정값
├── k8s/deployments/          # Raw K8s 매니페스트
├── terraform/                # AWS 인프라 코드
├── scripts/                  # 유틸리티 스크립트
└── .github/workflows/        # CI/CD 파이프라인
```

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Internet                                │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ HTTPS (443)
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AWS EKS Cluster (your-cluster)                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              Nginx Ingress Controller                          │ │
│  │              (TLS Termination, Rate Limiting)                  │ │
│  └────────────────────────────────┬───────────────────────────────┘ │
│                     ┌─────────────┴─────────────┐                   │
│                     │                           │                   │
│  ┌──────────────────▼──────────┐  ┌────────────▼────────────────┐  │
│  │  Frontend (React)           │  │  API Backend (Flask)        │  │
│  │  ────────────────────────   │  │  ────────────────────────   │  │
│  │  Port: 3000                 │  │  Port: 8080                 │  │
│  │  Image: sns-monitor-frontend│  │  Image: sns-monitor-api     │  │
│  │  Replicas: 1-3              │  │  Replicas: 1-3              │  │
│  └─────────────────────────────┘  └────────────┬────────────────┘  │
│                                                 │                   │
│                    ┌────────────────────────────┼─────────────┐     │
│                    │                            │             │     │
│  ┌─────────────────▼──────┐  ┌─────────────────▼──────┐      │     │
│  │  Redis (Cache)         │  │  PVC (local-data)      │      │     │
│  │  ──────────────────    │  │  ──────────────────    │      │     │
│  │  Port: 6379            │  │  Size: 5-50Gi          │      │     │
│  │  Memory: 100MB         │  │  StorageClass: gp3     │      │     │
│  └────────────────────────┘  └─────────────────┬──────┘      │     │
│                                                 │             │     │
│  ┌──────────────────────────────────────────────┼─────────────┤     │
│  │            CronJobs (Scheduled)              │             │     │
│  │  ┌─────────────────┐  ┌─────────────────┐   │             │     │
│  │  │ YouTube Crawler │  │ DCInside Crawler│   │             │     │
│  │  │ (every 2 hours) │  │ (every 2 hours) │───┘             │     │
│  │  └─────────────────┘  └─────────────────┘                 │     │
│  │                                                            │     │
│  │  ┌─────────────────┐  ┌─────────────────┐                 │     │
│  │  │ S3 Sync         │  │ Night Scaler    │                 │     │
│  │  │ (every 6 hours) │──│ (22:00-07:00)   │                 │     │
│  │  └────────┬────────┘  └─────────────────┘                 │     │
│  └───────────┼───────────────────────────────────────────────┘     │
└──────────────┼─────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────┐
│  AWS S3                       │
│  ──────────────────────────   │
│  Bucket: sns-monitor-data-*   │
│  Encryption: AES256           │
│  Tiering: Intelligent-Tiering │
└──────────────────────────────┘
```

### 2.2 Network Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    VPC (10.0.0.0/16)                             │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │  Public Subnet       │  │  Private Subnet      │             │
│  │  (10.0.1.0/24)       │  │  (10.0.2.0/24)       │             │
│  │  ┌────────────────┐  │  │  ┌────────────────┐  │             │
│  │  │ NAT Gateway    │  │  │  │ EKS Nodes      │  │             │
│  │  │ Internet GW    │◄─┼──┼──│ (t3.medium)    │  │             │
│  │  └────────────────┘  │  │  └────────────────┘  │             │
│  └──────────────────────┘  └──────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Details

### 3.1 Frontend (React)

| 항목 | 설명 |
|------|------|
| 경로 | `frontend/` |
| 프레임워크 | React 18.2.0 |
| 빌드 도구 | Create React App |
| 주요 라이브러리 | Axios, ReCharts |

**주요 컴포넌트:**

| 컴포넌트 | 파일 | 설명 |
|----------|------|------|
| Dashboard | `Dashboard.jsx` | 메인 대시보드 |
| ArchiveStudioDetail | `ArchiveStudioDetail.jsx` | AkaiV 스튜디오 상세 |
| SkoshismDetail | `SkoshismDetail.jsx` | SKOSHISM 갤러리 상세 |
| AuthLogin | `AuthLogin.jsx` | 인증 로그인 |

**라우팅:**

```javascript
/                 → Dashboard
/akaiv-studio     → ArchiveStudioDetail
/skoshism         → SkoshismDetail
```

### 3.2 API Backend (Flask)

| 항목 | 설명 |
|------|------|
| 경로 | `lambda/api-backend/` |
| 프레임워크 | Flask |
| 포트 | 8080 |

**API 엔드포인트:**

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/health` | 헬스체크 |
| GET | `/api/vuddy/creators` | 크리에이터 목록 |
| GET | `/api/youtube/channels` | YouTube 채널 데이터 |
| GET | `/api/dcinside/{gallery_id}` | DCInside 갤러리 데이터 |
| GET | `/api/crawler/results` | 크롤러 결과 조회 |

### 3.3 Crawlers

#### YouTube Crawler

| 항목 | 설명 |
|------|------|
| 경로 | `lambda/youtube-crawler/` |
| API | YouTube Data API v3 |
| 스케줄 | 매 2시간 |

**수집 데이터:**
- 채널 통계 (구독자, 조회수, 영상 수)
- 최신 영상 목록
- 댓글 및 좋아요

**설정 채널:**
```yaml
channels:
  - "@AkaivStudioOfficial"
  - "@BARABARA_KR"
  - "@irocloud_"
  - "@NIN0SUNDAY"
  - "@KoyoTempest"
```

#### DCInside Crawler

| 항목 | 설명 |
|------|------|
| 경로 | `lambda/dcinside-crawler/` |
| 도구 | Playwright (Chromium) |
| 스케줄 | 매 2시간 |

**수집 갤러리:**
```yaml
galleries:
  - ivnit (이브닛)
  - akaiv (아카이브 스튜디오)
  - skoshism (스코시즘)
  - soopvirtualstreamer (숲 버추얼)
```

### 3.4 Data Storage

#### Local Data (PVC)

```
/app/local-data/
├── youtube/
│   ├── channels/          # 채널별 데이터
│   │   └── {channel_id}/
│   │       └── {timestamp}.json
│   └── keywords/          # 키워드 검색 결과
├── dcinside/
│   └── {gallery_id}/      # 갤러리별 게시글
├── metadata/              # 크롤링 메타데이터
└── vuddy/
    └── comprehensive_analysis/
```

#### S3 Backup

```
s3://sns-monitor-data-{account-id}/
├── data/
│   ├── youtube/
│   ├── dcinside/
│   └── metadata/
└── raw-data/              # 원본 데이터 아카이브
```

---

## 4. Data Flow

### 4.1 크롤링 데이터 흐름

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  YouTube    │     │  DCInside   │     │  기타 플랫폼 │
│  API        │     │  Website    │     │             │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────┐
│              CronJob Crawlers                        │
│  (YouTube Crawler / DCInside Crawler)                │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │  PVC (local-data)    │
              │  JSON 파일 저장       │
              └──────────┬───────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ API Backend │  │ S3 Sync     │  │ Redis       │
│ (읽기)      │  │ (백업)      │  │ (캐싱)      │
└─────────────┘  └─────────────┘  └─────────────┘
```

### 4.2 사용자 요청 흐름

```
User Request → Ingress → Frontend → API Backend → Redis (Cache Hit?)
                                          │              │
                                          │   Yes ◄──────┘
                                          │
                                          ▼   No
                                    PVC (File Read)
                                          │
                                          ▼
                                    JSON Response
```

---

## 5. Infrastructure

### 5.1 AWS Resources

| 리소스 | 이름/ARN | 용도 |
|--------|----------|------|
| EKS Cluster | `your-cluster` | Kubernetes 클러스터 |
| S3 Bucket | `sns-monitor-data` | 데이터 백업 |
| IAM Role | `sns-monitor-pod-identity.platform.dev` | Pod Identity (S3 접근) |
| IAM Role | `sns-monitor-eks-deploy.iam.github` | GitHub Actions |

### 5.2 Kubernetes Resources

**Namespace:** `platform`

| 리소스 타입 | 이름 | 설명 |
|-------------|------|------|
| Deployment | sns-monitor-frontend | React 프론트엔드 |
| Deployment | sns-monitor-api-backend | Flask API 서버 |
| StatefulSet | sns-monitor-redis | Redis 캐시 |
| CronJob | sns-monitor-youtube-crawler | YouTube 크롤러 |
| CronJob | sns-monitor-dcinside-crawler | DCInside 크롤러 |
| CronJob | sns-monitor-s3-sync | S3 백업 동기화 |
| PVC | sns-monitor-local-data | 데이터 저장소 |
| Service | sns-monitor-frontend | Frontend ClusterIP |
| Service | sns-monitor-api-backend | API ClusterIP |
| Ingress | sns-monitor | 외부 접근 |

### 5.3 Terraform Modules

```
terraform/
├── main.tf              # Provider 설정
├── variables.tf         # 변수 정의
├── s3.tf                # S3 버킷 + 정책
├── github-oidc.tf       # GitHub Actions OIDC
└── pod-identity.tf      # Pod Identity 역할 (irsa-s3-sync.tf는 DEPRECATED)
```

**주요 변수:**

```hcl
variable "eks_cluster_name" { default = "your-cluster" }
variable "s3_bucket_name"   { default = "sns-monitor-data" }
variable "kubernetes_namespace" { default = "platform" }
variable "env" { default = "dev" }
```

---

## 6. Build & Deployment

### 6.1 Docker Images

| 이미지 | Dockerfile | 설명 |
|--------|------------|------|
| `sns-monitor-frontend` | `docker/Dockerfile.frontend` | React 프론트엔드 |
| `sns-monitor-api-backend` | `docker/Dockerfile.api` | Flask API |
| `sns-monitor-youtube-crawler` | `docker/Dockerfile.youtube-crawler` | YouTube 크롤러 |
| `sns-monitor-dcinside-crawler` | `docker/Dockerfile.crawler` | DCInside 크롤러 |

**이미지 레지스트리:** `ghcr.io/your-org/sns-monitor-*`

### 6.2 CI/CD Pipeline

#### 자동 빌드 (GitHub Actions)

**트리거 조건:**
- `main`, `develop` 브랜치 push
- `docker/**`, `lambda/**`, `frontend/**` 경로 변경

**워크플로우:** `.github/workflows/docker-build-push.yaml`

```yaml
# 빌드 매트릭스
matrix:
  - api-backend
  - frontend
  - youtube-crawler
  - dcinside-crawler
```

**빌드 단계:**
1. Checkout 코드
2. Docker Buildx 설정
3. GHCR 로그인
4. Multi-platform 빌드 (amd64/arm64)
5. 이미지 푸시 (latest + SHA 태그)

#### 수동 배포

EKS 클러스터가 Private Endpoint만 지원하므로 수동 배포 필요:

```bash
# 1. kubeconfig 설정
export KUBECONFIG=/path/to/kubeconfig

# 2. Helm 배포
helm upgrade --install sns-monitor ./helm/sns-monitor \
  --namespace platform \
  --values ./helm/sns-monitor/values.yaml

# 3. 특정 컴포넌트 롤아웃
kubectl rollout restart deployment sns-monitor-frontend -n platform
kubectl rollout restart deployment sns-monitor-api-backend -n platform
```

### 6.3 로컬 개발 환경

```bash
# Docker Compose로 전체 스택 실행
docker-compose up -d

# 개별 서비스 실행
docker-compose up frontend api-backend redis

# 프론트엔드 개발 모드
cd frontend && npm start

# 크롤러 수동 실행
docker-compose run youtube-crawler
docker-compose run dcinside-crawler
```

### 6.4 Helm Chart 배포

```bash
# 차트 의존성 업데이트
helm dependency update ./helm/sns-monitor

# Dry-run으로 확인
helm upgrade --install sns-monitor ./helm/sns-monitor \
  --namespace platform \
  --dry-run --debug

# 실제 배포
helm upgrade --install sns-monitor ./helm/sns-monitor \
  --namespace platform \
  --set image.tag=latest

# 프로덕션 배포
helm upgrade --install sns-monitor ./helm/sns-monitor \
  --namespace platform \
  --values ./helm/sns-monitor/values-production.yaml
```

### 6.5 Terraform 인프라 배포

```bash
cd terraform

# 초기화
terraform init

# 계획 확인
terraform plan

# 적용
terraform apply

# 특정 리소스만 적용
terraform apply -target=aws_iam_role.s3_sync
```

---

## 7. Cost Optimization

### 7.1 예상 월간 비용

| 항목 | 비용 (USD) | 비고 |
|------|------------|------|
| EKS Control Plane | $73 | 고정 비용 |
| EC2 (t3.medium x1) | ~$30 | 온디맨드 |
| EBS gp3 (10Gi) | ~$1 | 스토리지 |
| S3 Intelligent-Tiering | ~$1 | 데이터 백업 |
| Data Transfer | ~$5 | 아웃바운드 |
| **합계** | **~$110** | |

### 7.2 비용 최적화 전략

1. **야간 스케일다운**
   - 22:00~07:00 KST 동안 replica 0으로 축소
   - CronJob: `cronjob-scaler.yaml`

2. **크롤러 스케줄 최적화**
   - 매 2시간 실행 (연속 실행 대신)
   - YouTube API 쿼터 관리

3. **S3 Intelligent-Tiering**
   - 자동으로 비용 효율적인 스토리지 클래스로 이동
   - 30일 후 Standard-IA, 60일 후 Glacier

4. **Redis 메모리 제한**
   - 최대 100MB
   - LRU 정책으로 오래된 데이터 자동 삭제

---

## 8. Security

### 8.1 네트워크 보안

| 항목 | 설정 |
|------|------|
| Ingress TLS | Let's Encrypt SSL |
| Rate Limiting | 20 req/s per IP |
| Network Policy | Pod간 통신 제한 |

### 8.2 컨테이너 보안

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
```

### 8.3 데이터 보안

| 항목 | 설정 |
|------|------|
| S3 암호화 | AES256 (Server-Side) |
| S3 접근 | HTTPS Only |
| Secrets | Kubernetes Secrets + RBAC |

### 8.4 IAM 보안

- **OIDC**: GitHub Actions → AWS 역할 위임
- **Pod Identity**: EKS Pod → S3 접근 (최소 권한, 자동 자격 증명 주입)
- **Bucket Policy**: 암호화 강제

---

## 9. Monitoring & Operations

### 9.1 Health Checks

```yaml
# API Backend
livenessProbe:
  httpGet:
    path: /api/health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /api/health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
```

### 9.2 로그 확인

```bash
# Pod 로그
kubectl logs -f deployment/sns-monitor-api-backend -n platform

# CronJob 로그
kubectl logs job/sns-monitor-youtube-crawler-{job-id} -n platform

# 이전 Pod 로그
kubectl logs deployment/sns-monitor-api-backend -n platform --previous
```

### 9.3 트러블슈팅

| 증상 | 확인 방법 | 해결책 |
|------|----------|--------|
| Pod CrashLoopBackOff | `kubectl describe pod` | 리소스 증가, 환경변수 확인 |
| PVC 마운트 실패 | `kubectl get events` | 노드 재시작, PVC 재생성 |
| S3 AccessDenied | Pod Identity 확인 | Pod Identity Association 확인 |
| 크롤러 타임아웃 | CronJob 로그 확인 | timeout 증가, 리소스 증가 |
| CronJob DeadlineExceeded | `kubectl get jobs` | Pod Affinity 확인 (RWO PVC 노드) |

### 9.4 백업 및 복구

**S3 백업 (자동):**
```bash
# S3 동기화 상태 확인
kubectl get cronjob sns-monitor-s3-sync -n platform

# 수동 백업 실행
kubectl create job s3-sync-manual --from=cronjob/sns-monitor-s3-sync -n platform
```

**복구:**
```bash
# S3에서 데이터 복원
python scripts/s3_sync.py --mode restore
```

---

## Appendix

### A. 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LOCAL_MODE` | `true` | 로컬 파일 시스템 사용 |
| `LOCAL_DATA_DIR` | `/app/local-data` | 데이터 저장 경로 |
| `REDIS_HOST` | `redis` | Redis 호스트 |
| `REDIS_PORT` | `6379` | Redis 포트 |
| `S3_BUCKET` | `sns-monitor-data-*` | S3 버킷 이름 |
| `YOUTUBE_API_KEY` | - | YouTube API 키 (필수) |

### B. Pod Affinity (RWO PVC)

CronJob 크롤러들은 RWO (ReadWriteOnce) PVC를 사용하므로, API Backend와 같은 노드에서 실행되어야 합니다:

```yaml
affinity:
  podAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchLabels:
          app.kubernetes.io/name: sns-monitor
          app.kubernetes.io/component: api-backend
      topologyKey: kubernetes.io/hostname
```

### C. 참고 문서

- [Helm Chart README](../helm/sns-monitor/README.md)
- [Kubernetes Deployments](../k8s/README.md)
- [Terraform S3 Security](./terraform-s3-security-improvements.md)
- [Security Policy](../SECURITY.md)

### D. 연락처

- **Repository:** https://github.com/your-org/sns-monitor
- **Team:** DevSecOps Team
