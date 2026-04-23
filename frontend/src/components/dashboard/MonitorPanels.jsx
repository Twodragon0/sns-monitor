import React, { useState, useEffect } from 'react';
import { API_BASE } from '../../config';
import { PLATFORMS, formatNumber } from '../../constants/platforms';

// Split sub-components (kept as re-exports so existing imports keep working)
export { SentimentMiniBar } from './SentimentMiniBar';
export { GalleryMonitorPanel, GalleryTrendChart } from './GalleryMonitorPanel';
export { SocialPanel } from './SocialPanel';

import { GalleryMonitorPanel } from './GalleryMonitorPanel';

export const MiniStat = React.memo(function MiniStat({ icon, value, label }) {
  return (
    <div className="result__mini-stat">
      <span className="result__mini-icon">{icon}</span>
      <span className="result__mini-val">{value}</span>
      <span className="result__mini-label">{label}</span>
    </div>
  );
});

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

export const EmptyHint = React.memo(function EmptyHint({ title, description, text }) {
  const heading = title || '데이터 없음';
  const body = description || text || '상단 URL 검색으로 즉시 분석할 수 있습니다.';
  return (
    <div className="dash__empty">
      <span className="dash__empty-icon" aria-hidden="true">📭</span>
      <h4 className="dash__empty-title">{heading}</h4>
      <p className="dash__empty-desc">{body}</p>
    </div>
  );
});

/* StatBox is used internally by DCInsidePanel */
const StatBox = React.memo(function StatBox({ icon, label, value }) {
  return (
    <div className="dash__stat-box">
      <span className="dash__stat-icon">{icon}</span>
      <div>
        <div className="dash__stat-value">{value}</div>
        <div className="dash__stat-label">{label}</div>
      </div>
    </div>
  );
});
