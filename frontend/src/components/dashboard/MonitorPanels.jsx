import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  XAxis, YAxis,
  Tooltip, ResponsiveContainer,
  LineChart, Line,
} from 'recharts';
import { API_BASE } from '../../config';

const PLATFORMS = {
  youtube:    { label: 'YouTube',       color: '#FF0000', icon: '▶' },
  dcinside:   { label: 'DCInside',      color: '#0253fe', icon: '📋' },
  naver_cafe: { label: '네이버 카페',   color: '#03c75a', icon: '☕' },
  reddit:     { label: 'Reddit',       color: '#FF4500', icon: '🔗' },
  telegram:   { label: 'Telegram',     color: '#0088cc', icon: '✈' },
  kakao:      { label: 'Kakao',        color: '#FEE500', icon: '💬' },
  twitter:    { label: 'X (Twitter)',  color: '#000000', icon: '𝕏' },
  instagram:  { label: 'Instagram',    color: '#E1306C', icon: '📸' },
  facebook:   { label: 'Facebook',     color: '#1877F2', icon: '👥' },
  threads:    { label: 'Threads',      color: '#000000', icon: '🧵' },
};


function formatNumber(num) {
  if (num == null) return null;
  const n = typeof num === 'string' ? parseInt(num.replace(/[,\s]/g, ''), 10) : Number(num);
  if (isNaN(n)) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

export function MiniStat({ icon, value, label }) {
  return (
    <div className="result__mini-stat">
      <span className="result__mini-icon">{icon}</span>
      <span className="result__mini-val">{value}</span>
      <span className="result__mini-label">{label}</span>
    </div>
  );
}

/** Mini sentiment bar (inline, no chart library needed) */
export function SentimentMiniBar({ sentiment }) {
  if (!sentiment) return null;
  const { positive = 0, neutral = 0, negative = 0 } = sentiment;
  const total = positive + neutral + negative;
  if (total === 0) return null;
  const pct = (v) => Math.round((v / total) * 100);
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', background: '#e5e7eb' }}>
        {positive > 0 && <div style={{ width: `${pct(positive)}%`, background: '#10b981' }} />}
        {neutral > 0 && <div style={{ width: `${pct(neutral)}%`, background: '#9ca3af' }} />}
        {negative > 0 && <div style={{ width: `${pct(negative)}%`, background: '#ef4444' }} />}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: '#6b7280', marginTop: 2 }}>
        <span style={{ color: '#10b981' }}>+{positive}</span>
        <span>{total}건</span>
        <span style={{ color: '#ef4444' }}>-{negative}</span>
      </div>
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

  if (!trend || trend.length < 2) return <p style={{ fontSize: '0.7rem', color: '#9ca3af', margin: '4px 0' }}>트렌드 데이터 부족 (2회 이상 수집 필요)</p>;

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
          <XAxis dataKey="time" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 9 }} />
          <Tooltip contentStyle={{ fontSize: 11 }} />
          <Line type="monotone" dataKey="pos" stroke="#10b981" strokeWidth={2} dot={false} name="긍정" />
          <Line type="monotone" dataKey="neg" stroke="#ef4444" strokeWidth={2} dot={false} name="부정" />
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
  if (dcSources.length === 0) return null;

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
    <div style={{ marginTop: 20 }}>
      <h4 className="dash__section-title" style={{ marginBottom: 12 }}>DCInside 갤러리 모니터링</h4>

      {/* Negative alert banner */}
      {alerts.length > 0 && (
        <div style={{
          padding: '10px 14px', marginBottom: 12,
          background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8,
          fontSize: '0.8rem',
        }}>
          <strong style={{ color: '#dc2626' }}>부정 감성 경고</strong>
          {alerts.map(a => (
            <span key={a.id} style={{ marginLeft: 10, color: '#7f1d1d' }}>
              {a.name}: <strong>{a.negPct}%</strong> ({a.negative}건)
            </span>
          ))}
        </div>
      )}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: 12,
      }}>
        {dcSources.map(src => (
          <div key={src.id} className="panel-card" style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h5 className="panel-card__title" style={{ margin: 0, fontSize: '0.85rem' }}>{src.name || src.id}</h5>
              <button
                type="button"
                onClick={() => setExpanded(expanded === src.id ? null : src.id)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.7rem', color: '#6366f1' }}
              >
                {expanded === src.id ? '닫기' : '트렌드'}
              </button>
            </div>
            <div className="panel-card__body" style={{ fontSize: '0.75rem', color: '#6b7280' }}>
              <span>수집 {src.files || 0}회</span>
              <span style={{ marginLeft: 8 }}>{parseLatestDate(src.latest)}</span>
            </div>
            <SentimentMiniBar sentiment={sentiments[src.id]} />
            {expanded === src.id && <GalleryTrendChart galleryId={src.id} />}
            <button
              type="button"
              onClick={() => goAnalysis(src)}
              style={{
                padding: '5px 12px', marginTop: 4,
                background: 'var(--c-primary)', color: '#fff',
                border: 'none', borderRadius: 6,
                fontSize: '0.75rem', fontWeight: 700,
                cursor: 'pointer', alignSelf: 'flex-start',
              }}
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
    { label: 'CreatorBrand',  query: 'CreatorBrand' },
    { label: 'ExampleCorp',   query: 'ExampleCorp' },
    { label: 'ExampleCreator', query: 'ExampleCreator' },
    { label: 'Creator1',      query: 'Creator1' },
    { label: 'Creator2',      query: 'Creator2' },
    { label: 'Creator3',      query: 'Creator3' },
    { label: 'Creator4',      query: 'Creator4' },
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
