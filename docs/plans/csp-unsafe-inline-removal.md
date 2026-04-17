# CSP `unsafe-inline` 제거 로드맵

## 현황

- **총 인라인 스타일: 283개** (10개 컴포넌트 파일)
- 정적(CSS 클래스로 이전 가능): **244개 (86%)**
- 동적(CSS 변수/조건부 클래스 필요): **39개 (14%)**

## 파일별 분석

| 파일 | 인라인 스타일 | 정적 | 동적 | 난이도 |
|------|-------------|------|------|--------|
| `AnalysisTab.jsx` | 89 | 78 | 11 | Medium |
| `CreatorDetail.jsx` | 62 | 55 | 7 | Medium |
| `AnalysisWidgets.jsx` | 38 | 32 | 6 | Easy |
| `ResultPanels.jsx` | 34 | 28 | 6 | Easy |
| `MonitorPanels.jsx` | 24 | 20 | 4 | Easy |
| `AuthPanel.jsx` | 10 | 8 | 2 | Easy |
| `AnalysisResult.jsx` | 8 | 6 | 2 | Easy |
| `ErrorBoundary.jsx` | 8 | 8 | 0 | Easy |
| `Dashboard.jsx` | 6 | 5 | 1 | Easy |
| `App.jsx` | 4 | 4 | 0 | Easy |

## 정적 스타일 카테고리 (244개)

- **Padding/Spacing**: ~80개 (`padding: '20px'`, `margin: '0 auto'`, `gap: '8px'`)
- **Colors (Non-Dynamic)**: ~60개 (`color: '#666'`, `backgroundColor: '#fff'`)
- **Border/Radius**: ~45개 (`borderRadius: '8px'`, `border: '1px solid #dee2e6'`)
- **Typography**: ~35개 (`fontSize: '13px'`, `fontWeight: 'bold'`)
- **Layout**: ~24개 (`display: 'flex'`, `textAlign: 'center'`)

## 동적 스타일 해결 전략 (39개)

### 1. CSS Variables (70% - 감성 바, 진행바, 폰트 크기)
```jsx
// Before
<div style={{ width: `${pct}%`, backgroundColor: colors[key] }} />

// After
<div className="sentiment-bar" style={{ '--width': `${pct}%`, '--color': colors[key] }} />
/* CSS: .sentiment-bar { width: var(--width); background: var(--color); } */
```

### 2. 조건부 클래스 (20% - 선택/비선택 상태)
```jsx
// Before
<button style={{ backgroundColor: isSelected ? '#007bff' : 'white' }}>

// After
<button className={`source-btn ${isSelected ? 'source-btn--selected' : ''}`}>
```

### 3. Data Attributes (10% - 감성 타입별 색상)
```jsx
<div data-sentiment={sentiment}>
/* CSS: [data-sentiment="positive"] { color: #10b981; } */
```

## 실행 계획

| 주차 | 작업 | 대상 파일 | 예상 시간 |
|------|------|----------|----------|
| 1주차 | 유틸리티 CSS 클래스 라이브러리 생성 | `utils.css` (신규) | 2h |
| 2주차 | Phase 1: 정적 스타일 이전 (Easy) | Dashboard, ErrorBoundary, AuthPanel, App | 2h |
| 3주차 | Phase 2: 정적 스타일 이전 (Medium) | MonitorPanels, ResultPanels, AnalysisResult | 3h |
| 4주차 | Phase 3: 동적 스타일 이전 | AnalysisTab, AnalysisWidgets, CreatorDetail | 5h |
| 5주차 | 테스트 + CSP 정책 변경 | nginx-frontend.conf | 2h |

**총 예상 시간: 14-16시간**

## CSP 정책 변경

```diff
# Before (현재)
- style-src 'self' 'unsafe-inline';

# After (목표)
+ style-src 'self';
```

## 우선순위 파일 (87% 커버리지)

1. `AnalysisTab.jsx` (89개)
2. `CreatorDetail.jsx` (62개)
3. `AnalysisWidgets.jsx` (38개)
4. `ResultPanels.jsx` (34개)
5. `MonitorPanels.jsx` (24개)
