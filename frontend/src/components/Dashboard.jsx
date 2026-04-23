import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import axios from 'axios';
import './Dashboard.css';
import { API_BASE } from '../config';
import {
  loadResultsCache as _loadCache, saveResultsCache as _saveCache,
  trimResultForSummarize, detectPlatform,
} from '../utils/analysis';
import { PLATFORMS, formatNumber } from '../constants/platforms';
import {
  OverviewPanel, YouTubePanel,
  DCInsidePanel, TwitterPanel, SocialPanel,
  ScanHistoryPanel,
} from './dashboard/MonitorPanels';
import { AnalysisResult } from './dashboard/AnalysisResult';

const RESULTS_CACHE_KEY = 'sns-monitor-results';

function loadResultsCache() { return _loadCache(RESULTS_CACHE_KEY); }
function saveResultsCache(url, result) { _saveCache(RESULTS_CACHE_KEY, url, result); }


/* ============================================================
   usePlaceholderRotation Hook
   ============================================================ */
const PLACEHOLDER_URLS = [
  'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
  'https://gall.dcinside.com/mgallery/board/list/?id=example',
  'https://www.reddit.com/r/korea/comments/...',
  'https://t.me/example_channel',
  'https://cafe.naver.com/example',
  'https://x.com/username/status/123456',
  'https://www.instagram.com/p/ABC123/',
  'https://www.threads.net/@username/post/ABC',
];

function usePlaceholderRotation(isActive) {
  const [index, setIndex] = useState(0);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    if (!isActive) return;
    const iv = setInterval(() => {
      setFading(true);
      setTimeout(() => {
        setIndex(prev => (prev + 1) % PLACEHOLDER_URLS.length);
        setFading(false);
      }, 400);
    }, 3000);
    return () => clearInterval(iv);
  }, [isActive]);

  return { placeholder: PLACEHOLDER_URLS[index], fading };
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
  const { placeholder: rotatePlaceholder, fading: placeholderFading } = usePlaceholderRotation(!url);

  // --- Load monitoring data ---
  // 한 번만 에러 토스트를 띄워 스팸 방지 (60초 주기 재조회마다 알림 울리지 않도록)
  const monitorErrorNotifiedRef = useRef(false);
  const loadMonitorData = useCallback(async () => {
    const okOrThrow = (r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    };
    const [channelsRes, galleriesRes, creatorsRes] = await Promise.allSettled([
      fetch(`${API_BASE}/api/channels`).then(okOrThrow),
      fetch(`${API_BASE}/api/dcinside/galleries`, { signal: AbortSignal.timeout(10000) }).then(okOrThrow),
      fetch(`${API_BASE}/api/vuddy/creators`).then(okOrThrow),
    ]);

    const failures = [];
    const pick = (res, label, key) => {
      if (res.status === 'fulfilled') return res.value[key] || [];
      failures.push(label);
      return [];
    };

    setMonitorData({
      channels: pick(channelsRes, 'YouTube 채널', 'channels'),
      galleries: pick(galleriesRes, 'DCInside 갤러리', 'galleries'),
      creators: pick(creatorsRes, '크리에이터', 'creators'),
      loading: false,
    });

    // 세 엔드포인트 모두 실패 → 백엔드 오프라인 가능성 → 한 번만 알림
    // 부분 실패 또는 완전 복구 → 플래그 초기화 (다음 전체 실패 시 다시 알림)
    if (failures.length === 3) {
      if (!monitorErrorNotifiedRef.current) {
        monitorErrorNotifiedRef.current = true;
        onShowError?.(`모니터링 데이터 로드 실패 (${failures.join(', ')}). 백엔드 상태와 네트워크를 확인해 주세요.`);
      }
    } else {
      // 부분 복구 또는 완전 복구 → 다음 전체 실패 때 다시 알릴 수 있도록 플래그 초기화
      monitorErrorNotifiedRef.current = false;
      if (failures.length > 0) {
        // 부분 실패는 개발자 콘솔에만 남김
        console.warn('[Dashboard] partial monitor data failure:', failures);
      }
    }
  }, [onShowError]);

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
      if (!err.response && err.code === 'ECONNABORTED') {
        setAnalysisError('요청 시간이 초과되었습니다. URL 대상의 데이터가 너무 크거나 서버가 응답하지 않습니다. 잠시 후 다시 시도해 주세요.');
      } else if (!err.response && (err.code === 'ERR_NETWORK' || err.message === 'Network Error')) {
        setAnalysisError('API 서버에 연결할 수 없습니다. Docker를 실행했는지 확인해 주세요. (docker-compose up -d)');
      } else if (err.response?.status === 429) {
        setAnalysisError('요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.');
      } else if (err.response?.status >= 500) {
        setAnalysisError(`서버 오류 (${err.response.status}): 백엔드에서 분석 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요. ${msg ? `(${msg})` : ''}`);
      } else {
        setAnalysisError(msg);
      }
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
      if (!err.response && err.code === 'ECONNABORTED') {
        setAnalysisError('요약 요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.');
      } else if (!err.response && (err.code === 'ERR_NETWORK' || err.message === 'Network Error')) {
        setAnalysisError('API 서버에 연결할 수 없습니다. Docker를 실행했는지 확인해 주세요. (docker-compose up -d)');
      } else if (err.response?.status === 413) {
        setAnalysisError('요청 크기가 서버 제한을 초과했습니다.');
      } else if (err.response?.status === 429) {
        setAnalysisError('요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.');
      } else {
        setAnalysisError(err.response?.data?.error || err.message || '요약 실패');
      }
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
              className={`dash__search-input${placeholderFading ? ' dash__search-input--ph-fade' : ''}`}
              type="url"
              value={url}
              onChange={e => { setUrl(e.target.value); setAnalysisError(null); }}
              onKeyDown={e => { if (e.key === 'Enter' && url.trim() && !analysisLoading) handleAnalyze(e); }}
              placeholder={rotatePlaceholder}
              disabled={analysisLoading}
              aria-label="분석할 URL"
            />
            {detectedPlatform && (
              <span
                className="dash__search-badge"
                style={{ '--pf-color': PLATFORMS[detectedPlatform]?.color }}
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
        {analysisLoading && (
          <div className="dash__search-progress">
            <div className="dash__search-progress-bar" />
          </div>
        )}

        <div className="dash__platforms">
          {Object.entries(PLATFORMS).map(([k, v]) => (
            <span key={k} className="dash__platform-tag" style={{ '--pf-color': v.color }}>
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
              {history.slice(0, 6).map((h, i) => {
                const pInfo = PLATFORMS[h.platform];
                const now = new Date();
                const analyzedAt = h.analyzed_at ? new Date(h.analyzed_at) : null;
                let timeLabel = '';
                if (analyzedAt) {
                  const diffMs = now - analyzedAt;
                  const diffMin = Math.floor(diffMs / 60000);
                  const diffHr = Math.floor(diffMin / 60);
                  const diffDay = Math.floor(diffHr / 24);
                  if (diffMin < 1) timeLabel = '방금 전';
                  else if (diffMin < 60) timeLabel = `${diffMin}분 전`;
                  else if (diffHr < 24) timeLabel = `${diffHr}시간 전`;
                  else if (diffDay < 7) timeLabel = `${diffDay}일 전`;
                  else timeLabel = analyzedAt.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
                }
                return (
                  <li
                    key={h.url || i}
                    className="dash__history-item"
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') e.currentTarget.click(); }}
                    onClick={() => {
                      setUrl(h.url);
                      const cache = loadResultsCache();
                      const cached = cache.data[h.url];
                      setAnalysisResult(cached ?? null);
                      setAnalysisSummary(null);
                    }}
                  >
                    <span
                      className="dash__history-icon"
                      style={pInfo?.color ? { '--pf-color': pInfo.color } : undefined}
                      title={pInfo?.label || h.platform || ''}
                    >
                      {pInfo?.icon || '🔗'}
                    </span>
                    <span className="dash__history-title">{h.title}</span>
                    {pInfo && (
                      <span
                        className="dash__history-badge"
                        style={{ '--pf-color': pInfo.color, '--pf-color-soft': pInfo.color + '22' }}
                      >
                        {pInfo.label}
                      </span>
                    )}
                    <span className="dash__history-time" title={analyzedAt?.toLocaleString('ko-KR') || ''}>
                      {timeLabel}
                    </span>
                  </li>
                );
              })}
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

        <nav className="dash__tabs" aria-label="플랫폼 탭" role="tablist">
          {TABS.map(t => (
            <button
              key={t.id}
              id={`tab-${t.id}`}
              className={`dash__tab ${activeTab === t.id ? 'dash__tab--active' : ''}`}
              onClick={() => setActiveTab(t.id)}
              aria-selected={activeTab === t.id}
              aria-controls="dash-tabpanel"
              role="tab"
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div id="dash-tabpanel" className="dash__panel" role="tabpanel" aria-labelledby={`tab-${activeTab}`}>
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

      {/* ===== SCAN HISTORY ===== */}
      <section className="dash__scan-history" aria-labelledby="scan-history-title">
        <h2 id="scan-history-title" className="dash__section-title dash__scan-history-title">
          스캔 기록
        </h2>
        <ScanHistoryPanel />
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
                  key={c.name || handle}
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

export default Dashboard;
