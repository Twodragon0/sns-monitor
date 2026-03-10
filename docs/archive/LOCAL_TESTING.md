# 로컬 테스트 가이드

이 문서는 S3 및 AWS 데이터에 업로드하기 전에 로컬에서 먼저 테스트하는 방법을 설명합니다.

## 🚀 빠른 시작

### 1. 로컬 API 서버 시작

```bash
# 환경 변수 설정
export LOCAL_MODE=true
export LOCAL_DATA_DIR=./local-data

# 로컬 API 서버 시작
python scripts/start_local_api.py
```

서버가 `http://localhost:8080`에서 실행됩니다.

### 2. 프론트엔드에서 로컬 API 사용

프론트엔드가 로컬 API를 사용하도록 설정되어 있습니다. `package.json`의 `proxy` 설정이 `http://localhost:8080`으로 되어 있어 자동으로 로컬 API 서버를 사용합니다.

### 3. 전체 로컬 개발 환경 시작

```bash
# 로컬 API 서버와 함께 시작
./scripts/start_local_dev.sh
```

또는 수동으로:

```bash
# 터미널 1: 로컬 API 서버
export LOCAL_MODE=true
python scripts/start_local_api.py

# 터미널 2: 프론트엔드
cd frontend
npm start
```

## 📋 개요

로컬 테스트 모드를 사용하면:
- AWS S3 대신 로컬 파일 시스템에 데이터 저장
- DynamoDB 대신 로컬 JSON 파일에 메타데이터 저장
- Docker나 AWS 서비스 없이도 크롤러 테스트 가능
- 빠른 개발 및 디버깅

## 🔧 설정 방법

### 1. 환경 변수 설정

로컬 테스트를 위해 다음 환경 변수를 설정하세요:

```bash
export LOCAL_MODE=true
export LOCAL_DATA_DIR=./local-data
export YOUTUBE_API_KEY=your_youtube_api_key_here
```

또는 `.env` 파일에 추가:

```bash
LOCAL_MODE=true
LOCAL_DATA_DIR=./local-data
YOUTUBE_API_KEY=your_youtube_api_key_here
```

### 2. 로컬 테스트 스크립트 실행

```bash
# YouTube 크롤러 테스트
python scripts/test_local.py --youtube

# Vuddy 크롤러 테스트
python scripts/test_local.py --vuddy

# 모든 크롤러 테스트
python scripts/test_local.py --all

# 로컬 데이터 목록 조회
python scripts/test_local.py --list
```

### 3. 직접 Python으로 실행

```python
import os
import sys

# 로컬 모드 활성화
os.environ['LOCAL_MODE'] = 'true'
os.environ['LOCAL_DATA_DIR'] = './local-data'
os.environ['YOUTUBE_API_KEY'] = 'your_api_key'

# 크롤러 임포트 및 실행
from lambda.youtube_crawler.lambda_function import lambda_handler

event = {
    'type': 'keyword',
    'keywords': ['Archive Studio', '아카이브스튜디오']
}

result = lambda_handler(event, None)
print(result)
```

## 📁 데이터 저장 위치

로컬 모드에서 데이터는 다음 위치에 저장됩니다:

```
local-data/
├── youtube/
│   ├── Archive Studio/
│   │   └── 2025-01-18-12-30-45.json
│   └── 아카이브스튜디오/
│       └── 2025-01-18-12-31-20.json
├── vuddy/
│   └── comprehensive_analysis/
│       └── 2025-01-18-12-35-10.json
└── metadata/
    ├── youtube/
    │   └── youtube-Archive Studio-20250118123045.json
    └── vuddy/
        └── vuddy-Archive Studio-20250118123510.json
```

## 🔍 로컬 데이터 확인

### 데이터 파일 확인

```bash
# YouTube 데이터 확인
cat local-data/youtube/Archive\ Studio/2025-01-18-12-30-45.json | jq .

# 메타데이터 확인
cat local-data/metadata/youtube/youtube-Archive\ Studio-20250118123045.json | jq .
```

### Python으로 데이터 로드

```python
import json
from lambda.common.local_storage import load_from_local_file

# 데이터 파일 로드
data = load_from_local_file('local-data/youtube/Archive Studio/2025-01-18-12-30-45.json')
print(json.dumps(data, indent=2, ensure_ascii=False))
```

## 🚀 사용 예시

### YouTube 크롤러 테스트

```bash
# 환경 변수 설정
export LOCAL_MODE=true
export YOUTUBE_API_KEY=your_api_key

# 크롤러 실행
python -c "
import os
os.environ['LOCAL_MODE'] = 'true'
os.environ['YOUTUBE_API_KEY'] = 'your_api_key'

from lambda.youtube_crawler.lambda_function import lambda_handler

result = lambda_handler({
    'type': 'keyword',
    'keywords': ['Archive Studio']
}, None)

print(result)
"
```

### Vuddy 크롤러 테스트

```bash
export LOCAL_MODE=true

python -c "
import os
os.environ['LOCAL_MODE'] = 'true'

from lambda.vuddy_crawler.lambda_function import lambda_handler

result = lambda_handler({}, None)
print(result)
"
```

## ⚠️ 주의사항

1. **로컬 모드에서는 LLM 분석이 실행되지 않습니다**
   - LLM 분석은 프로덕션 모드에서만 실행됩니다
   - 로컬 테스트에서는 데이터 수집만 확인할 수 있습니다

2. **로컬 데이터는 Git에 커밋하지 마세요**
   - `.gitignore`에 `local-data/` 추가 권장
   - 수집된 데이터는 개인 정보를 포함할 수 있습니다

3. **API 키 보안**
   - API 키를 코드에 하드코딩하지 마세요
   - 환경 변수나 `.env` 파일 사용 (`.env`는 Git에 커밋하지 마세요)

## 🔄 프로덕션 모드로 전환

로컬 테스트가 완료되면 프로덕션 모드로 전환:

```bash
# 환경 변수 제거 또는 false로 설정
unset LOCAL_MODE
# 또는
export LOCAL_MODE=false
```

프로덕션 모드에서는 자동으로 S3와 DynamoDB를 사용합니다.

## 📝 로컬 데이터 정리

```bash
# 모든 로컬 데이터 삭제
rm -rf local-data/

# 특정 플랫폼 데이터만 삭제
rm -rf local-data/youtube/
```

## 🐛 문제 해결

### ImportError: No module named 'local_storage'

`lambda/common/local_storage.py` 파일이 존재하는지 확인하세요.

### Permission denied

로컬 데이터 디렉토리에 쓰기 권한이 있는지 확인하세요:

```bash
chmod -R 755 local-data/
```

### 데이터가 저장되지 않음

`LOCAL_MODE=true`가 올바르게 설정되었는지 확인:

```python
import os
print(os.environ.get('LOCAL_MODE'))  # 'true'가 출력되어야 함
```

