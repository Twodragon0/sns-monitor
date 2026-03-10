#!/bin/bash
# Docker를 사용한 로컬 API 서버 시작 스크립트

set -e

echo "=========================================="
echo "Docker 로컬 API 서버 시작"
echo "=========================================="

# 프로젝트 루트 디렉토리
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 로컬 데이터 디렉토리 생성
mkdir -p "$PROJECT_ROOT/local-data"
mkdir -p "$PROJECT_ROOT/local-data/metadata"
mkdir -p "$PROJECT_ROOT/local-data/youtube"
mkdir -p "$PROJECT_ROOT/local-data/vuddy"

echo "✅ 로컬 데이터 디렉토리 준비 완료: $PROJECT_ROOT/local-data"

# Docker Compose로 로컬 API 서버 시작
echo ""
echo "🚀 Docker 로컬 API 서버 시작 중..."

# docker-compose.local.yml이 있으면 사용, 없으면 일반 docker-compose.yml 사용
if [ -f "docker-compose.local.yml" ]; then
    docker-compose -f docker-compose.local.yml up -d api-backend-local
    echo "✅ Docker 로컬 API 서버 실행 중"
    echo "   서버 주소: http://localhost:8080"
    echo ""
    echo "로그 확인: docker-compose -f docker-compose.local.yml logs -f api-backend-local"
    echo "종료: docker-compose -f docker-compose.local.yml down"
else
    echo "⚠️  docker-compose.local.yml 파일이 없습니다."
    echo "   일반 docker-compose.yml을 사용합니다."
    
    # 환경 변수 설정
    export LOCAL_MODE=true
    export LOCAL_DATA_DIR=/app/local-data
    
    docker-compose up -d api-backend
    echo "✅ Docker API 서버 실행 중 (로컬 모드)"
    echo "   서버 주소: http://localhost:8080"
    echo ""
    echo "로그 확인: docker-compose logs -f api-backend"
    echo "종료: docker-compose down"
fi

echo ""
echo "=========================================="

