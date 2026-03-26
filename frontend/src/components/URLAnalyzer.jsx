import React, { useState, useCallback, useEffect, useMemo } from 'react';
import axios from 'axios';
import './URLAnalyzer.css';
import { API_BASE } from '../config';
import {
  loadResultsCache as _loadCache, saveResultsCache as _saveCache,
  trimResultForSummarize, detectPlatform,
} from '../utils/analysis';
import {
  PLATFORM_INFO, AnalysisResult, ThreadsPostBlock,
  DCInsideGalleryPosts, RedditSubredditPosts, RedditPostComments,
  TelegramMessages, YouTubeCommentsInline, TwitterReplies,
  GenericItemsAccordion, StatCard, formatNumber,
} from './url-analyzer/ResultComponents';

const RESULTS_CACHE_KEY = 'sns-analyzer-results';

function loadResultsCache() { return _loadCache(RESULTS_CACHE_KEY); }
function saveResultsCache(url, result) { _saveCache(RESULTS_CACHE_KEY, url, result); }

function URLAnalyzer() {
  const [url, setUrl] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [apiUsage, setApiUsage] = useState(null);
  const [showUsage, setShowUsage] = useState(false);
  const [dcOptions, setDcOptions] = useState({ fetchComments: true, maxCommentPosts: 5, maxComments: 500 });
  const [history, setHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('sns-analyzer-history') || '[]');
    } catch { return []; }
  });

  useEffect(() => {
    localStorage.setItem('sns-analyzer-history', JSON.stringify(history));
  }, [history]);

  // Fetch API usage stats
  const fetchApiUsage = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API_BASE}/api/platforms`, { timeout: 5000 });
      setApiUsage(data.api_usage || null);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchApiUsage(); }, [fetchApiUsage]);

  const detectedPlatform = detectPlatform(url);

  // 80% usage warning alerts
  const usageWarnings = useMemo(() => {
    if (!apiUsage) return [];
    const DISPLAY_NAMES = { naver_search: '네이버 검색', youtube: 'YouTube', reddit: 'Reddit' };
    return Object.entries(apiUsage)
      .filter(([, u]) => u.configured && u.daily_limit > 0 && (u.used_today / u.daily_limit) >= 0.8)
      .map(([key, u]) => ({
        name: DISPLAY_NAMES[key] || key,
        pct: Math.round((u.used_today / u.daily_limit) * 100),
        used: u.used_today,
        limit: u.daily_limit,
      }));
  }, [apiUsage]);

  const handleAnalyze = useCallback(async (e) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      // Append search query to URL for Naver Cafe
      let analyzeUrl = url.trim();
      if (searchQuery.trim() && detectPlatform(analyzeUrl) === 'naver_cafe') {
        const u = new URL(analyzeUrl);
        u.searchParams.set('q', searchQuery.trim());
        analyzeUrl = u.toString();
      }
      const options = {};
      if (detectPlatform(analyzeUrl) === 'dcinside') {
        options.fetch_comments = dcOptions.fetchComments;
        options.max_comment_posts = dcOptions.maxCommentPosts;
        options.max_comments = dcOptions.maxComments;
      }
      const response = await axios.post(`${API_BASE}/api/analyze/url`, { url: analyzeUrl, options }, { timeout: 300000 });
      const trimmedUrl = url.trim();
      setResult(response.data);
      saveResultsCache(trimmedUrl, response.data);
      setHistory(prev => [{
        url: trimmedUrl,
        platform: response.data.platform,
        title: response.data.title || response.data.gallery_id || response.data.subreddit || trimmedUrl,
        analyzed_at: response.data.analyzed_at,
      }, ...prev.filter(h => h.url !== trimmedUrl).slice(0, 9)]);
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Analysis failed';
      setError(
        !err.response && (err.message === 'Network Error' || err.code === 'ECONNABORTED')
          ? '서버 연결 실패 또는 요청 시간 초과입니다. 잠시 후 다시 시도해 주세요.'
          : msg
      );
    } finally {
      setLoading(false);
      fetchApiUsage(); // Refresh usage stats after analysis
    }
  }, [url, searchQuery, fetchApiUsage]);

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem(RESULTS_CACHE_KEY);
    setResult(null);
  };

  const openHistoryItem = (item) => {
    setUrl(item.url);
    const cache = loadResultsCache();
    setResult(cache.data[item.url] ?? null);
  };

  return (
    <div className="url-analyzer">
      <div className="analyzer-header">
        <h1>SNS URL Analyzer</h1>
        <p>Paste any supported URL to analyze content and sentiment</p>
      </div>

      <form className="analyzer-form" onSubmit={handleAnalyze}>
        <div className="url-input-wrapper">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://gall.dcinside.com/... 또는 지원 URL 붙여넣기"
            className="url-input"
            disabled={loading}
            aria-label="분석할 URL 입력"
          />
          {detectedPlatform && (
            <span
              className="platform-badge"
              style={{ backgroundColor: PLATFORM_INFO[detectedPlatform]?.color || '#666' }}
            >
              {PLATFORM_INFO[detectedPlatform]?.icon} {PLATFORM_INFO[detectedPlatform]?.name}
            </span>
          )}
        </div>
        <button type="submit" className="analyze-button" disabled={loading || !url.trim()}>
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </form>

      {detectedPlatform === 'naver_cafe' && (
        <div className="search-query-row">
          <label htmlFor="cafe-search" className="search-query-label">☕ 카페 내 검색</label>
          <input
            id="cafe-search"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="검색어 입력 (선택사항)"
            className="search-query-input"
            disabled={loading}
            onKeyDown={(e) => { if (e.key === 'Enter' && url.trim()) { e.preventDefault(); handleAnalyze(e); } }}
          />
          {searchQuery && (
            <button type="button" className="search-query-clear" onClick={() => setSearchQuery('')} title="검색어 지우기" aria-label="검색어 지우기">✕</button>
          )}
        </div>
      )}

      {detectedPlatform === 'dcinside' && !/board\/view/i.test(url) && (
        <div className="dc-options-row">
          <span className="dc-options-title">갤러리 목록 옵션</span>
          <label className="dc-option-check">
            <input
              type="checkbox"
              checked={dcOptions.fetchComments}
              onChange={(e) => setDcOptions(prev => ({ ...prev, fetchComments: e.target.checked }))}
              disabled={loading}
            />
            게시글 댓글 수집
          </label>
          {dcOptions.fetchComments && (
            <>
              <label className="dc-option-label">
                댓글 수집 글 수
                <select
                  value={dcOptions.maxCommentPosts}
                  onChange={(e) => setDcOptions(prev => ({ ...prev, maxCommentPosts: Number(e.target.value) }))}
                  disabled={loading}
                  className="dc-option-select"
                >
                  {[5, 10, 20, 30, 50].map(n => <option key={n} value={n}>{n}개</option>)}
                </select>
              </label>
              <label className="dc-option-label">
                글당 최대 댓글
                <select
                  value={dcOptions.maxComments}
                  onChange={(e) => setDcOptions(prev => ({ ...prev, maxComments: Number(e.target.value) }))}
                  disabled={loading}
                  className="dc-option-select"
                >
                  {[100, 200, 500, 1000].map(n => <option key={n} value={n}>{n}건</option>)}
                </select>
              </label>
            </>
          )}
        </div>
      )}

      {detectedPlatform === 'dcinside' && /board\/view/i.test(url) && (
        <div className="dc-options-row">
          <span className="dc-options-title">단일글 옵션</span>
          <label className="dc-option-label">
            최대 댓글 수
            <select
              value={dcOptions.maxComments}
              onChange={(e) => setDcOptions(prev => ({ ...prev, maxComments: Number(e.target.value) }))}
              disabled={loading}
              className="dc-option-select"
            >
              {[100, 200, 500, 1000].map(n => <option key={n} value={n}>{n}건</option>)}
            </select>
          </label>
        </div>
      )}

      <div className="supported-platforms" role="list" aria-label="지원 플랫폼">
        {Object.entries(PLATFORM_INFO).map(([key, info]) => (
          <span key={key} className="platform-tag" style={{ borderColor: info.color }} role="listitem">
            {info.icon} {info.name}
          </span>
        ))}
        {apiUsage && (
          <button
            type="button"
            className="api-usage-toggle"
            onClick={() => setShowUsage(v => !v)}
            title="API 사용량 보기"
          >
            {showUsage ? '▲' : '▼'} API
          </button>
        )}
      </div>

      {showUsage && apiUsage && (
        <div className="api-usage-panel">
          <h4 className="api-usage-title">API 사용량</h4>
          {Object.entries(apiUsage).map(([key, usage]) => {
            const pct = usage.daily_limit > 0 ? (usage.used_today / usage.daily_limit) * 100 : 0;
            const barColor = pct > 80 ? '#ef4444' : pct > 50 ? '#f59e0b' : '#22c55e';
            return (
              <div key={key} className="api-usage-item">
                <div className="api-usage-header">
                  <span className="api-usage-name">
                    {key === 'naver_search' ? '네이버 검색' : key}
                    {!usage.configured && <span className="api-usage-badge api-usage-badge--off">미설정</span>}
                    {usage.configured && <span className="api-usage-badge api-usage-badge--on">활성</span>}
                    <span className="api-usage-storage">{usage.storage === 'redis' ? '(Redis)' : '(Memory)'}</span>
                  </span>
                  <span className="api-usage-count">{usage.used_today.toLocaleString()} / {usage.daily_limit.toLocaleString()}</span>
                </div>
                <div className="api-usage-bar-bg">
                  <div className="api-usage-bar-fill" style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: barColor }} />
                </div>
                <div className="api-usage-footer">
                  <span>잔여: {usage.remaining.toLocaleString()}건</span>
                  <span>{usage.date}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {usageWarnings.length > 0 && (
        <div className="api-usage-warning-banner">
          {usageWarnings.map(w => (
            <div key={w.name} className="api-usage-warning-item">
              ⚠ {w.name} API 사용량 {w.pct}% ({w.used.toLocaleString()}/{w.limit.toLocaleString()}) — 한도 초과 시 분석이 실패할 수 있습니다.
            </div>
          ))}
        </div>
      )}

      {error && <div className="error-message" role="alert" aria-live="assertive">{error}</div>}

      {loading && (
        <div className="loading-container" aria-live="polite" aria-label="분석 중">
          <div className="loading-spinner" />
          <p>Analyzing content...</p>
        </div>
      )}

      <div aria-live="polite" aria-atomic="false">
        {result && <AnalysisResult result={result} />}
      </div>

      {history.length > 0 && (
        <div className="analysis-history">
          <div className="history-header">
            <h3>Recent Analyses</h3>
            <button className="clear-history-button" onClick={clearHistory} aria-label="분석 기록 전체 삭제">Clear</button>
          </div>
          <ul>
            {history.map((item, idx) => (
              <li key={idx}>
                <button type="button" className="history-item-button" onClick={() => openHistoryItem(item)} aria-label={`${item.title} 분석 결과 불러오기`}>
                  <span className="history-platform" style={{
                    color: PLATFORM_INFO[item.platform]?.color || '#666'
                  }} aria-hidden="true">
                    {PLATFORM_INFO[item.platform]?.icon}
                  </span>
                  <span className="history-title">{item.title}</span>
                  <span className="history-time">
                    {item.analyzed_at ? new Date(item.analyzed_at).toLocaleTimeString('ko-KR') : ''}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default URLAnalyzer;
