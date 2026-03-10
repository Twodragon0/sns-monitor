#!/bin/bash
# 로컬 개발 환경 시작 스크립트

set -e

echo "=========================================="
echo "로컬 개발 환경 시작"
echo "=========================================="

# 프로젝트 루트 디렉토리
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 환경 변수 설정
export LOCAL_MODE=true
export LOCAL_DATA_DIR="$PROJECT_ROOT/local-data"

# 로컬 데이터 디렉토리 생성
mkdir -p "$LOCAL_DATA_DIR"
mkdir -p "$LOCAL_DATA_DIR/metadata"
mkdir -p "$LOCAL_DATA_DIR/youtube"
mkdir -p "$LOCAL_DATA_DIR/vuddy"

echo "✅ 로컬 데이터 디렉토리 준비 완료: $LOCAL_DATA_DIR"

# 로컬 API 서버 시작 (백그라운드)
echo ""
echo "🚀 로컬 API 서버 시작 중..."
python3 scripts/start_local_api.py --port 8080 &
API_PID=$!

# API 서버가 시작될 때까지 대기
sleep 2

# API 서버 상태 확인
if curl -s http://localhost:8080/health > /dev/null; then
    echo "✅ 로컬 API 서버 실행 중 (PID: $API_PID)"
    echo "   서버 주소: http://localhost:8080"
else
    echo "❌ 로컬 API 서버 시작 실패"
    kill $API_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "📝 다음 단계:"
echo "1. 크롤러를 실행하여 데이터 수집:"
echo "   python scripts/test_local.py --youtube"
echo ""
echo "2. 프론트엔드 시작 (다른 터미널에서):"
echo "   cd frontend && npm start"
echo ""
echo "3. 브라우저에서 http://localhost:3000 접속"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."
echo "=========================================="

# 종료 시 API 서버도 함께 종료
trap "echo ''; echo '로컬 API 서버를 종료합니다...'; kill $API_PID 2>/dev/null || true; exit" INT TERM

# 대기
wait $API_PID

