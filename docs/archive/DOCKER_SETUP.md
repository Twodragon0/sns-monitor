# Docker 로컬 실행 가이드

이 가이드는 Docker를 사용하여 로컬에서 SNS 모니터링 시스템을 실행하는 방법을 설명합니다.

## 🚀 빠른 시작

### 1. 사전 준비

```bash
# Docker 및 Docker Compose 설치 확인
docker --version
docker-compose --version

# 설치되어 있지 않다면:
# macOS: https://docs.docker.com/desktop/install/mac-install/
# Linux: https://docs.docker.com/engine/install/
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
cat > .env << 'EOF'
# 필수 API 키
YOUTUBE_API_KEY=your_youtube_api_key_here
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNELS=

# 검색 키워드
SEARCH_KEYWORDS=Levvels,Vuddy,굿즈

# RSS 피드 (선택사항)
RSS_FEEDS=

# AI 분석 설정
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
ENABLE_MULTI_MODEL=false
CLAUDE_API_KEY=
OPENAI_API_KEY=

# OAuth 설정 (선택사항)
CLAUDE_OAUTH_CLIENT_ID=
CLAUDE_OAUTH_CLIENT_SECRET=
OPENAI_OAUTH_CLIENT_ID=
OPENAI_OAUTH_CLIENT_SECRET=
REDIRECT_URI=http://localhost:3000/auth/callback

# 크롤링 스케줄 (Cron 형식)
CRAWL_SCHEDULE=*/30 * * * *
EOF

# .env 파일 편집하여 API 키 설정
vi .env  # 또는 원하는 에디터 사용
```

**필수 설정:**
- `YOUTUBE_API_KEY`: YouTube Data API v3 키 (필수)
  - 발급: https://console.cloud.google.com/ → API 및 서비스 → YouTube Data API v3 활성화

**선택 설정:**
- `TELEGRAM_BOT_TOKEN`: Telegram 봇 토큰 (선택)
  - 발급: Telegram에서 @BotFather 검색 → /newbot 명령
- `RSS_FEEDS`: RSS 피드 URL 목록 (쉼표로 구분)

### 3. 자동 설정 및 실행

```bash
# 자동 설정 스크립트 실행
./setup.sh
```

이 스크립트는 다음을 자동으로 수행합니다:
- .env 파일 확인 및 생성
- 데이터 디렉토리 생성
- Docker 서비스 시작
- DynamoDB 테이블 초기화
- LocalStack S3 버킷 초기화

### 4. 수동 실행 (선택사항)

자동 스크립트를 사용하지 않으려면:

```bash
# 1. 데이터 디렉토리 생성
mkdir -p docker-data/dynamodb
mkdir -p docker-data/localstack
mkdir -p docker-data/redis

# 2. 인프라 서비스 시작
docker-compose up -d dynamodb-local localstack redis

# 3. 초기화 대기
sleep 10

# 4. DynamoDB 테이블 초기화
docker-compose up dynamodb-init

# 5. LocalStack S3 버킷 초기화
docker-compose up localstack-init

# 6. 모든 서비스 시작
docker-compose up -d
```

## 📊 접속 정보

서비스가 시작되면 다음 주소로 접속할 수 있습니다:

| 서비스 | URL | 설명 |
|--------|-----|------|
| 웹 대시보드 | http://localhost:3000 | React 기반 모니터링 대시보드 |
| API 서버 | http://localhost:8080 | REST API 엔드포인트 |
| API Health | http://localhost:8080/health | API 상태 확인 |
| Auth 서비스 | http://localhost:8081 | OAuth 인증 서비스 |
| LLM 분석기 | http://localhost:5000 | AI 분석 엔진 |
| DynamoDB | http://localhost:8000 | DynamoDB Local |

## 🔍 서비스 확인

### 서비스 상태 확인

```bash
# 모든 서비스 상태
docker-compose ps

# 특정 서비스 로그
docker-compose logs -f youtube-crawler
docker-compose logs -f llm-analyzer
docker-compose logs -f api-backend

# 모든 서비스 로그
docker-compose logs -f
```

### API 테스트

```bash
# Health Check
curl http://localhost:8080/health

# 최근 스캔 목록
curl http://localhost:8080/api/scans

# 대시보드 통계
curl http://localhost:8080/api/dashboard/stats
```

### DynamoDB 확인

```bash
# 테이블 목록
aws dynamodb list-tables \
  --endpoint-url http://localhost:8000 \
  --region ap-northeast-2

# 데이터 스캔
aws dynamodb scan \
  --table-name sns-monitor-results \
  --endpoint-url http://localhost:8000 \
  --region ap-northeast-2
```

### LocalStack S3 확인

```bash
# 버킷 목록
aws s3 ls --endpoint-url http://localhost:4566

# 파일 목록
aws s3 ls s3://sns-monitor-data --endpoint-url http://localhost:4566 --recursive
```

## 🛠 문제 해결

### 컨테이너가 시작되지 않음

```bash
# 로그 확인
docker-compose logs [서비스명]

# 컨테이너 재시작
docker-compose restart [서비스명]

# 전체 재시작
docker-compose down
docker-compose up -d
```

### 포트 충돌

다른 서비스가 포트를 사용 중인 경우:

```bash
# 포트 사용 확인
lsof -i :3000
lsof -i :8080
lsof -i :8000

# docker-compose.yml에서 포트 변경
# 예: "3001:3000" (호스트:컨테이너)
```

### DynamoDB 초기화 실패

```bash
# DynamoDB 데이터 삭제 후 재초기화
docker-compose down -v
rm -rf docker-data/dynamodb
docker-compose up -d dynamodb-local
sleep 5
docker-compose up dynamodb-init
```

### LocalStack 초기화 실패

```bash
# LocalStack 재시작
docker-compose restart localstack
sleep 10
docker-compose up localstack-init
```

### API 키 오류

```bash
# 환경 변수 확인
docker-compose exec youtube-crawler env | grep API

# .env 파일 재로드
docker-compose down
docker-compose up -d
```

## 🧹 정리

### 서비스 중지

```bash
# 모든 서비스 중지 (데이터 유지)
docker-compose down

# 모든 서비스 중지 + 볼륨 삭제 (데이터 삭제)
docker-compose down -v

# 이미지도 삭제
docker-compose down --rmi all
```

### 특정 서비스만 실행

```bash
# 최소 구성 (DB + API + Frontend만)
docker-compose up -d dynamodb-local localstack redis api-backend frontend

# 크롤러만 실행
docker-compose up -d youtube-crawler telegram-crawler rss-crawler
```

## 📝 수동 크롤링 실행

스케줄러를 사용하지 않고 수동으로 크롤링을 실행할 수 있습니다:

```bash
# YouTube 크롤링
curl -X POST http://localhost:5000/invoke \
  -H "Content-Type: application/json" \
  -d '{}'

# Telegram 크롤링
curl -X POST http://telegram-crawler:5000/invoke \
  -H "Content-Type: application/json" \
  -d '{}'

# RSS 크롤링
curl -X POST http://rss-crawler:5000/invoke \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 🔄 코드 변경 시 재빌드

```bash
# 특정 서비스 재빌드
docker-compose up -d --build youtube-crawler

# 모든 서비스 재빌드
docker-compose up -d --build
```

## 💡 팁

### 빠른 반복 개발

```bash
# 코드 변경 → 특정 서비스만 재빌드 (의존성 제외)
docker-compose up -d --build --no-deps youtube-crawler
```

### 멀티 모델 테스트

```bash
# .env에서 활성화
ENABLE_MULTI_MODEL=true
CLAUDE_API_KEY=your_key
OPENAI_API_KEY=your_key

# 재시작
docker-compose restart llm-analyzer
```

### 스케줄 변경

```bash
# .env 수정
CRAWL_SCHEDULE=*/15 * * * *  # 15분마다

# Scheduler 재시작
docker-compose restart scheduler
```

## 📚 추가 문서

- [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) - 상세 개발 가이드
- [README.md](README.md) - 프로젝트 개요
- [QUICKSTART.md](QUICKSTART.md) - 빠른 시작 (AWS 배포)

---

**Happy Coding! 🎉**

