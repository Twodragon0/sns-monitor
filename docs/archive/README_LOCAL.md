# 로컬 개발 환경 가이드

로컬에서 S3/DynamoDB 없이 개발 및 테스트를 수행하는 방법입니다.

## 🚀 빠른 시작

### 1. 로컬 API 서버 시작

```bash
# 환경 변수 설정
export LOCAL_MODE=true
export LOCAL_DATA_DIR=./local-data

# 로컬 API 서버 시작
python scripts/start_local_api.py
```

### 2. 크롤러 실행 (데이터 수집)

```bash
# YouTube 크롤러 실행
export YOUTUBE_API_KEY=your_api_key
python scripts/test_local.py --youtube

# Vuddy 크롤러 실행
python scripts/test_local.py --vuddy
```

### 3. 프론트엔드 시작

```bash
cd frontend
npm start
```

브라우저에서 `http://localhost:3000` 접속하면 로컬 데이터를 확인할 수 있습니다.

## 📁 데이터 구조

로컬 데이터는 `local-data/` 디렉토리에 저장됩니다:

```
local-data/
├── youtube/
│   ├── Archive Studio/
│   │   └── 2025-01-18-12-30-45.json
│   └── channels/
│       └── AkaivStudioOfficial/
│           └── 2025-01-18-12-35-20.json
├── vuddy/
│   └── comprehensive_analysis/
│       └── 2025-01-18-12-40-10.json
└── metadata/
    ├── youtube/
    │   └── youtube-Archive Studio-20250118123045.json
    └── vuddy/
        └── vuddy-Archive Studio-20250118123510.json
```

## 🔍 확인 방법

### API 엔드포인트 테스트

```bash
# Health check
curl http://localhost:8080/health

# 스캔 목록
curl http://localhost:8080/api/scans

# 대시보드 통계
curl http://localhost:8080/api/dashboard/stats

# Vuddy 크리에이터
curl http://localhost:8080/api/vuddy/creators
```

### 로컬 데이터 확인

```bash
# 데이터 목록 조회
python scripts/test_local.py --list

# 특정 파일 확인
cat local-data/youtube/Archive\ Studio/2025-01-18-12-30-45.json | jq .
```

## ⚙️ 환경 변수

로컬 개발을 위한 환경 변수:

```bash
# 필수
export LOCAL_MODE=true
export LOCAL_DATA_DIR=./local-data

# YouTube 크롤러용
export YOUTUBE_API_KEY=your_youtube_api_key

# Vuddy 크롤러용 (선택사항)
export GOOGLE_SEARCH_API_KEY=your_google_api_key
export GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
```

## 🔄 프로덕션 모드로 전환

로컬 테스트가 완료되면:

```bash
# 환경 변수 제거
unset LOCAL_MODE

# 또는 false로 설정
export LOCAL_MODE=false
```

프로덕션 모드에서는 자동으로 S3와 DynamoDB를 사용합니다.

