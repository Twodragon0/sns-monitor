# DC인사이드 모니터링 가이드

## 개요

DC인사이드 갤러리에서 인기 게시글 3개와 모든 댓글을 자동으로 수집하고, 긍정/부정 감성 분석을 수행합니다.

## 주요 기능

1. **인기 게시글 자동 선택**: 조회수 + 추천수 기반으로 상위 N개 게시글 자동 선택 (최소 10개 보장)
2. **전체 댓글 수집**: 각 게시글의 모든 댓글 수집
3. **감성 분석**: 게시글과 댓글에 대한 긍정/부정/중립 분류
4. **요약 정보**: 각 게시글에 대한 자동 요약 생성
5. **통계 제공**: 전체 감성 분포, 대표 댓글 등
6. **최소 게시글 보장**: 게시글이 적은 갤러리도 최소 10개까지 분석

## 사용 방법

### 기본 사용법

```bash
# 기본 설정으로 실행 (akaiv, ivnit 갤러리, 최소 10개 게시글)
# --top-n이 3이어도 최소 10개 게시글이 분석됩니다
python3 scripts/monitor_dcinside.py
```

### 고급 옵션

```bash
# 특정 갤러리만 모니터링
python3 scripts/monitor_dcinside.py --galleries akaiv

# 여러 갤러리 모니터링
python3 scripts/monitor_dcinside.py --galleries akaiv ivnit soopvirtualstreamer

# 분석할 게시글 수 조정 (상위 5개)
python3 scripts/monitor_dcinside.py --top-n 5

# 결과 저장 디렉토리 지정
python3 scripts/monitor_dcinside.py --output-dir ./results/dcinside
```

### 명령어 옵션 설명

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--galleries` | 모니터링할 갤러리 ID 리스트 | `akaiv ivnit` |
| `--top-n` | 분석할 인기 게시글 수 (최소 10개 보장) | `3` |
| `--output-dir` | 결과 저장 디렉토리 | `./local-data/dcinside-monitoring` |

**참고**: `--top-n` 옵션이 3으로 설정되어 있어도, 게시글이 적은 갤러리에서는 자동으로 최소 10개까지 분석합니다.

### 사용 가능한 갤러리 목록

- `akaiv`: 아카이브 스튜디오 갤러리
- `ivnit`: 이브닛 미니 갤러리
- `soopvirtualstreamer`: 숲 종합 갤러리
- `spv`: 숲 버추얼 갤러리
- `soopstreaming`: 숲 스트리밍 갤러리

## 결과 확인

### 결과 파일 위치

모니터링 결과는 다음 형식으로 저장됩니다:

```
local-data/dcinside-monitoring/{gallery_id}-monitoring-YYYY-MM-DD-HH-MM-SS.json
```

예시:
```
local-data/dcinside-monitoring/akaiv-monitoring-2025-11-21-10-30-45.json
```

### 결과 파일 구조

```json
{
  "gallery_id": "akaiv",
  "gallery_name": "아카이브 스튜디오 갤러리",
  "monitoring_date": "2025-11-21T10:30:45",
  "top_n": 3,
  "total_posts_analyzed": 3,
  "total_comments": 45,
  "overall_sentiment_statistics": {
    "positive": 30,
    "negative": 10,
    "neutral": 5,
    "positive_ratio": 0.667,
    "negative_ratio": 0.222,
    "neutral_ratio": 0.111
  },
  "posts": [
    {
      "post": {
        "post_id": "12345",
        "title": "게시글 제목",
        "author": "작성자",
        "view_count": 500,
        "recommend_count": 10
      },
      "content": "게시글 내용...",
      "comments": [
        {
          "author": "댓글 작성자",
          "text": "댓글 내용",
          "date": "2025-11-21 10:30:00",
          "sentiment": "positive"
        }
      ],
      "comment_count": 15,
      "post_sentiment": "positive",
      "sentiment_statistics": {
        "positive": 10,
        "negative": 3,
        "neutral": 2,
        "positive_ratio": 0.667,
        "negative_ratio": 0.200,
        "neutral_ratio": 0.133
      },
      "summary": "게시글 요약..."
    }
  ]
}
```

### 콘솔 출력 예시

```
================================================================================
📊 DC인사이드 갤러리 모니터링: akaiv
================================================================================
갤러리: 아카이브 스튜디오 갤러리
상위 3개 인기 게시글 분석

🔍 게시글 목록 가져오는 중...
ℹ️  게시글이 적어 최소 10개 게시글을 분석합니다.
✅ 상위 10개 게시글 선택 완료

📄 게시글 1/3: 사미드디어 기어나온 사미
   작성자: 결결 | 조회: 78 | 추천: 0
   💬 댓글 수집 중...
   ✅ 댓글 1개 수집 완료
   🤖 감성 분석:
      긍정: 1개 (50.0%)
      부정: 0개 (0.0%)
      중립: 1개 (50.0%)

================================================================================
📊 모니터링 결과 요약
================================================================================

🏢 갤러리: 아카이브 스튜디오 갤러리 (akaiv)
📅 분석 시간: 2025-11-21T10:30:45
📄 분석된 게시글: 3개
💬 총 댓글: 45개

📈 전체 감성 분석:
   긍정: 30개 (66.7%)
   부정: 10개 (22.2%)
   중립: 5개 (11.1%)

📝 게시글 요약:
   1. 사미드디어 기어나온 사미
      조회: 78 | 추천: 0 | 댓글: 1개
      감성: 긍정 50.0% | 부정 0.0% | 중립 50.0%
```

## 감성 분석 기준

### 긍정 (Positive)
- 긍정적 키워드: 좋아, 굿, 최고, 감사, 사랑, 축하, 대박, 멋지, 예쁘, 귀엽
- 응원/지지 표현: 화이팅, 응원, 존경, 멋있, 훌륭, 완벽
- 인터넷 용어: ㄱㅇㄷ, ㅊㅊ, 개좋, 레전드, 갓, 천재

### 부정 (Negative)
- 부정적 키워드: 싫어, 나쁘, 최악, 비난, 혐오, 짜증, 실망, 별로
- 비하 표현: 쓰레기, 망했, 노잼, 재미없, 허접, 구리
- 비속어: 병신, 개같, 개별로, 개망, 답없, 노답

### 중립 (Neutral)
- 긍정/부정 키워드가 없는 경우
- 사실 전달
- 질문

## 요약 정보

각 게시글에 대해 다음과 같은 요약 정보가 자동 생성됩니다:

1. **기본 정보**: 제목, 작성자, 조회수, 추천수
2. **게시글 감성**: 게시글 본문의 전체 감성
3. **댓글 통계**: 총 댓글 수, 긍정/부정/중립 비율
4. **대표 댓글**: 긍정/부정 대표 댓글 각 1개씩

## UI/UX 표시 예시

웹 UI에서는 다음과 같이 표시할 수 있습니다:

### 게시글 카드

```
┌─────────────────────────────────────────────┐
│ 📄 사미드디어 기어나온 사미                 │
│ 작성자: 결결 | 조회: 78 | 추천: 0           │
│                                             │
│ 💬 댓글 1개                                  │
│                                             │
│ 📊 감성 분석                                 │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━        │
│ 😊 긍정 50% ████████████░░░░░░░░░░░░        │
│ 😐 중립 50% ████████████░░░░░░░░░░░░        │
│ 😞 부정  0% ░░░░░░░░░░░░░░░░░░░░░░░░        │
│                                             │
│ 📝 요약                                      │
│ 제목: 사미드디어 기어나온 사미              │
│ 게시글 감성: positive                       │
│ 댓글: 긍정 1개, 부정 0개, 중립 1개          │
│                                             │
│ 💬 대표 댓글                                 │
│ [긍정] ㅋㅋㅋㅋㅋㅋ ㅜ                      │
└─────────────────────────────────────────────┘
```

### 전체 통계 대시보드

```
┌─────────────────────────────────────────────┐
│ 🏢 아카이브 스튜디오 갤러리                 │
│                                             │
│ 📊 전체 통계                                 │
│ • 분석된 게시글: 3개                        │
│ • 총 댓글: 45개                             │
│ • 분석 시간: 2025-11-21 10:30:45            │
│                                             │
│ 📈 감성 분포                                 │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━        │
│ 😊 긍정 66.7% ████████████████░░░░░░        │
│ 😐 중립 11.1% ██░░░░░░░░░░░░░░░░░░░░        │
│ 😞 부정 22.2% ████░░░░░░░░░░░░░░░░░░        │
└─────────────────────────────────────────────┘
```

## 프론트엔드 통합

### API 엔드포인트

프론트엔드에서 다음 API를 호출하여 모니터링 결과를 가져올 수 있습니다:

```javascript
// DC인사이드 모니터링 결과 가져오기
const response = await fetch('/api/dcinside/monitoring/akaiv/latest');
const data = await response.json();

// 결과 표시
console.log('전체 감성:', data.overall_sentiment_statistics);
console.log('게시글 목록:', data.posts);
```

### React 컴포넌트 예시

```jsx
import React, { useState, useEffect } from 'react';

function DCInsideMonitoring({ galleryId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/dcinside/monitoring/${galleryId}/latest`)
      .then(res => res.json())
      .then(data => {
        setData(data);
        setLoading(false);
      });
  }, [galleryId]);

  if (loading) return <div>로딩 중...</div>;

  return (
    <div className="dcinside-monitoring">
      <h2>{data.gallery_name}</h2>

      <div className="overall-stats">
        <h3>전체 통계</h3>
        <p>분석된 게시글: {data.total_posts_analyzed}개</p>
        <p>총 댓글: {data.total_comments}개</p>

        <div className="sentiment-bar">
          <div className="positive" style={{width: `${data.overall_sentiment_statistics.positive_ratio * 100}%`}}>
            긍정 {(data.overall_sentiment_statistics.positive_ratio * 100).toFixed(1)}%
          </div>
          <div className="negative" style={{width: `${data.overall_sentiment_statistics.negative_ratio * 100}%`}}>
            부정 {(data.overall_sentiment_statistics.negative_ratio * 100).toFixed(1)}%
          </div>
          <div className="neutral" style={{width: `${data.overall_sentiment_statistics.neutral_ratio * 100}%`}}>
            중립 {(data.overall_sentiment_statistics.neutral_ratio * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="posts-list">
        {data.posts.map((post, idx) => (
          <div key={idx} className="post-card">
            <h4>{post.post.title}</h4>
            <p>작성자: {post.post.author} | 조회: {post.post.view_count} | 추천: {post.post.recommend_count}</p>

            <div className="post-sentiment">
              <span className={`badge ${post.post_sentiment}`}>{post.post_sentiment}</span>
              <span>댓글 {post.comment_count}개</span>
            </div>

            <div className="summary">
              <h5>요약</h5>
              <pre>{post.summary}</pre>
            </div>

            <div className="comments-preview">
              <h5>댓글 미리보기</h5>
              {post.comments.slice(0, 3).map((comment, i) => (
                <div key={i} className={`comment ${comment.sentiment}`}>
                  <span className="author">{comment.author}</span>
                  <span className="text">{comment.text}</span>
                  <span className={`sentiment-badge ${comment.sentiment}`}>
                    {comment.sentiment === 'positive' ? '😊' :
                     comment.sentiment === 'negative' ? '😞' : '😐'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

## 자동화

### 정기 실행 (Cron)

매 시간마다 자동으로 모니터링:

```bash
# crontab 편집
crontab -e

# 매 시간 정각에 실행
0 * * * * cd /path/to/sns-monitoring-system && /usr/bin/python3 scripts/monitor_dcinside.py --galleries akaiv ivnit
```

## 주의사항

1. **Rate Limiting**: DC인사이드 크롤링 시 1초 딜레이가 적용됩니다
2. **게시글 수 제한**: 한 번에 최대 30개 게시글까지 수집
3. **댓글 페이지 제한**: 댓글은 최대 10페이지까지 수집
4. **감성 분석 정확도**: 키워드 기반 간단 분석이므로 100% 정확하지 않을 수 있습니다

## 문제 해결

### 게시글을 찾을 수 없음

```
⚠️  게시글을 찾을 수 없습니다.
```

**원인:**
- 갤러리 ID가 잘못되었거나
- 해당 갤러리에 게시글이 없거나
- DC인사이드 사이트 구조 변경

**해결 방법:**
- 갤러리 ID 확인
- 웹 브라우저로 직접 갤러리 접속 확인

### 댓글 수집 실패

```
Error getting comments via AJAX
```

**원인:**
- DC인사이드 API 변경
- 네트워크 오류

**해결 방법:**
- 잠시 후 재시도
- DC인사이드 사이트 정상 작동 확인

## 추가 리소스

- [DC인사이드 크롤러 소스](../lambda/dcinside-crawler/lambda_function.py)
- [모니터링 스크립트 소스](../scripts/monitor_dcinside.py)
- [프로젝트 README](../README.md)
