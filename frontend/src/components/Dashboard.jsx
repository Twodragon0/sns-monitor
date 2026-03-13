import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import './Dashboard.css';
import { API_BASE } from '../config';

const RESULTS_CACHE_KEY = 'sns-monitor-results';
const RESULTS_CACHE_MAX = 5;
const NAVER_FETCH_STATUS_LABELS = {
  ok: '정상',
  partial: '부분 수집',
  blocked: '수집 제한',
};
const NAVER_FETCH_REASON_LABELS = {
  html_fetch_failed: 'HTML 수집 실패',
  api_fetch_failed: 'API 수집 실패',
  mobile_fetch_failed: '모바일 수집 실패',
  no_posts_detected: '게시글 미감지',
  posts_found_but_comments_unavailable: '게시글만 수집, 댓글 미수집',
  content_and_comments_unavailable: '본문/댓글 모두 미수집',
  content_found_but_comments_unavailable: '본문 수집, 댓글 미수집',
  cookie_not_set: '로그인 쿠키 미설정',
  proxy_not_set: '프록시 미설정',
};

function loadResultsCache() {
  try {
    const raw = localStorage.getItem(RESULTS_CACHE_KEY);
    if (!raw) return { urls: [], data: {} };
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed?.urls) && parsed.data && typeof parsed.data === 'object'
      ? parsed
      : { urls: [], data: {} };
  } catch {
    return { urls: [], data: {} };
  }
}

function saveResultsCache(url, result) {
  const prev = loadResultsCache();
  const urls = [url, ...prev.urls.filter(u => u !== url)].slice(0, RESULTS_CACHE_MAX);
  const data = { ...prev.data, [url]: result };
  const trimmed = {};
  urls.forEach(u => { if (data[u]) trimmed[u] = data[u]; });
  localStorage.setItem(RESULTS_CACHE_KEY, JSON.stringify({ urls, data: trimmed }));
}

/** 요약 API 전송용으로 페이로드 축소 (413 Payload Too Large 방지) */
function trimResultForSummarize(result) {
  if (!result) return null;
  const statKeys = ['view_count', 'like_count', 'comment_count', 'subscriber_count', 'follower_count', 'tweet_count', 'total_posts', 'score'];
  const stats = {};
  statKeys.forEach(k => { if (result[k] != null) stats[k] = result[k]; });
  const base = {
    platform: result.platform,
    title: result.title,
    gallery_id: result.gallery_id,
    gallery_name: result.gallery_name,
    subreddit: result.subreddit,
    username: result.username,
    analyzed_at: result.analyzed_at,
    source_url: result.source_url,
    description: result.description ? String(result.description).slice(0, 2000) : undefined,
    fetch_status: result.fetch_status,
    fetch_reason: result.fetch_reason,
    content: result.content ? String(result.content).slice(0, 3000) : undefined,
    analysis: result.analysis ? {
      overall: result.analysis.overall,
      sentiment: result.analysis.sentiment,
      top_keywords: (result.analysis.top_keywords || []).slice(0, 10),
    } : undefined,
    ...stats,
  };
  const items = result.comments || result.posts || result.recent_videos;
  if (Array.isArray(items) && items.length > 0) {
    const key = result.comments ? 'comments' : (result.posts ? 'posts' : 'recent_videos');
    base[key] = items.slice(0, 50).map(item => ({
      text: (item.text || item.title || item.selftext || '').slice(0, 200),
      author: item.author,
      date: item.date || item.published_at,
    }));
  }
  return base;
}

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
  if (l.includes('cafe.naver.com')) return 'naver_cafe';
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
function Dashboard({ onShowError }) {
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
        fetch(`${API_BASE}/api/channels`).then(r => r.ok ? r.json() : { channels: [] }),
        fetch(`${API_BASE}/api/dcinside/galleries`, { signal: AbortSignal.timeout(10000) })
          .then(r => r.ok ? r.json() : { galleries: [] }),
        fetch(`${API_BASE}/api/vuddy/creators`).then(r => r.ok ? r.json() : { creators: [] }),
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

  // --- Computed stats (단일 소스: 상단 StatBar · 탭 라벨 · Overview 패널 카드에서 공통 사용) ---
  const stats = useMemo(() => {
    const ytComments = monitorData.channels.reduce((s, c) => s + (c.total_comments || 0), 0);
    const dcPosts = monitorData.galleries.reduce((s, g) => s + (g.total_posts || 0), 0);
    const dcComments = monitorData.galleries.reduce((s, g) => s + (g.total_comments || 0), 0);
    const dcPositive = monitorData.galleries.reduce((s, g) => s + (g.positive_count || 0), 0);
    const dcNegative = monitorData.galleries.reduce((s, g) => s + (g.negative_count || 0), 0);
    const creatorComments = monitorData.creators.reduce((s, c) => s + (c.comments?.length || 0), 0);
    return {
      ytComments,
      dcPosts,
      dcComments,
      dcPositive,
      dcNegative,
      galleryCount: monitorData.galleries.length,
      creatorComments,
      total: ytComments + dcComments + creatorComments,
    };
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
      const { data } = await axios.post(`${API_BASE}/api/analyze/url`, { url: trimmed }, { timeout: 300000 });
      setAnalysisResult(data);
      saveResultsCache(trimmed, data);
      setHistory(prev => [{
        url: trimmed,
        platform: data.platform,
        title: data.title || data.gallery_id || data.subreddit || data.username || trimmed,
        analyzed_at: data.analyzed_at,
      }, ...prev.filter(h => h.url !== trimmed).slice(0, 19)]);
    } catch (err) {
      const msg = err.response?.data?.error || err.message || '분석 실패';
      const isConnectionError =
        !err.response &&
        (err.code === 'ERR_NETWORK' ||
          err.message === 'Network Error' ||
          err.code === 'ECONNABORTED');
      setAnalysisError(
        isConnectionError
          ? 'API 서버에 연결할 수 없습니다. Docker를 실행했는지 확인해 주세요. (docker-compose up -d)'
          : msg
      );
    } finally {
      setAnalysisLoading(false);
    }
  }, [url]);

  const handleSummarize = useCallback(async () => {
    if (!analysisResult) return;
    setSummaryLoading(true);
    setAnalysisError(null);
    try {
      const payload = trimResultForSummarize(analysisResult);
      const { data } = await axios.post(`${API_BASE}/api/analyze/summarize`, { result: payload }, { timeout: 60000 });
      setAnalysisSummary(data);
    } catch (err) {
      const msg = err.response?.data?.error || err.message || '요약 실패';
      setAnalysisError(err.response?.status === 413 ? '요청 크기가 서버 제한을 초과했습니다.' : msg);
    } finally {
      setSummaryLoading(false);
    }
  }, [analysisResult]);

  // URL 분석 완료 시 해당 플랫폼 탭으로 자동 전환 (연결감 강화)
  const prevPlatformRef = useRef(null);
  useEffect(() => {
    const platform = analysisResult?.platform;
    if (!platform) {
      prevPlatformRef.current = null;
      return;
    }
    if (platform === prevPlatformRef.current) return;
    prevPlatformRef.current = platform;
    const map = { youtube: 'youtube', dcinside: 'dcinside', twitter: 'twitter', instagram: 'social', facebook: 'social', threads: 'social' };
    const tab = map[platform];
    if (tab) setActiveTab(tab);
  }, [analysisResult?.platform]);

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
              placeholder="https://www.youtube.com/... 또는 갤러리·네이버 카페·서브레딧 등 URL"
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
            onShowError={onShowError}
          />
        )}

        {!analysisResult && history.length > 0 && (
          <div className="dash__history">
            <div className="dash__history-header">
              <h4>최근 분석</h4>
              <button className="dash__history-clear" onClick={() => { setHistory([]); localStorage.removeItem(RESULTS_CACHE_KEY); }}>삭제</button>
            </div>
            <ul className="dash__history-list">
              {history.slice(0, 6).map((h, i) => (
                <li
                  key={i}
                  className="dash__history-item"
                  onClick={() => {
                    setUrl(h.url);
                    const cache = loadResultsCache();
                    const cached = cache.data[h.url];
                    setAnalysisResult(cached ?? null);
                    setAnalysisSummary(null);
                  }}
                >
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

        <p className="dash__hero-bridge" aria-hidden="true">
          분석 결과 아래에서 플랫폼별 수집 현황과 상세 모니터링을 확인할 수 있습니다.
        </p>
      </section>

      {/* ===== 모니터링 요약: 통계 + 탭 + 패널 (한 덩어리) ===== */}
      <section className="dash__monitoring" aria-labelledby="monitoring-title">
        <h2 id="monitoring-title" className="dash__monitoring-title">플랫폼별 모니터링</h2>
        <p className="dash__monitoring-desc">
          위에서 URL을 분석하거나 크롤러로 수집한 결과를, 플랫폼별로 한눈에 보는 영역입니다. URL 분석 후 해당 플랫폼 탭이 자동 선택됩니다.
        </p>
        {stats.total === 0 && (
          <p className="dash__monitoring-hint" role="status">
            상단 URL 검색으로 단일 URL을 즉시 분석하거나, 크롤러를 실행하면 이 아래에 수집 현황이 누적되어 표시됩니다.
          </p>
        )}

        <div className="dash__monitoring-analysis-cta">
          <span className="dash__monitoring-analysis-label">🐟 수집 데이터 분석 · 요약 (MiroFish)</span>
          <p className="dash__monitoring-analysis-desc">
            위 URL 분석과 크롤러로 쌓인 YouTube·DCInside 데이터를 한꺼번에 MiroFish AI로 보내,
            엔티티 그래프와 AI 채팅으로 <strong>전체 패턴과 인사이트</strong>를 보는 심화 분석 기능입니다.
          </p>
          {analysisResult && (
            <p className="dash__monitoring-analysis-recent">
              최근 URL 분석: <strong>{PLATFORMS[analysisResult.platform]?.label || analysisResult.platform}</strong> — {analysisResult.title || analysisResult.gallery_name || analysisResult.gallery_id || '분석 결과'} ({formatNumber(analysisResult.total_posts ?? analysisResult.comment_count ?? (analysisResult.comments || analysisResult.posts || analysisResult.recent_videos || []).length)}건).
              위의 URL 분석 결과 카드에서 <strong>「🐟 MiroFish로 심화 분석」</strong> 버튼을 누르면, 이 대상이 자동으로 MiroFish에 연결됩니다.
            </p>
          )}
          <button
            type="button"
            className="dash__monitoring-analysis-btn"
            onClick={() => {
              window.history.pushState({}, '', '/analysis');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
          >
            MiroFish 분석 페이지로 이동
          </button>
        </div>

        <div className="dash__stats" aria-label="통계">
          <StatBox icon="📊" label="총 수집" value={formatNumber(stats.total)} />
          <StatBox icon="▶" label="YouTube 댓글" value={formatNumber(stats.ytComments)} />
          <StatBox icon="📋" label="DCInside 게시글" value={formatNumber(stats.dcPosts)} />
          <StatBox icon="💬" label="DCInside 댓글" value={formatNumber(stats.dcComments)} />
        </div>

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

        <div className="dash__panel" role="tabpanel">
          {monitorData.loading ? (
            <div className="dash__loading">
              <div className="dash__spinner" />
              <p>데이터 로딩 중…</p>
            </div>
          ) : (
            <>
              {activeTab === 'overview' && <OverviewPanel stats={stats} channels={monitorData.channels} />}
              {activeTab === 'youtube' && <YouTubePanel channels={monitorData.channels} creators={monitorData.creators} />}
              {activeTab === 'dcinside' && <DCInsidePanel galleries={monitorData.galleries} />}
              {activeTab === 'twitter' && <TwitterPanel />}
              {activeTab === 'social' && <SocialPanel />}
            </>
          )}
        </div>
      </section>

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

/** 요약 텍스트 표시: 줄바꿈 유지, **bold** 만 <strong>으로 렌더 (마크다운 미지원 시 가독성) */
function renderSummaryContent(text) {
  if (!text || typeof text !== 'string') return null;
  const re = /\*\*(.+?)\*\*/g;
  const parts = [];
  let lastIndex = 0;
  let key = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    parts.push(text.slice(lastIndex, m.index));
    parts.push(<strong key={`b-${key++}`}>{m[1]}</strong>);
    lastIndex = m.index + m[0].length;
  }
  parts.push(text.slice(lastIndex));
  if (parts.length === 1 && typeof parts[0] === 'string') return parts[0];
  return parts;
}

/** MiroFish로 심화 분석 버튼: 상태 확인 후 이동, 현재 결과 소스 사전 선택. authRequired 시 로그인 유도. */
function MiroFishCtaButton({ result, onShowError }) {
  const [loading, setLoading] = useState(false);
  const { loggedIn, authRequired, login } = useAuth();

  const goToMiroFish = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API_BASE}/api/analysis/status`, { timeout: 5000 });
      if (!data.mirofish_available) {
        onShowError?.('MiroFish 서비스가 꺼져 있습니다. docker-compose --profile analysis up -d 및 .env.mirofish 설정 후 이용해 주세요.');
      }
      const preselect = [];
      if (result.platform === 'youtube' && (result.channel_id || result.channelId)) {
        preselect.push({ type: 'youtube', id: result.channel_id || result.channelId });
      }
      if (result.platform === 'dcinside' && result.gallery_id) {
        preselect.push({ type: 'dcinside', id: result.gallery_id });
      }
      if (preselect.length) {
        try {
          sessionStorage.setItem('analysisPreselect', JSON.stringify(preselect));
        } catch (_) { /* ignore */ }
      }
      window.history.pushState({}, '', '/analysis');
      window.dispatchEvent(new PopStateEvent('popstate'));
    } catch (_) {
      onShowError?.('MiroFish 상태 확인에 실패했습니다. API 서버 연결을 확인해 주세요.');
    } finally {
      setLoading(false);
    }
  }, [result, onShowError]);

  if (authRequired && !loggedIn) {
    return (
      <div className="result__mirofish-cta">
        <p className="result__mirofish-cta-desc">수집된 데이터를 엔티티 그래프로 구축하고 AI 채팅으로 인사이트를 질의할 수 있습니다. OpenAI 로그인 후 이용 가능합니다.</p>
        <button
          type="button"
          className="result__mirofish-cta-btn result__mirofish-cta-btn--login"
          onClick={() => login('/analysis')}
        >
          OpenAI(GPT)로 로그인 후 MiroFish 분석
        </button>
      </div>
    );
  }

  return (
    <div className="result__mirofish-cta">
      <p className="result__mirofish-cta-desc">수집된 데이터를 엔티티 그래프로 구축하고 AI 채팅으로 인사이트를 질의할 수 있습니다.</p>
      <button
        type="button"
        className="result__mirofish-cta-btn"
        onClick={goToMiroFish}
        disabled={loading}
      >
        {loading ? '확인 중…' : '🐟 MiroFish로 심화 분석'}
      </button>
    </div>
  );
}

/* --- Analysis Result --- */
function AnalysisResult({ result, summary, summaryLoading, onSummarize, onShowError }) {
  const platform = PLATFORMS[result.platform] || { label: result.platform, color: '#666' };
  const analysis = result.analysis;
  const sentiment = analysis?.sentiment;
  const hasYoutubeComments =
    result.platform === 'youtube' && Array.isArray(result.comments) && result.comments.length > 0;
  const items = !hasYoutubeComments ? (result.comments || result.posts || result.recent_videos || []) : [];
  const isNaverSinglePost = result.platform === 'naver_cafe' && result.type === 'post';
  const naverFetchStatus = result.fetch_status || 'ok';
  const naverFetchReason = result.fetch_reason || '';
  const naverReasonTokens = parseNaverReasonTokens(naverFetchReason);
  const naverFetchReasonLabel = formatNaverFetchReason(naverFetchReason);
  const naverFetchStatusLabel = NAVER_FETCH_STATUS_LABELS[naverFetchStatus] || naverFetchStatus;
  const naverActionItems = getNaverDiagnosticActions(naverReasonTokens);

  const sentimentData = sentiment ? [
    { name: '긍정', value: sentiment.positive ?? 0, color: SENTIMENT_COLORS.positive },
    { name: '중립', value: sentiment.neutral ?? 0, color: SENTIMENT_COLORS.neutral },
    { name: '부정', value: sentiment.negative ?? 0, color: SENTIMENT_COLORS.negative },
  ] : [];

  const keywordData = analysis?.top_keywords?.slice(0, 10) || [];

  const title = result.title || result.gallery_name || result.gallery_id || result.subreddit || result.channel_name || result.username || '분석 결과';

  return (
    <div className="result">
      <div className="result__header">
        <span className="result__platform" style={{ background: platform.color }}>{platform.label}</span>
        <h3 className="result__title">{title}</h3>
        {result.analyzed_at && (
          <span className="result__time">{new Date(result.analyzed_at).toLocaleString('ko-KR')}</span>
        )}
        {isNaverSinglePost && (
          <div className="result__naver-badges">
            {result.login_verified && (
              <span className="result__naver-badge result__naver-badge--login" title="로그인된 상태로 수집됨">로그인됨</span>
            )}
            <a href={result.url || result.source_url} target="_blank" rel="noopener noreferrer" className="result__naver-badge result__naver-badge--link">원문 URL</a>
            <span className="result__naver-badge">댓글 {formatNumber(result.comment_count ?? 0)}</span>
            {naverFetchStatus !== 'ok' && (
              <span className="result__naver-badge result__naver-badge--warn">
                {naverFetchStatusLabel}: {naverFetchReasonLabel || naverFetchStatusLabel}
              </span>
            )}
          </div>
        )}
      </div>

      {isNaverSinglePost && naverFetchStatus !== 'ok' && (
        <div className="result__naver-panel" role="status" aria-live="polite">
          <strong className="result__naver-panel-title">네이버 카페 진단</strong>
          <p className="result__naver-panel-summary">현재 상태: {naverFetchStatusLabel}</p>
          {naverFetchReasonLabel && (
            <p className="result__naver-panel-reasons">원인: {naverFetchReasonLabel}</p>
          )}
          {naverActionItems.length > 0 && (
            <ul className="result__naver-panel-actions">
              {naverActionItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="result__stats">
        {result.view_count != null && <MiniStat icon="👁" value={formatNumber(result.view_count)} label="조회" />}
        {result.like_count != null && <MiniStat icon="👍" value={formatNumber(result.like_count)} label="좋아요" />}
        {result.recommend != null && <MiniStat icon="👍" value={formatNumber(result.recommend)} label="추천" />}
        {(result.comment_count != null || result.comment_count === 0) && <MiniStat icon="💬" value={formatNumber(result.comment_count)} label="댓글" />}
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
        {(result.source_url || result.url) && (
          <a href={result.source_url || result.url} target="_blank" rel="noopener noreferrer" className="result__link">원문 보기 →</a>
        )}
      </div>

      {/* 네이버 카페 수집 제한 시 안내 (갤러리 0건 포함 항상 표시) */}
      {result.platform === 'naver_cafe' && naverFetchStatus !== 'ok' && (
        <div className="result__naver-hint" role="status" title={naverFetchReasonLabel}>
          <p className="result__naver-hint-status">
            ☕ 네이버 카페: {naverFetchStatusLabel}
            {naverFetchReasonLabel && (
              <span className="result__naver-hint-reasons"> — {naverFetchReasonLabel}</span>
            )}
          </p>
          <p className="result__naver-hint-action">
            <strong>수집하려면:</strong> .env에 <code>NAVER_CAFE_COOKIE</code>를 넣고 <code>docker compose up -d --build</code>로 재시작하세요. (필요 시 <code>NAVER_CAFE_PROXY_URL</code>도 설정)
          </p>
        </div>
      )}

      {/* Reddit API 403 시 안내 */}
      {result.platform === 'reddit' && result.fetch_status === 'blocked' && (
        <div className="result__reddit-hint" role="status">
          <p className="result__reddit-hint-status">
            🔗 Reddit: API 접근이 차단되었습니다.
          </p>
          <p className="result__reddit-hint-action">
            {result.description || 'Reddit이 비인증 요청을 막고 있습니다. .env에 REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET을 설정한 뒤 docker compose up -d --build로 재시작하세요.'}
          </p>
        </div>
      )}

      {summary && (
        <div className="result__summary">
          <span className="result__summary-src">{summary.source === 'mirofish' ? '🐟 MiroFish AI' : '📊 로컬 분석'}</span>
          <div className="result__summary-text">
            {renderSummaryContent(summary.summary)}
          </div>
        </div>
      )}

      {/* 이 분석을 MiroFish로 심화 분석 (요약/감성 아래 항상 노출) */}
      <MiroFishCtaButton result={result} onShowError={onShowError} />

      {/* DCInside 단일 게시글 본문 */}
      {(result.platform === 'dcinside' || result.platform === 'naver_cafe') && result.type === 'post' && result.content && (
        <div className="result__desc">
          <h4>본문</h4>
          <div className="result__content-body">{result.content}</div>
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
          <h4 className="result__sentiment-title">감성 분석 ({(analysis.total ?? 0)}건)</h4>
          <div className="result__sentiment-stats">
            <span className="result__sentiment-pill result__sentiment-pill--positive">긍정 {formatNumber(sentiment?.positive ?? 0)}</span>
            <span className="result__sentiment-pill result__sentiment-pill--neutral">중립 {formatNumber(sentiment?.neutral ?? 0)}</span>
            <span className="result__sentiment-pill result__sentiment-pill--negative">부정 {formatNumber(sentiment?.negative ?? 0)}</span>
          </div>
          <p className="result__overall result__overall--top">
            전체 감성: <span className={`sentiment--${analysis.overall || 'neutral'}`}>
              {analysis.overall === 'positive' ? '긍정적' : analysis.overall === 'negative' ? '부정적' : '중립적'}
            </span>
          </p>
          <div className="result__charts">
            {sentimentData.some(d => (d.value ?? 0) > 0) && (
              <div className="result__chart">
                <h5>감성 비율</h5>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={sentimentData.filter(d => (d.value ?? 0) > 0)} cx="50%" cy="50%" outerRadius={75} dataKey="value"
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
        </div>
      )}

      {/* DCInside·네이버 카페 갤러리: 게시글 목록 + 접기/펼치기 댓글 */}
      {(result.platform === 'dcinside' || result.platform === 'naver_cafe') && result.type === 'gallery' && result.posts?.length > 0 && (
        <DCInsideResultPosts
          posts={result.posts}
          totalPosts={result.total_posts}
          loginVerified={result.login_verified}
          isNaverCafe={result.platform === 'naver_cafe'}
        />
      )}

      {/* YouTube: 단일 영상/채널 모두 댓글 접기/펼치기 (DCInside UX와 유사) */}
      {hasYoutubeComments && (
        <YouTubeComments
          comments={result.comments}
          totalComments={result.comment_count}
        />
      )}

      {/* 수집된 콘텐츠: 댓글 / 게시글 / 최근 영상 (제목·목록·미리보기 개선) */}
      {!((result.platform === 'dcinside' || result.platform === 'naver_cafe') && result.type === 'gallery') && items.length > 0 && (
        <div className="result__items">
          <div className="result__items-head">
            <h4 className="result__items-title">
              수집된 콘텐츠
              <span className="result__items-count">{result.comments ? '댓글' : result.recent_videos ? '영상' : '게시글'} {formatNumber(items.length)}건</span>
            </h4>
          </div>
          {result.platform === 'instagram' && (
            <p className="result__items-hint">게시글 내용은 og:meta로 수집됩니다. 댓글 수집은 Instagram 공식 API가 필요합니다.</p>
          )}
          <div className="result__items-list">
            {items.slice(0, (result.platform === 'dcinside' || result.platform === 'instagram') ? 50 : 15).map((item, i) => (
              <div
                key={i}
                className={`result__item ${item.url ? 'result__item--clickable' : ''}`}
                onClick={() => {
                  if (item.url) {
                    window.open(item.url, '_blank', 'noopener,noreferrer');
                  }
                }}
              >
                {result.platform === 'instagram' && result.thumbnail && i === 0 && (
                  <a href={item.url || result.url} target="_blank" rel="noopener noreferrer" className="result__item-thumb">
                    <img src={result.thumbnail} alt="" width={120} height={120} style={{ objectFit: 'cover', borderRadius: 8 }} />
                  </a>
                )}
                <div className="result__item-text">{(item.text || item.title || item.selftext || '').trim() || '(내용 없음)'}</div>
                <div className="result__item-meta">
                  {item.author && <span className="result__item-author">{item.author}</span>}
                  {(item.like_count ?? item.score ?? item.recommend) != null && <span>👍 {formatNumber(item.like_count ?? item.score ?? item.recommend ?? 0)}</span>}
                  {item.view_count != null && <span>👁 {formatNumber(item.view_count)}</span>}
                  {(item.published_at || item.date) && <span>{item.published_at || item.date}</span>}
                </div>
                {item.url && (
                  <a href={item.url} target="_blank" rel="noopener noreferrer" className="result__item-link">원문 →</a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* 댓글 정렬: 등록순(기본) | 최신순 | 답글순(동일) */
function sortComments(comments, order) {
  if (!comments?.length) return comments || [];
  const list = [...comments];
  if (order === '최신순' && list.some(c => c.date)) {
    list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  }
  return list;
}

const POSTS_PER_PAGE = 50;

const POST_SORT_OPTIONS = [
  { value: 'date_desc', label: '최신순' },
  { value: 'date_asc', label: '오래된순' },
  { value: 'popular', label: '인기순' },
  { value: 'comments', label: '댓글 많은 순' },
];

function sortYoutubeComments(comments, order) {
  if (!comments?.length) return comments || [];
  const list = [...comments];
  if (order === '최신순' && list.some(c => c.published_at)) {
    list.sort((a, b) => (b.published_at || '').localeCompare(a.published_at || ''));
  }
  if (order === '좋아요순') {
    list.sort((a, b) => (b.like_count ?? 0) - (a.like_count ?? 0));
  }
  return list;
}

function sortPosts(posts, sortBy) {
  if (!posts?.length) return posts || [];
  const list = [...posts];
  switch (sortBy) {
    case 'date_asc':
      list.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
      break;
    case 'date_desc':
      list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
      break;
    case 'popular':
      list.sort((a, b) => (b.recommend ?? 0) - (a.recommend ?? 0));
      break;
    case 'comments':
      list.sort((a, b) => (b.comments?.length ?? 0) - (a.comments?.length ?? 0));
      break;
    default:
      break;
  }
  return list;
}

/* DCInside·네이버 카페 갤러리 게시글 + 댓글 (접기/펼치기, 통합 댓글, 전체 댓글 N개 헤더, 50개씩 페이지네이션)
   DCInside는 목록 기준 댓글 수(comment_count)는 있지만, API 차단 등으로 실제 수집이 실패하는 경우가 있어
   클릭 시 단건 URL을 다시 /api/analyze/url로 호출하여 댓글을 재수집(on-demand)합니다. */
function DCInsideResultPosts({ posts, totalPosts, loginVerified, isNaverCafe }) {
  const [expandedNo, setExpandedNo] = useState(null);
  const [showAllComments, setShowAllComments] = useState(false);
  const [commentSort, setCommentSort] = useState('등록순');
  const [currentPage, setCurrentPage] = useState(1);
  const [postSort, setPostSort] = useState('date_desc');
  const [localPosts, setLocalPosts] = useState(posts);
  const [loadingPostNo, setLoadingPostNo] = useState(null);

  useEffect(() => {
    setLocalPosts(posts);
  }, [posts]);

  const sortedPosts = useMemo(() => sortPosts(localPosts, postSort), [localPosts, postSort]);
  const totalPages = Math.max(1, Math.ceil(sortedPosts.length / POSTS_PER_PAGE));
  const start = (currentPage - 1) * POSTS_PER_PAGE;
  const postsOnPage = sortedPosts.slice(start, start + POSTS_PER_PAGE);

  const allComments = localPosts.reduce((acc, post) => {
    (post.comments || []).forEach((c) => {
      acc.push({ ...c, postTitle: post.text || `게시글 #${post.number ?? ''}`, postUrl: post.url });
    });
    return acc;
  }, []);

  const sortedAllComments = sortComments(allComments, commentSort);
  const totalCommentCount = allComments.length;

  const postsWithComments = localPosts.filter((p) => (p.comments?.length || 0) > 0).length;

  const listLabel = totalPosts != null && totalPosts > localPosts.length && isNaverCafe
    ? `수집 ${localPosts.length}건 / 전체 약 ${formatNumber(totalPosts)}건`
    : `${localPosts.length}건`;

  return (
    <div className="result__items">
      <div className="result__items-head">
        <h4>
          게시글 목록 ({listLabel})
          {isNaverCafe && loginVerified && (
            <span className="result__naver-login-badge" title="로그인된 상태로 수집됨">로그인됨</span>
          )}
        </h4>
        <p className="result__items-hint" aria-hidden="true">
          💬 카드 전체를 클릭하면 해당 글의 댓글이 아래에 펼쳐집니다. (댓글 있는 글 {postsWithComments}건)
        </p>
        <div className="result__items-sort" aria-label="게시글 정렬">
          <span className="result__items-sort-label">정렬:</span>
          {POST_SORT_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              className={`result__pagination-btn result__sort-btn ${postSort === value ? 'is-active' : ''}`}
              onClick={() => { setPostSort(value); setCurrentPage(1); setExpandedNo(null); }}
              aria-pressed={postSort === value}
            >
              {label}
            </button>
          ))}
        </div>
        {totalPages > 1 && (
          <div className="result__items-pagination" aria-label="게시글 페이지">
            <button
              type="button"
              className="result__pagination-btn"
              onClick={() => { setCurrentPage(p => Math.max(1, p - 1)); setExpandedNo(null); }}
              disabled={currentPage <= 1}
              aria-label="이전 페이지"
            >
              이전
            </button>
            <span className="result__pagination-info">
              {currentPage} / {totalPages} (50개씩)
            </span>
            <button
              type="button"
              className="result__pagination-btn"
              onClick={() => { setCurrentPage(p => Math.min(totalPages, p + 1)); setExpandedNo(null); }}
              disabled={currentPage >= totalPages}
              aria-label="다음 페이지"
            >
              다음
            </button>
          </div>
        )}
      </div>

      {totalCommentCount > 0 && (
        <div className="result__comment-count-bar" aria-label="전체 댓글">
          <div className="result__comment-count-inner">
            <span className="result__comment-count-label">
              전체 댓글 {totalCommentCount}개 · 클릭 시 댓글 표시
            </span>
            <div className="result__comment-sort">
              {['등록순', '최신순', '답글순'].map((order) => (
                <button
                  key={order}
                  type="button"
                  className={`result__comment-sort-btn ${commentSort === order ? 'is-active' : ''}`}
                  onClick={() => setCommentSort(order)}
                  aria-pressed={commentSort === order}
                >
                  {order}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="result__comments-toggle result__comments-toggle--all"
              onClick={() => setShowAllComments((v) => !v)}
              aria-expanded={showAllComments}
            >
              {showAllComments ? '통합 댓글 접기' : '통합 보기'}
            </button>
          </div>
        </div>
      )}

      {showAllComments && sortedAllComments.length > 0 && (
        <div className="result__all-comments" aria-label="전체 댓글 통합">
          <ul className="result__comments-sublist result__comments-sublist--all">
            {sortedAllComments.map((c, i) => (
              <li key={i} className="result__comment-item">
                <span className="result__comment-meta">
                  [{c.postTitle}]
                  {c.postUrl && (
                    <a href={c.postUrl} target="_blank" rel="noopener noreferrer" className="result__comment-post-link">
                      원문
                    </a>
                  )}{' '}
                  <span className="result__comment-author">{c.author}</span>
                  {c.date && <span className="result__comment-date">{c.date}</span>}
                </span>
                <span className="result__comment-text">{c.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="result__items-list">
        {postsOnPage.map((post, idx) => {
          const postKey = post.number ?? post.post_id ?? idx;
          const commentList = post.comments ?? [];
          const collectedCount = commentList.length;
          const listCount = post.comment_count ?? null;
          const isExpanded = expandedNo === postKey;
          const sortedPostComments = sortComments(commentList, commentSort);
          const commentLabel = listCount != null
            ? `댓글 (목록 ${listCount} / 수집 ${collectedCount})`
            : `댓글 (${collectedCount})`;
          const collectionFailed = listCount != null && listCount > 0 && collectedCount === 0;

          const toggleComments = async (e) => {
            if (e.target.closest('a')) return;
            const willExpand = !isExpanded;
            // 댓글이 목록상 1개 이상인데 아직 수집되지 않은 경우, 단건 URL로 재수집 시도
            if (willExpand && collectionFailed && post.url && !loadingPostNo) {
              try {
                setLoadingPostNo(postKey);
                const { data } = await axios.post(
                  `${API_BASE}/api/analyze/url`,
                  { url: post.url },
                  { timeout: 300000 },
                );
                const newComments = Array.isArray(data.comments) ? data.comments : [];
                setLocalPosts((prev) =>
                  prev.map((p) =>
                    (p.number ?? p.post_id ?? idx) === postKey
                      ? {
                          ...p,
                          comments: newComments,
                          comment_count:
                            typeof data.comment_count === 'number'
                              ? data.comment_count
                              : newComments.length || p.comment_count,
                        }
                      : p,
                  ),
                );
              } catch (err) {
                // 실패 시 기존 수집 실패 메시지 유지
              } finally {
                setLoadingPostNo(null);
              }
            }
            setExpandedNo(willExpand ? postKey : null);
          };

          return (
            <div
              key={postKey}
              className={`result__item result__item--dcinside ${isExpanded ? 'result__item--expanded' : ''}`}
              onClick={toggleComments}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleComments(e); } }}
              role="button"
              tabIndex={0}
              aria-expanded={isExpanded}
              aria-controls={`result-cmt-${postKey}`}
              aria-label={isExpanded ? `댓글 접기` : `댓글 ${collectedCount}개 보기`}
            >
              {post.url ? (
                <a
                  href={post.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="result__item-text result__item-text--link"
                  onClick={(e) => e.stopPropagation()}
                >
                  {post.text}
                </a>
              ) : (
                <div className="result__item-text">{post.text}</div>
              )}
              <div className="result__item-meta">
                {post.author && <span>{post.author}</span>}
                {post.view_count != null && <span>👁 {formatNumber(post.view_count)}</span>}
                {post.recommend != null && <span>👍 {formatNumber(post.recommend)}</span>}
                {post.date && <span>{post.date}</span>}
              </div>
              {post.url && (
                <a href={post.url} target="_blank" rel="noopener noreferrer" className="result__item-link" onClick={(e) => e.stopPropagation()}>
                  원문 보기 →
                </a>
              )}
              <div className="result__comment-wrap">
                <div className="result__comment-count">
                  <span className="result__comment-hint" aria-hidden="true">
                    💬 {commentLabel}
                    {collectionFailed && !loadingPostNo && (
                      <span
                        className="result__comment-fail"
                        title="목록에는 댓글이 있으나 초기 수집에 실패했습니다. 클릭 시 단건 URL로 다시 시도합니다."
                      >
                        {' '}
                        (수집 실패)
                      </span>
                    )}
                    {loadingPostNo === postKey && (
                      <span className="result__comment-fail"> (댓글 불러오는 중…)</span>
                    )}
                    {' '}{isExpanded ? '접기 ▲' : '클릭 시 보기 ▼'}
                  </span>
                </div>
                {isExpanded && (
                  <ul
                    id={`result-cmt-${postKey}`}
                    className="result__comments-sublist"
                    aria-label={`댓글 ${collectedCount}개`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {sortedPostComments.length === 0 ? (
                      <li className="result__comment-item result__comment-item--empty">
                        {collectionFailed ? (
                          <span className="result__comment-fail-hint">
                            댓글 수집에 실패했습니다. 위 <strong>원문 보기</strong>에서 댓글을 확인할 수 있습니다.
                          </span>
                        ) : (
                          '수집된 댓글이 없습니다.'
                        )}
                      </li>
                    ) : (
                      sortedPostComments.map((c, i) => (
                        <li key={i} className="result__comment-item">
                          <span className="result__comment-meta-inline">
                            <span className="result__comment-author">{c.author}</span>
                            {c.date && <span className="result__comment-date">{c.date}</span>}
                          </span>
                          <span className="result__comment-text">{c.text}</span>
                        </li>
                      ))
                    )}
                  </ul>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div className="result__items-pagination result__items-pagination--bottom" aria-label="게시글 페이지">
          <button
            type="button"
            className="result__pagination-btn"
            onClick={() => { setCurrentPage(p => Math.max(1, p - 1)); setExpandedNo(null); }}
            disabled={currentPage <= 1}
            aria-label="이전 페이지"
          >
            이전
          </button>
          <span className="result__pagination-info">
            {currentPage} / {totalPages} (50개씩)
          </span>
          <button
            type="button"
            className="result__pagination-btn"
            onClick={() => { setCurrentPage(p => Math.min(totalPages, p + 1)); setExpandedNo(null); }}
            disabled={currentPage >= totalPages}
            aria-label="다음 페이지"
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}

/* YouTube 단일 영상 댓글: 총 댓글 수 · 정렬 · 접기/펼치기 */
function YouTubeComments({ comments, totalComments }) {
  const [expanded, setExpanded] = useState(true);
  const [order, setOrder] = useState('등록순');

  const grouped = useMemo(() => {
    if (!comments?.length) return [];
    const buckets = new Map();
    comments.forEach((c) => {
      const key = c.video_id || 'video';
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(c);
    });
    const groups = [];
    buckets.forEach((list, key) => {
      const sortedList = sortYoutubeComments(list, order);
      const sample = sortedList[0] || {};
      groups.push({
        videoId: key === 'video' ? null : key,
        title: sample.video_title || sample.video_id || '영상',
        comments: sortedList,
      });
    });
    return groups;
  }, [comments, order]);

  const collectedCount = comments.length;
  const label = totalComments != null
    ? `댓글 (목록 ${formatNumber(totalComments)} / 수집 ${formatNumber(collectedCount)})`
    : `댓글 (${formatNumber(collectedCount)})`;

  return (
    <div className="result__items">
      <div className="result__comment-count-bar" aria-label="YouTube 댓글">
        <div className="result__comment-count-inner">
          <div className="result__comment-count-main">
            <span className="result__comment-count-label">
              💬 {label}
            </span>
            <button
              type="button"
              className="result__comments-toggle result__comments-toggle--all"
              onClick={() => setExpanded(v => !v)}
              aria-expanded={expanded}
            >
              {expanded ? '댓글 접기' : '댓글 펼치기'}
            </button>
          </div>
          <div className="result__comment-controls">
            <span className="result__comment-sort-label">정렬</span>
            <div className="result__comment-sort">
              {['등록순', '최신순', '좋아요순'].map(o => (
                <button
                  key={o}
                  type="button"
                  className={`result__comment-sort-btn ${order === o ? 'is-active' : ''}`}
                  onClick={() => setOrder(o)}
                  aria-pressed={order === o}
                >
                  {o}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
      {expanded && (
        <div className="result__all-comments" aria-label="YouTube 댓글 목록">
          {grouped.map((group, gi) => (
            <div key={group.videoId || gi} className="result__comments-group">
              <div className="result__comments-group-head">
                <span className="result__comments-group-title">
                  [{group.title}]
                </span>
                {group.videoId && (
                  <a
                    href={`https://www.youtube.com/watch?v=${group.videoId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="result__comment-post-link"
                  >
                    원문
                  </a>
                )}
                <span className="result__comments-group-count">
                  댓글 {formatNumber(group.comments.length)}개
                </span>
              </div>
              <ul className="result__comments-sublist result__comments-sublist--all">
                {group.comments.map((c, i) => (
                  <li key={i} className="result__comment-item">
                    <span className="result__comment-meta-inline">
                      {c.author && <span className="result__comment-author">{c.author}</span>}
                      {c.published_at && <span className="result__comment-date">{c.published_at}</span>}
                      {c.like_count != null && (
                        <span className="result__comment-like">👍 {formatNumber(c.like_count)}</span>
                      )}
                    </span>
                    <span className="result__comment-text">{c.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
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

/* --- Overview Panel (stats는 Dashboard에서 계산된 단일 소스 사용) --- */
function OverviewPanel({ stats, channels }) {
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
          <h4 className="panel-card__title">YouTube</h4>
          <div className="panel-card__body">
            <p><strong>{channels.length}</strong> 키워드 모니터링</p>
            <p><strong>{formatNumber(stats.ytComments)}</strong> 댓글 수집됨</p>
          </div>
        </div>
        <div className="panel-card">
          <h4 className="panel-card__title">DCInside</h4>
          <div className="panel-card__body">
            <p><strong>{stats.galleryCount}</strong> 갤러리 모니터링</p>
            <p><strong>{formatNumber(stats.dcPosts)}</strong> 게시글 수집됨</p>
            <p>긍정 <strong style={{ color: 'var(--c-success)' }}>{stats.dcPositive}</strong> · 부정 <strong style={{ color: 'var(--c-danger)' }}>{stats.dcNegative}</strong></p>
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
      <div className="panel-overview__analysis">
        <div className="panel-card panel-card--analysis">
          <h4 className="panel-card__title">🐟 수집 데이터 분석 · 요약</h4>
          <div className="panel-card__body">
            <p>크롤러로 수집한 YouTube·DCInside 데이터를 MiroFish AI로 분석·요약합니다.</p>
            <p className="panel-card__hint">엔티티 그래프 구축 후 AI 채팅으로 인사이트를 질의할 수 있습니다.</p>
            <button type="button" className="panel-card__btn" onClick={goAnalysis}>
              분석 페이지로 이동
            </button>
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
        <EmptyHint
          title="YouTube 수집 데이터 없음"
          description="상단 URL 검색에서 영상·채널 URL을 입력하면 즉시 분석할 수 있습니다. 주기적 수집은 YouTube 크롤러를 실행하세요."
        />
      )}
    </div>
  );
}

/* --- DCInside Panel --- */
function DCInsidePanel({ galleries }) {
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

function EmptyHint({ title, description, text }) {
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

function formatNaverFetchReason(reason) {
  if (!reason) return '';
  return reason
    .split(',')
    .map(token => token.trim())
    .filter(Boolean)
    .map(token => NAVER_FETCH_REASON_LABELS[token] || token)
    .join(', ');
}

function parseNaverReasonTokens(reason) {
  if (!reason) return [];
  return reason
    .split(',')
    .map(token => token.trim())
    .filter(Boolean);
}

function getNaverDiagnosticActions(tokens) {
  const actions = [];
  if (tokens.includes('cookie_not_set')) {
    actions.push('.env에 NAVER_CAFE_COOKIE를 추가하고 docker-compose up -d --build로 재시작하세요.');
  }
  if (tokens.includes('proxy_not_set')) {
    actions.push('사내망 환경이면 NAVER_CAFE_PROXY_URL을 설정하고 필요 시 사용자/비밀번호를 함께 지정하세요.');
  }
  if (tokens.includes('posts_found_but_comments_unavailable') || tokens.includes('content_found_but_comments_unavailable')) {
    actions.push('공개 글/댓글 허용 게시글 URL로 재시도하고 단건 URL(ArticleRead) 기준으로 확인하세요.');
  }
  if (tokens.includes('html_fetch_failed') || tokens.includes('api_fetch_failed') || tokens.includes('mobile_fetch_failed')) {
    actions.push('네트워크/차단 상태를 점검하고, 프록시 사용 시 인증 정보를 확인하세요.');
  }
  if (actions.length === 0) {
    actions.push('URL 접근 권한과 네트워크 상태를 확인한 뒤 다시 시도하세요.');
  }
  return actions;
}

export default Dashboard;
