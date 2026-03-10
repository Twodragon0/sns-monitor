# OAuth 웹 로그인 설정 가이드

API 키 대신 웹 로그인 방식으로 Claude Console과 OpenAI에 인증하는 방법

## 왜 OAuth 웹 로그인인가?

### 장점:
- ✅ **API 키 불필요**: 직접 API 키를 관리할 필요 없음
- ✅ **보안 강화**: OAuth 2.0 표준 프로토콜 사용
- ✅ **자동 토큰 갱신**: Refresh token으로 자동 갱신
- ✅ **사용자 친화적**: 웹 브라우저에서 로그인만 하면 됨
- ✅ **권한 제어**: 필요한 권한만 부여 가능

### 기존 API 키 방식과 비교:

| 항목 | API 키 방식 | OAuth 웹 로그인 |
|------|-------------|-----------------|
| 설정 | API 키 직접 입력 | 웹에서 로그인 |
| 보안 | 키 노출 위험 | OAuth 토큰 사용 |
| 만료 | 수동 갱신 | 자동 갱신 |
| 사용자 경험 | 복잡 | 간단 |

---

## Claude Console OAuth 설정

### 1. Claude Console에서 OAuth App 생성

```bash
# 1. https://console.anthropic.com/ 접속
# 2. Settings → OAuth Apps 메뉴
# 3. "Create OAuth App" 클릭
```

### 2. OAuth App 설정

**App 정보:**
- **App Name**: SNS Monitor
- **Description**: SNS Monitoring & AI Analysis System
- **Redirect URIs**:
  ```
  http://localhost:3000/auth/callback
  https://your-domain.com/auth/callback
  ```
- **Scopes**: `api:messages` (Claude API 메시지 권한)

### 3. 자격 증명 복사

생성 후 다음 정보를 복사:

```bash
Client ID: claude_xxxxxxxxxxxxxxxxxxxxx
Client Secret: sk_claude_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. .env 파일에 추가

```bash
# .env
CLAUDE_OAUTH_CLIENT_ID=claude_xxxxxxxxxxxxxxxxxxxxx
CLAUDE_OAUTH_CLIENT_SECRET=sk_claude_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## OpenAI OAuth 설정

### 1. OpenAI Platform에서 OAuth App 생성

```bash
# 1. https://platform.openai.com/ 접속
# 2. Settings → OAuth Apps 메뉴
# 3. "Create OAuth App" 클릭
```

### 2. OAuth App 설정

**App 정보:**
- **App Name**: SNS Monitor
- **Description**: SNS Monitoring System
- **Redirect URIs**:
  ```
  http://localhost:3000/auth/callback
  https://your-domain.com/auth/callback
  ```
- **Scopes**: `api` (OpenAI API 권한)

### 3. 자격 증명 복사

```bash
Client ID: oauth_xxxxxxxxxxxxxxxxxxxxx
Client Secret: sk_oauth_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. .env 파일에 추가

```bash
# .env
OPENAI_OAUTH_CLIENT_ID=oauth_xxxxxxxxxxxxxxxxxxxxx
OPENAI_OAUTH_CLIENT_SECRET=sk_oauth_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 로컬 개발 환경에서 사용

### 1. Docker Compose 시작

```bash
cd sns-monitoring-system

# .env 파일 확인
cat .env

# OAuth 설정 확인
# CLAUDE_OAUTH_CLIENT_ID=...
# CLAUDE_OAUTH_CLIENT_SECRET=...
# OPENAI_OAUTH_CLIENT_ID=...
# OPENAI_OAUTH_CLIENT_SECRET=...

# Docker 시작
docker-compose up -d
```

### 2. 웹 대시보드 접속

```bash
# 브라우저에서 접속
open http://localhost:3000
```

### 3. AI 모델 로그인

1. 대시보드에서 "AI 모델 인증" 섹션 찾기
2. "Claude Console 로그인" 버튼 클릭
3. 새 창에서 Claude Console 로그인
4. 권한 승인
5. 자동으로 대시보드로 리다이렉트
6. ✅ 로그인 완료!

같은 방식으로 OpenAI도 로그인

---

## AWS 배포 시 설정

### 1. Terraform 변수 설정

```hcl
# terraform.tfvars
claude_oauth_client_id     = "claude_xxxxx"
claude_oauth_client_secret = "sk_claude_xxxxx"
openai_oauth_client_id     = "oauth_xxxxx"
openai_oauth_client_secret = "sk_oauth_xxxxx"

# Redirect URI (CloudFront URL)
redirect_uri = "https://xxxxx.cloudfront.net/auth/callback"
```

### 2. Terraform 배포

```bash
cd terraform
terraform apply
```

### 3. OAuth App Redirect URI 업데이트

배포 후 CloudFront URL을 OAuth App에 추가:

**Claude Console:**
```
Settings → OAuth Apps → SNS Monitor → Redirect URIs 추가
https://xxxxx.cloudfront.net/auth/callback
```

**OpenAI Platform:**
```
Settings → OAuth Apps → SNS Monitor → Redirect URIs 추가
https://xxxxx.cloudfront.net/auth/callback
```

---

## 인증 플로우

### 사용자 로그인 플로우:

```
1. 사용자가 "Claude Console 로그인" 클릭
   ↓
2. /api/auth/claude 호출
   ↓
3. Claude Console OAuth URL 생성 (PKCE 포함)
   ↓
4. 사용자를 Claude Console로 리다이렉트
   ↓
5. 사용자가 Claude Console에서 로그인 및 권한 승인
   ↓
6. Claude Console이 /auth/callback으로 리다이렉트 (code 포함)
   ↓
7. 백엔드에서 code를 access_token으로 교환
   ↓
8. access_token을 DynamoDB에 안전하게 저장
   ↓
9. 사용자에게 user_id 쿠키 설정
   ↓
10. 대시보드로 리다이렉트
   ↓
11. ✅ 로그인 완료! AI 분석 사용 가능
```

### 토큰 갱신 플로우:

```
1. AI 분석 요청
   ↓
2. 백엔드에서 access_token 확인
   ↓
3. 만료되었으면 refresh_token으로 자동 갱신
   ↓
4. 새 access_token 저장
   ↓
5. AI API 호출 진행
```

---

## 보안 고려사항

### PKCE (Proof Key for Code Exchange)

OAuth 2.0의 보안 강화를 위해 PKCE 사용:

```python
# code_verifier 생성
code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32))

# code_challenge 생성
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
)
```

### State Parameter

CSRF 공격 방지를 위한 state 파라미터:

```python
state = secrets.token_urlsafe(32)
# DynamoDB에 임시 저장 (TTL 10분)
```

### Token 저장

- ✅ DynamoDB에 암호화되어 저장
- ✅ TTL 설정으로 자동 삭제 (30일)
- ✅ Refresh token으로 자동 갱신

---

## 문제 해결

### OAuth App 권한 오류

```
Error: insufficient_scope
```

**해결:**
1. OAuth App 설정에서 Scope 확인
2. Claude: `api:messages` 필요
3. OpenAI: `api` 필요

### Redirect URI 불일치

```
Error: redirect_uri_mismatch
```

**해결:**
1. .env의 REDIRECT_URI 확인
2. OAuth App의 Redirect URIs와 정확히 일치해야 함
3. http vs https 확인
4. 포트 번호 확인

### Token 만료

```
Error: token_expired
```

**해결:**
- 자동 갱신 실패 시 재로그인
- 브라우저에서 "로그아웃" → "다시 로그인"

### PKCE 검증 실패

```
Error: invalid_grant
```

**해결:**
- DynamoDB의 state 세션 확인
- code_verifier가 올바르게 저장되었는지 확인

---

## API 키 방식과 병행 사용

### 하이브리드 모드

OAuth와 API 키를 동시에 지원:

```python
# .env
# OAuth (권장)
CLAUDE_OAUTH_CLIENT_ID=xxx
CLAUDE_OAUTH_CLIENT_SECRET=xxx

# API 키 (백업)
CLAUDE_API_KEY=sk-ant-xxx
```

### 우선순위:

1. OAuth access_token (있으면 사용)
2. API 키 (fallback)

---

## 다음 단계

1. **로컬 테스트**: Docker Compose로 로컬에서 테스트
2. **AWS 배포**: Terraform으로 프로덕션 배포
3. **모니터링**: CloudWatch로 인증 로그 확인

---

## 참고 자료

- [OAuth 2.0 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
- [PKCE RFC 7636](https://datatracker.ietf.org/doc/html/rfc7636)
- [Claude API Documentation](https://docs.anthropic.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)

---

**OAuth 웹 로그인으로 더 안전하고 편리하게!** 🔐
