# SNS 모니터링 시스템 - 빠른 시작 가이드

## 5분 만에 시작하기

### 1. API 키 발급 (3분)

```bash
# YouTube API 키 (필수, 무료)
# https://console.cloud.google.com/
# → API 및 서비스 → YouTube Data API v3 활성화
# → 사용자 인증 정보 → API 키 생성

# Telegram Bot (필수, 무료)
# Telegram에서 @BotFather 검색
# /newbot 명령으로 봇 생성
```

### 2. 배포 (2분)

```bash
cd sns-monitoring-system/terraform

# 설정 파일 생성
cp terraform.tfvars.example terraform.tfvars

# API 키 입력
vi terraform.tfvars
# youtube_api_key = "YOUR_KEY"
# telegram_bot_token = "YOUR_TOKEN"

# 배포
terraform init
terraform apply
# "yes" 입력
```

### 3. 완료!

배포 완료 후 출력된 URL로 대시보드 접속:

```bash
terraform output cloudfront_url
# https://xxxxx.cloudfront.net
```

---

## 주요 기능

- ✅ YouTube 댓글 자동 수집
- ✅ Telegram 메시지 모니터링
- ✅ RSS 피드 크롤링 (블로그, 뉴스)
- ✅ AI 감성 분석 (Bedrock Claude)
- ✅ 멀티 모델 분석 (Claude API + OpenAI, 선택사항)
- ✅ 실시간 대시보드
- ✅ Slack/이메일 알림
- ✅ Chrome Extension (Twitter 무료 수집)

---

## 비용

**최소 구성**: 월 $10-15 ✅ 비용 절감 최적화

**비용 절감 전략 적용:**
- ✅ Twitter API 대신 Chrome Extension → **-$100/월**
- ✅ CloudWatch Logs 비활성화 → **-$5/월**
- ✅ 크롤링 빈도 2시간마다 → **-50% Lambda 비용**

**세부 비용:**
- YouTube + Telegram + RSS (무료 API)
- 2시간마다 자동 크롤링
- AI 분석 포함 (Claude Haiku)
- 웹 대시보드

**고급 옵션 (선택사항):**
- 멀티 모델 분석: +$10-20/월 (더 정확한 분석)

---

## Chrome Extension 사용

Twitter, Instagram 등 유료 API를 회피하려면:

```bash
cd chrome-extension

# Chrome에서
# 1. chrome://extensions 접속
# 2. "개발자 모드" 활성화
# 3. "압축해제된 확장 프로그램" 로드
# 4. chrome-extension 폴더 선택
```

**사용법**:
1. YouTube/Twitter 방문
2. Extension 클릭
3. 키워드 입력 → "데이터 수집"
4. 자동 분석 완료!

---

## 키워드 변경

```hcl
# terraform.tfvars
search_keywords = ["Levvels", "Vuddy", "굿즈", "새키워드"]

# 적용
terraform apply
```

---

## 문제 해결

### Bedrock 권한 오류

```bash
# AWS Console → Bedrock (us-east-1)
# → Model access → Anthropic Claude 활성화
```

### 비용이 높아요

```hcl
# terraform.tfvars
enable_twitter = false  # -$100/월
crawl_schedule = "rate(2 hours)"  # 비용 50% 절감
enable_cloudwatch_logs = false  # -$5/월
```

### 대시보드 접속 안 됨

```bash
# CloudFront 배포 완료까지 5-10분 대기
terraform output cloudfront_url
```

---

## 다음 단계

1. **알림 설정**: Slack Webhook URL 추가
2. **키워드 확장**: 모니터링 키워드 추가
3. **비용 최적화**: [cost-optimization.md](docs/cost-optimization.md)
4. **상세 가이드**: [deployment-guide.md](docs/deployment-guide.md)

---

## 주요 파일

```
sns-monitoring-system/
├── README.md                           # 프로젝트 개요
├── QUICKSTART.md                       # 이 파일
├── lambda/
│   ├── youtube-crawler/                # YouTube 크롤러
│   ├── telegram-crawler/               # Telegram 크롤러
│   └── llm-analyzer/                   # AI 분석기
├── terraform/
│   ├── terraform.tfvars.example        # 설정 예제
│   └── *.tf                            # 인프라 코드
├── chrome-extension/                   # Chrome Extension
└── docs/
    ├── deployment-guide.md             # 상세 배포 가이드
    └── cost-optimization.md            # 비용 절감 가이드
```

---

## 지원

- **전체 문서**: [README.md](README.md)
- **배포 가이드**: [docs/deployment-guide.md](docs/deployment-guide.md)
- **비용 가이드**: [docs/cost-optimization.md](docs/cost-optimization.md)
- **이슈 리포트**: GitHub Issues

---

## 라이선스

MIT License
