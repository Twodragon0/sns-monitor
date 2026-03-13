import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import './Dashboard.css';

const API_BASE = process.env.REACT_APP_API_URL || '';

const PLATFORMS = {
  youtube:   { label: 'YouTube',      color: '#FF0000', icon: '▶' },
  dcinside:  { label: 'DCInside',     color: '#0253fe', icon: '📋' },
  reddit:    { label: 'Reddit',       color: '#FF4500', icon: '🔗' },
  telegram:  { label: 'Telegram',     color: '#0088cc', icon: '✈' },
  kakao:     { label: 'Kakao',        color: '#FEE500', icon: '💬' },
  twitter:   { label: 'X (Twitter)',  color: '#000000', icon: '𝕏' },
  instagram: { label: 'Instagram',    color: '#E1306C', icon: '📸' },
  facebook:  { label: 'Facebook',     color: '#1877F2', icon: '👥' },
  threads:   { label: 'Threads',      color: '#000000', icon: '🧵' },
};

const SENTIMENT_COLORS = {
  positive: '#10b981',
  neutral:  '#9ca3af',
  negative: '#ef4444',
};

function formatNumber(num) {
  if (num == null) return null;
  const n = typeof num === 'string' ? parseInt(num.replace(/[,\s]/g, ''), 10) : Number(num);
  if (isNaN(n)) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function detectPlatform(url) {
  if (!url) return null;
  const l = url.toLowerCase();
  if (l.includes('youtube.com') || l.includes('youtu.be')) return 'youtube';
  if (l.includes('dcinside.com')) return 'dcinside';
  if (l.includes('reddit.com')) return 'reddit';
  if (l.includes('t.me/')) return 'telegram';
  if (l.includes('kakao.com')) return 'kakao';
  if (l.includes('x.com') || l.includes('twitter.com')) return 'twitter';
  if (l.includes('instagram.com')) return 'instagram';
  if (l.includes('facebook.com') || l.includes('fb.com')) return 'facebook';
  if (l.includes('threads.net')) return 'threads';
  return null;
}

/* ============================================================
   Main Dashboard Component
   ============================================================ */
function Dashboard() {
  // --- URL Analyzer state ---
  const [url, setUrl] = useState('');
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisSummary, setAnalysisSummary] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem('sns-monitor-history') || '[]'); }
    catch { return []; }
  });

  // --- Monitoring state ---
  const [activeTab, setActiveTab] = useState('overview');
  const [monitorData, setMonitorData] = useState({
    channels: [],
    galleries: [],
    creators: [],
    loading: true,
  });

  useEffect(() => {
    localStorage.setItem('sns-monitor-history', JSON.stringify(history));
  }, [history]);

  const detectedPlatform = detectPlatform(url);

  // --- Load monitoring data ---
  const loadMonitorData = useCallback(async () => {
    try {
      const [channelsRes, galleriesRes, creatorsRes] = await Promise.allSettled([
        fetch('/api/channels').then(r => r.ok ? r.json() : { channels: [] }),
        fetch('/api/dcinside/galleries', { signal: AbortSignal.timeout(10000) })
          .then(r => r.ok ? r.json() : { galleries: [] }),
        fetch('/api/vuddy/creators').then(r => r.ok ? r.json() : { creators: [] }),
      ]);

      setMonitorData({
        channels: channelsRes.status === 'fulfilled' ? (channelsRes.value.channels || []) : [],
        galleries: galleriesRes.status === 'fulfilled' ? (galleriesRes.value.galleries || []) : [],
        creators: creatorsRes.status === 'fulfilled' ? (creatorsRes.value.creators || []) : [],
        loading: false,
      });
    } catch {
      setMonitorData(prev => ({ ...prev, loading: false }));
    }
  }, []);

  useEffect(() => {
    loadMonitorData();
    const iv = setInterval(loadMonitorData, 60000);
    return () => clearInterval(iv);
  }, [loadMonitorData]);

  // --- Computed stats ---
  const stats = useMemo(() => {
    const ytComments = monitorData.channels.reduce((s, c) => s + (c.total_comments || 0), 0);
    const dcPosts = monitorData.galleries.reduce((s, g) => s + (g.total_posts || 0), 0);
    const dcComments = monitorData.galleries.reduce((s, g) => s + (g.total_comments || 0), 0);
    const creatorComments = monitorData.creators.reduce((s, c) => s + (c.comments?.length || 0), 0);
    return { ytComments, dcPosts, dcComments, creatorComments, total: ytComments + dcComments + creatorComments };
  }, [monitorData]);

  // --- URL analysis handlers ---
  const handleAnalyze = useCallback(async (e) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    setAnalysisLoading(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    setAnalysisSummary(null);
    try {
      const { data } = await axios.post(`${API_BASE}/api/analyze/url`, { url: trimmed });
      setAnalysisResult(data);
      setHistory(prev => [{
        url: trimmed,
        platform: data.platform,
        title: data.title || data.gallery_id || data.subreddit || data.username || trimmed,
        analyzed_at: data.analyzed_at,
      }, ...prev.filter(h => h.url !== trimmed).slice(0, 19)]);
    } catch (err) {
      setAnalysisError(err.response?.data?.error || err.message || '분석 실패');
    } finally {
      setAnalysisLoading(false);
    }
  }, [url]);

  const handleSummarize = useCallback(async () => {
    if (!analysisResult) return;
    setSummaryLoading(true);
    try {
      const { data } = await axios.post(`${API_BASE}/api/analyze/summarize`, { result: analysisResult });
      setAnalysisSummary(data);
    } catch (err) {
      setAnalysisError(err.response?.data?.error || err.message || '요약 실패');
    } finally {
      setSummaryLoading(false);
    }
  }, [analysisResult]);

  // --- Tabs ---
  const TABS = [
    { id: 'overview',  label: '전체 개요' },
    { id: 'youtube',   label: `YouTube (${formatNumber(stats.ytComments)})` },
    { id: 'dcinside',  label: `DCInside (${formatNumber(stats.dcPosts)})` },
    { id: 'twitter',   label: 'X (Twitter)' },
    { id: 'social',    label: 'Instagram · Facebook · Threads' },
  ];

  return (
    <div className="dash">
      {/* ===== URL ANALYZER HERO ===== */}
      <section className="dash__hero" aria-labelledby="hero-title">
        <h2 id="hero-title" className="dash__hero-title">URL 검색 · 분석</h2>
        <p className="dash__hero-desc">
          지원 플랫폼의 URL을 입력하면 콘텐츠, 댓글, 감성을 즉시 분석합니다.
        </p>

        <form className="dash__search" onSubmit={handleAnalyze}>
          <div className="dash__search-wrap">
            <input
              className="dash__search-input"
              type="url"
              value={url}
              onChange={e => { setUrl(e.target.value); setAnalysisError(null); }}
              placeholder="https://www.youtube.com/watch?v=... 또는 갤러리/서브레딧/텔레그램 등 URL"
              disabled={analysisLoading}
              aria-label="분석할 URL"
            />
            {detectedPlatform && (
              <span
                className="dash__search-badge"
                style={{ background: PLATFORMS[detectedPlatform]?.color }}
              >
                {PLATFORMS[detectedPlatform]?.icon} {PLATFORMS[detectedPlatform]?.label}
              </span>
            )}
          </div>
          <button
            className="dash__search-btn"
            type="submit"
            disabled={analysisLoading || !url.trim()}
          >
            {analysisLoading ? '분석 중…' : '분석'}
          </button>
        </form>

        <div className="dash__platforms">
          {Object.entries(PLATFORMS).map(([k, v]) => (
            <span key={k} className="dash__platform-tag" style={{ borderColor: v.color, color: v.color }}>
              {v.icon} {v.label}
            </span>
          ))}
        </div>

        {analysisError && <div className="dash__error" role="alert">{analysisError}</div>}

        {analysisResult && (
          <AnalysisResult
            result={analysisResult}
            summary={analysisSummary}
            summaryLoading={summaryLoading}
            onSummarize={handleSummarize}
          />
        )}

        {!analysisResult && history.length > 0 && (
          <div className="dash__history">
            <div className="dash__history-header">
              <h4>최근 분석</h4>
              <button className="dash__history-clear" onClick={() => setHistory([])}>삭제</button>
            </div>
            <ul className="dash__history-list">
              {history.slice(0, 6).map((h, i) => (
                <li key={i} className="dash__history-item" onClick={() => setUrl(h.url)}>
                  <span className="dash__history-icon" style={{ color: PLATFORMS[h.platform]?.color }}>
                    {PLATFORMS[h.platform]?.icon || '🔗'}
                  </span>
                  <span className="dash__history-title">{h.title}</span>
                  <span className="dash__history-time">
                    {h.analyzed_at ? new Date(h.analyzed_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) : ''}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* ===== STATS BAR ===== */}
      <section className="dash__stats" aria-label="통계">
        <StatBox icon="📊" label="총 수집" value={formatNumber(stats.total)} />
        <StatBox icon="▶" label="YouTube 댓글" value={formatNumber(stats.ytComments)} />
        <StatBox icon="📋" label="DCInside 게시글" value={formatNumber(stats.dcPosts)} />
        <StatBox icon="💬" label="DCInside 댓글" value={formatNumber(stats.dcComments)} />
      </section>

      {/* ===== TAB NAVIGATION ===== */}
      <nav className="dash__tabs" aria-label="플랫폼 탭">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`dash__tab ${activeTab === t.id ? 'dash__tab--active' : ''}`}
            onClick={() => setActiveTab(t.id)}
            aria-selected={activeTab === t.id}
            role="tab"
          >
            {t.label}
          </button>
        ))}
      </nav>

      {/* ===== TAB PANELS ===== */}
      <div className="dash__panel" role="tabpanel">
        {monitorData.loading ? (
          <div className="dash__loading">
            <div className="dash__spinner" />
            <p>데이터 로딩 중…</p>
          </div>
        ) : (
          <>
            {activeTab === 'overview' && <OverviewPanel stats={stats} galleries={monitorData.galleries} channels={monitorData.channels} />}
            {activeTab === 'youtube' && <YouTubePanel channels={monitorData.channels} creators={monitorData.creators} />}
            {activeTab === 'dcinside' && <DCInsidePanel galleries={monitorData.galleries} />}
            {activeTab === 'twitter' && <TwitterPanel />}
            {activeTab === 'social' && <SocialPanel />}
          </>
        )}
      </div>

      {/* ===== CREATOR LINKS ===== */}
      {monitorData.creators.length > 0 && (
        <section className="dash__creators" aria-label="크리에이터">
          <h3 className="dash__section-title">크리에이터 상세</h3>
          <div className="dash__creator-grid">
            {monitorData.creators.map((c, i) => {
              const handle = c.youtube_channel?.replace('@', '') || `creator-${i}`;
              return (
                <a
                  key={i}
                  className="dash__creator-card"
                  href={`/creator/${handle}`}
                  onClick={e => {
                    e.preventDefault();
                    window.history.pushState({}, '', `/creator/${handle}`);
                    window.dispatchEvent(new PopStateEvent('popstate'));
                  }}
                >
                  <strong>{c.name}</strong>
                  <span className="dash__creator-meta">댓글 {c.comments?.length || 0}개 · 좋아요 {c.total_likes || 0}</span>
                </a>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}

/* ============================================================
   Sub-components
   ============================================================ */

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

/* --- Analysis Result --- */
function AnalysisResult({ result, summary, summaryLoading, onSummarize }) {
  const platform = PLATFORMS[result.platform] || { label: result.platform, color: '#666' };
  const analysis = result.analysis;
  const items = result.comments || result.posts || result.recent_videos || [];

  const sentimentData = analysis ? [
    { name: '긍정', value: analysis.sentiment.positive, color: SENTIMENT_COLORS.positive },
    { name: '중립', value: analysis.sentiment.neutral,  color: SENTIMENT_COLORS.neutral },
    { name: '부정', value: analysis.sentiment.negative, color: SENTIMENT_COLORS.negative },
  ] : [];

  const keywordData = analysis?.top_keywords?.slice(0, 10) || [];

  return (
    <div className="result">
      <div className="result__header">
        <span className="result__platform" style={{ background: platform.color }}>{platform.label}</span>
        <h3 className="result__title">
          {result.title || result.gallery_id || result.subreddit || result.channel_name || result.username || '분석 결과'}
        </h3>
        {result.analyzed_at && (
          <span className="result__time">{new Date(result.analyzed_at).toLocaleString('ko-KR')}</span>
        )}
      </div>

      <div className="result__stats">
        {result.view_count != null && <MiniStat icon="👁" value={formatNumber(result.view_count)} label="조회" />}
        {result.like_count != null && <MiniStat icon="👍" value={formatNumber(result.like_count)} label="좋아요" />}
        {result.comment_count != null && <MiniStat icon="💬" value={formatNumber(result.comment_count)} label="댓글" />}
        {result.subscriber_count != null && <MiniStat icon="👤" value={formatNumber(result.subscriber_count)} label="구독" />}
        {result.total_posts != null && <MiniStat icon="📝" value={formatNumber(result.total_posts)} label="게시글" />}
        {result.total_messages != null && <MiniStat icon="✉" value={formatNumber(result.total_messages)} label="메시지" />}
        {result.follower_count != null && <MiniStat icon="👥" value={formatNumber(result.follower_count)} label="팔로워" />}
        {result.tweet_count != null && <MiniStat icon="𝕏" value={formatNumber(result.tweet_count)} label="트윗" />}
      </div>

      <div className="result__actions">
        <button className="result__summarize-btn" onClick={onSummarize} disabled={summaryLoading}>
          {summaryLoading ? '🤖 요약 생성 중…' : '🤖 AI 요약'}
        </button>
        {result.source_url && (
          <a href={result.source_url} target="_blank" rel="noopener noreferrer" className="result__link">원문 보기 →</a>
        )}
      </div>

      {summary && (
        <div className="result__summary">
          <span className="result__summary-src">{summary.source === 'mirofish' ? '🐟 MiroFish AI' : '📊 로컬 분석'}</span>
          <div className="result__summary-text">{summary.summary}</div>
        </div>
      )}

      {result.description && (
        <div className="result__desc">
          <h4>설명</h4>
          <p>{result.description}</p>
        </div>
      )}

      {analysis && (
        <div className="result__sentiment">
          <h4>감성 분석 ({analysis.total}건)</h4>
          <div className="result__charts">
            {sentimentData.some(d => d.value > 0) && (
              <div className="result__chart">
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={sentimentData.filter(d => d.value > 0)} cx="50%" cy="50%" outerRadius={75} dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}>
                      {sentimentData.map((e, i) => <Cell key={i} fill={e.color} />)}
                    </Pie>
                    <Legend /><Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
            {keywordData.length > 0 && (
              <div className="result__chart">
                <h5>주요 키워드</h5>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={keywordData} layout="vertical">
                    <XAxis type="number" /><YAxis type="category" dataKey="word" width={80} />
                    <Tooltip /><Bar dataKey="count" fill="var(--c-primary)" radius={[0,4,4,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
          <p className="result__overall">
            전체 감성: <span className={`sentiment--${analysis.overall}`}>
              {analysis.overall === 'positive' ? '긍정적' : analysis.overall === 'negative' ? '부정적' : '중립적'}
            </span>
          </p>
        </div>
      )}

      {items.length > 0 && (
        <div className="result__items">
          <h4>{result.comments ? '댓글' : result.recent_videos ? '최근 영상' : '게시글'} ({items.length})</h4>
          <div className="result__items-list">
            {items.slice(0, 15).map((item, i) => (
              <div key={i} className="result__item">
                <div className="result__item-text">{item.text || item.title || item.selftext || ''}</div>
                <div className="result__item-meta">
                  {item.author && <span>{item.author}</span>}
                  {(item.like_count ?? item.score ?? item.recommend) != null && <span>👍 {formatNumber(item.like_count ?? item.score ?? item.recommend ?? 0)}</span>}
                  {item.view_count != null && <span>👁 {formatNumber(item.view_count)}</span>}
                  {(item.published_at || item.date) && <span>{item.published_at || item.date}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MiniStat({ icon, value, label }) {
  return (
    <div className="result__mini-stat">
      <span className="result__mini-icon">{icon}</span>
      <span className="result__mini-val">{value}</span>
      <span className="result__mini-label">{label}</span>
    </div>
  );
}

/* --- Overview Panel --- */
function OverviewPanel({ stats, galleries, channels }) {
  const dcPositive = galleries.reduce((s, g) => s + (g.positive_count || 0), 0);
  const dcNegative = galleries.reduce((s, g) => s + (g.negative_count || 0), 0);

  return (
    <div className="panel-overview">
      <div className="panel-overview__grid">
        <div className="panel-card">
          <h4 className="panel-card__title">YouTube</h4>
          <div className="panel-card__body">
            <p><strong>{channels.length}</strong> 키워드 모니터링</p>
            <p><strong>{formatNumber(stats.ytComments)}</strong> 댓글 수집됨</p>
          </div>
        </div>
        <div className="panel-card">
          <h4 className="panel-card__title">DCInside</h4>
          <div className="panel-card__body">
            <p><strong>{galleries.length}</strong> 갤러리 모니터링</p>
            <p><strong>{formatNumber(stats.dcPosts)}</strong> 게시글 수집됨</p>
            <p>긍정 <strong style={{ color: 'var(--c-success)' }}>{dcPositive}</strong> · 부정 <strong style={{ color: 'var(--c-danger)' }}>{dcNegative}</strong></p>
          </div>
        </div>
        <div className="panel-card">
          <h4 className="panel-card__title">X (Twitter)</h4>
          <div className="panel-card__body">
            <p>키워드 검색 링크 기반 모니터링</p>
            <p className="panel-card__hint">트위터 API 유료 → 직접 검색 방식</p>
          </div>
        </div>
        <div className="panel-card">
          <h4 className="panel-card__title">Instagram · Facebook · Threads</h4>
          <div className="panel-card__body">
            <p>URL 분석 기반 모니터링</p>
            <p className="panel-card__hint">상단 URL 입력에서 분석 가능</p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* --- YouTube Panel --- */
function YouTubePanel({ channels, creators }) {
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
        <EmptyHint text="YouTube 크롤러를 실행하여 데이터를 수집해 주세요." />
      )}
    </div>
  );
}

/* --- DCInside Panel --- */
function DCInsidePanel({ galleries }) {
  const [expanded, setExpanded] = useState({});

  if (galleries.length === 0) return <EmptyHint text="DCInside 크롤러를 실행하여 갤러리 게시글을 수집해 주세요." />;

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
function TwitterPanel() {
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
function SocialPanel() {
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

function EmptyHint({ text }) {
  return (
    <div className="dash__empty">
      <span className="dash__empty-icon">📭</span>
      <p>{text}</p>
    </div>
  );
}

export default Dashboard;
