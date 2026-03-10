# RSS 피드 목록 - SNS 모니터링용

이 문서는 SNS 모니터링에 유용한 RSS 피드 목록을 제공합니다.

## 📰 한국 주요 뉴스 사이트 RSS

### 종합 뉴스
- 네이버 뉴스 (IT/과학): `https://news.naver.com/main/rss/section.naver?sid=105`
- 네이버 뉴스 (연예): `https://news.naver.com/main/rss/section.naver?sid=106`
- 네이버 뉴스 (스포츠): `https://news.naver.com/main/rss/section.naver?sid=107`
- 다음 뉴스 (IT/과학): `https://news.daum.net/rss/it`
- 다음 뉴스 (연예): `https://news.daum.net/rss/entertain`
- 연합뉴스 (IT/과학): `https://www.yna.co.kr/rss/industry/10000001.xml`
- 연합뉴스 (연예): `https://www.yna.co.kr/rss/entertainment/10000002.xml`

### IT/테크 뉴스
- 네이버 IT/과학: `https://news.naver.com/main/rss/section.naver?sid=105`
- 블로터: `https://www.bloter.net/rss`
- 테크크런치 한국어: `https://kr.techcrunch.com/feed/`
- ZDNet Korea: `https://www.zdnet.co.kr/rss/all.xml`
- IT조선: `https://it.chosun.com/rss/all.xml`
- 디지털데일리: `https://www.ddaily.co.kr/rss/all.xml`

## 🎮 게임/엔터테인먼트
- 게임메카: `https://www.gamemeca.com/rss/all.xml`
- 인벤: `https://www.inven.co.kr/rss/rss.xml`
- 디스이즈게임: `https://www.thisisgame.com/rss/all.xml`

## 💼 비즈니스/경제
- 네이버 경제: `https://news.naver.com/main/rss/section.naver?sid=101`
- 매일경제: `https://www.mk.co.kr/rss/30000041/`
- 한국경제: `https://www.hankyung.com/rss/all.xml`
- 조선비즈: `https://biz.chosun.com/rss/all.xml`

## 🎨 문화/라이프스타일
- 네이버 문화: `https://news.naver.com/main/rss/section.naver?sid=103`
- 다음 문화: `https://news.daum.net/rss/culture`
- 오마이뉴스: `https://www.ohmynews.com/NWS_Web/RSS/rss.xml`

## 📱 모바일/스마트폰
- 네이버 모바일: `https://news.naver.com/main/rss/section.naver?sid=105&cid=731`
- 아이뉴스24: `https://www.inews24.com/rss/all.xml`

## 🛍️ 쇼핑/이커머스
- 네이버 쇼핑 뉴스: `https://shopping.naver.com/news/rss`
- 쿠팡 뉴스: `https://www.coupang.com/np/rss`

## 🎵 음악/엔터테인먼트
- 멜론 뉴스: `https://www.melon.com/rss/news.xml`
- 벅스 뉴스: `https://music.bugs.co.kr/rss/news.xml`

## 📺 방송/미디어
- 네이버 TV연예: `https://news.naver.com/main/rss/section.naver?sid=106`
- 스포츠동아: `https://sports.donga.com/rss/all.xml`
- 스포츠조선: `https://sports.chosun.com/rss/all.xml`

## 🌐 글로벌 뉴스 (한국어)
- BBC 한국어: `https://www.bbc.com/korean/rss.xml`
- CNN 한국어: `https://edition.cnn.com/korean/rss.xml`

## 📝 블로그 플랫폼
- 티스토리 (인기글): `https://www.tistory.com/rss`
- 브런치 (인기글): `https://brunch.co.kr/rss`
- 미디엄 (한국어): `https://medium.com/feed/tag/korea`

## 🎯 SNS/소셜미디어 관련
- 소셜미디어 트렌드: `https://www.socialmediatoday.com/rss.xml`
- 마케팅 뉴스: `https://www.marketingland.com/feed`

## 💡 사용 예시

### .env 파일에 추가
```bash
RSS_FEEDS=https://news.naver.com/main/rss/section.naver?sid=105,https://news.daum.net/rss/it,https://www.bloter.net/rss,https://www.zdnet.co.kr/rss/all.xml
```

### docker-compose.yml 환경 변수
```yaml
environment:
  - RSS_FEEDS=https://news.naver.com/main/rss/section.naver?sid=105,https://news.daum.net/rss/it
```

### terraform.tfvars
```hcl
rss_feeds = [
  "https://news.naver.com/main/rss/section.naver?sid=105",
  "https://news.daum.net/rss/it",
  "https://www.bloter.net/rss",
  "https://www.zdnet.co.kr/rss/all.xml"
]
```

## ⚠️ 주의사항

1. **RSS 피드 가용성**: 일부 RSS 피드는 사이트 정책에 따라 변경되거나 비활성화될 수 있습니다.
2. **요청 빈도**: 너무 많은 RSS 피드를 추가하면 크롤링 시간이 길어질 수 있습니다.
3. **키워드 필터링**: RSS 크롤러는 설정된 키워드로 자동 필터링합니다.
4. **최신성**: 최근 24시간 이내 게시물만 수집됩니다.

## 🔍 RSS 피드 확인 방법

RSS 피드가 유효한지 확인:
```bash
curl -I https://news.naver.com/main/rss/section.naver?sid=105
```

RSS 피드 내용 확인:
```bash
curl https://news.naver.com/main/rss/section.naver?sid=105 | head -50
```

