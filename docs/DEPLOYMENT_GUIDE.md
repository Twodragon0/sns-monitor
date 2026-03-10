# 보안 개선 사항 배포 가이드

이 문서는 NetworkPolicy 및 보안 설정 개선 사항을 배포하는 단계별 가이드입니다.

---

## 📋 사전 준비 사항

### 1. 필수 도구 확인

```bash
# kubectl 설치 확인
kubectl version --client

# Helm 설치 확인 (v3.14.0 이상 권장)
helm version

# AWS 자격 증명 확인 (EKS 접근용)
aws sts get-caller-identity
```

### 2. 환경 변수 설정

```bash
# Kubernetes 네임스페이스 (기본값: platform)
export NAMESPACE="platform"

# 배포 환경 (dev 또는 prod)
export ENVIRONMENT="dev"

# YouTube API Key (선택사항, 기존 Secret 사용 가능)
export YOUTUBE_API_KEY="your-api-key-here"
```

### 3. kubeconfig 설정

```bash
# EKS 클러스터 kubeconfig 업데이트
aws eks update-kubeconfig \
  --name your-cluster \
  --region ap-northeast-2

# 연결 테스트
kubectl cluster-info
kubectl get nodes
```

---

## 🚀 배포 단계

### Step 1: 변경 사항 검토

```bash
# 변경된 파일 확인
git status

# 주요 변경 사항 확인
git diff helm/sns-monitor/values.yaml
git diff helm/sns-monitor/templates/networkpolicy.yaml
git diff helm/sns-monitor/templates/deployment-frontend.yaml

# 또는 문서 확인
cat docs/security-improvements-applied.md
```

**주요 변경 사항**:
- ✅ NetworkPolicy 활성화 (`security.networkPolicies.enabled: true`)
- ✅ Frontend readOnlyRootFilesystem 활성화
- ✅ NetworkPolicy 세분화 (Ingress Controller 네임스페이스만 허용)
- ✅ Ingress 네임스페이스 설정 추가

---

### Step 2: Dry-run 배포 (권장)

**실제 배포 전에 변경 사항을 확인**합니다:

```bash
# Dry-run 모드로 배포
./scripts/deploy-security-updates.sh platform dev true

# 또는 수동 실행
helm upgrade --install sns-monitor ./helm/sns-monitor \
  --namespace platform \
  -f ./helm/sns-monitor/values.yaml \
  --dry-run \
  --debug
```

**확인 사항**:
- [ ] NetworkPolicy 리소스가 생성되는지 확인
- [ ] Frontend securityContext에 readOnlyRootFilesystem이 설정되는지 확인
- [ ] 기존 설정과 충돌이 없는지 확인

---

### Step 3: 실제 배포

Dry-run이 성공하면 실제 배포를 진행합니다:

```bash
# 자동 배포 스크립트 사용
./scripts/deploy-security-updates.sh platform dev false

# 또는 수동 배포
helm upgrade --install sns-monitor ./helm/sns-monitor \
  --namespace platform \
  -f ./helm/sns-monitor/values.yaml \
  --set secrets.youtubeApiKey=$YOUTUBE_API_KEY \
  --wait \
  --timeout 10m \
  --atomic
```

**배포 옵션 설명**:
- `--wait`: Pod가 Ready 상태가 될 때까지 대기
- `--timeout 10m`: 최대 10분 대기
- `--atomic`: 실패 시 자동 롤백

---

### Step 4: 배포 검증

배포 후 다음을 확인합니다:

```bash
# 1. Pod 상태 확인
kubectl get pods -n platform -l app.kubernetes.io/instance=sns-monitor

# 2. NetworkPolicy 확인
kubectl get networkpolicies -n platform | grep sns-monitor

# 3. NetworkPolicy 상세 확인
kubectl describe networkpolicy sns-monitor-default-deny -n platform

# 4. Frontend 보안 컨텍스트 확인
FRONTEND_POD=$(kubectl get pods -n platform -l app.kubernetes.io/component=frontend -o jsonpath='{.items[0].metadata.name}')
kubectl get pod $FRONTEND_POD -n platform -o jsonpath='{.spec.containers[0].securityContext}' | jq

# 5. 자동 테스트 스크립트 실행
./scripts/test-network-policy.sh platform
```

---

### Step 5: 통신 테스트

NetworkPolicy 적용 후 통신이 정상적으로 작동하는지 확인합니다:

```bash
# Frontend Pod 이름 확인
FRONTEND_POD=$(kubectl get pods -n platform -l app.kubernetes.io/component=frontend -o jsonpath='{.items[0].metadata.name}')
API_BACKEND_POD=$(kubectl get pods -n platform -l app.kubernetes.io/component=api-backend -o jsonpath='{.items[0].metadata.name}')

# 1. Frontend → API Backend 통신 테스트
kubectl exec -n platform $FRONTEND_POD -- curl -s http://sns-monitor-api-backend:8080/api/health

# 2. API Backend Health Check
kubectl exec -n platform $API_BACKEND_POD -- curl -s http://localhost:8080/api/health

# 3. 외부에서 Ingress를 통한 접근 테스트
curl -k https://sns-monitor.example.com/api/health
```

**예상 결과**:
- Frontend → API Backend: ✅ 통신 성공
- 외부 → Ingress → Frontend: ✅ 통신 성공
- 외부 → Ingress → API Backend: ✅ 통신 성공

---

## 🔍 문제 해결

### 문제 1: NetworkPolicy로 인한 통신 실패

**증상**: Pod 간 통신이 실패함

**해결 방법**:

```bash
# 1. NetworkPolicy 확인
kubectl get networkpolicies -n platform

# 2. 특정 Pod의 NetworkPolicy 확인
kubectl describe networkpolicy <networkpolicy-name> -n platform

# 3. 임시로 NetworkPolicy 비활성화 (테스트용)
helm upgrade sns-monitor ./helm/sns-monitor \
  --namespace platform \
  --set security.networkPolicies.enabled=false \
  --wait

# 4. Ingress Controller 네임스페이스 확인 및 수정
# values.yaml에서 ingress.namespace 설정 확인
```

**일반적인 원인**:
- Ingress Controller 네임스페이스가 잘못 설정됨
- NetworkPolicy의 selector가 Pod label과 일치하지 않음

---

### 문제 2: Frontend Pod가 시작되지 않음

**증상**: Frontend Pod가 CrashLoopBackOff 상태

**해결 방법**:

```bash
# 1. Pod 로그 확인
kubectl logs -n platform -l app.kubernetes.io/component=frontend --tail=50

# 2. readOnlyRootFilesystem 관련 오류 확인
# 만약 파일 쓰기 오류가 발생하면, 필요한 볼륨 마운트 확인

# 3. 임시로 readOnlyRootFilesystem 비활성화 (테스트용)
helm upgrade sns-monitor ./helm/sns-monitor \
  --namespace platform \
  --set frontend.securityContext.readOnlyRootFilesystem=false \
  --wait
```

---

### 문제 3: Ingress 접근 불가

**증상**: 외부에서 서비스에 접근할 수 없음

**해결 방법**:

```bash
# 1. Ingress 리소스 확인
kubectl get ingress -n platform

# 2. Ingress 상세 확인
kubectl describe ingress -n platform

# 3. ALB 상태 확인 (AWS 콘솔 또는 CLI)
aws elbv2 describe-load-balancers --region ap-northeast-2

# 4. NetworkPolicy에서 Ingress Controller 네임스페이스 확인
kubectl get networkpolicy -n platform -o yaml | grep namespaceSelector
```

---

## 📊 모니터링

배포 후 다음 메트릭을 모니터링하세요:

### 1. Pod 상태

```bash
# Pod 상태 지속 모니터링
watch kubectl get pods -n platform -l app.kubernetes.io/instance=sns-monitor
```

### 2. 네트워크 트래픽

```bash
# NetworkPolicy 적용 통계 (CNI 플러그인에 따라 다름)
# Calico의 경우
calicoctl get networkpolicy -n platform

# 또는 kubectl로 확인
kubectl get networkpolicies -n platform -o wide
```

### 3. 로그 확인

```bash
# Frontend 로그
kubectl logs -n platform -l app.kubernetes.io/component=frontend --tail=100 -f

# API Backend 로그
kubectl logs -n platform -l app.kubernetes.io/component=api-backend --tail=100 -f
```

---

## 🔄 롤백 가이드

문제 발생 시 다음 방법으로 롤백할 수 있습니다:

### 방법 1: NetworkPolicy만 비활성화

```bash
helm upgrade sns-monitor ./helm/sns-monitor \
  --namespace platform \
  -f ./helm/sns-monitor/values.yaml \
  --set security.networkPolicies.enabled=false \
  --wait
```

### 방법 2: 이전 Helm 릴리스로 롤백

```bash
# 릴리스 히스토리 확인
helm history sns-monitor -n platform

# 이전 릴리스로 롤백
helm rollback sns-monitor -n platform

# 특정 릴리스로 롤백
helm rollback sns-monitor <revision-number> -n platform
```

### 방법 3: Git으로 롤백

```bash
# 변경 사항 되돌리기
git checkout HEAD -- helm/sns-monitor/values.yaml
git checkout HEAD -- helm/sns-monitor/templates/networkpolicy.yaml
git checkout HEAD -- helm/sns-monitor/templates/deployment-frontend.yaml

# 다시 배포
./scripts/deploy-security-updates.sh platform dev false
```

---

## ✅ 체크리스트

배포 완료 후 다음 항목을 확인하세요:

### 보안 설정
- [ ] NetworkPolicy가 활성화되어 있음
- [ ] Frontend readOnlyRootFilesystem이 활성화되어 있음
- [ ] Pod Security Context가 올바르게 설정되어 있음
- [ ] NetworkPolicy가 올바른 네임스페이스를 허용함

### 통신 테스트
- [ ] Frontend → API Backend 통신 성공
- [ ] API Backend → Redis 통신 성공
- [ ] 외부 → Ingress → Frontend 접근 성공
- [ ] 외부 → Ingress → API Backend 접근 성공

### 운영 상태
- [ ] 모든 Pod가 Running 상태
- [ ] Health Check가 정상 작동
- [ ] 로그에 오류가 없음
- [ ] 서비스 응답 시간이 정상 범위 내

---

## 📚 참고 자료

- [보안 개선 사항 상세 내역](security-improvements-applied.md)
- [아키텍처 보안 검토 보고서](architecture-security-review.md)
- [Kubernetes NetworkPolicy 공식 문서](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Helm 배포 가이드](DEPLOYMENT.md)

---

## 🆘 지원

문제가 발생하거나 질문이 있으시면:
1. 로그 및 에러 메시지 확인
2. 위의 문제 해결 섹션 참조
3. 팀 채널 또는 이슈 트래커에 문의
