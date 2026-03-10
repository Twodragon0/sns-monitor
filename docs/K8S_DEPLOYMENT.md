# Kubernetes 배포 가이드

kubeconfig를 사용하여 백엔드 재시작과 프론트엔드 빌드/배포를 진행하는 방법입니다.

## 📋 사전 요구사항

1. **kubectl** 설치
2. **Helm** 설치 (v3.x)
3. **kubeconfig 파일** 경로 확인
4. **Node.js 및 npm** 설치 (프론트엔드 빌드용)

## 🚀 빠른 시작

### 기본 사용법

```bash
# 전체 배포 (프론트엔드 빌드 + 백엔드 재시작 + 프론트엔드 재시작)
./scripts/deploy-k8s.sh [namespace] [environment] [component]

# 예시
./scripts/deploy-k8s.sh sns-monitor dev all
```

### 파라미터 설명

- `namespace`: Kubernetes 네임스페이스 (기본값: `sns-monitor`)
- `environment`: 환경 (기본값: `dev`, `prod` 또는 `production` 가능)
- `component`: 배포할 컴포넌트 (기본값: `all`)
  - `all`: 프론트엔드와 백엔드 모두
  - `frontend`: 프론트엔드만
  - `backend`: 백엔드만

### kubeconfig 설정

기본 kubeconfig 경로: `~/.kube/config`

환경 변수로 변경 가능:
```bash
export KUBECONFIG_PATH=~/.kube/config
./scripts/deploy-k8s.sh
```

## 📝 사용 예시

### 1. 전체 배포 (프론트엔드 빌드 + 백엔드/프론트엔드 재시작)

```bash
./scripts/deploy-k8s.sh sns-monitor dev all
```

### 2. 백엔드만 재시작

```bash
./scripts/deploy-k8s.sh sns-monitor dev backend
```

### 3. 프론트엔드만 빌드 및 재시작

```bash
./scripts/deploy-k8s.sh sns-monitor dev frontend
```

### 4. 프로덕션 환경 배포

```bash
./scripts/deploy-k8s.sh sns-monitor prod all
```

## 🔍 스크립트 동작 과정

1. **kubeconfig 설정**: 지정된 kubeconfig 파일을 사용하여 kubectl 연결 확인
2. **Namespace 확인**: 네임스페이스가 없으면 생성
3. **프론트엔드 빌드** (component가 `all` 또는 `frontend`인 경우):
   - `frontend` 디렉토리에서 `npm run build` 실행
   - 빌드 성공 시 다음 단계 진행
4. **백엔드 재시작** (component가 `all` 또는 `backend`인 경우):
   - Deployment가 존재하면 `kubectl rollout restart` 실행
   - Deployment가 없으면 Helm으로 배포
5. **프론트엔드 재시작** (component가 `all` 또는 `frontend`인 경우):
   - Deployment가 존재하면 `kubectl rollout restart` 실행
   - Deployment가 없으면 Helm으로 배포
6. **배포 후 검증**: Pod, Service, Deployment 상태 확인

## 🛠️ 문제 해결

### kubeconfig 파일을 찾을 수 없음

```bash
# kubeconfig 경로 확인
ls -la ~/.kube/config

# 환경 변수로 경로 지정
export KUBECONFIG_PATH=/path/to/your/kubeconfig
./scripts/deploy-k8s.sh
```

### kubectl 연결 실패

```bash
# 클러스터 연결 확인
kubectl --kubeconfig=~/.kube/config cluster-info

# kubeconfig 권한 확인
chmod 600 ~/.kube/config
```

### 프론트엔드 빌드 실패

```bash
# 프론트엔드 디렉토리에서 직접 빌드
cd frontend
npm install
npm run build
```

### Deployment를 찾을 수 없음

스크립트가 자동으로 Helm을 사용하여 배포를 시도합니다. Helm 차트가 올바르게 설정되어 있는지 확인하세요:

```bash
# Helm 차트 확인
helm lint ./helm/sns-monitor

# Helm 차트 값 확인
helm template ./helm/sns-monitor -f ./helm/sns-monitor/values.yaml
```

## 📊 배포 상태 확인

### Pod 상태 확인

```bash
kubectl get pods -n sns-monitor -l app.kubernetes.io/instance=sns-monitor
```

### 로그 확인

```bash
# 백엔드 로그
kubectl logs -n sns-monitor -l app.kubernetes.io/component=api-backend --tail=100

# 프론트엔드 로그
kubectl logs -n sns-monitor -l app.kubernetes.io/component=frontend --tail=100
```

### 롤아웃 상태 확인

```bash
# 백엔드 롤아웃 상태
kubectl rollout status deployment/sns-monitor-api-backend -n sns-monitor

# 프론트엔드 롤아웃 상태
kubectl rollout status deployment/sns-monitor-frontend -n sns-monitor
```

### 서비스 접근 테스트

```bash
# 백엔드 포트 포워딩
kubectl port-forward -n sns-monitor svc/sns-monitor-api-backend 8080:8080

# 프론트엔드 포트 포워딩
kubectl port-forward -n sns-monitor svc/sns-monitor-frontend 3000:3000
```

## 🔐 보안 고려사항

1. **kubeconfig 파일 권한**: `chmod 600` 권한으로 설정 권장
2. **환경 변수**: 민감한 정보는 환경 변수로 관리
3. **네트워크 정책**: NetworkPolicy가 적용되어 있는지 확인

## 📚 관련 문서

- [DEPLOYMENT.md](./DEPLOYMENT.md): 전체 배포 가이드
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md): 보안 배포 가이드
- [k8s/README.md](../k8s/README.md): Kubernetes 매니페스트 가이드
