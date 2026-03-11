import React, { useState, useCallback } from 'react';
import axios from 'axios';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import './URLAnalyzer.css';

const PLATFORM_INFO = {
  youtube: { name: 'YouTube', color: '#FF0000', icon: '▶' },
  dcinside: { name: 'DCInside', color: '#2B65EC', icon: '📋' },
  reddit: { name: 'Reddit', color: '#FF4500', icon: '🔗' },
  telegram: { name: 'Telegram', color: '#0088cc', icon: '✈' },
  kakao: { name: 'Kakao', color: '#FEE500', icon: '💬' },
  twitter: { name: 'X (Twitter)', color: '#000000', icon: '𝕏' },
};

const SENTIMENT_COLORS = {
  positive: '#4CAF50',
  neutral: '#9E9E9E',
  negative: '#F44336',
};

const API_BASE = process.env.REACT_APP_API_URL || '';

function detectPlatform(url) {
  if (!url) return null;
  const lower = url.toLowerCase();
  if (lower.includes('youtube.com') || lower.includes('youtu.be')) return 'youtube';
  if (lower.includes('dcinside.com')) return 'dcinside';
  if (lower.includes('reddit.com')) return 'reddit';
  if (lower.includes('t.me/')) return 'telegram';
  if (lower.includes('kakao.com')) return 'kakao';
  if (lower.includes('x.com') || lower.includes('twitter.com')) return 'twitter';
  return null;
}

function URLAnalyzer() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  const detectedPlatform = detectPlatform(url);

  const handleAnalyze = useCallback(async (e) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.post(`${API_BASE}/api/analyze/url`, { url: url.trim() });
      setResult(response.data);
      setHistory(prev => [{
        url: url.trim(),
        platform: response.data.platform,
        title: response.data.title || response.data.gallery_id || response.data.subreddit || url.trim(),
        analyzed_at: response.data.analyzed_at,
      }, ...prev.slice(0, 9)]);
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Analysis failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [url]);

  const goBack = () => {
    window.history.pushState({}, '', '/');
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  return (
    <div className="url-analyzer">
      <div className="analyzer-header">
        <button className="back-button" onClick={goBack}>← Dashboard</button>
        <h1>SNS URL Analyzer</h1>
        <p>Paste any supported URL to analyze content and sentiment</p>
      </div>

      <form className="analyzer-form" onSubmit={handleAnalyze}>
        <div className="url-input-wrapper">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=... or any supported URL"
            className="url-input"
            disabled={loading}
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
          <h3>Recent Analyses</h3>
          <ul>
            {history.map((item, idx) => (
              <li key={idx} onClick={() => setUrl(item.url)}>
                <span className="history-platform" style={{
                  color: PLATFORM_INFO[item.platform]?.color || '#666'
                }}>
                  {PLATFORM_INFO[item.platform]?.icon}
                </span>
                <span className="history-title">{item.title}</span>
                <span className="history-time">
                  {new Date(item.analyzed_at).toLocaleTimeString('ko-KR')}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function AnalysisResult({ result }) {
  const platform = PLATFORM_INFO[result.platform] || { name: result.platform, color: '#666' };
  const analysis = result.analysis;
  const items = result.comments || result.posts || result.recent_videos || [];
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);

  const handleSummarize = async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const resp = await axios.post(`${API_BASE}/api/analyze/summarize`, { result });
      setSummary(resp.data);
    } catch (err) {
      setSummaryError(err.response?.data?.error || err.message || 'Summarization failed');
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
    <div className="analysis-result">
      <div className="result-header">
        <div className="result-platform" style={{ backgroundColor: platform.color }}>
          {platform.name}
        </div>
        <h2>{result.title || result.gallery_id || result.subreddit || result.channel_name || result.username || 'Analysis Result'}</h2>
        {result.analyzed_at && (
          <span className="result-time">
            {new Date(result.analyzed_at).toLocaleString('ko-KR')}
          </span>
        )}
      </div>

      <div className="result-stats">
        {result.view_count != null && <StatCard label="Views" value={formatNumber(result.view_count)} />}
        {result.like_count != null && <StatCard label="Likes" value={formatNumber(result.like_count)} />}
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

      {result.description && (
        <div className="result-description">
          <h3>Description</h3>
          <p>{result.description}</p>
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

      {items.length > 0 && (
        <div className="items-section">
          <h3>
            {result.comments ? 'Comments' : result.recent_videos ? 'Recent Videos' : 'Posts'}
            ({items.length})
          </h3>
          <div className="items-list">
            {items.slice(0, 20).map((item, idx) => (
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
                {item.permalink && (
                  <a href={item.permalink} target="_blank" rel="noopener noreferrer" className="item-link">
                    View →
                  </a>
                )}
              </div>
            ))}
          </div>
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
