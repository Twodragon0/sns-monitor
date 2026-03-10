# SNS 모니터링 & AI 분석 시스템

Levvels, Vuddy, 굿즈 등 키워드를 SNS에서 실시간 모니터링하고 Amazon Bedrock AI로 분석하는 서버리스 시스템

## 주요 기능

- 🔍 **멀티 플랫폼 모니터링**: YouTube, 트위터, 텔레그램, 인스타그램, RSS 피드
- 🤖 **AI 분석**: Amazon Bedrock Claude로 감성 분석, 트렌드 분석, 키워드 추출
- 📊 **실시간 대시보드**: React 기반 웹 대시보드
- 🔔 **알림 시스템**: Slack, 이메일, 텔레그램 알림
- 💰 **비용 최적화**: 서버리스 아키텍처로 월 $10-15 운영 가능
- 🔌 **Chrome Extension**: Twitter API 없이 무료 수집 ($100/월 절감)

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                      SNS 플랫폼들                              │
│  YouTube │ Telegram │ RSS 피드 │ Instagram                  │
│  + Chrome Extension으로 Twitter 무료 수집 (API 비용 $0)      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               EventBridge (스케줄러)                          │
│              2시간마다 크롤링 실행 (비용 절감 50%)             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Lambda Crawlers                             │
│  YouTube API │ Telegram Bot │ RSS Parser │ Instagram API   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    S3 (원본 데이터)                           │
│              raw-data/youtube/2024-01-15.json               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda LLM Analyzer (Bedrock)                   │
│         감성 분석 │ 트렌드 분석 │ 키워드 추출                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  DynamoDB (분석 결과)                         │
│    timestamp │ platform │ sentiment │ keywords │ summary    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           CloudFront + S3 (React Dashboard)                  │
│              실시간 차트 및 인사이트 시각화                     │
└─────────────────────────────────────────────────────────────┘
```

## 비용 예측 (월별)

### 💰 최소 구성 (~$10-15/월) ✅ 권장

**비용 절감 전략 적용:**
- ✅ Twitter API 대신 Chrome Extension 사용 → **-$100/월**
- ✅ CloudWatch Logs 비활성화 → **-$5/월**
- ✅ 크롤링 빈도 2시간마다 → **-50% Lambda 비용**

**세부 비용:**
- Lambda 실행 (2시간 주기): ~$1-2
- DynamoDB (온디맨드): ~$2-3
- S3 저장: ~$1
- Bedrock Claude Haiku: ~$3-5
- CloudFront: ~$1-2
- API 호출 (YouTube 무료, Telegram 무료, RSS 무료): ~$0

**총합: $10-15/월**

### 표준 구성 (~$25-30/월)
- 1시간마다 크롤링
- Instagram 추가
- Claude Haiku

### 실시간 구성 (~$120-150/월)
- Twitter API 포함 ($100/월)
- 15분마다 크롤링
- Claude Sonnet
- WAF 추가

## 지원 플랫폼

| 플랫폼 | API 지원 | 비용 | 비고 |
|--------|----------|------|------|
| YouTube | ✅ 무료 | 무료 (할당량 10,000/일) | YouTube Data API v3 |
| Twitter/X | 🔌 Extension | **무료** | Chrome Extension으로 무료 수집 |
| Telegram | ✅ 무료 | 무료 | Bot API 사용 |
| RSS 피드 | ✅ 무료 | 무료 | 블로그, 뉴스 사이트 RSS |
| Instagram | ✅ 제한적 | 무료 | Meta Graph API (공개 계정만) |
| Twitter API | ⚠️ 선택사항 | $100/월 (Basic) | Extension 사용 시 불필요 |

## 빠른 시작

### 방법 1: Docker 로컬 실행 (권장 - 개발/테스트용)

로컬에서 빠르게 테스트하고 싶다면 Docker를 사용하세요:

```bash
# 1. 환경 변수 설정
cat > .env << 'EOF'
YOUTUBE_API_KEY=your_youtube_api_key_here
SEARCH_KEYWORDS=Levvels,Vuddy,굿즈
CRAWL_SCHEDULE=*/30 * * * *
EOF

# 2. 자동 설정 및 실행
./setup.sh

# 3. 웹 대시보드 접속
open http://localhost:3000
```

**자세한 내용**: [DOCKER_SETUP.md](DOCKER_SETUP.md) 참조

### 방법 2: AWS 배포 (프로덕션용)

AWS에 배포하려면:

```bash
# 1. 사전 준비
aws configure
brew install terraform

# 2. API 키 발급
# - YouTube: https://console.cloud.google.com/ → YouTube Data API v3 활성화
# - Telegram: @BotFather → 봇 생성 (무료)

# 3. 배포
cd terraform
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars 편집하여 API 키 설정

terraform init
terraform apply

# 4. 대시보드 접속
terraform output cloudfront_url
```

## Chrome Extension (선택사항)

API 비용을 절감하고 싶다면 Chrome Extension으로 수동 데이터 수집:

```bash
cd chrome-extension

# Chrome 브라우저에서 로드
# 1. chrome://extensions 접속
# 2. "개발자 모드" 활성화
# 3. "압축해제된 확장 프로그램을 로드합니다" 클릭
# 4. chrome-extension 폴더 선택
```

**사용 방법:**
1. YouTube, Twitter 등 접속
2. Extension 아이콘 클릭
3. "데이터 수집" 버튼 클릭
4. 자동으로 Lambda API로 전송

## 프로젝트 구조

```
sns-monitoring-system/
├── README.md                           # 이 파일
├── docs/
│   ├── architecture.md                 # 상세 아키텍처
│   ├── api-documentation.md            # API 문서
│   └── cost-optimization.md            # 비용 최적화 가이드
├── lambda/
│   ├── youtube-crawler/                # YouTube 댓글 크롤러
│   │   ├── lambda_function.py
│   │   ├── requirements.txt
│   │   └── README.md
│   ├── twitter-crawler/                # Twitter 트윗 크롤러
│   ├── telegram-crawler/               # Telegram 메시지 크롤러
│   ├── instagram-crawler/              # Instagram 포스트 크롤러
│   ├── naver-cafe-crawler/             # Naver Cafe 게시글 크롤러
│   ├── llm-analyzer/                   # Bedrock AI 분석기
│   │   ├── lambda_function.py
│   │   ├── prompts/
│   │   │   ├── sentiment_analysis.txt
│   │   │   └── trend_analysis.txt
│   │   └── requirements.txt
│   └── api-backend/                    # API Gateway 백엔드
│       ├── lambda_function.py
│       └── requirements.txt
├── terraform/
│   ├── main.tf                         # 메인 설정
│   ├── variables.tf                    # 변수 정의
│   ├── lambda.tf                       # Lambda 함수
│   ├── dynamodb.tf                     # DynamoDB 테이블
│   ├── s3.tf                           # S3 버킷
│   ├── api-gateway.tf                  # API Gateway
│   ├── cloudfront.tf                   # CloudFront CDN
│   ├── eventbridge.tf                  # 스케줄러
│   ├── iam.tf                          # IAM 역할/정책
│   ├── sns.tf                          # 알림
│   ├── secrets.tf                      # Secrets Manager (API 키)
│   └── terraform.tfvars.example        # 설정 예제
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.jsx           # 메인 대시보드
│   │   │   ├── SentimentChart.jsx      # 감성 분석 차트
│   │   │   ├── TrendChart.jsx          # 트렌드 차트
│   │   │   ├── KeywordCloud.jsx        # 키워드 클라우드
│   │   │   └── PlatformStats.jsx       # 플랫폼별 통계
│   │   ├── App.jsx
│   │   └── index.jsx
│   ├── package.json
│   └── README.md
├── chrome-extension/
│   ├── manifest.json                   # Extension 설정
│   ├── popup.html                      # Extension UI
│   ├── popup.js                        # Extension 로직
│   ├── content.js                      # 페이지 스크립트
│   └── README.md
└── knowledge-base/
    ├── sns-analysis-guide.md           # SNS 분석 가이드
    └── keyword-dictionary.md           # 키워드 사전

```

## 설정 옵션

### terraform.tfvars

```hcl
# 기본 설정
project_name = "sns-monitor"
aws_region = "ap-northeast-2"
environment = "dev"

# 검색 키워드
search_keywords = ["Levvels", "Vuddy", "굿즈"]

# 크롤링 스케줄 (비용에 영향)
crawl_schedule = "rate(2 hours)"    # 2시간마다 (비용 절감 50%, 권장)
# crawl_schedule = "rate(1 hour)"    # 1시간마다 (표준)
# crawl_schedule = "rate(30 minutes)" # 30분마다
# crawl_schedule = "rate(15 minutes)" # 15분마다 (실시간성 향상)

# API 키 (Secrets Manager에 저장)
youtube_api_key = ""
twitter_bearer_token = ""
telegram_bot_token = ""
instagram_access_token = ""

# AI 모델 설정
bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0"  # 비용 절감
# bedrock_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"  # 성능 향상

# 플랫폼 활성화 (비용 제어)
enable_youtube = true
enable_twitter = false    # Chrome Extension 사용 (무료)
enable_telegram = true
enable_rss = true         # RSS 피드 (무료, 권장)
enable_instagram = false

# RSS 피드 URL 목록
rss_feeds = [
  "https://news.naver.com/main/rss/section.naver?sid=105",  # 네이버 IT/과학
  "https://news.daum.net/rss/it",                          # 다음 IT
  "https://www.bloter.net/rss",                            # 블로터
  "https://www.zdnet.co.kr/rss/all.xml",                   # ZDNet Korea
  "https://news.naver.com/main/rss/section.naver?sid=106", # 네이버 연예
  "https://news.daum.net/rss/entertain",                   # 다음 연예
  "https://www.yna.co.kr/rss/industry/10000001.xml",       # 연합뉴스 IT/과학
  "https://www.yna.co.kr/rss/entertainment/10000002.xml"   # 연합뉴스 연예
]

# 알림 설정
slack_webhook_url = ""
sns_email = ""

# 비용 최적화 (권장 설정)
enable_cloudwatch_logs = false    # -$5/월 절감
enable_waf = false                # -$8/월 절감
enable_chrome_extension_api = true  # Twitter 무료 수집
dynamodb_billing_mode = "PAY_PER_REQUEST"
```

## 주요 기능 상세

### 1. YouTube 댓글 크롤링
- YouTube Data API v3 사용
- 특정 채널 또는 키워드 검색
- 댓글, 대댓글, 좋아요 수 수집
- 일일 할당량: 10,000 유닛 (무료)

### 2. AI 분석 (Bedrock)
- **감성 분석**: 긍정/부정/중립 분류
- **트렌드 분석**: 시간대별 언급량 증감
- **키워드 추출**: 주요 키워드 및 연관어
- **요약 생성**: 핵심 내용 요약

### 3. 실시간 대시보드
- 플랫폼별 통계
- 감성 분석 차트 (긍정/부정 비율)
- 키워드 클라우드
- 시간대별 트렌드
- 최근 댓글/포스트 목록

### 4. 알림 시스템
- 특정 키워드 감지 시 즉시 알림
- 부정적 감정 급증 시 알림
- Slack, 이메일, 텔레그램 지원

## Chrome Extension 사용법

API 비용 없이 데이터 수집:

1. Extension 설치
2. YouTube, Twitter 등 방문
3. Extension 클릭 → "데이터 수집"
4. 현재 페이지의 댓글/포스트 수집
5. Lambda API로 자동 전송 및 분석

## 비용 최적화 팁

1. **크롤링 빈도 조절**: 30분 → 1시간 (비용 50% 절감)
2. **플랫폼 선택**: Twitter API 비활성화 ($100/월 절감)
3. **Claude Haiku 사용**: Sonnet 대비 80% 저렴
4. **CloudWatch Logs 비활성화**: $5-8/월 절감
5. **DynamoDB TTL 설정**: 오래된 데이터 자동 삭제
6. **Chrome Extension 활용**: API 비용 제로

## 다음 단계

- [ ] 카카오톡 오픈채팅 모니터링 (비공식 API)
- [ ] 페이스북 그룹 모니터링
- [ ] 디스코드 서버 모니터링
- [ ] AI 자동 응답 기능
- [ ] 경쟁사 모니터링 대시보드

## 라이선스

MIT License

## 지원

이슈가 있으면 GitHub Issues에 등록해주세요.
