# 데이터 수집 구조 및 Docker/Kubernetes 배포 구조 검토 보고서

## 📋 실행 요약

현재 시스템은 **로컬 개발 환경**과 **프로덕션 환경**을 모두 지원하는 하이브리드 구조로 설계되어 있습니다. 전반적으로 잘 구성되어 있으나, Kubernetes 배포를 위한 몇 가지 개선 사항이 필요합니다.

### ✅ 잘 구성된 부분
- Docker Compose 기반 로컬 개발 환경
- LOCAL_MODE를 통한 유연한 데이터 저장소 전환
- 마이크로서비스 아키텍처 (크롤러 분리)
- Helm 차트를 통한 배포 자동화 준비

### ⚠️ 개선이 필요한 부분
- Kubernetes에서 ReadWriteMany PVC의 성능 이슈
- 크롤러 스케줄링 메커니즘 부재
- 데이터 동기화 전략 부재
- 프로덕션 환경에서의 데이터 일관성 보장

---

## 1. 데이터 수집 구조 분석

### 1.1 현재 구조

```
┌─────────────────────────────────────────────────────────┐
│              데이터 수집 레이어                          │
├─────────────────────────────────────────────────────────┤
│  YouTube Crawler  │  Vuddy Crawler  │  DCInside Crawler│
│  Twitter Crawler  │  RSS Crawler    │  Telegram Crawler│
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │   LOCAL_MODE 체크             │
        └───────────────────────────────┘
                │              │
        ┌───────┘              └───────┐
        ▼                              ▼
┌───────────────┐            ┌──────────────────┐
│ 로컬 파일 시스템│            │  S3 + DynamoDB    │
│ (JSON Files)  │            │  (AWS Services)  │
│               │            │                  │
│ local-data/   │            │  s3://bucket/    │
│   ├─ vuddy/   │            │  dynamodb table  │
│   ├─ youtube/ │            │                  │
│   └─ dcinside/│            │                  │
└───────────────┘            └──────────────────┘
```

### 1.2 데이터 저장 메커니즘

#### 로컬 모드 (LOCAL_MODE=true)
- **저장 위치**: `local-data/` 디렉토리
- **형식**: JSON 파일
- **구조**:
  ```
  local-data/
  ├── vuddy/
  │   └── comprehensive_analysis/
  │       └── vuddy-creators.json
  ├── youtube/
  │   └── {channel_id}.json
  └── dcinside/
      └── {gallery_id}/
          └── {timestamp}.json
  ```
- **장점**: 개발/테스트 용이, 외부 의존성 없음
- **단점**: 확장성 제한, 데이터 백업 필요

#### 프로덕션 모드 (LOCAL_MODE=false)
- **저장 위치**: AWS S3 + DynamoDB
- **S3 구조**: `s3://bucket/raw-data/{platform}/{source}/{timestamp}.json`
- **DynamoDB**: 메타데이터 및 인덱스
- **장점**: 확장성, 내구성, 자동 백업
- **단점**: AWS 비용, 네트워크 의존성

### 1.3 데이터 수집 플로우

```python
# 크롤러 실행
crawler.invoke() 
    ↓
데이터 수집 (YouTube API, 웹 스크래핑 등)
    ↓
LOCAL_MODE 체크
    ├─ true  → local_storage.save_to_local_file()
    └─ false → s3_client.put_object()
    ↓
메타데이터 저장
    ├─ true  → local_storage.save_metadata_to_local()
    └─ false → dynamodb.put_item()
    ↓
LLM 분석 트리거 (선택적)
    ↓
완료
```

### 1.4 문제점 및 개선 사항

#### 문제점 1: 데이터 일관성
- **현재**: 로컬 파일과 S3 간 동기화 메커니즘 부재
- **영향**: 환경 전환 시 데이터 불일치 가능
- **개선**: 데이터 마이그레이션 스크립트 필요

#### 문제점 2: 파일 기반 저장소의 확장성
- **현재**: 단일 파일에 모든 크리에이터 데이터 저장 (`vuddy-creators.json`)
- **영향**: 파일 크기 증가 시 성능 저하, 동시 쓰기 충돌
- **개선**: 크리에이터별 파일 분리 또는 데이터베이스 전환

#### 문제점 3: 백업 전략 부재
- **현재**: 수동 백업 파일 생성 (`.backup_*`)
- **영향**: 데이터 손실 위험
- **개선**: 자동 백업 스케줄링 (CronJob)

---

## 2. Docker 구조 분석

### 2.1 현재 Docker Compose 구조

```yaml
services:
  # 인프라 서비스
  - dynamodb-local (포트 8002)
  - localstack (포트 4566)
  - redis (포트 6379)
  
  # 크롤러 서비스
  - youtube-crawler (내부 포트 5000)
  - vuddy-crawler (내부 포트 5000)
  - dcinside-crawler (내부 포트 5000)
  - telegram-crawler
  - rss-crawler
  - twitter-crawler
  - instagram-crawler
  - facebook-crawler
  - threads-crawler
  
  # 분석 서비스
  - llm-analyzer (포트 5000)
  
  # API 서비스
  - api-backend (포트 8090)
  - auth-service (포트 8081)
  
  # 프론트엔드
  - frontend (포트 3000)
  
  # 스케줄러
  - scheduler (Cron 기반)
```

### 2.2 Docker 네트워크 구조

```
sns-monitor-network (bridge)
    │
    ├─ 모든 서비스가 동일 네트워크에 연결
    ├─ 서비스 간 통신: http://service-name:port
    └─ 볼륨 마운트: ./local-data → /app/local-data
```

### 2.3 장점
- ✅ 서비스 분리로 독립적 개발/배포 가능
- ✅ 로컬 개발 환경 구축 용이
- ✅ 의존성 관리 명확 (depends_on)

### 2.4 개선 사항

#### 개선 1: 포트 충돌 방지
- **현재**: 일부 포트가 하드코딩되어 있음
- **개선**: 환경 변수로 포트 관리

#### 개선 2: 리소스 제한 설정
- **현재**: 리소스 제한 없음
- **개선**: 메모리/CPU 제한 추가

```yaml
services:
  api-backend:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
        reservations:
          memory: 512M
          cpus: '0.25'
```

---

## 3. Kubernetes 구조 분석

### 3.1 현재 Kubernetes 구조

```
k8s/
├── namespace.yaml
├── config/
│   ├── configmap.yaml
│   └── secrets.yaml
├── deployments/
│   ├── api-backend.yaml
│   ├── frontend.yaml
│   ├── youtube-crawler.yaml
│   ├── dynamodb.yaml
│   ├── redis.yaml
│   └── auth-service.yaml
├── services/ (비어있음)
└── ingress/
    └── ingress.yaml

helm/
└── sns-monitor/
    ├── Chart.yaml
    ├── values.yaml
    └── templates/
```

### 3.2 주요 구성 요소

#### 3.2.1 PersistentVolumeClaim (PVC)

**현재 설정**:
```yaml
# api-backend.yaml
volumes:
  - name: local-data
    persistentVolumeClaim:
      claimName: local-data-pvc
      
# PVC 정의
spec:
  accessModes:
    - ReadWriteMany  # ⚠️ 문제점
  resources:
    requests:
      storage: 20Gi
```

**문제점**:
- `ReadWriteMany`는 대부분의 스토리지 클래스에서 지원하지 않음
- NFS 또는 특수 스토리지 클래스 필요
- 성능 이슈 가능성

**개선 방안**:
```yaml
# 옵션 1: ReadWriteOnce + StatefulSet
accessModes:
  - ReadWriteOnce  # 표준 스토리지 클래스 지원

# 옵션 2: NFS 기반 스토리지
storageClassName: nfs-client

# 옵션 3: S3 마운트 (s3fs-fuse)
# 프로덕션 환경에서는 S3 직접 사용 권장
```

#### 3.2.2 ConfigMap 및 Secrets

**현재 구조**:
- ConfigMap: 공개 설정값
- Secrets: 민감 정보 (API 키 등)

**개선 사항**:
- Secrets 암호화 (Sealed Secrets 또는 External Secrets Operator)
- 환경별 ConfigMap 분리 (dev/staging/prod)

#### 3.2.3 크롤러 스케줄링

**현재**: 스케줄러 컨테이너가 Cron 실행
**문제점**:
- 컨테이너 재시작 시 스케줄 유지 어려움
- 로그 추적 어려움
- 실패 시 재시도 메커니즘 부재

**개선 방안**: Kubernetes CronJob 사용

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: youtube-crawler-job
  namespace: sns-monitor
spec:
  schedule: "*/30 * * * *"  # 30분마다
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: youtube-crawler
            image: sns-monitoring-system-youtube-crawler:latest
            command: ["/app/invoke"]
            args: ["--type", "comprehensive"]
          restartPolicy: OnFailure
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
```

### 3.3 데이터 일관성 문제

#### 문제 시나리오
1. **로컬 개발**: `LOCAL_MODE=true`, 로컬 파일 사용
2. **Kubernetes 배포**: `LOCAL_MODE=false`, S3 사용
3. **데이터 불일치**: 로컬 파일과 S3 데이터가 다름

#### 해결 방안

**방안 1: 데이터 마이그레이션 스크립트**
```python
# scripts/migrate_local_to_s3.py
def migrate_local_to_s3():
    local_files = list_local_files('vuddy')
    for filepath in local_files:
        data = load_from_local_file(filepath)
        s3_key = upload_to_s3(data)
        print(f"Migrated: {filepath} → {s3_key}")
```

**방안 2: 통합 데이터 레이어**
```python
# lambda/common/data_layer.py
class DataLayer:
    def save(self, data):
        if LOCAL_MODE:
            self._save_local(data)
        else:
            self._save_s3(data)
        # 선택적: 양쪽 모두 저장 (동기화)
        if SYNC_MODE:
            self._save_both(data)
```

### 3.4 리소스 관리

#### 현재 리소스 설정
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

#### 권장 리소스 설정

| 서비스 | Requests | Limits | 이유 |
|--------|----------|--------|------|
| API Backend | 512Mi / 250m | 1Gi / 1000m | 적절 |
| Frontend | 128Mi / 100m | 256Mi / 500m | 정적 파일 위주 |
| YouTube Crawler | 512Mi / 250m | 2Gi / 1000m | API 호출 많음 |
| LLM Analyzer | 1Gi / 500m | 2Gi / 2000m | 모델 로딩 필요 |
| Redis | 256Mi / 100m | 512Mi / 500m | 캐시만 사용 |
| DynamoDB Local | 512Mi / 250m | 1Gi / 500m | 적절 |

### 3.5 고가용성 구성

#### 현재 상태
- API Backend: `replicas: 2` ✅
- Frontend: `replicas: 2` ✅
- 크롤러: `replicas: 1` ⚠️

#### 개선 사항

**크롤러 고가용성**:
- 크롤러는 상태 비저장(stateless)이므로 여러 레플리카 가능
- 단, 동일 작업 중복 실행 방지 필요 (Distributed Lock)

```yaml
# Redis 기반 분산 락 사용
apiVersion: apps/v1
kind: Deployment
metadata:
  name: youtube-crawler
spec:
  replicas: 2  # 고가용성
  template:
    spec:
      containers:
      - name: youtube-crawler
        env:
        - name: REDIS_LOCK_ENABLED
          value: "true"
```

---

## 4. 프로덕션 배포 권장 구조

### 4.1 데이터 저장소 전략

#### 옵션 1: 완전 클라우드 (권장)
```
LOCAL_MODE=false
    ↓
S3 (원본 데이터)
    ↓
DynamoDB (메타데이터 및 인덱스)
    ↓
ElastiCache (Redis 캐시)
```

**장점**:
- 확장성
- 자동 백업
- 다중 리전 복제 가능

**비용**: ~$50-100/월

#### 옵션 2: 하이브리드
```
로컬 PVC (최신 데이터)
    ↓
S3 (아카이브 데이터)
    ↓
DynamoDB (메타데이터)
```

**장점**:
- 빠른 접근 (로컬)
- 장기 보관 (S3)

**비용**: ~$30-50/월

### 4.2 크롤러 실행 전략

#### 전략 1: Kubernetes CronJob (권장)
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: vuddy-crawler-schedule
spec:
  schedule: "0 */6 * * *"  # 6시간마다
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: crawler
            image: sns-monitoring-system-vuddy-crawler:latest
            command: ["python", "/app/lambda_function.py"]
            args: ["--type", "comprehensive"]
```

#### 전략 2: Event-Driven (SQS/Kafka)
```
SQS Queue
    ↓
Lambda Function (또는 K8s Job)
    ↓
크롤러 실행
    ↓
결과 저장
```

### 4.3 모니터링 및 로깅

#### 필수 구성 요소
1. **메트릭 수집**: Prometheus + Grafana
2. **로그 집중화**: ELK Stack 또는 CloudWatch
3. **알람**: AlertManager 또는 PagerDuty

```yaml
# k8s/monitoring/prometheus.yaml
apiVersion: v1
kind: ServiceMonitor
metadata:
  name: api-backend-metrics
spec:
  selector:
    matchLabels:
      app: api-backend
  endpoints:
  - port: http
    path: /metrics
```

---

## 5. 보안 고려사항

### 5.1 현재 보안 상태

#### ✅ 잘 구성된 부분
- Secrets를 통한 민감 정보 관리
- 네트워크 격리 (ClusterIP)
- OAuth2 Proxy 통합

#### ⚠️ 개선 필요
- Secrets 암호화 (Sealed Secrets)
- 네트워크 정책 (NetworkPolicy)
- Pod Security Policy

### 5.2 권장 보안 강화

```yaml
# NetworkPolicy 예시
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-backend-policy
spec:
  podSelector:
    matchLabels:
      app: api-backend
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
```

---

## 6. 개선 권장 사항 요약

### 우선순위 높음 (P0)

1. **Kubernetes CronJob으로 크롤러 스케줄링 전환**
   - 현재: 스케줄러 컨테이너
   - 개선: CronJob 리소스 사용
   - 영향: 안정성 향상, 로그 추적 용이

2. **PVC Access Mode 수정**
   - 현재: ReadWriteMany
   - 개선: ReadWriteOnce 또는 NFS
   - 영향: 배포 호환성 향상

3. **데이터 동기화 메커니즘 구현**
   - 현재: 수동 마이그레이션
   - 개선: 자동 동기화 스크립트
   - 영향: 환경 전환 시 데이터 일관성 보장

### 우선순위 중간 (P1)

4. **리소스 제한 명시**
   - 모든 Deployment에 resources 추가
   - 영향: 리소스 사용 예측 가능

5. **Health Check 강화**
   - Liveness/Readiness Probe 개선
   - 영향: 자동 복구 기능 향상

6. **모니터링 구성**
   - Prometheus + Grafana 추가
   - 영향: 운영 가시성 향상

### 우선순위 낮음 (P2)

7. **Helm Chart 완성**
   - 모든 서비스 템플릿화
   - 영향: 배포 자동화

8. **CI/CD 파이프라인**
   - GitHub Actions 또는 GitLab CI
   - 영향: 배포 자동화

---

## 7. 마이그레이션 계획

### Phase 1: Kubernetes 기본 구성 (1주)
- [ ] PVC Access Mode 수정
- [ ] 기본 CronJob 생성
- [ ] ConfigMap/Secrets 검증

### Phase 2: 데이터 동기화 (1주)
- [ ] 마이그레이션 스크립트 작성
- [ ] 테스트 환경 검증
- [ ] 프로덕션 마이그레이션

### Phase 3: 모니터링 및 보안 (2주)
- [ ] Prometheus 구성
- [ ] 로깅 파이프라인 구축
- [ ] 보안 정책 적용

### Phase 4: 최적화 (지속적)
- [ ] 리소스 튜닝
- [ ] 성능 모니터링
- [ ] 비용 최적화

---

## 8. 결론

현재 구조는 **로컬 개발 환경**에 최적화되어 있으며, Kubernetes 배포를 위한 기본 틀은 잘 갖춰져 있습니다. 다만, 프로덕션 환경에서의 안정성과 확장성을 위해 다음 사항들을 개선하는 것을 권장합니다:

1. ✅ **즉시 개선**: PVC Access Mode, CronJob 전환
2. ✅ **단기 개선**: 데이터 동기화, 모니터링 구성
3. ✅ **장기 개선**: 완전 클라우드 전환, CI/CD 구축

전반적으로 **양호한 구조**이며, 위 개선 사항들을 적용하면 프로덕션 환경에서도 안정적으로 운영 가능합니다.

---

**작성일**: 2025-11-25
**검토자**: AI Assistant
**버전**: 1.0


























