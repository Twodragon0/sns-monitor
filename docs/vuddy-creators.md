# Vuddy 크리에이터 모니터링 가이드

이 문서는 vuddy.io의 모든 크리에이터에 대한 댓글과 반응을 수집하는 방법을 설명합니다.

## 📋 개요

Vuddy 크롤러는 다음을 수행합니다:
1. vuddy.io 웹사이트에서 크리에이터 목록을 자동으로 수집
2. 각 크리에이터의 YouTube 채널을 찾아서 모니터링
3. 인수한 회사들의 채널도 함께 모니터링

## 🎯 모니터링 대상

### 인수한 회사 채널
- **바라바라 (BARABARA)**: `@BARABARA_KR`
- **이브닛 (IVNIT)**: `@IVNITOFFICIAL`
- **아카이브 스튜디오**: 채널 핸들 확인 필요

### Vuddy 크리에이터
- vuddy.io 웹사이트에서 동적으로 수집
- 각 크리에이터의 YouTube 채널 자동 감지

## 🔧 설정 방법

### 1. 환경 변수 설정

`.env` 파일에 다음을 추가:

```bash
# YouTube 채널 (인수한 회사 및 주요 크리에이터)
YOUTUBE_CHANNELS=@IVNITOFFICIAL,@BARABARA_KR

# Vuddy 설정
VUDDY_URL=https://vuddy.io
```

### 2. Docker Compose 설정

`docker-compose.yml`에 `vuddy-crawler` 서비스가 자동으로 포함되어 있습니다.

### 3. 수동 실행

```bash
# Vuddy 크롤러 직접 실행
docker-compose exec vuddy-crawler python -c "
import requests
import json

payload = {}
response = requests.post('http://localhost:5000/invoke', json=payload)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
"
```

## 📊 데이터 수집 프로세스

### 1. 크리에이터 목록 수집
```
vuddy.io 웹사이트 크롤링
  ↓
크리에이터 카드/링크 추출
  ↓
각 크리에이터 상세 페이지 방문
  ↓
YouTube 채널 링크 추출
```

### 2. YouTube 채널 분석
```
크리에이터별 YouTube 채널 목록
  ↓
YouTube 크롤러에 전달
  ↓
각 채널의 영상 및 댓글 수집
  ↓
버튜버 댓글 분석
```

### 3. 데이터 저장
```
S3에 저장: raw-data/vuddy/creators/{timestamp}.json
  ↓
LLM 분석기 트리거
  ↓
DynamoDB에 분석 결과 저장
```

## 📁 데이터 구조

### 크리에이터 정보
```json
{
  "name": "크리에이터 이름",
  "vuddy_url": "https://vuddy.io/creator/...",
  "youtube_channel": "@channel_handle"
}
```

### 수집된 데이터
```json
{
  "platform": "vuddy",
  "crawled_at": "2025-11-18T...",
  "total_creators": 50,
  "total_channels": 45,
  "creators": [...],
  "acquired_companies": [...],
  "youtube_results": [...]
}
```

## 🔍 크리에이터 찾기

Vuddy 크롤러는 다음 방법으로 크리에이터를 찾습니다:

1. **웹 크롤링**: vuddy.io 메인 페이지에서 크리에이터 링크 추출
2. **상세 페이지 분석**: 각 크리에이터 페이지에서 YouTube 채널 링크 추출
3. **API 엔드포인트** (있는 경우): `/api/creators` 같은 엔드포인트 사용

## ⚠️ 주의사항

### 웹 크롤링 제한
- vuddy.io의 HTML 구조가 변경되면 크롤러 수정 필요
- robots.txt 및 이용약관 준수 필요
- 요청 빈도 제한 (너무 자주 요청하지 않기)

### YouTube API 할당량
- 일일 10,000 유닛 제한
- 크리에이터가 많을 경우 배치 처리 필요
- 채널당 최대 영상 수 제한 (기본 10개)

### 아카이브 스튜디오 채널
- 아카이브 스튜디오의 YouTube 채널 핸들을 찾아서 `YOUTUBE_CHANNELS`에 추가 필요

## 🚀 자동화

### 스케줄러 설정

`docker-compose.yml`의 `scheduler` 서비스가 자동으로 Vuddy 크롤러를 실행합니다:

```yaml
CRAWL_SCHEDULE=*/30 * * * *  # 30분마다
```

### 수동 트리거

```bash
# 스케줄러를 통해 모든 크롤러 실행
docker-compose exec scheduler sh /app/run_crawlers.sh

# Vuddy 크롤러만 실행
curl -X POST http://localhost:5000/invoke \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 📈 모니터링 결과 확인

### S3에서 데이터 확인

```bash
docker-compose exec -T vuddy-crawler python -c "
import boto3
import json

s3_client = boto3.client(
    's3',
    endpoint_url='http://localstack:4566',
    aws_access_key_id='test',
    aws_secret_access_key='test',
    region_name='us-east-1'
)

response = s3_client.list_objects_v2(
    Bucket='sns-monitor-data',
    Prefix='raw-data/vuddy/'
)

for obj in response.get('Contents', []):
    print(f\"{obj['Key']} ({obj['Size']/1024:.1f} KB)\")
"
```

### DynamoDB에서 분석 결과 확인

```bash
aws dynamodb scan \
  --table-name sns-monitor-results \
  --filter-expression "begins_with(source, :source)" \
  --expression-attribute-values '{":source":{"S":"vuddy"}}' \
  --endpoint-url http://localhost:8000 \
  --region ap-northeast-2
```

## 🔄 업데이트

### 새로운 크리에이터 추가
- vuddy.io에 새 크리에이터가 추가되면 자동으로 감지
- 다음 크롤링 주기에서 자동으로 수집 시작

### 채널 정보 업데이트
- 크리에이터의 YouTube 채널이 변경되면 자동으로 업데이트
- S3에 저장된 이전 데이터는 유지

## 📝 문제 해결

### 크리에이터를 찾지 못하는 경우
1. vuddy.io HTML 구조 확인
2. 크롤러 로직 수정 필요할 수 있음
3. API 엔드포인트가 있는지 확인

### YouTube 채널을 찾지 못하는 경우
1. 크리에이터 페이지에 YouTube 링크가 있는지 확인
2. 링크 형식이 예상과 다른지 확인
3. 수동으로 채널 핸들 추가 가능

### 크롤링 속도가 느린 경우
1. 크리에이터 수가 많으면 시간이 오래 걸릴 수 있음
2. 배치 처리로 나누어 실행 고려
3. 병렬 처리 구현 고려

