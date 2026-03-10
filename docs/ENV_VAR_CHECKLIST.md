# 환경 변수 검증 체크리스트

## 개요
API Backend Lambda 함수가 정상적으로 구동되기 위해 필요한 환경 변수들을 확인하는 체크리스트입니다.

## 필수 환경 변수

### K8s ConfigMap (`sns-monitor-config`)에 설정되어야 하는 변수들

#### AWS 설정
- ✅ `AWS_DEFAULT_REGION`: AWS 리전 (예: `ap-northeast-2`)
- ⚠️ `AWS_ACCESS_KEY_ID`: Pod Identity 사용 시 불필요 (주석 처리됨)
- ⚠️ `AWS_SECRET_ACCESS_KEY`: Pod Identity 사용 시 불필요 (주석 처리됨)

#### 데이터베이스 설정
- ✅ `DYNAMODB_TABLE`: DynamoDB 테이블 이름 (예: `sns-monitor-results`)
- ✅ `DYNAMODB_ENDPOINT`: DynamoDB 엔드포인트 (로컬: `http://dynamodb-local:8000`, 프로덕션: 생략)

#### 스토리지 설정
- ✅ `S3_BUCKET`: S3 버킷 이름 (예: `sns-monitor-data`)
- ✅ `S3_ENDPOINT`: S3 엔드포인트 (로컬: `http://localstack:4566`, 프로덕션: 생략)

#### 서비스 엔드포인트
- ✅ `AUTH_SERVICE_ENDPOINT`: 인증 서비스 엔드포인트 (예: `http://auth-service:8080`)
- ✅ `REDIS_HOST`: Redis 호스트 (예: `sns-monitor-redis-master`)
- ✅ `REDIS_PORT`: Redis 포트 (예: `6379`)

#### 애플리케이션 설정
- ✅ `LOCAL_MODE`: 로컬 모드 활성화 여부 (`true` 또는 `false`)
- ✅ `LOCAL_DATA_DIR`: 로컬 데이터 디렉토리 경로 (예: `/app/local-data`)

### 선택적 환경 변수

#### 크롤러 엔드포인트 (필요 시)
- `YOUTUBE_CRAWLER_ENDPOINT`: YouTube 크롤러 엔드포인트 (기본값: `http://youtube-crawler:5000`)
- `TWITTER_CRAWLER_ENDPOINT`: Twitter 크롤러 엔드포인트 (기본값: `http://twitter-crawler:5000`)

## 배포 전 확인 사항

### 1. ConfigMap 확인
```bash
# ConfigMap 존재 확인
kubectl get configmap sns-monitor-config -n sns-monitor

# ConfigMap 내용 확인
kubectl get configmap sns-monitor-config -n sns-monitor -o yaml

# 필수 환경 변수 확인
kubectl get configmap sns-monitor-config -n sns-monitor -o jsonpath='{.data}' | jq
```

### 2. 환경 변수 검증 스크립트
```bash
# Pod에서 환경 변수 확인
kubectl exec -it deployment/api-backend -n sns-monitor -- env | grep -E "(DYNAMODB|S3|AUTH|LOCAL|REDIS)"
```

### 3. 로그 확인
```bash
# 환경 변수 검증 로그 확인
kubectl logs deployment/api-backend -n sns-monitor | grep -i "environment\|validation\|missing"
```

## 환경별 설정 가이드

### 로컬 개발 환경 (`LOCAL_MODE=true`)
```yaml
LOCAL_MODE: "true"
LOCAL_DATA_DIR: "/app/local-data"
DYNAMODB_ENDPOINT: "http://dynamodb-local:8000"
S3_ENDPOINT: "http://localstack:4566"
```

### 프로덕션 환경 (`LOCAL_MODE=false`)
```yaml
LOCAL_MODE: "false"
DYNAMODB_ENDPOINT: ""  # AWS DynamoDB 직접 사용
S3_ENDPOINT: ""  # AWS S3 직접 사용
# Pod Identity 또는 IRSA 사용 (AWS 자격 증명 불필요)
```

## 문제 해결

### 환경 변수가 설정되지 않은 경우
- **증상**: `ValueError: Missing required environment variables`
- **해결**: ConfigMap에 필수 환경 변수 추가 후 Pod 재시작

### 로컬 모드에서 파일 접근 오류
- **증상**: `Local file not found` 경고
- **해결**: `LOCAL_DATA_DIR` 경로 확인 및 PVC 마운트 확인

### AWS 서비스 연결 실패
- **증상**: `boto3` 관련 오류
- **해결**: 
  1. Pod Identity 또는 IRSA 설정 확인
  2. IAM Role 권한 확인
  3. 네트워크 정책 확인

## 참고 문서
- [K8s ConfigMap 설정](./k8s/config/configmap.yaml)
- [Helm Values 설정](../helm/sns-monitor/values.yaml)
- [API Backend Deployment](../k8s/deployments/api-backend.yaml)
