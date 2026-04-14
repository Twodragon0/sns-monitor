import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  XAxis, YAxis,
  Tooltip, ResponsiveContainer,
  LineChart, Line,
} from 'recharts';
import { API_BASE } from '../../config';
import { PLATFORMS, formatNumber } from '../../constants/platforms';

export function MiniStat({ icon, value, label }) {
  return (
    <div className="result__mini-stat">
      <span className="result__mini-icon">{icon}</span>
      <span className="result__mini-val">{value}</span>
      <span className="result__mini-label">{label}</span>
    </div>
  );
}

/** Mini sentiment bar (CSS classes, dark mode compatible) */
export function SentimentMiniBar({ sentiment }) {
  if (!sentiment) return null;
  const { positive = 0, neutral = 0, negative = 0 } = sentiment;
  const total = positive + neutral + negative;
  if (total === 0) return null;
  const pct = (v) => Math.round((v / total) * 100);
  return (
    <div className="sentiment-mini-bar">
      <div className="sentiment-mini-bar__track">
        {positive > 0 && <div className="sentiment-mini-bar__seg--pos" style={{ width: `${pct(positive)}%` }} />}
        {neutral > 0 && <div className="sentiment-mini-bar__seg--neu" style={{ width: `${pct(neutral)}%` }} />}
        {negative > 0 && <div className="sentiment-mini-bar__seg--neg" style={{ width: `${pct(negative)}%` }} />}
      </div>
      <div className="sentiment-mini-bar__labels">
        <span className="sentiment-mini-bar__pos">+{positive}</span>
        <span>{total}건</span>
        <span className="sentiment-mini-bar__neg">-{negative}</span>
      </div>
    </div>
  );
}

/** Custom tooltip that respects CSS variable colours */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div style={{
      background: 'var(--c-surface)',
      border: '1px solid var(--c-border)',
      borderRadius: 8,
      padding: '6px 10px',
      fontSize: 11,
      color: 'var(--c-text)',
      boxShadow: 'var(--shadow-md)',
    }}>
      <p style={{ margin: '0 0 4px', color: 'var(--c-text-secondary)', fontSize: 10 }}>{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} style={{ margin: '2px 0', color: entry.color, fontWeight: 600 }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
}

/** Trend mini chart for a single gallery */
export function GalleryTrendChart({ galleryId }) {
  const [trend, setTrend] = useState(null);
  useEffect(() => {
    axios.get(`${API_BASE}/api/analysis/trend?type=dcinside&id=${galleryId}`)
      .then(({ data }) => setTrend(data.trend || []))
      .catch(() => setTrend([]));
  }, [galleryId]);

  if (!trend || trend.length < 2) return (
    <p className="panel-card__hint" style={{ margin: '4px 0', fontStyle: 'italic' }}>
      트렌드 데이터 부족 — 크롤러가 2회 이상 수집한 후 표시됩니다
    </p>
  );

  const chartData = trend.map(t => ({
    time: t.timestamp?.slice(5, 16).replace('T', ' ') || '',
    pos: t.positive,
    neg: t.negative,
    total: t.total,
  }));

  return (
    <div style={{ marginTop: 6 }}>
      <ResponsiveContainer width="100%" height={80}>
        <LineChart data={chartData} margin={{ top: 2, right: 4, bottom: 0, left: -20 }}>
          <XAxis dataKey="time" tick={{ fontSize: 9, fill: 'var(--c-text-secondary)' }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 9, fill: 'var(--c-text-secondary)' }} />
          <Tooltip content={<ChartTooltip />} />
          <Line type="monotone" dataKey="pos" stroke="#10b981" strokeWidth={2} dot={false} name="긍정" animationDuration={800} />
          <Line type="monotone" dataKey="neg" stroke="#ef4444" strokeWidth={2} dot={false} name="부정" animationDuration={800} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function GalleryMonitorPanel() {
  const [dcSources, setDcSources] = useState([]);
  const [sentiments, setSentiments] = useState({});
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null); // gallery ID for trend chart

  useEffect(() => {
    axios.get(`${API_BASE}/api/analysis/sources`)
      .then(({ data }) => {
        const dc = (data.sources || []).filter(s => s.type === 'dcinside' && !s.id.startsWith('example'));
        setDcSources(dc);
        if (dc.length > 0) {
          axios.post(`${API_BASE}/api/analysis/local-summary`, {
            sources: dc.map(s => ({ type: 'dcinside', id: s.id })),
          }).then(({ data: result }) => {
            const map = {};
            (result.sources || []).forEach(s => { map[s.id] = s.sentiment?.sentiment; });
            setSentiments(map);
          }).catch(() => {});
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function parseLatestDate(latest) {
    if (!latest) return '—';
    const m = latest.match(/^(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})/);
    if (m) return `${m[2]}.${m[3]} ${m[4]}:${m[5]}`;
    return latest.replace('.json', '');
  }

  function goAnalysis(source) {
    try {
      sessionStorage.setItem('analysisPreselect', JSON.stringify([{ type: 'dcinside', id: source.id }]));
    } catch (_) { /* ignore */ }
    window.history.pushState({}, '', '/analysis');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }

  if (loading) return null;
  if (dcSources.length === 0) return (
    <div className="gallery-monitor" style={{ marginTop: 20 }}>
      <h4 className="dash__section-title" style={{ marginBottom: 10 }}>DCInside 갤러리 모니터링</h4>
      <div style={{
        padding: '20px 18px',
        background: 'var(--c-bg)',
        border: '1.5px dashed var(--c-border)',
        borderRadius: 10,
        textAlign: 'center',
        color: 'var(--c-text-secondary)',
        fontSize: '0.85rem',
        lineHeight: 1.6,
      }}>
        <span style={{ fontSize: 28, display: 'block', marginBottom: 8 }} aria-hidden="true">📋</span>
        <strong style={{ color: 'var(--c-text)', display: 'block', marginBottom: 4 }}>수집된 갤러리 없음</strong>
        DCInside 크롤러를 실행하거나 상단 URL 검색에서 갤러리 URL을 입력하면 여기에 모니터링 카드가 표시됩니다.
      </div>
    </div>
  );

  // Detect negative sentiment alerts (neg > 5% of total)
  const alerts = Object.entries(sentiments)
    .map(([id, s]) => {
      if (!s) return null;
      const total = (s.positive || 0) + (s.neutral || 0) + (s.negative || 0);
      const negPct = total > 0 ? Math.round((s.negative || 0) / total * 100) : 0;
      return negPct >= 5 ? { id, name: dcSources.find(d => d.id === id)?.name || id, negPct, negative: s.negative } : null;
    })
    .filter(Boolean);

  return (
    <div className="gallery-monitor">
      <h4 className="dash__section-title" style={{ marginBottom: 12 }}>DCInside 갤러리 모니터링</h4>

      {alerts.length > 0 && (
        <div className="gallery-monitor__alert">
          <strong className="gallery-monitor__alert-title">부정 감성 경고</strong>
          {alerts.map(a => (
            <span key={a.id} className="gallery-monitor__alert-item">
              {a.name}:{' '}
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                background: 'rgba(239,68,68,0.12)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 12,
                padding: '1px 7px',
                fontSize: 11,
                fontWeight: 700,
                color: 'var(--c-danger)',
                marginLeft: 4,
              }}>
                {a.negPct}% · {a.negative}건
              </span>
            </span>
          ))}
        </div>
      )}
      <div className="gallery-monitor__grid">
        {dcSources.map(src => (
          <div key={src.id} className="panel-card gallery-monitor__card">
            <div className="gallery-monitor__card-head">
              <h5 className="panel-card__title gallery-monitor__card-title">{src.name || src.id}</h5>
              <button
                type="button"
                className="gallery-monitor__trend-btn"
                onClick={() => setExpanded(expanded === src.id ? null : src.id)}
              >
                {expanded === src.id ? '닫기' : '트렌드'}
              </button>
            </div>
            <div className="panel-card__body gallery-monitor__meta">
              <span>수집 {src.files || 0}회</span>
              <span>{parseLatestDate(src.latest)}</span>
            </div>
            <SentimentMiniBar sentiment={sentiments[src.id]} />
            {expanded === src.id && <GalleryTrendChart galleryId={src.id} />}
            <button
              type="button"
              className="gallery-monitor__analyze-btn"
              onClick={() => goAnalysis(src)}
            >
              분석
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

/* --- Overview Panel (stats는 Dashboard에서 계산된 단일 소스 사용) --- */
export function OverviewPanel({ stats, channels }) {
  const goAnalysis = (e) => {
    e.preventDefault();
    window.history.pushState({}, '', '/analysis');
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  return (
    <div className="panel-overview">
      {stats.total === 0 && (
        <p className="panel-overview__empty-hint" role="status">
          수집 데이터가 없습니다. 상단 URL 검색을 사용하거나 크롤러를 실행해 주세요.
        </p>
      )}
      <div className="panel-overview__grid">
        <div className="panel-card">
          <h3 className="panel-card__title">YouTube</h3>
          <div className="panel-card__body">
            <p><strong>{channels.length}</strong> 키워드 모니터링</p>
            <p><strong>{formatNumber(stats.ytComments)}</strong> 댓글 수집됨</p>
          </div>
        </div>
        <div className="panel-card">
          <h3 className="panel-card__title">DCInside</h3>
          <div className="panel-card__body">
            <p><strong>{stats.galleryCount}</strong> 갤러리 모니터링</p>
            <p><strong>{formatNumber(stats.dcPosts)}</strong> 게시글 수집됨</p>
            <p>긍정 <strong style={{ color: 'var(--c-success)' }}>{stats.dcPositive}</strong> · 부정 <strong style={{ color: 'var(--c-danger)' }}>{stats.dcNegative}</strong></p>
          </div>
        </div>
        <div className="panel-card">
          <h3 className="panel-card__title">X (Twitter)</h3>
          <div className="panel-card__body">
            <p>키워드 검색 링크 기반 모니터링</p>
            <p className="panel-card__hint">트위터 API 유료 → 직접 검색 방식</p>
          </div>
        </div>
        <div className="panel-card">
          <h3 className="panel-card__title">Instagram · Facebook · Threads</h3>
          <div className="panel-card__body">
            <p>URL 분석 기반 모니터링</p>
            <p className="panel-card__hint">상단 URL 입력에서 분석 가능</p>
          </div>
        </div>
      </div>
      <div className="panel-overview__analysis">
        <div className="panel-card panel-card--analysis">
          <h3 className="panel-card__title">수집 데이터 분석 · 요약</h3>
          <div className="panel-card__body">
            <p>크롤러로 수집한 YouTube·DCInside 데이터를 AI로 분석·요약합니다.</p>
            <p className="panel-card__hint">엔티티 그래프 구축 후 AI 채팅으로 인사이트를 질의할 수 있습니다.</p>
            <button type="button" className="panel-card__btn" onClick={goAnalysis}>
              분석 페이지로 이동
            </button>
          </div>
        </div>
      </div>
      <GalleryMonitorPanel />
    </div>
  );
}

/* --- YouTube Panel --- */
export function YouTubePanel({ channels, creators }) {
  return (
    <div className="panel-yt">
      {channels.length > 0 && (
        <div className="panel-yt__channels">
          <h4 className="dash__section-title">키워드별 채널 데이터</h4>
          <div className="panel-yt__grid">
            {channels.map((ch, i) => (
              <div key={i} className="panel-card">
                <h5 className="panel-card__title">{ch.channel_title || ch.channel}</h5>
                <div className="panel-card__body">
                  <p>영상 <strong>{ch.videos_analyzed || 0}</strong>개 분석</p>
                  <p>댓글 <strong>{formatNumber(ch.total_comments || 0)}</strong>개</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {creators.length > 0 && (
        <div className="panel-yt__creators">
          <h4 className="dash__section-title" style={{ marginTop: 24 }}>크리에이터 댓글</h4>
          {creators.map((c, ci) => (
            <div key={ci} className="panel-card" style={{ marginBottom: 12 }}>
              <h5 className="panel-card__title">{c.name}</h5>
              <div className="panel-card__body">
                <p>댓글 <strong>{c.comments?.length || 0}</strong>개 · 좋아요 <strong>{c.total_likes || 0}</strong></p>
                {c.sentiment_distribution && (
                  <p style={{ fontSize: 12, color: 'var(--c-text-secondary)' }}>
                    긍정 {Math.round((c.sentiment_distribution.positive || 0) * 100)}% ·
                    중립 {Math.round((c.sentiment_distribution.neutral || 0) * 100)}% ·
                    부정 {Math.round((c.sentiment_distribution.negative || 0) * 100)}%
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {channels.length === 0 && creators.length === 0 && (
        <EmptyHint
          title="YouTube 수집 데이터 없음"
          description="상단 URL 검색에서 영상·채널 URL을 입력하면 즉시 분석할 수 있습니다. 주기적 수집은 YouTube 크롤러를 실행하세요."
        />
      )}
    </div>
  );
}

/* --- DCInside Panel --- */
export function DCInsidePanel({ galleries }) {
  const [expanded, setExpanded] = useState({});

  if (galleries.length === 0) {
    return (
      <EmptyHint
        title="DCInside 갤러리 데이터 없음"
        description="상단 URL 검색에서 갤러리·게시글 URL을 입력하면 즉시 분석할 수 있습니다. 주기적 수집은 DCInside 크롤러를 실행하세요."
      />
    );
  }

  return (
    <div className="panel-dc">
      <div className="panel-dc__summary">
        <StatBox icon="📝" label="총 게시글" value={formatNumber(galleries.reduce((s, g) => s + (g.total_posts || 0), 0))} />
        <StatBox icon="💬" label="총 댓글" value={formatNumber(galleries.reduce((s, g) => s + (g.total_comments || 0), 0))} />
        <StatBox icon="😊" label="긍정" value={galleries.reduce((s, g) => s + (g.positive_count || 0), 0)} />
        <StatBox icon="😞" label="부정" value={galleries.reduce((s, g) => s + (g.negative_count || 0), 0)} />
      </div>

      {galleries.map(g => {
        const isOpen = expanded[g.gallery_id];
        const posts = g.posts || [];
        const visible = isOpen ? posts : posts.slice(0, 3);
        return (
          <div key={g.gallery_id} className="panel-card panel-dc__gallery">
            <div className="panel-dc__gallery-head">
              <h5 className="panel-card__title">{g.gallery_name}</h5>
              <span className="panel-dc__gallery-meta">
                게시글 {g.total_posts || 0} · 댓글 {g.total_comments || 0}
              </span>
            </div>
            {visible.map((p, pi) => (
              <div key={pi} className="panel-dc__post">
                <a href={p.url} target="_blank" rel="noopener noreferrer" className="panel-dc__post-title">
                  {p.title}
                </a>
                <span className="panel-dc__post-meta">
                  {p.author} · {p.date} · 👁 {p.view_count} · 👍 {p.recommend_count} · 💬 {p.comment_count || 0}
                </span>
              </div>
            ))}
            {posts.length > 3 && (
              <button className="panel-dc__toggle" onClick={() => setExpanded(p => ({ ...p, [g.gallery_id]: !p[g.gallery_id] }))}>
                {isOpen ? '접기 ▲' : `+${posts.length - 3}개 더 보기 ▼`}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* --- Twitter Panel --- */
export function TwitterPanel() {
  const [keyword, setKeyword] = useState('');
  const QUICK_KEYWORDS = [
    { label: '유튜브 클립',   query: '유튜브 클립' },
    { label: 'SNS 이슈',      query: 'SNS 이슈 -filter:retweets' },
    { label: '트위터 트렌드', query: '실시간 트렌드' },
    { label: '커뮤니티 반응', query: '커뮤니티 반응' },
    { label: '인터넷 밈',     query: '인터넷 밈' },
    { label: '핫클립',        query: '핫클립 -filter:retweets' },
    { label: '뉴스 이슈',     query: '뉴스 이슈 lang:ko' },
  ];

  const openTwitterSearch = (q) => {
    window.open(`https://twitter.com/search?q=${encodeURIComponent(q)}&src=typed_query&f=live`, '_blank');
  };

  return (
    <div className="panel-tw">
      <div className="panel-card">
        <h5 className="panel-card__title">🐦 키워드 실시간 검색</h5>
        <div className="panel-tw__search">
          <input
            className="panel-tw__input"
            type="text"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && keyword.trim()) openTwitterSearch(keyword.trim()); }}
            placeholder="검색할 키워드…"
          />
          <button className="panel-tw__btn" onClick={() => keyword.trim() && openTwitterSearch(keyword.trim())}>
            X에서 검색
          </button>
        </div>
        <div className="panel-tw__quick">
          {QUICK_KEYWORDS.map(k => (
            <button key={k.query} className="panel-tw__tag" onClick={() => openTwitterSearch(k.query)}>
              {k.label}
            </button>
          ))}
        </div>
        <p className="panel-card__hint" style={{ marginTop: 12 }}>
          Twitter/X API는 유료 구독이 필요하여, 키워드 링크를 통해 직접 검색하는 방식으로 제공됩니다.
        </p>
      </div>
    </div>
  );
}

/* --- Social Panel (Instagram, Facebook, Threads) --- */
export function SocialPanel() {
  const socials = [
    { key: 'instagram', ...PLATFORMS.instagram, example: 'https://www.instagram.com/username/', desc: '프로필 및 게시물 분석' },
    { key: 'facebook',  ...PLATFORMS.facebook,  example: 'https://www.facebook.com/page/', desc: '페이지 및 게시물 분석' },
    { key: 'threads',   ...PLATFORMS.threads,   example: 'https://www.threads.net/@username/', desc: '프로필 및 스레드 분석' },
  ];

  return (
    <div className="panel-social">
      <div className="panel-social__grid">
        {socials.map(s => (
          <div key={s.key} className="panel-card panel-social__card">
            <div className="panel-social__icon" style={{ background: s.color }}>{s.icon}</div>
            <h5 className="panel-card__title">{s.label}</h5>
            <p className="panel-card__body">{s.desc}</p>
            <code className="panel-social__example">{s.example}</code>
            <p className="panel-card__hint">상단 URL 입력란에 붙여넣어 분석하세요</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* --- Scan History helpers --- */
function buildPageNums(page, totalPages) {
  const near = new Set(
    [1, totalPages, page - 1, page, page + 1].filter(n => n >= 1 && n <= totalPages)
  );
  const sorted = [...near].sort((a, b) => a - b);
  const result = [];
  sorted.forEach((n, i) => {
    if (i > 0 && n - sorted[i - 1] > 1) result.push('…');
    result.push(n);
  });
  return result;
}

function ScanPagination({ page, totalPages, loading, onPage }) {
  const pageNums = buildPageNums(page, totalPages);
  return (
    <div className="scan-history__pagination">
      <button
        className="scan-history__page-btn"
        onClick={() => onPage(p => Math.max(1, p - 1))}
        disabled={page <= 1 || loading}
      >
        이전
      </button>
      {pageNums.map((n, i) =>
        n === '…'
          ? <span key={`gap-${i}`} className="scan-history__page-ellipsis">…</span>
          : <button
              key={n}
              className={`scan-history__page-btn${page === n ? ' scan-history__page-btn--active' : ''}`}
              onClick={() => onPage(n)}
              disabled={loading}
            >
              {n}
            </button>
      )}
      <button
        className="scan-history__page-btn"
        onClick={() => onPage(p => Math.min(totalPages, p + 1))}
        disabled={page >= totalPages || loading}
      >
        다음
      </button>
    </div>
  );
}

/* --- Scan History Panel --- */
const SCAN_PLATFORMS = [
  { value: '', label: '전체 플랫폼' },
  { value: 'youtube',    label: 'YouTube' },
  { value: 'dcinside',   label: 'DCInside' },
  { value: 'reddit',     label: 'Reddit' },
  { value: 'telegram',   label: 'Telegram' },
  { value: 'kakao',      label: 'Kakao' },
  { value: 'naver_cafe', label: '네이버 카페' },
  { value: 'twitter',    label: 'X (Twitter)' },
  { value: 'threads',    label: 'Threads' },
];

export function ScanHistoryPanel() {
  const [scans, setScans] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [platform, setPlatform] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const LIMIT = 10;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ page, limit: LIMIT });
    if (platform) params.set('platform', platform);
    fetch(`${API_BASE}/api/scans?${params}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        if (cancelled) return;
        setScans(data.scans || []);
        setTotal(data.total || 0);
      })
      .catch(err => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [page, platform]);

  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  function handlePlatformChange(e) {
    setPlatform(e.target.value);
    setPage(1);
  }

  function formatDate(val) {
    if (!val) return '—';
    try {
      return new Date(val).toLocaleString('ko-KR', {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit',
      });
    } catch {
      return val;
    }
  }

  return (
    <div className="scan-history">
      <div className="scan-history__toolbar">
        <div className="scan-history__meta">
          {loading
            ? <span className="scan-history__count">로딩 중…</span>
            : <span className="scan-history__count">총 <strong>{total.toLocaleString()}</strong>건</span>
          }
          {totalPages > 1 && (
            <span className="scan-history__page-info">{page} / {totalPages} 페이지</span>
          )}
        </div>
        <select
          className="scan-history__filter"
          value={platform}
          onChange={handlePlatformChange}
          aria-label="플랫폼 필터"
        >
          {SCAN_PLATFORMS.map(p => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="scan-history__error" role="alert">
          데이터를 불러오지 못했습니다: {error}
        </div>
      )}

      {!loading && !error && scans.length === 0 && (
        <div className="scan-history__empty">
          <span aria-hidden="true">📭</span>
          <p>스캔 기록이 없습니다.</p>
        </div>
      )}

      {scans.length > 0 && (
        <ul className="scan-history__list">
          {scans.map((scan, i) => {
            const pInfo = PLATFORMS[scan.platform] || { label: scan.platform, color: '#6b7280', icon: '🔗' };
            return (
              <li key={scan.id || i} className="scan-history__item">
                <span
                  className="scan-history__platform-badge"
                  style={{ background: pInfo.color }}
                  title={pInfo.label}
                >
                  {pInfo.icon} {pInfo.label}
                </span>
                <div className="scan-history__item-body">
                  <span className="scan-history__item-title">
                    {scan.title || scan.url || '(제목 없음)'}
                  </span>
                  {scan.url && scan.url !== scan.title && (
                    <a
                      href={scan.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="scan-history__item-url"
                    >
                      {scan.url}
                    </a>
                  )}
                </div>
                <span className="scan-history__item-time">{formatDate(scan.analyzed_at || scan.created_at)}</span>
              </li>
            );
          })}
        </ul>
      )}

      {totalPages > 1 && (
        <ScanPagination
          page={page}
          totalPages={totalPages}
          loading={loading}
          onPage={setPage}
        />
      )}
    </div>
  );
}

export function EmptyHint({ title, description, text }) {
  const heading = title || '데이터 없음';
  const body = description || text || '상단 URL 검색으로 즉시 분석할 수 있습니다.';
  return (
    <div className="dash__empty">
      <span className="dash__empty-icon" aria-hidden="true">📭</span>
      <h4 className="dash__empty-title">{heading}</h4>
      <p className="dash__empty-desc">{body}</p>
    </div>
  );
}

/* StatBox is used internally by DCInsidePanel */
function StatBox({ icon, label, value }) {
  return (
    <div className="dash__stat-box">
      <span className="dash__stat-icon">{icon}</span>
      <div>
        <div className="dash__stat-value">{value}</div>
        <div className="dash__stat-label">{label}</div>
      </div>
    </div>
  );
}
