# Kubernetes 배포 가이드

## 📋 개요

이 디렉토리는 SNS Monitoring System을 Kubernetes 클러스터에 배포하기 위한 매니페스트 파일들을 포함합니다.

## 📁 디렉토리 구조

```
k8s/
├── namespace.yaml              # 네임스페이스 정의
├── config/
│   ├── configmap.yaml         # 설정값 (공개)
│   └── secrets.yaml           # 민감 정보 (API 키 등)
├── deployments/
│   ├── api-backend.yaml       # API 백엔드 (2 replicas)
│   ├── frontend.yaml          # React 프론트엔드 (2 replicas)
│   ├── youtube-crawler.yaml   # YouTube 크롤러
│   ├── dynamodb.yaml          # DynamoDB Local
│   ├── redis.yaml             # Redis 캐시
│   └── auth-service.yaml      # 인증 서비스
├── cronjob-youtube-crawler.yaml  # 크롤러 스케줄링 (CronJob)
├── pvc/
│   └── local-data-pvc-fixed.yaml  # 영구 볼륨 클레임 (수정된 버전)
├── network-policy/
│   └── api-backend-policy.yaml    # 네트워크 정책 예시
└── ingress/
    └── ingress.yaml           # Ingress 설정
```

## 🚀 배포 순서

### 1. 네임스페이스 생성

```bash
kubectl apply -f k8s/namespace.yaml
```

### 2. ConfigMap 및 Secrets 생성

```bash
# ConfigMap 생성
kubectl apply -f k8s/config/configmap.yaml

# Secrets 생성 (값 수정 필요)
kubectl apply -f k8s/config/secrets.yaml
```

**주의**: `secrets.yaml`의 실제 값은 환경에 맞게 수정하거나, Sealed Secrets를 사용하세요.

### 3. PVC 생성

```bash
# 표준 스토리지 (ReadWriteOnce)
kubectl apply -f k8s/pvc/local-data-pvc-fixed.yaml

# 또는 NFS 기반 스토리지 (ReadWriteMany) 사용 시
# NFS 서버 설정 후 storageClassName을 nfs-client로 변경
```

### 4. 인프라 서비스 배포

```bash
# DynamoDB Local
kubectl apply -f k8s/deployments/dynamodb.yaml

# Redis
kubectl apply -f k8s/deployments/redis.yaml

# LocalStack (선택사항)
# kubectl apply -f k8s/deployments/localstack.yaml
```

### 5. 애플리케이션 서비스 배포

```bash
# API Backend
kubectl apply -f k8s/deployments/api-backend.yaml

# Frontend
kubectl apply -f k8s/deployments/frontend.yaml

# Auth Service
kubectl apply -f k8s/deployments/auth-service.yaml
```

### 6. 크롤러 배포

```bash
# YouTube Crawler (Deployment)
kubectl apply -f k8s/deployments/youtube-crawler.yaml

# YouTube Crawler (CronJob - 권장)
kubectl apply -f k8s/deployments/cronjob-youtube-crawler.yaml
```

### 7. Ingress 설정

```bash
kubectl apply -f k8s/ingress/ingress.yaml
```

### 8. 네트워크 정책 (선택사항)

```bash
kubectl apply -f k8s/network-policy/api-backend-policy.yaml
```

## 🔧 주요 설정

### 환경 변수

#### ConfigMap (k8s/config/configmap.yaml)
- `LOCAL_MODE`: "false" (프로덕션) 또는 "true" (로컬)
- `DYNAMODB_ENDPOINT`: DynamoDB 서비스 엔드포인트
- `S3_ENDPOINT`: S3 서비스 엔드포인트 (LocalStack 사용 시)
- `REDIS_HOST`: Redis 서비스 이름

#### Secrets (k8s/config/secrets.yaml)
- `AWS_SECRET_ACCESS_KEY`: AWS 시크릿 키
- `YOUTUBE_API_KEY`: YouTube API 키
- 기타 API 키들

### 스토리지

#### PVC Access Mode

**현재 설정**: `ReadWriteOnce` (표준 스토리지 클래스 지원)

**다중 Pod 접근이 필요한 경우**:
1. NFS 기반 스토리지 클래스 사용
2. 또는 프로덕션 환경에서는 `LOCAL_MODE=false`로 설정하여 S3 직접 사용

### 크롤러 스케줄링

#### 옵션 1: CronJob (권장)
```bash
kubectl apply -f k8s/deployments/cronjob-youtube-crawler.yaml
```

**장점**:
- Kubernetes 네이티브 스케줄링
- 로그 추적 용이
- 실패 시 자동 재시도

#### 옵션 2: Deployment + 외부 스케줄러
```bash
kubectl apply -f k8s/deployments/youtube-crawler.yaml
# 외부 Cron 또는 스케줄러가 HTTP 호출
```

## 📊 모니터링

### Pod 상태 확인

```bash
# 모든 Pod 상태 확인
kubectl get pods -n sns-monitor

# 특정 서비스 로그 확인
kubectl logs -f deployment/api-backend -n sns-monitor

# CronJob 실행 이력 확인
kubectl get jobs -n sns-monitor
kubectl logs job/youtube-crawler-schedule-<timestamp> -n sns-monitor
```

### 리소스 사용량 확인

```bash
# 리소스 사용량
kubectl top pods -n sns-monitor

# PVC 사용량
kubectl get pvc -n sns-monitor
```

## 🔒 보안 고려사항

### 1. Secrets 관리

**권장 방법**:
- Sealed Secrets 사용
- External Secrets Operator 사용
- AWS Secrets Manager 연동

**예시 (Sealed Secrets)**:
```bash
# Secrets 암호화
kubectl create secret generic sns-monitor-secrets \
  --from-literal=YOUTUBE_API_KEY=your-key \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > k8s/config/secrets-sealed.yaml
```

### 2. 네트워크 정책

네트워크 정책을 적용하여 Pod 간 통신을 제한하세요:

```bash
kubectl apply -f k8s/network-policy/api-backend-policy.yaml
```

### 3. RBAC

필요한 경우 Role 및 RoleBinding을 생성하여 권한을 제한하세요.

## 🐛 트러블슈팅

### PVC 마운트 실패

**증상**: Pod가 `Pending` 상태로 유지

**원인**: ReadWriteMany를 지원하지 않는 스토리지 클래스 사용

**해결**:
1. `ReadWriteOnce`로 변경
2. 또는 NFS 기반 스토리지 클래스 사용

### 크롤러가 실행되지 않음

**증상**: CronJob이 Job을 생성하지 않음

**원인**: 스케줄 형식 오류 또는 권한 문제

**해결**:
```bash
# CronJob 상태 확인
kubectl describe cronjob youtube-crawler-schedule -n sns-monitor

# 수동 실행 테스트
kubectl create job --from=cronjob/youtube-crawler-schedule manual-test -n sns-monitor
```

### 데이터 동기화 문제

**증상**: 로컬 파일과 S3 데이터 불일치

**해결**: 마이그레이션 스크립트 실행
```bash
python3 scripts/migrate_local_to_s3.py
```

## 📚 추가 리소스

- [Architecture Review](./docs/architecture-review.md): 상세 구조 분석
- [Helm Chart](../helm/sns-monitor/): Helm을 통한 배포
- [Docker Compose](../docker-compose.yml): 로컬 개발 환경

## 🔄 업그레이드

### 롤링 업데이트

```bash
# 이미지 업데이트
kubectl set image deployment/api-backend \
  api-backend=sns-monitoring-system-api-backend:v1.1.0 \
  -n sns-monitor

# 업데이트 상태 확인
kubectl rollout status deployment/api-backend -n sns-monitor
```

### 롤백

```bash
# 이전 버전으로 롤백
kubectl rollout undo deployment/api-backend -n sns-monitor
```

---

**작성일**: 2025-11-25
**버전**: 1.0


























