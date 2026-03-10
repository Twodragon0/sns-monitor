# Vuddy 크리에이터 종합 분석 가이드

이 문서는 vuddy.io 크리에이터 이름을 기준으로 YouTube, 블로그, 구글 검색을 통합하여 댓글 및 좋아요를 분석하는 방법을 설명합니다.

## 📋 개요

Vuddy 크롤러는 각 크리에이터에 대해 다음을 수행합니다:
1. **YouTube 검색**: 크리에이터 이름으로 영상 검색 및 댓글/좋아요 수집
2. **YouTube 채널 분석**: 크리에이터의 공식 채널 분석 (있는 경우)
3. **블로그 검색**: RSS 피드를 통한 블로그 포스트 검색
4. **구글 검색**: Google Custom Search API 또는 DuckDuckGo를 통한 웹 검색
5. **종합 분석**: 모든 플랫폼 데이터를 통합하여 분석

## 🔧 설정 방법

### 1. 기본 설정

`.env` 파일에 다음을 추가:

```bash
# Vuddy 설정
VUDDY_URL=https://vuddy.io

# Google 검색 설정 (선택사항)
GOOGLE_SEARCH_API_KEY=your_api_key
GOOGLE_SEARCH_ENGINE_ID=your_engine_id
```

### 2. Google Custom Search API 설정 (선택사항)

Google Custom Search API를 사용하면 더 정확한 검색 결과를 얻을 수 있습니다:

1. **API 키 발급**:
   - https://console.cloud.google.com/ 접속
   - Custom Search API 활성화
   - API 키 생성

2. **검색 엔진 생성**:
   - https://programmablesearchengine.google.com/ 접속
   - 새 검색 엔진 생성
   - 검색 엔진 ID 복사

3. **환경 변수 설정**:
   ```bash
   GOOGLE_SEARCH_API_KEY=your_api_key_here
   GOOGLE_SEARCH_ENGINE_ID=your_engine_id_here
   ```

**참고**: Google Custom Search API는 무료 할당량이 일일 100회입니다. API 키가 없으면 DuckDuckGo 웹 크롤링을 사용합니다.

## 📊 데이터 수집 프로세스

### 1. 크리에이터 목록 수집
```
vuddy.io 웹사이트 크롤링
  ↓
크리에이터 이름 및 YouTube 채널 추출
```

### 2. YouTube 검색
```
크리에이터 이름으로 YouTube 검색
  ↓
관련 영상 수집
  ↓
각 영상의 댓글 및 좋아요 수집
```

### 3. YouTube 채널 분석
```
크리에이터의 공식 채널 분석 (있는 경우)
  ↓
채널의 최근 영상 수집
  ↓
댓글 및 버튜버 분석
```

### 4. 블로그 검색
```
RSS 피드에서 크리에이터 이름 검색
  ↓
관련 블로그 포스트 수집
```

### 5. 구글 검색
```
Google Custom Search API 또는 DuckDuckGo 사용
  ↓
웹 검색 결과 수집
```

### 6. 종합 분석
```
모든 플랫폼 데이터 통합
  ↓
통계 계산 (댓글, 좋아요, 블로그 포스트 등)
  ↓
S3 저장 및 LLM 분석 트리거
```

## 🚀 사용 방법

### 수동 실행

```bash
# Vuddy 크롤러 직접 실행
docker-compose exec vuddy-crawler python -c "
import requests
import json

payload = {}
response = requests.post('http://localhost:5000/invoke', json=payload)
result = response.json()
print(json.dumps(result, indent=2, ensure_ascii=False))
"
```

### 자동 실행

스케줄러가 설정된 주기마다 자동으로 실행합니다 (기본: 30분마다).

## 📁 데이터 구조

### 종합 분석 결과

```json
{
  "platform": "vuddy",
  "crawled_at": "2025-11-18T...",
  "comprehensive_analysis": [
    {
      "creator_name": "크리에이터 이름",
      "youtube_channel": "@channel_handle",
      "youtube_search": {
        "status": "success",
        "data": [...]
      },
      "youtube_channel_analysis": {
        "status": "success",
        "data": [...]
      },
      "blog_search": {
        "status": "success",
        "data": [...]
      },
      "google_search": {
        "status": "success",
        "data": [...]
      },
      "total_comments": 100,
      "total_likes": 500,
      "total_blog_posts": 10,
      "total_google_results": 5
    }
  ],
  "statistics": {
    "total_creators_analyzed": 20,
    "total_comments": 2000,
    "total_likes": 10000,
    "total_blog_posts": 50,
    "total_google_results": 100
  }
}
```

## 🎯 대시보드에서 확인

웹 대시보드 (`http://localhost:3000`)에서 다음을 확인할 수 있습니다:

1. **Vuddy 크리에이터 종합 분석 섹션**
   - 각 크리에이터별 통계
   - 댓글 수, 좋아요 수, 블로그 포스트 수, 구글 결과 수
   - 플랫폼별 검색 상태

2. **실시간 통계**
   - 전체 수집 항목 수
   - 오늘 수집 항목 수
   - 분석 완료 항목 수
   - 총 댓글 수

## ⚠️ 주의사항

### API 할당량
- **YouTube API**: 일일 10,000 유닛 (무료)
- **Google Custom Search API**: 일일 100회 (무료)
- 크리에이터가 많을 경우 배치 처리 필요

### 검색 정확도
- 크리에이터 이름이 일반적인 단어인 경우 부정확한 결과가 나올 수 있음
- 따옴표로 감싸서 정확한 매칭 시도

### 웹 크롤링
- DuckDuckGo API는 무료이지만 제한이 있을 수 있음
- robots.txt 및 이용약관 준수 필요

## 🔍 문제 해결

### Google 검색이 작동하지 않는 경우
1. Google Custom Search API 키 확인
2. 검색 엔진 ID 확인
3. API 할당량 확인
4. DuckDuckGo 웹 크롤링으로 대체 확인

### 블로그 검색 결과가 없는 경우
1. RSS 피드 설정 확인
2. 크리에이터 이름이 RSS 피드에 포함되는지 확인
3. RSS 크롤러 로그 확인

### YouTube 검색 결과가 부정확한 경우
1. 크리에이터 이름이 정확한지 확인
2. 검색 쿼리에 따옴표 추가 확인
3. 필터링 로직 확인

## 📈 성능 최적화

1. **배치 처리**: 크리에이터를 여러 배치로 나누어 처리
2. **캐싱**: 이전 검색 결과 캐싱
3. **병렬 처리**: 여러 크리에이터 동시 분석
4. **API 할당량 관리**: 할당량 초과 방지

## 🎯 다음 단계

- [ ] 검색 결과 정확도 개선
- [ ] 실시간 알림 기능 추가
- [ ] 크리에이터별 트렌드 분석
- [ ] 비교 분석 기능 추가

