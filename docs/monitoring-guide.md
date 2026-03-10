# SNS 모니터링 가이드

## 개요

이 시스템은 YouTube에서 인기 영상 3개를 자동으로 선택하고, 모든 댓글을 수집한 후 각 댓글에 대한 긍정/부정 감성 분석을 수행합니다.

## 주요 기능

1. **인기 영상 자동 선택**: 조회수 기준 상위 3개 영상 자동 선택
2. **최신 정보 우선**: 최근 30일 이내 게시된 영상 중심으로 검색
3. **전체 댓글 수집**: 영상당 최대 100개 댓글 수집
4. **개별 댓글 감성 분석**: 각 댓글별로 긍정/부정/중립 분류
5. **통계 제공**: 전체 감성 분포, 국가별 통계 등

## 사전 준비

### 1. 환경 변수 설정

`.env` 파일에 다음 환경 변수를 설정하세요:

```bash
# YouTube Data API v3 키
YOUTUBE_API_KEY=your_youtube_api_key_here

# Bedrock (선택사항 - 감성 분석 향상)
BEDROCK_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
```

### 2. YouTube API 키 발급

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성
3. "API 및 서비스" > "라이브러리" 이동
4. "YouTube Data API v3" 검색 및 활성화
5. "사용자 인증 정보" > "사용자 인증 정보 만들기" > "API 키" 선택
6. 생성된 API 키를 `.env` 파일에 추가

## 사용 방법

### 기본 사용법

```bash
# 기본 설정으로 실행 (AkaiV Studio, BARABARA 키워드, 최근 30일, 상위 3개 영상)
python3 scripts/monitor_top_posts.py
```

### 고급 옵션

```bash
# 사용자 정의 키워드로 실행
python3 scripts/monitor_top_posts.py --keywords "버튜버" "VTuber" "아카이브스튜디오"

# 검색 기간 설정 (최근 7일)
python3 scripts/monitor_top_posts.py --days 7

# 분석할 영상 수 조정 (상위 5개)
python3 scripts/monitor_top_posts.py --top-n 5

# 영상당 댓글 수 조정 (200개)
python3 scripts/monitor_top_posts.py --max-comments 200

# 모든 옵션 조합
python3 scripts/monitor_top_posts.py \
  --keywords "버튜버" "VTuber" \
  --days 7 \
  --top-n 5 \
  --max-comments 200 \
  --output-dir ./results
```

### 명령어 옵션 설명

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--keywords` | 검색할 키워드 리스트 (공백으로 구분) | `AkaiV Studio BARABARA` |
| `--days` | 검색 기간 (일) | `30` |
| `--top-n` | 분석할 인기 영상 수 (조회수 기준) | `3` |
| `--max-comments` | 영상당 최대 댓글 수 | `100` |
| `--output-dir` | 결과 저장 디렉토리 | `./local-data/monitoring` |

## 결과 확인

### 결과 파일 위치

모니터링 결과는 다음 디렉토리에 JSON 형식으로 저장됩니다:

```
local-data/monitoring/monitoring-YYYY-MM-DD-HH-MM-SS.json
```

### 결과 파일 구조

```json
{
  "monitoring_date": "2025-11-21T10:00:00",
  "keywords": ["AkaiV Studio"],
  "results": [
    {
      "keyword": "AkaiV Studio",
      "search_date": "2025-11-21T10:00:00",
      "search_period_days": 30,
      "videos": [
        {
          "video": {
            "video_id": "abc123",
            "title": "영상 제목",
            "view_count": 10000,
            "like_count": 500,
            "comment_count": 100
          },
          "comments": [
            {
              "text": "댓글 내용",
              "author": "작성자",
              "like_count": 10,
              "sentiment": "positive",
              "sentiment_confidence": 0.85
            }
          ],
          "sentiment_statistics": {
            "total": 100,
            "positive": 60,
            "negative": 20,
            "neutral": 20,
            "positive_ratio": 0.6,
            "negative_ratio": 0.2,
            "neutral_ratio": 0.2
          }
        }
      ]
    }
  ]
}
```

### 콘솔 출력 예시

```
================================================================================
📊 SNS 모니터링 시작
================================================================================

🔍 키워드: 'AkaiV Studio' 검색 중...
   기간: 최근 30일
   상위 3개 인기 영상 분석

   ✅ 3개의 인기 영상 발견

   📹 영상 1/3: [영상 제목]
      조회수: 15,234 | 좋아요: 823 | 댓글: 145
      수집된 댓글: 100개
      🤖 감성 분석 중...
      ✅ 감성 분석 완료:
         긍정: 65개 (65.0%)
         부정: 15개 (15.0%)
         중립: 20개 (20.0%)

================================================================================
📊 모니터링 결과 요약
================================================================================

🔑 키워드: AkaiV Studio
   분석된 영상: 3개
   총 댓글 수: 300개
   긍정 댓글: 180개 (60.0%)
   부정 댓글: 60개 (20.0%)
   중립 댓글: 60개 (20.0%)
```

## 감성 분석 기준

### 긍정 (Positive)
- 긍정적, 호의적인 표현
- 칭찬, 격려, 지지
- 예: "훌륭해요!", "최고입니다!", "감사합니다"

### 부정 (Negative)
- 부정적, 비판적인 표현
- 불만, 반대, 비난
- 예: "실망이에요", "별로네요", "최악"

### 중립 (Neutral)
- 중립적인 표현
- 사실 전달, 질문
- 예: "언제 올라오나요?", "재미있네요"

## 주의사항

### API 할당량

YouTube Data API v3는 하루 10,000 할당량을 제공합니다.

**할당량 소비 예시:**
- 영상 검색: 100 할당량
- 영상 정보 조회: 1 할당량 (배치)
- 댓글 조회: 1 할당량

**최적화 팁:**
- 채널 ID를 지정하면 할당량이 크게 절약됩니다 (100 → 2)
- Redis 캐시를 사용하면 중복 요청을 방지할 수 있습니다
- `--max-comments` 옵션으로 댓글 수를 조절하세요

### Bedrock 감성 분석

Bedrock을 사용하지 않는 경우, 로컬 키워드 기반 간단 분석이 사용됩니다. 더 정확한 분석을 원하시면 AWS Bedrock을 설정하세요.

## 문제 해결

### YouTube API 키 오류

```
❌ 오류: YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.
```

**해결 방법:**
- `.env` 파일에 `YOUTUBE_API_KEY=your_key` 추가
- 또는 환경 변수로 설정: `export YOUTUBE_API_KEY=your_key`

### 할당량 초과 오류

```
⚠️  YouTube API quota exceeded. Reason: quotaExceeded
```

**해결 방법:**
- 다음 날까지 대기 (할당량은 매일 자정 PST 기준으로 리셋)
- 여러 API 키를 번갈아 사용
- `--max-comments` 값을 줄여서 할당량 소비 감소

### 댓글을 찾을 수 없음

```
⚠️  댓글이 없거나 수집할 수 없습니다.
```

**원인:**
- 영상에 댓글이 비활성화됨
- 영상이 비공개로 전환됨
- 댓글이 아직 없음

## 자동화

### Cron을 이용한 정기 실행

매일 오전 9시에 자동 실행:

```bash
# crontab 편집
crontab -e

# 다음 라인 추가
0 9 * * * cd /path/to/sns-monitoring-system && /usr/bin/python3 scripts/monitor_top_posts.py --keywords "버튜버" --days 1
```

### Docker를 이용한 실행

```bash
# Docker 이미지 빌드 (향후 제공 예정)
docker build -t sns-monitor .

# 컨테이너 실행
docker run -e YOUTUBE_API_KEY=your_key sns-monitor \
  --keywords "버튜버" --days 7 --top-n 3
```

## 추가 리소스

- [YouTube Data API v3 문서](https://developers.google.com/youtube/v3)
- [AWS Bedrock Claude 문서](https://docs.aws.amazon.com/bedrock/)
- [프로젝트 README](../README.md)

## 지원

문제가 발생하거나 질문이 있으시면 다음 채널을 이용하세요:

- GitHub Issues
- 이메일: support@example.com
