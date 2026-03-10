# 아키텍처 보안 및 운영 효율성 검토 보고서

**검토 일자**: 2025-01-XX  
**검토자**: DevSecOps 엔지니어  
**검토 범위**: 보안, 비용 최적화, 운영 효율성

---

## 📊 종합 평가

| 항목 | 점수 | 상태 | 비고 |
|------|------|------|------|
| **보안** | 7.5/10 | ⚠️ 개선 필요 | NetworkPolicy 비활성화, 일부 보안 강화 필요 |
| **비용 최적화** | 8.5/10 | ✅ 양호 | S3 Lifecycle, HPA 설정 적절 |
| **운영 효율성** | 8.0/10 | ✅ 양호 | Helm, CI/CD 구성 양호, 모니터링 보강 필요 |

---

## 🔒 보안 검토

### ✅ 잘 구현된 부분

#### 1. **인프라 보안 (Terraform)**

**S3 버킷 보안** (`terraform/s3.tf`):
- ✅ 서버 사이드 암호화 (AES256) 적용
- ✅ 퍼블릭 액세스 완전 차단 (`block_public_acls = true`)
- ✅ 버킷 소유권 제어 (ACL 비활성화)
- ✅ HTTPS 강제 (`aws:SecureTransport` 조건)
- ✅ 암호화 없는 업로드 차단 (`s3:x-amz-server-side-encryption` 조건)

**Pod Identity** (`terraform/pod-identity.tf`):
- ✅ IRSA 대신 Pod Identity 사용 (최신 모범 사례)
- ✅ 최소 권한 원칙 적용 (S3 접근만 허용)
- ✅ IAM Role Trust Policy 적절히 구성

#### 2. **CI/CD 보안 (GitHub Actions)**

**OIDC 인증** (`.github/workflows/deploy.yml`):
- ✅ GitHub OIDC Provider 사용 (`id-token: write`)
- ✅ 장기 자격 증명 불필요
- ✅ 최소 권한 원칙 (`contents: read`, `packages: read`)
- ✅ Pull Request에서 배포 차단 (`workflow_dispatch`만 허용)

**Secrets 관리**:
- ✅ GitHub Secrets 사용 (`secrets.YOUTUBE_API_KEY`)
- ✅ 하드코딩 없음

#### 3. **Kubernetes 보안**

**Pod Security Context** (`helm/sns-monitor/values.yaml`):
- ✅ `runAsNonRoot: true`
- ✅ `runAsUser: 1000`, `runAsGroup: 1000`
- ✅ `seccompProfile: RuntimeDefault`
- ✅ `allowPrivilegeEscalation: false`
- ✅ `capabilities.drop: ["ALL"]`

**Dockerfile 보안**:
- ✅ Frontend: `nginx` 사용자로 실행 (`USER nginx`)
- ✅ Python 이미지: `python:3.11-slim` 사용 (경량화)

### ⚠️ 개선이 필요한 부분

#### 1. **NetworkPolicy 비활성화**

**현재 상태** (`helm/sns-monitor/values.yaml:82`):
```yaml
security:
  networkPolicies:
    enabled: false  # ⚠️ 비활성화됨
```

**문제점**:
- 모든 Pod 간 통신이 허용되어 있음
- 네트워크 공격 표면 확대
- 방어 심층화(Defense in Depth) 원칙 위배

**권장 사항**:
```yaml
security:
  networkPolicies:
    enabled: true  # ✅ 활성화
```

**추가 개선** (`helm/sns-monitor/templates/networkpolicy.yaml`):
- 현재 NetworkPolicy는 `namespaceSelector: {}`로 모든 네임스페이스 허용
- **개선**: 특정 네임스페이스만 허용하도록 제한

```yaml
# 개선 전
- namespaceSelector: {}

# 개선 후
- namespaceSelector:
    matchLabels:
      name: ingress-nginx  # Ingress Controller만 허용
```

#### 2. **API Backend 보안 컨텍스트**

**현재 상태** (`helm/sns-monitor/values.yaml:76`):
```yaml
containerSecurityContext:
  readOnlyRootFilesystem: false  # ⚠️ 쓰기 가능
```

**문제점**:
- 루트 파일시스템이 쓰기 가능하여 악성 코드 실행 위험
- `/tmp`는 별도 `emptyDir` 볼륨으로 마운트되어 있으나 루트 파일시스템도 보호 필요

**권장 사항**:
```yaml
containerSecurityContext:
  readOnlyRootFilesystem: true  # ✅ 읽기 전용
```

**주의사항**:
- `/tmp` 볼륨은 이미 마운트되어 있으므로 문제없음
- `/app/local-data` PVC도 마운트되어 있으므로 데이터 저장 가능

#### 3. **환경 변수 검증 부족**

**현재 상태** (`lambda/api-backend/lambda_function.py`):
- 환경 변수 존재 여부 검증 없음
- `os.environ.get()` 사용 시 기본값만 제공

**권장 사항**:
```python
# 앱 시작 시점 검증
REQUIRED_ENV_VARS = ['REDIS_HOST', 'LOCAL_DATA_DIR']
for var in REQUIRED_ENV_VARS:
    if not os.getenv(var):
        raise ValueError(f"Required environment variable {var} is not set")
```

#### 4. **로그 마스킹 부족**

**현재 상태**:
- API 키, 토큰 등이 로그에 노출될 가능성
- `print()` 사용 (프로덕션 환경 부적절)

**권장 사항**:
```python
import logging

logger = logging.getLogger(__name__)

# 민감 정보 마스킹 함수
def mask_sensitive(value: str, show_last: int = 4) -> str:
    if not value or len(value) <= show_last:
        return "***"
    return "*" * (len(value) - show_last) + value[-show_last:]

# 사용 예시
logger.info(f"API Key: {mask_sensitive(api_key)}")
```

#### 5. **k8s/deployments/api-backend.yaml 보안 이슈**

**문제점** (`k8s/deployments/api-backend.yaml:45-54`):
```yaml
- name: AWS_ACCESS_KEY_ID
  valueFrom:
    configMapKeyRef:  # ⚠️ ConfigMap에 자격 증명 저장
      name: sns-monitor-config
      key: AWS_ACCESS_KEY_ID
- name: AWS_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:  # ✅ Secret 사용 (좋음)
      name: sns-monitor-secrets
      key: AWS_SECRET_ACCESS_KEY
```

**문제점**:
- `AWS_ACCESS_KEY_ID`가 ConfigMap에 저장되어 있음 (보안 위험)
- Pod Identity를 사용하는 경우 AWS 자격 증명 불필요

**권장 사항**:
- Pod Identity 사용 시 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` 환경 변수 제거
- 또는 모두 Secret으로 이동

---

## 💰 비용 최적화 검토

### ✅ 잘 구현된 부분

#### 1. **S3 Lifecycle 정책**

**현재 설정** (`terraform/s3.tf:67-116`):
- ✅ 30일 후 STANDARD_IA로 전환
- ✅ 60일 후 GLACIER로 전환
- ✅ 180일 후 삭제 (raw-data)
- ✅ 분석 데이터는 365일 보관

**예상 비용 절감**:
- STANDARD → STANDARD_IA: ~50% 절감
- STANDARD → GLACIER: ~80% 절감
- **월 예상 절감**: ~$5-10 (데이터 양에 따라)

#### 2. **리소스 제한 설정**

**현재 설정** (`helm/sns-monitor/values.yaml`):
```yaml
frontend:
  resources:
    requests:
      cpu: 25m
      memory: 64Mi
    limits:
      cpu: 200m
      memory: 256Mi

apiBackend:
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
    limits:
      cpu: 200m
      memory: 256Mi
```

**평가**: 적절한 리소스 제한으로 노이지 네이버 방지

#### 3. **크롤러 스케줄링**

**현재 설정** (`helm/sns-monitor/values.yaml:183, 201`):
```yaml
crawlers:
  youtube:
    schedule: "0 */2 * * *"  # 2시간마다
  dcinside:
    schedule: "0 */2 * * *"  # 2시간마다
```

**평가**: API 비용 절감을 위한 적절한 스케줄링

#### 4. **HPA 설정**

**현재 설정** (`helm/sns-monitor/values.yaml:97-100`):
```yaml
hpa:
  enabled: false  # 초기 배포 시 비활성화
  minReplicas: 1
  maxReplicas: 2  # 비용 절감: 3 → 2
  targetCPUUtilization: 80
```

**평가**: 비용 절감을 위한 적절한 설정 (필요 시 활성화 가능)

#### 5. **Storage Class**

**현재 설정** (`helm/sns-monitor/values.yaml:12`):
```yaml
global:
  storageClass: "ebs-gp3-ext4"  # gp3 사용 (gp2 대비 20% 저렴)
```

**평가**: 비용 효율적인 스토리지 선택

### ⚠️ 개선이 필요한 부분

#### 1. **HPA 비활성화**

**현재 상태**: HPA가 비활성화되어 있어 트래픽 증가 시 수동 스케일링 필요

**권장 사항**:
- 트래픽 패턴 모니터링 후 HPA 활성화 고려
- CPU 사용률이 지속적으로 60% 이상이면 활성화

#### 2. **야간 스케일 다운 미구현**

**현재 상태** (`helm/sns-monitor/values.yaml:87-94`):
```yaml
costOptimization:
  enabled: true
  scaleDown:
    schedule: "0 22 * * *"  # 정의만 되어 있음
  scaleUp:
    schedule: "0 7 * * 1-5"
```

**문제점**: CronJob 템플릿이 없어 실제로 동작하지 않음

**권장 사항**:
- `cronjob-scaler.yaml` 템플릿 생성 또는 KEDA ScaledObject 사용

#### 3. **Redis 리소스 최적화**

**현재 설정** (`helm/sns-monitor/values.yaml:224-230`):
```yaml
redis:
  master:
    resources:
      requests:
        cpu: 25m
        memory: 32Mi
      limits:
        cpu: 100m
        memory: 128Mi
```

**평가**: 적절하나, 캐시 사용량 모니터링 후 조정 필요

---

## 🚀 운영 효율성 검토

### ✅ 잘 구현된 부분

#### 1. **Helm 차트 구조**

**평가**:
- ✅ 템플릿 구조화 (`_helpers.tpl` 사용)
- ✅ Values 파일 분리 (`values.yaml`, `values-production.yaml`)
- ✅ 보안 컨텍스트 헬퍼 함수 사용

#### 2. **CI/CD 파이프라인**

**평가**:
- ✅ 멀티 플랫폼 빌드 (amd64, arm64)
- ✅ Docker Buildx 캐시 활용
- ✅ GitHub Packages 사용
- ✅ Helm lint, dry-run 검증

#### 3. **Health Check**

**현재 설정**:
```yaml
livenessProbe:
  httpGet:
    path: /api/health
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /api/health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
```

**평가**: 적절한 Health Check 설정

### ⚠️ 개선이 필요한 부분

#### 1. **모니터링 부재**

**현재 상태**:
- Prometheus 메트릭 수집 없음
- CloudWatch 로그 수집 설정 없음
- 알람 설정 없음

**권장 사항**:
```yaml
# Prometheus ServiceMonitor 추가
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: sns-monitor-api-backend
spec:
  selector:
    matchLabels:
      app.kubernetes.io/component: api-backend
  endpoints:
    - port: http
      path: /metrics
```

#### 2. **로깅 표준화 부족**

**현재 상태**:
- `print()` 사용 (프로덕션 부적절)
- 구조화된 로깅 없음
- 로그 레벨 관리 없음

**권장 사항**:
```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log(self, level, message, **kwargs):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'message': message,
            **kwargs
        }
        getattr(self.logger, level)(json.dumps(log_data))
```

#### 3. **배포 전략**

**현재 상태**: RollingUpdate 사용 (기본값)

**권장 사항**:
- Blue-Green 배포 고려 (중단 시간 최소화)
- Canary 배포 고려 (위험 최소화)

#### 4. **백업 전략**

**현재 상태**: S3 Sync CronJob만 존재 (`s3Sync.schedule: "0 */6 * * *"`)

**개선 사항**:
- 백업 검증 자동화
- 복원 테스트 정기 실행
- 백업 보존 정책 명확화

---

## 📋 우선순위별 개선 사항

### 🔴 높은 우선순위 (즉시 조치)

1. **NetworkPolicy 활성화**
   - 보안 위험도: 높음
   - 작업량: 낮음
   - 파일: `helm/sns-monitor/values.yaml:82`

2. **API Backend readOnlyRootFilesystem 활성화**
   - 보안 위험도: 중간
   - 작업량: 낮음
   - 파일: `helm/sns-monitor/values.yaml:76`

3. **환경 변수 검증 추가**
   - 보안 위험도: 중간
   - 작업량: 중간
   - 파일: `lambda/api-backend/lambda_function.py`

4. **ConfigMap에서 AWS 자격 증명 제거**
   - 보안 위험도: 높음
   - 작업량: 낮음
   - 파일: `k8s/deployments/api-backend.yaml:45-54`

### 🟡 중간 우선순위 (1-2주 내)

5. **로깅 표준화**
   - 운영 효율성: 높음
   - 작업량: 중간
   - 파일: 모든 Python 파일

6. **모니터링 설정**
   - 운영 효율성: 높음
   - 작업량: 높음
   - 파일: 새로 생성 필요

7. **NetworkPolicy 세분화**
   - 보안 위험도: 중간
   - 작업량: 중간
   - 파일: `helm/sns-monitor/templates/networkpolicy.yaml`

### 🟢 낮은 우선순위 (1개월 내)

8. **야간 스케일 다운 구현**
   - 비용 절감: 중간
   - 작업량: 중간
   - 파일: `helm/sns-monitor/templates/cronjob-scaler.yaml` (신규)

9. **HPA 활성화 검토**
   - 비용/성능: 중간
   - 작업량: 낮음
   - 파일: `helm/sns-monitor/values.yaml:97`

10. **백업 검증 자동화**
    - 운영 효율성: 중간
    - 작업량: 중간
    - 파일: 새로 생성 필요

---

## 📊 비용 예상 절감

| 개선 사항 | 월 예상 절감 | 연간 예상 절감 |
|-----------|-------------|---------------|
| S3 Lifecycle (이미 적용) | $5-10 | $60-120 |
| 야간 스케일 다운 (미구현) | $10-15 | $120-180 |
| HPA 최적화 (활성화 시) | $5-10 | $60-120 |
| **합계** | **$20-35** | **$240-420** |

---

## ✅ 체크리스트

### 보안
- [x] S3 버킷 암호화 설정
- [x] 퍼블릭 액세스 차단
- [x] Pod Security Context 설정
- [x] GitHub OIDC 사용
- [ ] NetworkPolicy 활성화 ⚠️
- [ ] readOnlyRootFilesystem 활성화 ⚠️
- [ ] 환경 변수 검증 추가 ⚠️
- [ ] ConfigMap에서 자격 증명 제거 ⚠️

### 비용 최적화
- [x] S3 Lifecycle 정책
- [x] 리소스 제한 설정
- [x] 크롤러 스케줄링 최적화
- [x] Storage Class 최적화 (gp3)
- [ ] 야간 스케일 다운 구현 ⚠️
- [ ] HPA 활성화 검토 ⚠️

### 운영 효율성
- [x] Helm 차트 구조화
- [x] CI/CD 파이프라인
- [x] Health Check 설정
- [ ] 모니터링 설정 ⚠️
- [ ] 로깅 표준화 ⚠️
- [ ] 백업 검증 자동화 ⚠️

---

## 📝 결론

전체적으로 **보안과 비용 최적화가 잘 구현**되어 있으나, **일부 보안 강화**와 **운영 효율성 개선**이 필요합니다.

**즉시 조치 필요**:
1. NetworkPolicy 활성화
2. readOnlyRootFilesystem 활성화
3. 환경 변수 검증 추가
4. ConfigMap에서 AWS 자격 증명 제거

**중기 개선**:
1. 모니터링 설정
2. 로깅 표준화
3. NetworkPolicy 세분화

이러한 개선을 통해 **보안성 향상**, **비용 절감**, **운영 효율성 개선**을 달성할 수 있습니다.
