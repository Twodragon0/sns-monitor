import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import axios from 'axios';
import './Dashboard.css';
import { API_BASE } from '../config';
import {
  loadResultsCache as _loadCache, saveResultsCache as _saveCache,
  trimResultForSummarize, detectPlatform,
} from '../utils/analysis';
import {
  OverviewPanel, GalleryMonitorPanel, YouTubePanel,
  DCInsidePanel, TwitterPanel, SocialPanel,
} from './dashboard/MonitorPanels';
import { AnalysisResult, AiCtaButton } from './dashboard/AnalysisResult';

const RESULTS_CACHE_KEY = 'sns-monitor-results';

function loadResultsCache() { return _loadCache(RESULTS_CACHE_KEY); }
function saveResultsCache(url, result) { _saveCache(RESULTS_CACHE_KEY, url, result); }

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
    const iv = setInterval(() => {
      if (document.visibilityState === 'visible') loadMonitorData();
    }, 60000);
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
          <span className="dash__monitoring-analysis-label">수집 데이터 분석 · 요약</span>
          <p className="dash__monitoring-analysis-desc">
            위 URL 분석과 크롤러로 쌓인 YouTube·DCInside 데이터를 한꺼번에 AI로 보내,
            엔티티 그래프와 AI 채팅으로 <strong>전체 패턴과 인사이트</strong>를 보는 심화 분석 기능입니다.
          </p>
          {analysisResult && (
            <p className="dash__monitoring-analysis-recent">
              최근 URL 분석: <strong>{PLATFORMS[analysisResult.platform]?.label || analysisResult.platform}</strong> — {analysisResult.title || analysisResult.gallery_name || analysisResult.gallery_id || '분석 결과'} ({formatNumber(analysisResult.total_posts ?? analysisResult.comment_count ?? (analysisResult.comments || analysisResult.posts || analysisResult.recent_videos || []).length)}건).
              위의 URL 분석 결과 카드에서 <strong>「AI 심화 분석」</strong> 버튼을 누르면, 이 대상이 자동으로 AI 분석에 연결됩니다.
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
            AI 분석 페이지로 이동
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
export default Dashboard;
