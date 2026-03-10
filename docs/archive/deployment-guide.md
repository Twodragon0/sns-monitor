# SNS 모니터링 시스템 배포 가이드

## 목차

1. [사전 준비](#사전-준비)
2. [API 키 발급](#api-키-발급)
3. [Terraform 배포](#terraform-배포)
4. [Chrome Extension 설치](#chrome-extension-설치)
5. [대시보드 접속](#대시보드-접속)
6. [문제 해결](#문제-해결)

---

## 사전 준비

### 1. 필수 도구 설치

```bash
# AWS CLI 설치 및 설정
aws configure
# AWS Access Key ID, Secret Access Key, Region 입력

# Terraform 설치 (macOS)
brew install terraform

# 또는 Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# 버전 확인
terraform --version
```

### 2. AWS 권한 확인

다음 AWS 서비스에 대한 권한이 필요합니다:

- Lambda
- DynamoDB
- S3
- API Gateway
- CloudFront
- Secrets Manager
- EventBridge
- SNS
- IAM
- Bedrock (us-east-1 리전)

---

## API 키 발급

### 1. YouTube Data API v3 (무료, 권장)

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. API 및 서비스 → 라이브러리
4. "YouTube Data API v3" 검색 및 활성화
5. API 및 서비스 → 사용자 인증 정보
6. "사용자 인증 정보 만들기" → "API 키"
7. API 키 복사

**할당량**: 10,000 유닛/일 (무료)

### 2. Telegram Bot (무료, 권장)

1. Telegram에서 [@BotFather](https://t.me/botfather) 검색
2. `/newbot` 명령 입력
3. 봇 이름 및 username 입력
4. Bot Token 복사 (예: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

**채널 모니터링 설정:**
```bash
# 1. 봇을 채널에 추가
# 2. 봇을 관리자로 설정
# 3. terraform.tfvars에 채널명 입력 (예: @your_channel)
```

### 3. Twitter API (선택사항, $100/월)

⚠️ **비용 주의**: Twitter API는 월 $100의 비용이 발생합니다.

1. [Twitter Developer Portal](https://developer.twitter.com/) 접속
2. Developer 계정 신청
3. Basic Plan 구독 ($100/월)
4. App 생성
5. Keys and Tokens → Bearer Token 복사

**무료 대안**: Chrome Extension으로 수동 수집

### 4. Instagram Graph API (선택사항, 제한적)

1. [Meta for Developers](https://developers.facebook.com/) 접속
2. 앱 생성
3. Instagram Basic Display API 추가
4. Access Token 발급

**제약사항**: 공개 계정만 접근 가능

---

## Terraform 배포

### 1. 설정 파일 준비

```bash
cd sns-monitoring-system/terraform

# 설정 파일 복사
cp terraform.tfvars.example terraform.tfvars

# 설정 파일 편집
vi terraform.tfvars
```

### 2. terraform.tfvars 설정

최소 구성 예시:

```hcl
# 기본 설정
project_name = "sns-monitor"
aws_region = "ap-northeast-2"
environment = "dev"

# 키워드
search_keywords = ["Levvels", "Vuddy", "굿즈"]

# 크롤링 스케줄 (1시간마다 = 비용 절감)
crawl_schedule = "rate(1 hour)"

# API 키 (필수: YouTube, Telegram만)
youtube_api_key = "YOUR_YOUTUBE_API_KEY"
telegram_bot_token = "YOUR_TELEGRAM_BOT_TOKEN"
telegram_channels = ["@your_channel"]

# 플랫폼 활성화
enable_youtube = true
enable_telegram = true
enable_twitter = false  # $100/월 비용 발생

# AI 모델 (비용 절감)
bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0"

# 알림 (선택사항)
slack_webhook_url = ""
sns_email = ""

# 비용 절감 옵션
enable_cloudwatch_logs = false
enable_waf = false
```

### 3. Bedrock 모델 접근 권한 활성화

```bash
# AWS Console에서
# 1. Bedrock 서비스 접속 (us-east-1 리전)
# 2. Model access 메뉴
# 3. "Manage model access" 클릭
# 4. "Anthropic Claude" 모델 선택
# 5. "Save changes"

# 또는 CLI로
aws bedrock list-foundation-models --region us-east-1
```

### 4. Terraform 초기화 및 배포

```bash
# Terraform 초기화
terraform init

# 배포 계획 확인
terraform plan

# 배포 실행
terraform apply

# "yes" 입력하여 배포 시작
```

배포 소요 시간: 약 5-10분

### 5. 출력 확인

배포 완료 후 중요한 정보가 출력됩니다:

```bash
Outputs:

api_gateway_url = "https://xxxxx.execute-api.ap-northeast-2.amazonaws.com/dev"
cloudfront_url = "https://xxxxx.cloudfront.net"
youtube_crawler_function_name = "sns-monitor-youtube-crawler"
telegram_crawler_function_name = "sns-monitor-telegram-crawler"
llm_analyzer_function_name = "sns-monitor-llm-analyzer"
dynamodb_table_name = "sns-monitor-analysis-results"
```

**중요**: `api_gateway_url`과 `cloudfront_url`을 메모해두세요!

---

## Chrome Extension 설치

### 1. Extension 로드

```bash
cd sns-monitoring-system/chrome-extension

# Chrome 브라우저 열기
# 1. chrome://extensions 접속
# 2. 오른쪽 상단 "개발자 모드" 활성화
# 3. "압축해제된 확장 프로그램을 로드합니다" 클릭
# 4. chrome-extension 폴더 선택
```

### 2. API 설정

Extension 설치 후:

1. Extension 아이콘 클릭
2. "API 설정" 버튼 클릭
3. API Gateway URL 입력 (Terraform 출력에서 확인)
4. API Key 입력 (Terraform 출력 또는 AWS Console에서 확인)
5. 저장

### 3. 사용 방법

1. YouTube, Twitter 등 지원 플랫폼 방문
2. Extension 아이콘 클릭
3. 키워드 입력 (예: "Levvels")
4. "데이터 수집 시작" 버튼 클릭
5. 수집된 데이터가 자동으로 분석됨

---

## 대시보드 접속

### 1. CloudFront URL 접속

```bash
# Terraform 출력에서 CloudFront URL 확인
terraform output cloudfront_url

# 브라우저에서 접속
open https://xxxxx.cloudfront.net
```

### 2. 대시보드 기능

- **실시간 통계**: 플랫폼별 수집 현황
- **감성 분석 차트**: 긍정/부정/중립 비율
- **키워드 클라우드**: 주요 키워드 시각화
- **트렌드 분석**: 시간대별 변화
- **최근 데이터**: 최신 댓글/포스트 목록

---

## 문제 해결

### 1. Terraform 배포 실패

#### "Error: AccessDeniedException: User is not authorized"

**원인**: Bedrock 모델 접근 권한 없음

**해결**:
```bash
# AWS Console에서 Bedrock 모델 접근 활성화
# us-east-1 리전에서 수행
```

#### "Error: BucketAlreadyExists"

**원인**: S3 버킷 이름 중복

**해결**:
```hcl
# terraform.tfvars 수정
project_name = "sns-monitor-unique-name"
```

### 2. Lambda 함수 실패

#### YouTube API Quota 초과

**증상**: `quotaExceeded` 에러

**해결**:
```hcl
# terraform.tfvars 수정
# 크롤링 빈도 낮추기
crawl_schedule = "rate(2 hours)"  # 2시간마다
```

#### Telegram Bot 권한 오류

**증상**: `Forbidden: bot was kicked from the channel`

**해결**:
1. 봇을 채널에 다시 추가
2. 봇을 관리자로 설정
3. Lambda 함수 재실행

### 3. Chrome Extension 문제

#### "API 전송 실패" 에러

**해결**:
1. Extension 설정에서 API Gateway URL 확인
2. API Key가 올바른지 확인
3. CORS 설정 확인:

```bash
# Terraform에서 CORS 활성화 확인
# api-gateway.tf 파일 수정 필요 시
```

#### 데이터 수집이 안 됨

**해결**:
1. 페이지 새로고침 후 재시도
2. 댓글이 로드된 상태인지 확인
3. 브라우저 콘솔에서 에러 확인 (F12)

### 4. 비용 문제

#### 예상보다 높은 비용 발생

**확인사항**:
1. Twitter API 활성화 여부 ($100/월)
2. 크롤링 빈도 확인
3. CloudWatch Logs 비활성화 확인

**비용 절감**:
```hcl
# terraform.tfvars 수정
enable_twitter = false
enable_cloudwatch_logs = false
crawl_schedule = "rate(2 hours)"  # 빈도 낮추기
```

### 5. 대시보드 접속 불가

#### CloudFront 배포 진행 중

**증상**: 403 Forbidden

**해결**: CloudFront 배포 완료까지 5-10분 대기

#### S3 버킷이 비어있음

**증상**: 빈 페이지 또는 404 에러

**해결**:
```bash
# 프론트엔드 빌드 및 배포
cd frontend
npm install
npm run build
aws s3 sync build/ s3://your-frontend-bucket-name/
```

---

## 다음 단계

1. **데이터 확인**: 첫 크롤링이 완료될 때까지 대기 (스케줄에 따라)
2. **알림 설정**: Slack 또는 이메일 알림 설정
3. **키워드 추가**: 모니터링할 키워드 확장
4. **대시보드 커스터마이징**: 필요에 따라 프론트엔드 수정

---

## 유지보수

### 정기 작업

```bash
# 비용 확인
aws ce get-cost-and-usage --time-period Start=2024-01-01,End=2024-01-31 --granularity MONTHLY --metrics BlendedCost

# Lambda 로그 확인 (CloudWatch 활성화 시)
aws logs tail /aws/lambda/sns-monitor-youtube-crawler --follow

# DynamoDB 데이터 확인
aws dynamodb scan --table-name sns-monitor-analysis-results --limit 10
```

### 업데이트

```bash
cd sns-monitoring-system/terraform

# 변경사항 적용
terraform plan
terraform apply
```

### 삭제

```bash
# 모든 리소스 삭제
terraform destroy

# "yes" 입력하여 삭제 확인
```

⚠️ **주의**: S3 버킷의 데이터는 수동으로 삭제해야 할 수 있습니다.

---

## 지원

문제가 발생하면 다음을 확인하세요:

1. [README.md](../README.md) - 프로젝트 개요
2. [Cost Optimization Guide](cost-optimization.md) - 비용 절감 팁
3. [API Documentation](api-documentation.md) - API 사용법
4. GitHub Issues - 버그 리포트

---

## 체크리스트

배포 전 확인사항:

- [ ] AWS CLI 설정 완료
- [ ] Terraform 설치 완료
- [ ] YouTube API 키 발급
- [ ] Telegram Bot 생성
- [ ] Bedrock 모델 접근 권한 활성화
- [ ] terraform.tfvars 파일 설정
- [ ] 비용 예산 확인
- [ ] S3 버킷 이름 중복 확인

배포 후 확인사항:

- [ ] Terraform 배포 성공
- [ ] Lambda 함수 정상 작동
- [ ] CloudFront 배포 완료
- [ ] Chrome Extension 설치 및 설정
- [ ] 대시보드 접속 가능
- [ ] 첫 데이터 수집 완료
- [ ] 알림 설정 완료
