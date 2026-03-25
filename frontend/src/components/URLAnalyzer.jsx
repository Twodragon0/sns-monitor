import React, { useState, useCallback, useEffect, useMemo } from 'react';
import axios from 'axios';
import DOMPurify from 'dompurify';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import './URLAnalyzer.css';
import { API_BASE } from '../config';
import {
  NAVER_FETCH_STATUS_LABELS, NAVER_FETCH_REASON_LABELS,
  loadResultsCache as _loadCache, saveResultsCache as _saveCache,
  trimResultForSummarize, detectPlatform,
  formatNaverFetchReason, parseNaverReasonTokens, getNaverDiagnosticActions,
} from '../utils/analysis';

const PLATFORM_INFO = {
  youtube: { name: 'YouTube', color: '#FF0000', icon: '▶' },
  dcinside: { name: 'DCInside', color: '#2B65EC', icon: '📋' },
  naver_cafe: { name: '네이버 카페', color: '#03c75a', icon: '☕' },
  reddit: { name: 'Reddit', color: '#FF4500', icon: '🔗' },
  telegram: { name: 'Telegram', color: '#0088cc', icon: '✈' },
  kakao: { name: 'Kakao', color: '#FEE500', icon: '💬' },
  twitter: { name: 'X (Twitter)', color: '#000000', icon: '𝕏' },
  instagram: { name: 'Instagram', color: '#E4405F', icon: '📸' },
  threads: { name: 'Threads', color: '#000000', icon: '🧵' },
  tiktok: { name: 'TikTok', color: '#000000', icon: '🎵' },
  vuddy: { name: 'Vuddy', color: '#7C3AED', icon: '🎁' },
};

const SENTIMENT_COLORS = {
  positive: '#4CAF50',
  neutral: '#9E9E9E',
  negative: '#F44336',
};

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
            <button type="button" className="search-query-clear" onClick={() => setSearchQuery('')} title="검색어 지우기">✕</button>
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

      <div className="supported-platforms">
        {Object.entries(PLATFORM_INFO).map(([key, info]) => (
          <span key={key} className="platform-tag" style={{ borderColor: info.color }}>
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

      {error && <div className="error-message">{error}</div>}

      {loading && (
        <div className="loading-container">
          <div className="loading-spinner" />
          <p>Analyzing content...</p>
        </div>
      )}

      {result && <AnalysisResult result={result} />}

      {history.length > 0 && (
        <div className="analysis-history">
          <div className="history-header">
            <h3>Recent Analyses</h3>
            <button className="clear-history-button" onClick={clearHistory}>Clear</button>
          </div>
          <ul>
            {history.map((item, idx) => (
              <li key={idx} onClick={() => openHistoryItem(item)}>
                <span className="history-platform" style={{
                  color: PLATFORM_INFO[item.platform]?.color || '#666'
                }}>
                  {PLATFORM_INFO[item.platform]?.icon}
                </span>
                <span className="history-title">{item.title}</span>
                <span className="history-time">
                  {item.analyzed_at ? new Date(item.analyzed_at).toLocaleTimeString('ko-KR') : ''}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ThreadsPostBlock({ embedHtml, url, replies, description, content, result }) {
  const embedRef = React.useRef(null);
  const [showAllReplies, setShowAllReplies] = React.useState(false);

  React.useEffect(() => {
    if (!embedHtml) return;
    const container = embedRef.current;
    if (!container) return;
    if (container.querySelector('[data-text-post-permalink]')) return;
    const sanitized = DOMPurify.sanitize(embedHtml, {
      ADD_TAGS: ['blockquote'],
      ADD_ATTR: ['data-text-post-permalink', 'data-text-post-version', 'class', 'style', 'cite'],
      FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form'],
    });
    container.innerHTML = sanitized;
    const existing = document.querySelector('script[src="https://www.threads.com/embed.js"]');
    if (existing) return;
    const script = document.createElement('script');
    script.src = 'https://www.threads.com/embed.js';
    script.async = true;
    document.body.appendChild(script);
    return () => {
      if (script.parentNode) script.parentNode.removeChild(script);
    };
  }, [embedHtml]);

  const replyList = Array.isArray(replies) ? replies : [];
  const hasEmbed = !!embedHtml?.trim();
  const postContent = content || description || '';
  const displayReplies = showAllReplies ? replyList : replyList.slice(0, 20);
  const hasToken = result?.source === 'threads_api';

  return (
    <div className="result-content threads-post-block">
      <h3>게시글</h3>
      {hasEmbed ? (
        <div ref={embedRef} className="threads-embed-wrap" />
      ) : postContent ? (
        <div className="threads-post-content">
          <p className="threads-post-text">{postContent}</p>
        </div>
      ) : (
        <p className="threads-no-embed">게시글 내용을 불러오지 못했습니다. 원문 링크에서 확인해 주세요.</p>
      )}
      {url && (
        <a href={url} target="_blank" rel="noopener noreferrer" className="result-origin-link">
          Threads 원문 보기 →
        </a>
      )}
      <h3>
        댓글 {replyList.length > 0
          ? `(${replyList.length}${result?.reply_count > replyList.length ? ` / ${result.reply_count}` : ''})`
          : result?.reply_count > 0 ? `(${result.reply_count}건)` : ''}
      </h3>
      {replyList.length > 0 ? (
        <>
          <ul className="comments-sublist">
            {displayReplies.map((r, i) => (
              <li key={i} className="comment-item">
                <span className="comment-meta-inline">
                  {r.author && <span className="comment-author">{r.author}</span>}
                  {r.date && <span className="comment-date">{r.date}</span>}
                </span>
                <span className="comment-text">{r.text || r.title || ''}</span>
              </li>
            ))}
          </ul>
          {replyList.length > 20 && !showAllReplies && (
            <button className="show-more-btn" onClick={() => setShowAllReplies(true)}>
              나머지 {replyList.length - 20}개 댓글 더 보기
            </button>
          )}
        </>
      ) : !hasToken ? (
        <div className="threads-replies-hint">
          <p>THREADS_ACCESS_TOKEN을 설정하면 댓글(답글)을 수집할 수 있습니다.</p>
          <p className="threads-hint-detail">
            Meta Developer 앱에서 Threads API 권한(threads_basic, threads_read_replies)을 활성화하고,
            발급받은 Access Token을 .env에 설정하세요.
          </p>
        </div>
      ) : (
        <p className="threads-replies-hint">이 게시글에 댓글이 없습니다.</p>
      )}
    </div>
  );
}

function AnalysisResult({ result }) {
  const platform = PLATFORM_INFO[result.platform] || { name: result.platform, color: '#666' };
  const analysis = result.analysis;
  const hasYoutubeComments =
    result.platform === 'youtube' && Array.isArray(result.comments) && result.comments.length > 0;
  const hasTwitterComments =
    result.platform === 'twitter' && result.type === 'tweet' && Array.isArray(result.comments) && result.comments.length > 0;
  // When YouTube or Twitter has dedicated comment sections, exclude comments from generic items
  const items = (hasYoutubeComments || hasTwitterComments)
    ? (result.posts || result.recent_videos || [])
    : (result.comments || result.replies || result.posts || result.recent_videos || []);
  const isNaverSinglePost = result.platform === 'naver_cafe' && result.type === 'post';
  const naverFetchStatus = result.fetch_status || 'ok';
  const naverFetchReason = result.fetch_reason || '';
  const naverReasonTokens = parseNaverReasonTokens(naverFetchReason);
  const naverFetchReasonLabel = formatNaverFetchReason(naverFetchReason);
  const naverFetchStatusLabel = NAVER_FETCH_STATUS_LABELS[naverFetchStatus] || naverFetchStatus;
  const naverActionItems = getNaverDiagnosticActions(naverReasonTokens);
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);

  const handleSummarize = async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const payload = trimResultForSummarize(result);
      const resp = await axios.post(`${API_BASE}/api/analyze/summarize`, { result: payload }, { timeout: 60000 });
      setSummary(resp.data);
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Summarization failed';
      setSummaryError(err.response?.status === 413 ? 'Request too large. Payload was trimmed; try again.' : msg);
    } finally {
      setSummaryLoading(false);
    }
  };

  const sentimentData = analysis ? [
    { name: 'Positive', value: analysis.sentiment.positive, color: SENTIMENT_COLORS.positive },
    { name: 'Neutral', value: analysis.sentiment.neutral, color: SENTIMENT_COLORS.neutral },
    { name: 'Negative', value: analysis.sentiment.negative, color: SENTIMENT_COLORS.negative },
  ] : [];

  const keywordData = analysis?.top_keywords?.slice(0, 10) || [];

  return (
    <div className="analysis-result" role="region" aria-label="분석 결과">
      <div className="result-header">
        <div className="result-platform" style={{ backgroundColor: platform.color }}>
          {platform.name}
        </div>
        <h2>{result.title || result.gallery_name || result.gallery_id || result.subreddit || result.channel_name || result.username || 'Analysis Result'}</h2>
        {result.analyzed_at && (
          <span className="result-time">
            {new Date(result.analyzed_at).toLocaleString('ko-KR')}
          </span>
        )}
        {isNaverSinglePost && (
          <div className="naver-result-badges">
            {result.login_verified && (
              <span className="naver-result-badge naver-result-badge--login" title="로그인된 상태로 수집됨">로그인됨</span>
            )}
            <a href={result.url || result.source_url} target="_blank" rel="noopener noreferrer" className="naver-result-badge naver-result-badge--link">원문 URL</a>
            <span className="naver-result-badge">댓글 {formatNumber(result.comment_count ?? 0)}</span>
            {naverFetchStatus !== 'ok' && (
              <span className="naver-result-badge naver-result-badge--warn">
                {naverFetchStatusLabel}: {naverFetchReasonLabel || naverFetchStatusLabel}
              </span>
            )}
          </div>
        )}
      </div>

      {isNaverSinglePost && naverFetchStatus !== 'ok' && (
        <div className="naver-diagnostic-panel" role="status" aria-live="polite">
          <strong className="naver-diagnostic-panel__title">네이버 카페 진단</strong>
          <p className="naver-diagnostic-panel__summary">
            현재 상태: {naverFetchStatusLabel}
          </p>
          {naverFetchReasonLabel && (
            <p className="naver-diagnostic-panel__reasons">원인: {naverFetchReasonLabel}</p>
          )}
          {naverActionItems.length > 0 && (
            <ul className="naver-diagnostic-panel__actions">
              {naverActionItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {result.platform === 'naver_cafe' && naverFetchStatus !== 'ok' && (
        <div className="naver-hint-block" role="status" title={naverFetchReasonLabel}>
          <p className="naver-hint-block__status">
            ☕ 네이버 카페: {naverFetchStatusLabel}
            {naverFetchReasonLabel && (
              <span className="naver-hint-block__reasons"> — {naverFetchReasonLabel}</span>
            )}
          </p>
          <p className="naver-hint-block__action">
            <strong>수집하려면:</strong> .env에 <code>NAVER_CAFE_COOKIE</code>를 넣고 <code>docker compose up -d --build</code>로 재시작하세요. (필요 시 <code>NAVER_CAFE_PROXY_URL</code>도 설정)
          </p>
        </div>
      )}

      {result.platform === 'reddit' && result.fetch_status === 'blocked' && (
        <div className="reddit-hint-block" role="status">
          <p className="reddit-hint-block__status">🔗 Reddit: API 접근이 차단되었습니다.</p>
          <p className="reddit-hint-block__action">
            {result.description || 'Reddit이 비인증 요청을 막고 있습니다. .env에 REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET을 설정한 뒤 docker compose up -d --build로 재시작하세요.'}
          </p>
        </div>
      )}

      <div className="result-stats">
        {result.view_count != null && <StatCard label="Views" value={formatNumber(result.view_count)} />}
        {result.like_count != null && <StatCard label="Likes" value={formatNumber(result.like_count)} />}
        {result.recommend != null && <StatCard label="추천" value={formatNumber(result.recommend)} />}
        {result.comment_count != null && <StatCard label="Comments" value={formatNumber(result.comment_count)} />}
        {result.subscriber_count != null && <StatCard label="Subscribers" value={formatNumber(result.subscriber_count)} />}
        {result.video_count != null && <StatCard label="Videos" value={formatNumber(result.video_count)} />}
        {result.subscribers != null && <StatCard label="Members" value={formatNumber(result.subscribers)} />}
        {result.active_users != null && <StatCard label="Active" value={formatNumber(result.active_users)} />}
        {result.total_posts != null && <StatCard label="Posts" value={formatNumber(result.total_posts)} />}
        {result.total_messages != null && <StatCard label="Messages" value={formatNumber(result.total_messages)} />}
        {result.score != null && <StatCard label="Score" value={formatNumber(result.score)} />}
        {result.follower_count != null && <StatCard label="Followers" value={formatNumber(result.follower_count)} />}
        {result.following_count != null && <StatCard label="Following" value={formatNumber(result.following_count)} />}
        {result.tweet_count != null && <StatCard label="Tweets" value={formatNumber(result.tweet_count)} />}
        {result.retweet_count != null && <StatCard label="Retweets" value={formatNumber(result.retweet_count)} />}
        {result.reply_count != null && <StatCard label="Replies" value={formatNumber(result.reply_count)} />}
      </div>

      {result.comment_fetch_note && (
        <div className="comment-fetch-note">{result.comment_fetch_note}</div>
      )}

      <div className="ai-summary-section">
        <button
          className="summarize-button"
          onClick={handleSummarize}
          disabled={summaryLoading}
        >
          {summaryLoading ? '분석 중...' : 'AI 요약'}
        </button>
        <button
          className="summarize-button"
          style={{ marginLeft: '8px', backgroundColor: '#6366f1' }}
          onClick={() => {
            const payload = trimResultForSummarize(result);
            sessionStorage.setItem('urlAnalysisResult', JSON.stringify(payload));
            window.history.pushState({}, '', '/analysis');
            window.dispatchEvent(new PopStateEvent('popstate'));
          }}
        >
          AI 심화 분석
        </button>
        {summaryError && <div className="error-message">{summaryError}</div>}
        {summary && (
          <div className="summary-content">
            <div className="summary-source">
              {summary.source === 'mirofish'
                ? 'AI 분석'
                : summary.source === 'anthropic'
                ? 'Claude AI'
                : summary.source === 'openai' || summary.source === 'openai_oauth'
                ? 'ChatGPT'
                : '로컬 분석'}
              {summary.model && <span style={{ fontSize: '11px', marginLeft: '6px', color: '#888' }}>({summary.model})</span>}
            </div>
            <div className="summary-text">{summary.summary}</div>
          </div>
        )}
      </div>

      {(result.platform === 'dcinside' || result.platform === 'naver_cafe') && result.type === 'post' && (
        <div className="result-content result-description">
          {result.content && (
            <>
              <h3>본문</h3>
              <div className="result-content-body">{result.content}</div>
            </>
          )}
          {result.url && (
            <a href={result.url} target="_blank" rel="noopener noreferrer" className="result-origin-link">
              원문 보기 →
            </a>
          )}
        </div>
      )}

      {result.platform === 'threads' && result.type === 'post' && (
        <ThreadsPostBlock
          embedHtml={result.embed_html}
          url={result.url}
          replies={result.replies}
          description={result.description}
          content={result.content}
          result={result}
        />
      )}

      {result.description && !(result.platform === 'threads' && result.type === 'post') && (
        <div className="result-description">
          <h3>설명</h3>
          <p>{result.description}</p>
          {result.platform === 'instagram' && result.url && (
            <a href={result.url} target="_blank" rel="noopener noreferrer" className="result-origin-link">
              Instagram 원문 보기 →
            </a>
          )}
        </div>
      )}

      {analysis && (
        <div className="sentiment-section">
          <h3>Sentiment Analysis ({analysis.total} items)</h3>
          <div className="charts-row">
            {sentimentData.length > 0 && (
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={sentimentData.filter(d => d.value > 0)}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {sentimentData.map((entry, index) => (
                        <Cell key={index} fill={entry.color} />
                      ))}
                    </Pie>
                    <Legend />
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
            {keywordData.length > 0 && (
              <div className="chart-container">
                <h4>Top Keywords</h4>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={keywordData} layout="vertical">
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="word" width={80} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#667eea" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
          <div className="sentiment-overall">
            Overall: <span className={`sentiment-${analysis.overall}`}>{analysis.overall}</span>
          </div>
        </div>
      )}

      {(result.platform === 'dcinside' || result.platform === 'naver_cafe') && result.type === 'gallery' && result.posts?.length > 0 && (
        <DCInsideGalleryPosts
          posts={result.posts}
          totalPosts={result.total_posts}
          loginVerified={result.login_verified}
          isNaverCafe={result.platform === 'naver_cafe'}
          searchQuery={result.search_query}
        />
      )}

      {result.platform === 'naver_cafe' && !result.login_verified && result.posts?.length > 0 && !(result.posts.some(p => p.comments?.length > 0)) && (
        <div className="naver-cookie-hint" role="status">
          <p>
            <strong>☕ 댓글을 수집하려면 로그인 쿠키가 필요합니다.</strong>
          </p>
          <p>
            <code>.env</code> 파일에 <code>NAVER_CAFE_COOKIE</code>를 설정하고 재시작하면 각 게시글의 댓글도 함께 수집됩니다.
            자세한 설정 방법은 <code>scripts/naver_cookie_helper.html</code>을 참고하세요.
          </p>
        </div>
      )}

      {result.platform === 'reddit' && result.type === 'subreddit' && result.posts?.length > 0 && (
        <RedditSubredditPosts posts={result.posts} totalPosts={result.total_posts} />
      )}

      {result.platform === 'reddit' && result.type === 'post' && result.comments?.length > 0 && (
        <RedditPostComments result={result} />
      )}

      {/* YouTube: 단일 영상/채널 모두 댓글 접기/펼치기 지원 */}
      {hasYoutubeComments && (
        <YouTubeCommentsInline
          comments={result.comments}
          totalComments={result.comment_count}
        />
      )}

      {/* Twitter/X: 트윗 댓글(리플라이) */}
      {(hasTwitterComments || (result.platform === 'twitter' && result.type === 'tweet' && (result.reply_count > 0 || result.comment_count > 0))) && (
        <TwitterReplies
          comments={result.comments || []}
          replyCount={result.reply_count || result.comment_count || (result.comments || []).length}
        />
      )}

      {result.platform === 'telegram' && result.posts?.length > 0 && (
        <TelegramMessages messages={result.posts} totalMessages={result.total_messages} />
      )}

      {!((result.platform === 'dcinside' || result.platform === 'naver_cafe') && result.type === 'gallery') && !(result.platform === 'reddit' && (result.type === 'subreddit' || result.type === 'post')) && !(result.platform === 'telegram') && !(result.platform === 'threads' && result.type === 'post') && !(result.platform === 'twitter' && result.type === 'tweet') && items.length > 0 && (
        <GenericItemsAccordion items={items} result={result} />
      )}
    </div>
  );
}

function sortComments(comments, order) {
  if (!comments?.length) return comments || [];
  const list = [...comments];
  if (order === '최신순' && list.some(c => c.date)) {
    list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  }
  return list;
}

function sortYoutubeCommentsInline(comments, order) {
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

function DCInsideGalleryPosts({ posts, totalPosts, loginVerified, isNaverCafe, searchQuery }) {
  const [expandedNo, setExpandedNo] = useState(null);
  const [showAllComments, setShowAllComments] = useState(false);
  const [commentSort, setCommentSort] = useState('등록순');
  const [commentVisibleCounts, setCommentVisibleCounts] = useState({});
  const COMMENT_PAGE_SIZE = 10;

  const showMoreComments = (postKey) => {
    setCommentVisibleCounts(prev => ({
      ...prev,
      [postKey]: (prev[postKey] || COMMENT_PAGE_SIZE) + COMMENT_PAGE_SIZE,
    }));
  };

  const allComments = posts.reduce((acc, post) => {
    (post.comments || []).forEach((c) => {
      acc.push({ ...c, postTitle: post.text || `게시글 #${post.number ?? ''}`, postUrl: post.url });
    });
    return acc;
  }, []);

  const sortedAllComments = sortComments(allComments, commentSort);
  const totalCommentCount = allComments.length;
  const postsWithComments = posts.filter((p) => (p.comments?.length || 0) > 0 || (p.comment_count || 0) > 0).length;

  const listLabel = totalPosts != null && totalPosts > posts.length && isNaverCafe
    ? `수집 ${posts.length}건 / 전체 약 ${formatNumber(totalPosts)}건`
    : `${posts.length}건`;

  return (
    <div className="items-section dcinside-posts-section">
      <div className="dcinside-posts-section__head">
        <h3>
          게시글 목록 ({listLabel})
          {isNaverCafe && loginVerified && (
            <span className="naver-login-badge" title="로그인된 상태로 수집됨">로그인됨</span>
          )}
        </h3>
        {searchQuery && (
          <p className="dcinside-posts-section__search-query">
            🔍 검색: <strong>{searchQuery}</strong>
          </p>
        )}
        <p className="dcinside-posts-section__hint" aria-hidden="true">
          💬 각 항목을 클릭하면 댓글이 표시됩니다. (댓글 있는 글 {postsWithComments}건)
        </p>
      </div>

      {totalCommentCount > 0 && (
        <div className="comment-count-bar" aria-label="전체 댓글">
          <div className="comment-count-inner">
            <span className="comment-count-label">전체 댓글 {totalCommentCount}개 · 클릭 시 댓글 표시</span>
            <div className="comment-sort">
              {['등록순', '최신순', '답글순'].map((order) => (
                <button
                  key={order}
                  type="button"
                  className={`comment-sort-btn ${commentSort === order ? 'is-active' : ''}`}
                  onClick={() => setCommentSort(order)}
                  aria-pressed={commentSort === order}
                >
                  {order}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="comments-toggle comments-toggle--all"
              onClick={() => setShowAllComments((v) => !v)}
              aria-expanded={showAllComments}
            >
              {showAllComments ? '통합 댓글 접기' : '통합 보기'}
            </button>
          </div>
        </div>
      )}

      {showAllComments && sortedAllComments.length > 0 && (
        <div className="all-comments-box" aria-label="전체 댓글 통합">
          <ul className="comments-sublist comments-sublist--all">
            {sortedAllComments.map((c, i) => (
              <li key={i} className="comment-item">
                <span className="comment-meta">
                  [{c.postTitle}]
                  {c.postUrl && (
                    <a href={c.postUrl} target="_blank" rel="noopener noreferrer" className="comment-post-link">원문</a>
                  )}{' '}
                  <span className="comment-author">{c.author}</span>
                  {c.date && <span className="comment-date">{c.date}</span>}
                </span>
                <span className="comment-text">{c.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="items-list">
        {posts.slice(0, 50).map((post, idx) => {
          const postKey = post.number ?? post.post_id ?? idx;
          const hasComments = post.comments?.length > 0;
          const apiCommentCount = post.comment_count || 0;
          const displayCommentCount = hasComments ? post.comments.length : apiCommentCount;
          const isExpanded = expandedNo === postKey;
          const sortedPostComments = sortComments(post.comments, commentSort);
          return (
            <div key={postKey} className="item-card item-card--dcinside">
              {post.url ? (
                <a href={post.url} target="_blank" rel="noopener noreferrer" className="item-text item-text--link">
                  {post.text}
                </a>
              ) : (
                <div className="item-text">{post.text}</div>
              )}
              <div className="item-meta">
                {post.author && <span className="item-author">{post.author}</span>}
                {post.view_count != null && <span className="item-views">👁 {formatNumber(post.view_count)}</span>}
                {post.recommend != null && <span className="item-likes">👍 {formatNumber(post.recommend)}</span>}
                {displayCommentCount > 0 && <span className="item-comments">💬 {formatNumber(displayCommentCount)}</span>}
                {post.date && <span className="item-date">{post.date}</span>}
              </div>
              {post.search_snippet && (
                <p className="search-snippet">{post.search_snippet}</p>
              )}
              {post.url && (
                <a href={post.url} target="_blank" rel="noopener noreferrer" className="item-link">
                  원문 보기 →
                </a>
              )}
              {hasComments && (
                <div className="comment-wrap">
                  <div className="comment_count">
                    <button
                      type="button"
                      className="comments-toggle comments-toggle--post"
                      onClick={() => setExpandedNo(isExpanded ? null : postKey)}
                      aria-expanded={isExpanded}
                      aria-controls={`focus-cmt-${postKey}`}
                    >
                      💬 댓글 {post.comments.length}개 {isExpanded ? '접기 ▲' : '클릭 시 보기 ▼'}
                    </button>
                  </div>
                  {isExpanded && (
                    <ul
                      id={`focus-cmt-${postKey}`}
                      className="comments-sublist"
                      aria-label={`댓글 ${post.comments.length}개`}
                    >
                      {sortedPostComments.slice(0, commentVisibleCounts[postKey] || COMMENT_PAGE_SIZE).map((c, i) => (
                        <li key={i} className="comment-item">
                          <span className="comment-meta-inline">
                            <span className="comment-author">{c.author}</span>
                            {c.date && <span className="comment-date">{c.date}</span>}
                          </span>
                          <span className="comment-text">{c.text}</span>
                        </li>
                      ))}
                      {sortedPostComments.length > (commentVisibleCounts[postKey] || COMMENT_PAGE_SIZE) && (
                        <li className="comment-show-more">
                          <button
                            type="button"
                            className="comment-show-more-btn"
                            onClick={() => showMoreComments(postKey)}
                          >
                            더 보기 ({commentVisibleCounts[postKey] || COMMENT_PAGE_SIZE}/{sortedPostComments.length})
                          </button>
                        </li>
                      )}
                    </ul>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RedditSubredditPosts({ posts, totalPosts }) {
  const [expandedNo, setExpandedNo] = useState(null);
  const [commentVisibleCounts, setCommentVisibleCounts] = useState({});
  const COMMENT_PAGE_SIZE = 10;

  const showMoreComments = (postKey) => {
    setCommentVisibleCounts(prev => ({
      ...prev,
      [postKey]: (prev[postKey] || COMMENT_PAGE_SIZE) + COMMENT_PAGE_SIZE,
    }));
  };

  const postsWithComments = posts.filter(p => p.comments?.length > 0).length;

  return (
    <div className="items-section dcinside-posts-section">
      <div className="dcinside-posts-section__head">
        <h3>Posts ({posts.length}건{totalPosts > posts.length ? ` / 전체 ${totalPosts}건` : ''})</h3>
        <p className="dcinside-posts-section__hint" aria-hidden="true">
          💬 각 항목을 클릭하면 댓글이 표시됩니다. (댓글 있는 글 {postsWithComments}건)
        </p>
      </div>
      <div className="items-list">
        {posts.slice(0, 50).map((post, idx) => {
          const postKey = idx;
          const hasComments = post.comments?.length > 0;
          const isExpanded = expandedNo === postKey;
          return (
            <div key={postKey} className="item-card item-card--dcinside">
              {post.permalink ? (
                <a href={post.permalink} target="_blank" rel="noopener noreferrer" className="item-text item-text--link">
                  {post.text}
                </a>
              ) : (
                <div className="item-text">{post.text}</div>
              )}
              {post.selftext && <div className="item-selftext">{post.selftext}</div>}
              <div className="item-meta">
                {post.author && <span className="item-author">{post.author}</span>}
                {post.score != null && <span className="item-likes">⬆ {formatNumber(post.score)}</span>}
                {post.num_comments != null && <span className="item-comments">💬 {post.num_comments}</span>}
                {post.created_utc > 0 && (
                  <span className="item-date">{new Date(post.created_utc * 1000).toLocaleString('ko-KR')}</span>
                )}
              </div>
              {post.permalink && (
                <a href={post.permalink} target="_blank" rel="noopener noreferrer" className="item-link">
                  View →
                </a>
              )}
              {hasComments && (
                <div className="comment-wrap">
                  <div className="comment_count">
                    <button
                      type="button"
                      className="comments-toggle comments-toggle--post"
                      onClick={() => setExpandedNo(isExpanded ? null : postKey)}
                      aria-expanded={isExpanded}
                    >
                      💬 댓글 {post.comments.length}개 {isExpanded ? '접기 ▲' : '클릭 시 보기 ▼'}
                    </button>
                  </div>
                  {isExpanded && (
                    <ul className="comments-sublist">
                      {post.comments.slice(0, commentVisibleCounts[postKey] || COMMENT_PAGE_SIZE).map((c, i) => (
                        <li key={i} className="comment-item">
                          <span className="comment-meta-inline">
                            <span className="comment-author">{c.author}</span>
                            {c.score != null && <span className="comment-score">⬆ {c.score}</span>}
                          </span>
                          <span className="comment-text">{c.text}</span>
                        </li>
                      ))}
                      {post.comments.length > (commentVisibleCounts[postKey] || COMMENT_PAGE_SIZE) && (
                        <li className="comment-show-more">
                          <button
                            type="button"
                            className="comment-show-more-btn"
                            onClick={() => showMoreComments(postKey)}
                          >
                            더 보기 ({commentVisibleCounts[postKey] || COMMENT_PAGE_SIZE}/{post.comments.length})
                          </button>
                        </li>
                      )}
                    </ul>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RedditPostComments({ result }) {
  const [expanded, setExpanded] = useState(false);
  const [visibleCount, setVisibleCount] = useState(10);
  const [order, setOrder] = useState('등록순');
  const PAGE_SIZE = 10;

  const sorted = useMemo(() => {
    if (!result.comments?.length) return [];
    const list = [...result.comments];
    if (order === '최신순') list.sort((a, b) => (b.created_utc || 0) - (a.created_utc || 0));
    if (order === '좋아요순') list.sort((a, b) => (b.score || 0) - (a.score || 0));
    return list;
  }, [result.comments, order]);

  return (
    <div className="items-section">
      <div className="comment-count-bar">
        <div className="comment-count-inner">
          <span className="comment-count-label">💬 Comments ({sorted.length})</span>
          <div className="comment-sort">
            {['등록순', '최신순', '좋아요순'].map(o => (
              <button
                key={o}
                type="button"
                className={`comment-sort-btn ${order === o ? 'is-active' : ''}`}
                onClick={() => setOrder(o)}
              >
                {o}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="comments-toggle comments-toggle--all"
            onClick={() => setExpanded(v => !v)}
            aria-expanded={expanded}
          >
            {expanded ? '접기' : '펼치기'}
          </button>
        </div>
      </div>
      {expanded && (
        <ul className="comments-sublist">
          {sorted.slice(0, visibleCount).map((c, i) => (
            <li key={i} className="comment-item">
              <span className="comment-meta-inline">
                <span className="comment-author">{c.author}</span>
                {c.score != null && <span className="comment-score">⬆ {c.score}</span>}
                {c.created_utc > 0 && (
                  <span className="comment-date">{new Date(c.created_utc * 1000).toLocaleString('ko-KR')}</span>
                )}
              </span>
              <span className="comment-text">{c.text}</span>
            </li>
          ))}
          {sorted.length > visibleCount && (
            <li className="comment-show-more">
              <button
                type="button"
                className="comment-show-more-btn"
                onClick={() => setVisibleCount(v => v + PAGE_SIZE)}
              >
                더 보기 ({visibleCount}/{sorted.length})
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function TelegramMessages({ messages, totalMessages }) {
  const [expanded, setExpanded] = useState(false);
  const [visibleCount, setVisibleCount] = useState(20);
  const [order, setOrder] = useState('등록순');
  const PAGE_SIZE = 20;

  const sorted = useMemo(() => {
    if (!messages?.length) return [];
    const list = [...messages];
    if (order === '최신순' && list.some(m => m.date)) {
      list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    }
    return list;
  }, [messages, order]);

  const label = totalMessages ? `${messages.length}건 / 전체 ${formatNumber(totalMessages)}건` : `${messages.length}건`;

  return (
    <div className="items-section">
      <div className="comment-count-bar">
        <div className="comment-count-inner">
          <span className="comment-count-label">✈ 메시지 ({label})</span>
          <div className="comment-sort">
            {['등록순', '최신순'].map(o => (
              <button
                key={o}
                type="button"
                className={`comment-sort-btn ${order === o ? 'is-active' : ''}`}
                onClick={() => setOrder(o)}
              >
                {o}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="comments-toggle comments-toggle--all"
            onClick={() => setExpanded(v => !v)}
            aria-expanded={expanded}
          >
            {expanded ? '접기' : '펼치기'}
          </button>
        </div>
      </div>
      {expanded && (
        <div className="items-list">
          {sorted.slice(0, visibleCount).map((msg, idx) => (
            <div key={idx} className="item-card">
              <div className="item-text">{msg.text || ''}</div>
              <div className="item-meta">
                {msg.date && <span className="item-date">{msg.date}</span>}
                {msg.views && <span className="item-views">👁 {msg.views}</span>}
              </div>
            </div>
          ))}
          {sorted.length > visibleCount && (
            <button
              type="button"
              className="yt-show-more-btn"
              onClick={() => setVisibleCount(v => v + PAGE_SIZE)}
              style={{ margin: '12px auto', display: 'block' }}
            >
              더 보기 ({visibleCount}/{sorted.length})
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function YouTubeCommentsInline({ comments, totalComments }) {
  const [expandedGroups, setExpandedGroups] = useState(new Set());
  const [order, setOrder] = useState('등록순');
  const [visibleCounts, setVisibleCounts] = useState({});
  const PAGE_SIZE = 10;

  const showMore = (gi) => {
    setVisibleCounts(prev => ({
      ...prev,
      [gi]: (prev[gi] || PAGE_SIZE) + PAGE_SIZE,
    }));
  };

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
      const sortedList = sortYoutubeCommentsInline(list, order);
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

  const allExpanded = grouped.length > 0 && expandedGroups.size === grouped.length;
  const toggleAll = () => {
    if (allExpanded) {
      setExpandedGroups(new Set());
    } else {
      setExpandedGroups(new Set(grouped.map((_, i) => i)));
    }
  };
  const toggleGroup = (idx) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div className="items-section yt-comments-section">
      <div className="comment-count-bar" aria-label="YouTube 댓글">
        <div className="comment-count-inner">
          <span className="comment-count-label">💬 {label}</span>
          <div className="comment-sort">
            <span className="comment-sort-label">정렬</span>
            {['등록순', '최신순', '좋아요순'].map((orderLabel) => (
              <button
                key={orderLabel}
                type="button"
                className={`comment-sort-btn ${order === orderLabel ? 'is-active' : ''}`}
                onClick={() => setOrder(orderLabel)}
                aria-pressed={order === orderLabel}
              >
                {orderLabel}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="comments-toggle comments-toggle--all"
            onClick={toggleAll}
            aria-expanded={allExpanded}
          >
            {allExpanded ? '모두 접기' : '모두 펼치기'}
          </button>
        </div>
      </div>

      <div className="yt-accordion" aria-label="YouTube 댓글 목록">
        {grouped.map((group, gi) => {
          const isOpen = expandedGroups.has(gi);
          return (
            <div key={group.videoId || gi} className={`yt-accordion-item ${isOpen ? 'is-open' : ''}`}>
              <button
                type="button"
                className="yt-accordion-header"
                onClick={() => toggleGroup(gi)}
                aria-expanded={isOpen}
                aria-controls={`yt-cmt-${gi}`}
              >
                <span className="yt-accordion-icon">{isOpen ? '▾' : '▸'}</span>
                <span className="yt-accordion-title">{group.title}</span>
                <span className="yt-accordion-count">💬 {group.comments.length}</span>
                {group.videoId && (
                  <a
                    href={`https://www.youtube.com/watch?v=${group.videoId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="yt-accordion-link"
                    onClick={(e) => e.stopPropagation()}
                  >
                    원문 ↗
                  </a>
                )}
              </button>
              {isOpen && (
                <ul
                  id={`yt-cmt-${gi}`}
                  className="yt-accordion-body"
                  aria-label={`${group.title} 댓글 ${group.comments.length}개`}
                >
                  {group.comments.slice(0, visibleCounts[gi] || PAGE_SIZE).map((c, i) => (
                    <li key={i} className="yt-comment-row">
                      <div className="yt-comment-meta">
                        {c.author && <span className="yt-comment-author">{c.author}</span>}
                        {c.published_at && (
                          <span className="yt-comment-date">
                            {new Date(c.published_at).toLocaleDateString('ko-KR')}
                          </span>
                        )}
                        {c.like_count != null && c.like_count > 0 && (
                          <span className="yt-comment-like">👍 {formatNumber(c.like_count)}</span>
                        )}
                      </div>
                      <div className="yt-comment-text">{c.text}</div>
                    </li>
                  ))}
                  {group.comments.length > (visibleCounts[gi] || PAGE_SIZE) && (
                    <li className="yt-show-more-row">
                      <button
                        type="button"
                        className="yt-show-more-btn"
                        onClick={() => showMore(gi)}
                      >
                        더 보기 ({(visibleCounts[gi] || PAGE_SIZE)}/{group.comments.length})
                      </button>
                    </li>
                  )}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TwitterReplies({ comments, replyCount }) {
  const [expanded, setExpanded] = useState(true);
  const [visibleCount, setVisibleCount] = useState(20);
  const [sortOrder, setSortOrder] = useState('좋아요순');
  const PAGE_SIZE = 20;

  const sorted = useMemo(() => {
    const list = [...comments];
    if (sortOrder === '좋아요순') {
      list.sort((a, b) => (b.like_count ?? 0) - (a.like_count ?? 0));
    } else if (sortOrder === '최신순') {
      list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    }
    return list;
  }, [comments, sortOrder]);

  return (
    <div className="items-section">
      <div className="comment-count-bar">
        <div className="comment-count-inner">
          <span className="comment-count-label">💬 댓글 ({replyCount}건 중 {comments.length}건 수집)</span>
          <select
            className="comment-sort-select"
            value={sortOrder}
            onChange={e => setSortOrder(e.target.value)}
          >
            <option value="좋아요순">좋아요순</option>
            <option value="최신순">최신순</option>
            <option value="등록순">등록순</option>
          </select>
          <button
            type="button"
            className="comments-toggle comments-toggle--all"
            onClick={() => setExpanded(v => !v)}
            aria-expanded={expanded}
          >
            {expanded ? '접기' : '펼치기'}
          </button>
        </div>
      </div>
      {expanded && (
        <div className="items-list">
          {sorted.slice(0, visibleCount).map((c, idx) => (
            <div key={idx} className="item-card">
              <div className="item-text">{c.text}</div>
              <div className="item-meta">
                {c.author && <span className="item-author">{c.author}</span>}
                {c.like_count != null && <span className="item-likes">👍 {formatNumber(c.like_count)}</span>}
                {c.date && <span className="item-date">{c.date}</span>}
              </div>
            </div>
          ))}
          {sorted.length > visibleCount && (
            <button
              type="button"
              className="yt-show-more-btn"
              onClick={() => setVisibleCount(v => v + PAGE_SIZE)}
              style={{ margin: '12px auto', display: 'block' }}
            >
              더 보기 ({visibleCount}/{sorted.length})
            </button>
          )}
        </div>
      )}
      {!comments.length && replyCount > 0 && (
        <div className="naver-cookie-hint" role="status">
          <p><strong>💬 댓글을 수집하려면 TWITTER_BEARER_TOKEN이 필요합니다.</strong></p>
          <p>.env에 <code>TWITTER_BEARER_TOKEN</code>을 설정하고 재시작하면 트윗의 댓글(리플라이)이 함께 수집됩니다.</p>
        </div>
      )}
    </div>
  );
}

function GenericItemsAccordion({ items, result }) {
  const [expanded, setExpanded] = useState(false);
  const [visibleCount, setVisibleCount] = useState(20);
  const PAGE_SIZE = 20;

  const label = result.platform === 'dcinside' && result.type === 'post'
    ? `댓글 (${items.length})`
    : result.replies
      ? `댓글 (${items.length})`
      : `${result.comments ? 'Comments' : result.recent_videos ? 'Recent Videos' : 'Posts'} (${items.length})`;

  return (
    <div className="items-section">
      <div className="comment-count-bar">
        <div className="comment-count-inner">
          <span className="comment-count-label">💬 {label}</span>
          <button
            type="button"
            className="comments-toggle comments-toggle--all"
            onClick={() => setExpanded(v => !v)}
            aria-expanded={expanded}
          >
            {expanded ? '접기' : '펼치기'}
          </button>
        </div>
      </div>
      {expanded && (
        <div className="items-list">
          {items.slice(0, visibleCount).map((item, idx) => (
            <div key={idx} className="item-card">
              <div className="item-text">{item.text || item.title || item.selftext || ''}</div>
              <div className="item-meta">
                {item.author && <span className="item-author">{item.author}</span>}
                {(item.like_count != null || item.score != null || item.recommend != null) && (
                  <span className="item-likes">
                    👍 {formatNumber(item.like_count ?? item.score ?? item.recommend ?? 0)}
                  </span>
                )}
                {item.view_count != null && <span className="item-views">👁 {formatNumber(item.view_count)}</span>}
                {item.num_comments != null && <span className="item-comments">💬 {item.num_comments}</span>}
                {(item.published_at || item.date) && (
                  <span className="item-date">{item.published_at || item.date}</span>
                )}
                {item.views && <span className="item-views">👁 {item.views}</span>}
              </div>
              {(item.permalink || item.url) && (
                <a href={item.permalink || item.url} target="_blank" rel="noopener noreferrer" className="item-link">
                  View →
                </a>
              )}
            </div>
          ))}
          {items.length > visibleCount && (
            <button
              type="button"
              className="yt-show-more-btn"
              onClick={() => setVisibleCount(v => v + PAGE_SIZE)}
              style={{ margin: '12px auto', display: 'block' }}
            >
              더 보기 ({visibleCount}/{items.length})
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function formatNumber(num) {
  if (typeof num === 'string') {
    num = parseInt(num.replace(/[,\s]/g, ''), 10);
  }
  if (isNaN(num)) return '0';
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toLocaleString();
}

export default URLAnalyzer;
