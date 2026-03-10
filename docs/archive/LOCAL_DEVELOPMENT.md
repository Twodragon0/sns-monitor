# 로컬 개발 환경 가이드

AWS에 배포하지 않고 Docker로 로컬에서 전체 시스템을 실행할 수 있습니다.

## 🚀 빠른 시작

### 1. 사전 준비

```bash
# Docker 설치 확인
docker --version
docker-compose --version

# API 키 발급 (무료)
# - YouTube: https://console.cloud.google.com/
# - Telegram: @BotFather (t.me/botfather)
```

### 2. 환경 설정

```bash
cd sns-monitoring-system

# 환경 변수 파일 생성
cp .env.example .env

# .env 파일 편집
vi .env
```

**필수 설정:**
```bash
# .env
YOUTUBE_API_KEY=YOUR_YOUTUBE_API_KEY_HERE
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE
SEARCH_KEYWORDS=Levvels,Vuddy,굿즈
```

### 3. 실행

```bash
# 모든 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 서비스 상태 확인
docker-compose ps
```

### 4. 접속

- **웹 대시보드**: http://localhost:3000
- **API**: http://localhost:8080/api/health
- **DynamoDB Admin**: http://localhost:8000

## 📦 서비스 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend | 3000 | React 웹 대시보드 |
| API Backend | 8080 | REST API 서버 |
| YouTube Crawler | - | YouTube 댓글 수집 |
| Telegram Crawler | - | Telegram 메시지 수집 |
| RSS Crawler | - | RSS 피드 수집 |
| LLM Analyzer | 5000 | AI 분석 엔진 |
| DynamoDB Local | 8000 | 로컬 DynamoDB |
| LocalStack | 4566 | 로컬 S3/SNS |
| Redis | 6379 | 캐싱 |
| Scheduler | - | Cron 스케줄러 |

## 🔧 개발 모드

### 특정 서비스만 실행

```bash
# 최소 구성 (DB + API + Frontend만)
docker-compose up -d dynamodb-local api-backend frontend

# 크롤러만 실행
docker-compose up -d youtube-crawler telegram-crawler rss-crawler

# 특정 크롤러만
docker-compose up -d youtube-crawler
```

### 수동 크롤링 실행

```bash
# YouTube 크롤링 수동 트리거
curl -X POST http://localhost:5000/invoke \
  -H "Content-Type: application/json" \
  -d '{}'

# Telegram 크롤링
curl -X POST http://localhost:5001/invoke \
  -H "Content-Type: application/json" \
  -d '{}'

# RSS 크롤링
curl -X POST http://localhost:5002/invoke \
  -H "Content-Type: application/json" \
  -d '{}'
```

### LLM 분석 수동 실행

```bash
curl -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "s3_key": "raw-data/youtube/keyword/2024-01-15.json",
    "keyword": "Levvels",
    "source": "youtube"
  }'
```

### 코드 변경 시 재시작

```bash
# 특정 서비스 재빌드
docker-compose up -d --build youtube-crawler

# 모든 서비스 재빌드
docker-compose up -d --build
```

## 🧪 테스트

### API 테스트

```bash
# Health Check
curl http://localhost:8080/health

# 최근 스캔 목록
curl http://localhost:8080/api/scans

# 특정 스캔 상세
curl http://localhost:8080/api/scans/{scan_id}

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

# 전체 로그
docker-compose logs

# 컨테이너 재시작
docker-compose restart [서비스명]
```

### DynamoDB 초기화

```bash
# DynamoDB 데이터 삭제
docker-compose down -v
rm -rf docker-data/dynamodb

# 재시작
docker-compose up -d dynamodb-local
```

### Redis 캐시 초기화

```bash
# Redis 접속
docker-compose exec redis redis-cli

# 모든 캐시 삭제
> FLUSHALL

# 특정 키 삭제
> DEL analysis:*
```

### API 키 오류

```bash
# 환경 변수 확인
docker-compose exec youtube-crawler env | grep API

# .env 파일 재로드
docker-compose down
docker-compose up -d
```

### 포트 충돌

.env 파일에서 포트 변경:

```bash
API_PORT=8081
FRONTEND_PORT=3001
DYNAMODB_PORT=8001
```

## 📊 모니터링

### 컨테이너 리소스 사용량

```bash
docker stats
```

### 로그 스트리밍

```bash
# 모든 서비스 로그
docker-compose logs -f

# 특정 서비스만
docker-compose logs -f youtube-crawler llm-analyzer

# 최근 100줄
docker-compose logs --tail=100
```

### Redis 모니터링

```bash
# Redis 접속
docker-compose exec redis redis-cli

# 정보 확인
> INFO

# 키 목록
> KEYS *

# 캐시 히트율
> INFO stats
```

## 🔄 데이터 플로우

```
1. Scheduler (Cron)
   ↓
2. Crawlers (YouTube, Telegram, RSS)
   ↓ 데이터 수집
3. LocalStack S3 (원본 저장)
   ↓
4. LLM Analyzer (AI 분석)
   ↓ 분석 결과
5. DynamoDB Local (저장)
   ↓
6. API Backend (REST API)
   ↓
7. Frontend (웹 대시보드)
```

## 🚀 프로덕션 배포

로컬 테스트 완료 후 AWS 배포:

```bash
# Terraform으로 AWS 배포
cd terraform
terraform init
terraform apply
```

자세한 내용은 [deployment-guide.md](docs/deployment-guide.md) 참조

## 🧹 정리

```bash
# 모든 컨테이너 중지 및 삭제
docker-compose down

# 볼륨 포함 삭제 (모든 데이터 삭제)
docker-compose down -v

# 이미지도 삭제
docker-compose down --rmi all
```

## 💡 팁

### 빠른 반복 개발

```bash
# 코드 변경 → 특정 서비스만 재빌드
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

### 디버깅 모드

```bash
# 디버그 로그 활성화
LOG_LEVEL=DEBUG docker-compose up -d

# 특정 서비스 디버그
docker-compose exec youtube-crawler python lambda_function.py
```

## 📚 추가 문서

- [README.md](README.md) - 프로젝트 개요
- [QUICKSTART.md](QUICKSTART.md) - 빠른 시작
- [deployment-guide.md](docs/deployment-guide.md) - AWS 배포 가이드
- [cost-optimization.md](docs/cost-optimization.md) - 비용 최적화

## 🤝 기여

로컬 개발 중 이슈 발견 시 GitHub Issues에 등록해주세요.

---

**Happy Coding! 🎉**
