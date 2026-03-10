# kubectl + Okta OIDC 포트 분석

## 📋 Kubeconfig 분석

### Cluster 정보
- **Name**: your-cluster
- **Type**: EKS (AWS Elastic Kubernetes Service)
- **Region**: ap-northeast-2
- **Namespace**: kube-system
- **Server**: https://your-eks-endpoint.gr7.ap-northeast-2.eks.amazonaws.com

### OIDC 인증 설정

```yaml
user:
  exec:
    command: kubectl
    args:
      - oidc-login
      - get-token
      - --oidc-issuer-url=https://your-okta-domain.okta.com/oauth2/your-auth-server-id
      - --oidc-client-id=your-oidc-client-id
      - --oidc-extra-scope=email
      - --oidc-extra-scope=offline_access
      - --oidc-extra-scope=profile
      - --oidc-extra-scope=openid
```

## 🔌 kubectl oidc-login 포트 사용

### 기본 포트
kubectl oidc-login은 OAuth2 인증 플로우를 처리하기 위해 로컬 웹서버를 시작합니다:

| 포트 | 용도 | 사용 시점 |
|-----|------|----------|
| **8000** | 기본 로컬 웹서버 | 인증 콜백 수신 |
| **8080** | 대체 포트 (8000 사용 불가 시) | 인증 콜백 수신 |
| **18000** | kubelogin 기본 포트 | 일부 구현에서 사용 |

### 인증 플로우

```
1. kubectl get pods 실행
   ↓
2. kubectl oidc-login 호출
   ↓
3. 로컬 웹서버 시작 (포트 8000)
   ↓
4. 브라우저 열기 → Okta 로그인 페이지
   ↓
5. 사용자 로그인
   ↓
6. Okta → 로컬 웹서버로 리다이렉트 (http://localhost:8000/callback)
   ↓
7. 토큰 수신 및 저장
   ↓
8. 로컬 웹서버 종료
   ↓
9. kubectl 명령 실행
```

## ✅ 포트 충돌 해결 확인

### 변경 전 (문제 상황)

```
❌ Port 8000: DynamoDB Local 사용 중
❌ Port 8080: API Backend 사용 중
→ kubectl oidc-login이 포트를 사용할 수 없음
→ 인증 실패 발생
```

### 변경 후 (해결됨)

```
✅ Port 8000: 완전히 비어있음
   → kubectl oidc-login이 자유롭게 사용 가능

✅ Port 8080: 완전히 비어있음
   → 대체 포트로 사용 가능

✅ Port 8002: DynamoDB Local (새 포트)
✅ Port 8090: API Backend (새 포트)
```

## 🧪 테스트 결과

### kubectl 명령 실행 성공

```bash
$ export KUBECONFIG=~/.kube/config
$ kubectl config use-context your-cluster
Switched to context "your-cluster".

$ kubectl get pods -n kube-system
NAME                                                              READY   STATUS    RESTARTS   AGE
aws-load-balancer-controller-5888dd8675-ncdsl                     1/1     Running   0          43h
aws-load-balancer-controller-5888dd8675-tghnk                     1/1     Running   0          43h
aws-node-46l7g                                                    2/2     Running   0          20h
...
```

**결과**: ✅ 정상 작동 (포트 충돌 없음)

### 포트 확인

```bash
$ lsof -i :8000
# 출력 없음 → 포트 8000 비어있음 ✅

$ lsof -i :8080
# 출력 없음 → 포트 8080 비어있음 ✅

$ lsof -i :8002
COMMAND     PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
com.docke 24171 yong  294u  IPv6 0x110bffe52da094d0      0t0  TCP *:teradataordbms (LISTEN)
# DynamoDB가 8002 사용 중 ✅

$ lsof -i :8090
COMMAND     PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
com.docke 24171 yong  198u  IPv6 0x919b46d20e3d7793      0t0  TCP *:8090 (LISTEN)
# API Backend가 8090 사용 중 ✅
```

## 📊 최종 포트 매핑

### Docker Services

| 서비스 | 이전 호스트 포트 | 새 호스트 포트 | 컨테이너 포트 | 상태 |
|--------|----------------|---------------|--------------|------|
| DynamoDB | ❌ 8000 | ✅ 8002 | 8000 | kubectl 충돌 해결 |
| API Backend | ❌ 8080 | ✅ 8090 | 8080 | kubectl 대체 포트 확보 |
| Frontend | 3000 | 3000 | 3000 | 유지 |
| Auth Service | 8081 | 8081 | 8080 | 유지 |

### kubectl oidc-login

| 포트 | 상태 | 용도 |
|-----|------|------|
| 8000 | ✅ FREE | 기본 OAuth2 콜백 |
| 8080 | ✅ FREE | 대체 OAuth2 콜백 |
| 18000 | ✅ FREE | kubelogin 대체 포트 |

## 🚀 사용 방법

### your-cluster 프로필로 kubectl 사용

```bash
# 환경변수 설정
export KUBECONFIG=~/.kube/config

# Context 확인
kubectl config get-contexts

# your-cluster로 전환 (이미 기본값)
kubectl config use-context your-cluster

# Pods 조회
kubectl get pods -n kube-system

# 특정 namespace의 pods 조회
kubectl get pods -n default

# 모든 namespace의 pods 조회
kubectl get pods --all-namespaces
```

### k9s 사용

```bash
# 환경변수 설정
export KUBECONFIG=~/.kube/config

# k9s 실행 (your-cluster context 사용)
k9s

# 특정 namespace로 시작
k9s -n kube-system

# 모든 namespace
k9s -A
```

### 영구 설정 (선택사항)

```bash
# .zshrc 또는 .bashrc에 추가
echo 'export KUBECONFIG=~/.kube/config' >> ~/.zshrc

# 적용
source ~/.zshrc
```

## 🔧 Troubleshooting

### OIDC 인증 에러 발생 시

```bash
# 에러: oidc error: oidc discovery error
# 원인: Okta 연결 문제 또는 포트 충돌

# 1. 포트 확인
lsof -i :8000
lsof -i :8080

# 2. Docker 서비스 확인
docker ps | grep -E "8000|8080"

# 3. Docker 서비스가 8000/8080을 사용 중이면 중지
docker-compose down

# 4. kubectl 재시도
kubectl get pods
```

### 토큰 캐시 삭제

```bash
# 오래된 토큰이 문제를 일으킬 경우
rm -rf ~/.kube/cache/oidc-login

# kubectl 재실행
kubectl get pods
```

### 브라우저가 자동으로 열리지 않을 때

```bash
# 수동으로 브라우저 URL 복사
kubectl get pods
# 출력된 URL을 브라우저에 붙여넣기
```

## ✅ 검증 체크리스트

- [x] kubeconfig 파일 확인
- [x] your-cluster context 활성화
- [x] kubectl get pods 실행 성공
- [x] 포트 8000 비어있음 (kubectl oidc-login용)
- [x] 포트 8080 비어있음 (대체 포트)
- [x] Docker 서비스가 8002, 8090 사용 중
- [x] 포트 충돌 없음

## 📝 요약

**문제**: kubectl oidc-login이 포트 8000/8080을 사용하는데, Docker 서비스가 이미 사용 중이어서 충돌 발생

**해결**:
1. DynamoDB: 8000 → 8002로 변경
2. API Backend: 8080 → 8090으로 변경
3. kubectl oidc-login이 포트 8000/8080을 자유롭게 사용 가능

**결과**: ✅ kubectl 및 k9s 정상 작동

---

**Last Updated**: 2025-11-21
