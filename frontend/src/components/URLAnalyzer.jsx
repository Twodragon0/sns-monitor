import React, { useState, useCallback, useEffect, useMemo } from 'react';
import axios from 'axios';
import DOMPurify from 'dompurify';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import './URLAnalyzer.css';
import { API_BASE } from '../config';

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
};

const SENTIMENT_COLORS = {
  positive: '#4CAF50',
  neutral: '#9E9E9E',
  negative: '#F44336',
};

const RESULTS_CACHE_KEY = 'sns-analyzer-results';
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
  no_search_results: '검색 결과 없음',
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

/** 요약 API 전송용 페이로드 축소 (413 Payload Too Large 방지) */
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
    analysis: result.analysis ? { overall: result.analysis.overall, sentiment: result.analysis.sentiment, top_keywords: (result.analysis.top_keywords || []).slice(0, 10) } : undefined,
    ...stats,
  };
  const items = result.comments || result.replies || result.posts || result.recent_videos;
  if (Array.isArray(items) && items.length > 0) {
    const key = result.comments ? 'comments' : (result.replies ? 'replies' : (result.posts ? 'posts' : 'recent_videos'));
    base[key] = items.slice(0, 50).map(item => ({
      text: (item.text || item.title || item.selftext || '').slice(0, 200),
      author: item.author,
      date: item.date || item.published_at,
    }));
  }
  return base;
}

function detectPlatform(url) {
  if (!url) return null;
  const lower = url.toLowerCase();
  if (lower.includes('youtube.com') || lower.includes('youtu.be')) return 'youtube';
  if (lower.includes('dcinside.com')) return 'dcinside';
  if (lower.includes('cafe.naver.com')) return 'naver_cafe';
  if (lower.includes('reddit.com')) return 'reddit';
  if (lower.includes('t.me/')) return 'telegram';
  if (lower.includes('kakao.com')) return 'kakao';
  if (lower.includes('x.com') || lower.includes('twitter.com')) return 'twitter';
  if (lower.includes('instagram.com')) return 'instagram';
  if (lower.includes('threads.net') || lower.includes('threads.com')) return 'threads';
  return null;
}

function URLAnalyzer() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('sns-analyzer-history') || '[]');
    } catch { return []; }
  });

  useEffect(() => {
    localStorage.setItem('sns-analyzer-history', JSON.stringify(history));
  }, [history]);

  const detectedPlatform = detectPlatform(url);

  const handleAnalyze = useCallback(async (e) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.post(`${API_BASE}/api/analyze/url`, { url: url.trim() }, { timeout: 300000 });
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
    }
  }, [url]);

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

      <div className="supported-platforms">
        {Object.entries(PLATFORM_INFO).map(([key, info]) => (
          <span key={key} className="platform-tag" style={{ borderColor: info.color }}>
            {info.icon} {info.name}
          </span>
        ))}
      </div>

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

function ThreadsPostBlock({ embedHtml, url, replies, description }) {
  const embedRef = React.useRef(null);

  React.useEffect(() => {
    if (!embedHtml) return;
    const container = embedRef.current;
    if (!container) return;
    if (container.querySelector('[data-text-post-permalink]')) return;
    // Sanitize embed HTML to prevent XSS (allow only Threads embed markup)
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

  return (
    <div className="result-content threads-post-block">
      <h3>게시글</h3>
      {hasEmbed ? (
        <div ref={embedRef} className="threads-embed-wrap" />
      ) : (
        <>
          {description && (
            <p className="threads-post-fallback-desc">{description}</p>
          )}
          {!description && (
            <p className="threads-no-embed">임베드를 불러오지 못했습니다. 원문 링크에서 확인해 주세요.</p>
          )}
        </>
      )}
      {url && (
        <a href={url} target="_blank" rel="noopener noreferrer" className="result-origin-link">
          Threads 원문 보기 →
        </a>
      )}
      <h3>댓글 {replyList.length > 0 ? `(${replyList.length})` : '(Threads API 미제공)'}</h3>
      {replyList.length > 0 ? (
        <ul className="comments-sublist">
          {replyList.map((r, i) => (
            <li key={i} className="comment-item">
              <span className="comment-meta-inline">
                {r.author && <span className="comment-author">{r.author}</span>}
                {r.date && <span className="comment-date">{r.date}</span>}
              </span>
              <span className="comment-text">{r.text || r.title || ''}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="threads-replies-hint">Threads는 댓글(답글) 데이터를 공개 API로 제공하지 않아 여기서는 표시되지 않습니다.</p>
      )}
    </div>
  );
}

function AnalysisResult({ result }) {
  const platform = PLATFORM_INFO[result.platform] || { name: result.platform, color: '#666' };
  const analysis = result.analysis;
  const hasYoutubeComments =
    result.platform === 'youtube' && Array.isArray(result.comments) && result.comments.length > 0;
  const items = !hasYoutubeComments ? (result.comments || result.replies || result.posts || result.recent_videos || []) : [];
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

      <div className="ai-summary-section">
        <button
          className="summarize-button"
          onClick={handleSummarize}
          disabled={summaryLoading}
        >
          {summaryLoading ? '🤖 분석 중...' : '🤖 AI 요약'}
        </button>
        {summaryError && <div className="error-message">{summaryError}</div>}
        {summary && (
          <div className="summary-content">
            <div className="summary-source">
              {summary.source === 'mirofish' ? '🐟 MiroFish AI' : '📊 로컬 분석'}
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

      {result.platform === 'telegram' && result.posts?.length > 0 && (
        <TelegramMessages messages={result.posts} totalMessages={result.total_messages} />
      )}

      {!((result.platform === 'dcinside' || result.platform === 'naver_cafe') && result.type === 'gallery') && !(result.platform === 'reddit' && (result.type === 'subreddit' || result.type === 'post')) && !(result.platform === 'telegram') && !(result.platform === 'threads' && result.type === 'post') && items.length > 0 && (
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

export default URLAnalyzer;
