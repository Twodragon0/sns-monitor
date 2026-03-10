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

### 크롤러 설정

모니터링할 갤러리 ID는 Helm values 또는 환경 변수로 설정합니다:

```yaml
# helm/sns-monitor/values.yaml
crawlers:
  dcinside:
    galleries:
      - your-gallery-id-1
      - your-gallery-id-2
```

### API를 통한 조회

```bash
# 특정 갤러리 데이터 조회
curl http://localhost:8080/api/dcinside/your-gallery-id

# 모든 갤러리 목록 조회
curl http://localhost:8080/api/dcinside/galleries
```

### 명령어 옵션 설명

DCInside 크롤러는 다음 설정을 지원합니다:

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `GALLERIES` | 모니터링할 갤러리 ID 리스트 | 환경 변수로 설정 |
| `TOP_N` | 분석할 인기 게시글 수 (최소 10개 보장) | `3` |
| `OUTPUT_DIR` | 결과 저장 디렉토리 | `./local-data/dcinside` |

**참고**: `TOP_N`이 3으로 설정되어 있어도, 게시글이 적은 갤러리에서는 자동으로 최소 10개까지 분석합니다.

## 결과 확인

### 결과 파일 위치

모니터링 결과는 다음 형식으로 저장됩니다:

```
local-data/dcinside/{gallery_id}/{timestamp}.json
```

예시:
```
local-data/dcinside/my-gallery/2025-11-21-10-30-45.json
```

### 결과 파일 구조

```json
{
  "gallery_id": "my-gallery",
  "gallery_name": "내 갤러리",
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

## 프론트엔드 통합

### API 엔드포인트

프론트엔드에서 다음 API를 호출하여 모니터링 결과를 가져올 수 있습니다:

```javascript
// DC인사이드 모니터링 결과 가져오기
const response = await fetch('/api/dcinside/my-gallery/latest');
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

### 정기 실행 (Kubernetes CronJob)

```yaml
# Helm values.yaml
crawlers:
  dcinside:
    enabled: true
    schedule: "0 */2 * * *"  # 매 2시간
    galleries:
      - your-gallery-id-1
      - your-gallery-id-2
```

## 주의사항

1. **Rate Limiting**: DC인사이드 크롤링 시 1초 딜레이가 적용됩니다
2. **게시글 수 제한**: 한 번에 최대 30개 게시글까지 수집
3. **댓글 페이지 제한**: 댓글은 최대 10페이지까지 수집
4. **감성 분석 정확도**: 키워드 기반 간단 분석이므로 100% 정확하지 않을 수 있습니다

## 문제 해결

### 게시글을 찾을 수 없음

```
갤러리를 찾을 수 없습니다.
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

- [DC인사이드 크롤러 소스](../crawlers/dcinside/)
- [프로젝트 README](../README.md)
