#!/bin/bash
# SNS 모니터링 시스템 로컬 실행 설정 스크립트

set -e

echo "=========================================="
echo "SNS 모니터링 시스템 로컬 실행 설정"
echo "=========================================="

# 프로젝트 루트 디렉토리 확인
if [ ! -f "docker-compose.yml" ]; then
    echo "✗ 오류: docker-compose.yml 파일을 찾을 수 없습니다."
    echo "  프로젝트 루트 디렉토리에서 실행해주세요."
    exit 1
fi

# Docker 및 Docker Compose 설치 확인
if ! command -v docker &> /dev/null; then
    echo "✗ 오류: Docker가 설치되어 있지 않습니다."
    echo "  https://docs.docker.com/get-docker/ 에서 설치해주세요."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "✗ 오류: Docker Compose가 설치되어 있지 않습니다."
    exit 1
fi

echo "✓ Docker 및 Docker Compose 확인 완료"

# .env 파일 확인 및 생성
if [ ! -f ".env" ]; then
    echo ""
    echo ".env 파일이 없습니다. 생성 중..."
    
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✓ .env.example을 .env로 복사했습니다."
    else
        # .env.example이 없으면 기본 템플릿 생성
        cat > .env << 'EOF'
# SNS 모니터링 시스템 - 환경 변수 설정

# 필수 API 키
YOUTUBE_API_KEY=your_youtube_api_key_here
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNELS=

# 검색 키워드
SEARCH_KEYWORDS=ExampleCorp,CreatorBrand,굿즈

# YouTube 채널 (인수한 회사 및 주요 크리에이터)
YOUTUBE_CHANNELS=@IVNITOFFICIAL,@BARABARA_KR

# RSS 피드 (선택사항)
# 한국 주요 뉴스 사이트 RSS 피드 (기본값)
RSS_FEEDS=https://news.naver.com/main/rss/section.naver?sid=105,https://news.daum.net/rss/it,https://www.bloter.net/rss,https://www.zdnet.co.kr/rss/all.xml,https://news.naver.com/main/rss/section.naver?sid=106

# Vuddy 설정
VUDDY_URL=https://vuddy.io

# Google 검색 설정 (선택사항)
# Google Custom Search API 키가 있으면 설정 (무료 할당량: 일일 100회)
GOOGLE_SEARCH_API_KEY=
GOOGLE_SEARCH_ENGINE_ID=

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

# 크롤링 스케줄
CRAWL_SCHEDULE=*/30 * * * *
EOF
        echo "✓ 기본 .env 파일을 생성했습니다."
    fi
    
    echo ""
    echo "⚠️  중요: .env 파일을 열어서 API 키를 설정해주세요!"
    echo "   최소한 YOUTUBE_API_KEY는 설정해야 합니다."
    echo ""
    read -p "계속하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "설정을 완료한 후 다시 실행해주세요."
        exit 0
    fi
else
    echo "✓ .env 파일이 존재합니다."
fi

# docker-data 디렉토리 생성
echo ""
echo "데이터 디렉토리 생성 중..."
mkdir -p docker-data/dynamodb
mkdir -p docker-data/localstack
mkdir -p docker-data/redis
echo "✓ 데이터 디렉토리 생성 완료"

# Docker 이미지 빌드 및 서비스 시작
echo ""
echo "=========================================="
echo "Docker 서비스 시작 중..."
echo "=========================================="

# 인프라 서비스 먼저 시작 (DynamoDB, LocalStack, Redis)
echo ""
echo "1. 인프라 서비스 시작 (DynamoDB, LocalStack, Redis)..."
docker-compose up -d dynamodb-local localstack redis

echo ""
echo "2. 인프라 서비스 준비 대기 중..."
sleep 10

echo ""
echo "3. DynamoDB 테이블 초기화..."
docker-compose up dynamodb-init

echo ""
echo "4. LocalStack S3 버킷 초기화..."
docker-compose up localstack-init

echo ""
echo "5. 애플리케이션 서비스 시작..."
docker-compose up -d

echo ""
echo "=========================================="
echo "✓ 모든 서비스 시작 완료!"
echo "=========================================="
echo ""
echo "서비스 상태 확인:"
docker-compose ps

echo ""
echo "=========================================="
echo "접속 정보"
echo "=========================================="
echo "🌐 웹 대시보드: http://localhost:3000"
echo "🔌 API 서버:    http://localhost:8080"
echo "📊 API Health:  http://localhost:8080/health"
echo "🔐 Auth 서비스: http://localhost:8081"
echo "🤖 LLM 분석기:  http://localhost:5000"
echo "💾 DynamoDB:    http://localhost:8000"
echo ""
echo "로그 확인:"
echo "  docker-compose logs -f              # 모든 서비스"
echo "  docker-compose logs -f youtube-crawler  # 특정 서비스"
echo ""
echo "서비스 중지:"
echo "  docker-compose down                 # 중지"
echo "  docker-compose down -v              # 중지 + 데이터 삭제"
echo ""

