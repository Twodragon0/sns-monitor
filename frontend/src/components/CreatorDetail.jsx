import React, { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './Dashboard.css';

// Generic monitoring keywords for public release example
const MONITORING_KEYWORDS = [
  'ExampleCreator', 'examplecreator',
  'CreatorBrand', 'creatorbrand',
  'ExampleCorp', 'examplecorp',
  // Security/hacking keywords
  'hack', 'hacked', 'hacking', 'security', 'leak', 'leaked', 'scam', 'phishing', 'malware',
  // Content keywords
  'creator', 'vtuber', 'streamer', 'youtube', 'live', 'stream',
  'merch', 'goods', 'album', 'cover', 'original',
  'fan', 'subscribe', 'membership',
];

const KEYWORD_CATEGORIES = {
  'Creator': ['ExampleCreator', 'examplecreator'],
  'Brand': ['CreatorBrand', 'creatorbrand'],
  'Company': ['ExampleCorp', 'examplecorp'],
  'Security': ['hack', 'hacked', 'hacking', 'security', 'leak', 'leaked', 'scam', 'phishing', 'malware'],
  'Content': ['creator', 'vtuber', 'streamer', 'youtube', 'live', 'stream'],
  'Merchandise': ['merch', 'goods', 'album', 'cover', 'original'],
  'Fan Activity': ['fan', 'subscribe', 'membership'],
};

// Sentiment analysis helper
const analyzeSentiment = (text) => {
  if (!text) return 'neutral';
  const lower = text.toLowerCase();
  const positiveWords = ['good', 'great', 'love', 'amazing', 'best', 'awesome', 'wonderful', 'excellent', 'perfect'];
  const negativeWords = ['bad', 'hate', 'terrible', 'worst', 'awful', 'horrible', 'disappoint', 'scam', 'fake'];
  const hasPositive = positiveWords.some(w => lower.includes(w));
  const hasNegative = negativeWords.some(w => lower.includes(w));
  if (hasPositive && !hasNegative) return 'positive';
  if (hasNegative && !hasPositive) return 'negative';
  return 'neutral';
};

const findMatchingKeywords = (text) => {
  if (!text) return [];
  const lower = text.toLowerCase();
  return MONITORING_KEYWORDS.filter(k => lower.includes(k.toLowerCase()));
};

// Example channel members for a generic creator group
const EXAMPLE_CHANNELS = [
  { name: 'Creator1', handle: '@example-creator-1', youtubeUrl: 'https://www.youtube.com/@example-creator-1' },
  { name: 'Creator2', handle: '@example-creator-2', youtubeUrl: 'https://www.youtube.com/@example-creator-2' },
  { name: 'Creator3', handle: '@example-creator-3', youtubeUrl: 'https://www.youtube.com/@example-creator-3' },
];

const SENTIMENT_COLORS = { positive: '#4caf50', neutral: '#ff9800', negative: '#f44336' };
const CHART_COLORS = ['#667eea', '#764ba2', '#f64f59', '#c471ed', '#12c2e9'];

function CreatorDetail({ creatorId }) {
  const [channelsData, setChannelsData] = useState([]);
  const [dcGalleries, setDcGalleries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedChannels, setExpandedChannels] = useState({});
  const [commentDisplayLimit, setCommentDisplayLimit] = useState({});
  const [lastUpdated, setLastUpdated] = useState('');
  const INITIAL_COMMENT_COUNT = 5;
  const LOAD_MORE_COUNT = 10;

  const creatorLabel = creatorId
    ? creatorId.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    : 'Example Creator';

  useEffect(() => {
    loadCreatorData();
  }, [creatorId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadCreatorData = async () => {
    setLoading(true);
    try {
      const timestamp = Date.now();
      // Try to load from a generic creator API endpoint
      const response = await fetch(`/api/creator/${encodeURIComponent(creatorId || 'example')}?_t=${timestamp}`, {
        cache: 'no-cache',
        headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache' },
      });

      if (response.ok) {
        const data = await response.json();
        setChannelsData(data.channels || []);
        setDcGalleries(data.galleries || []);
        if (data.last_updated) setLastUpdated(data.last_updated);
      } else {
        // Fall back to example placeholder data
        setChannelsData(getExampleChannelData());
      }
    } catch (err) {
      setChannelsData(getExampleChannelData());
    } finally {
      setLoading(false);
    }
  };

  const getExampleChannelData = () => {
    return EXAMPLE_CHANNELS.map((ch, idx) => ({
      name: ch.name,
      handle: ch.handle,
      youtubeUrl: ch.youtubeUrl,
      total_comments: 20 + idx * 5,
      total_likes: 150 + idx * 40,
      overall_score: 80 + idx * 3,
      sentiment_distribution: { positive: 0.75 + idx * 0.02, neutral: 0.18, negative: 0.07 - idx * 0.01 },
      comments: [
        { text: 'Great content! Love the style.', likes: 42, sentiment: 'positive', country: 'US' },
        { text: 'Amazing video, keep it up!', likes: 35, sentiment: 'positive', country: 'KR' },
        { text: 'Really interesting content.', likes: 20, sentiment: 'neutral', country: 'JP' },
        { text: 'Looking forward to the next upload.', likes: 18, sentiment: 'positive', country: 'US' },
        { text: 'Subscribed! This is awesome.', likes: 15, sentiment: 'positive', country: 'KR' },
        { text: 'Nice work on the editing.', likes: 12, sentiment: 'positive', country: 'US' },
      ],
      videos: [
        { title: `${ch.name} - Debut Video`, video_id: `${ch.handle}_v001`, views: 50000 + idx * 10000, likes: 3000, comments: 120 },
        { title: `${ch.name} - Monthly Update`, video_id: `${ch.handle}_v002`, views: 38000, likes: 2200, comments: 85 },
        { title: `${ch.name} - Special Collab`, video_id: `${ch.handle}_v003`, views: 62000, likes: 4100, comments: 178 },
      ],
    }));
  };

  const toggleChannel = (channelName) => {
    setExpandedChannels(prev => ({ ...prev, [channelName]: !prev[channelName] }));
  };

  const loadMoreComments = (channelName) => {
    setCommentDisplayLimit(prev => ({
      ...prev,
      [channelName]: (prev[channelName] || INITIAL_COMMENT_COUNT) + LOAD_MORE_COUNT,
    }));
  };

  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading creator data...</p>
      </div>
    );
  }

  // Aggregate sentiment across all channels
  const totalPositive = channelsData.reduce((sum, ch) => {
    const dist = ch.sentiment_distribution || {};
    const total = ch.total_comments || 0;
    return sum + Math.round((dist.positive || 0) * total);
  }, 0);
  const totalNeutral = channelsData.reduce((sum, ch) => {
    const dist = ch.sentiment_distribution || {};
    const total = ch.total_comments || 0;
    return sum + Math.round((dist.neutral || 0) * total);
  }, 0);
  const totalNegative = channelsData.reduce((sum, ch) => {
    const dist = ch.sentiment_distribution || {};
    const total = ch.total_comments || 0;
    return sum + Math.round((dist.negative || 0) * total);
  }, 0);

  const sentimentPieData = [
    { name: 'Positive', value: totalPositive },
    { name: 'Neutral', value: totalNeutral },
    { name: 'Negative', value: totalNegative },
  ].filter(d => d.value > 0);

  const channelBarData = channelsData.map(ch => ({
    name: ch.name || ch.handle,
    comments: ch.total_comments || 0,
    likes: ch.total_likes || 0,
    score: ch.overall_score || 0,
  }));

  return (
    <div className="dashboard" style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
        <button
          onClick={() => { window.history.pushState({}, '', '/'); window.dispatchEvent(new PopStateEvent('popstate')); }}
          style={{ padding: '8px 16px', background: '#667eea', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}
        >
          Back to Dashboard
        </button>
        <div>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: '900' }}>{creatorLabel} Creator Monitoring</h1>
          {lastUpdated && (
            <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#888' }}>
              Last updated: {new Date(lastUpdated).toLocaleString()}
            </p>
          )}
        </div>
      </div>

      {/* Summary stats */}
      <div className="stats-grid" style={{ marginBottom: '32px' }}>
        {[
          { icon: '📊', label: 'Channels Monitored', value: channelsData.length },
          { icon: '💬', label: 'Total Comments', value: channelsData.reduce((s, c) => s + (c.total_comments || 0), 0) },
          { icon: '😊', label: 'Positive Reactions', value: totalPositive },
          { icon: '😞', label: 'Negative Reactions', value: totalNegative },
        ].map(({ icon, label, value }) => (
          <div key={label} className="stat-card">
            <div className="stat-icon">{icon}</div>
            <div className="stat-content">
              <h3>{label}</h3>
              <p className="stat-value">{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Monitoring keywords display */}
      <div style={{ marginBottom: '32px', padding: '20px', background: '#f8f9ff', border: '2px solid #667eea', borderRadius: '12px' }}>
        <h2 style={{ marginTop: 0, color: '#667eea', fontSize: '18px' }}>Monitoring Keywords</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
          {Object.entries(KEYWORD_CATEGORIES).map(([category, keywords]) => (
            <div key={category} style={{ marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', color: '#888', fontWeight: 'bold', marginRight: '6px' }}>{category}:</span>
              {keywords.slice(0, 3).map(kw => (
                <span key={kw} style={{ display: 'inline-block', padding: '3px 8px', background: '#667eea', color: '#fff', borderRadius: '12px', fontSize: '11px', marginRight: '4px' }}>
                  {kw}
                </span>
              ))}
            </div>
          ))}
        </div>
        <p style={{ margin: 0, fontSize: '12px', color: '#888' }}>
          {MONITORING_KEYWORDS.length} keywords tracked across {Object.keys(KEYWORD_CATEGORIES).length} categories
        </p>
      </div>

      {/* Charts: Sentiment + Channel comparison */}
      {channelsData.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px', marginBottom: '32px' }}>
          {/* Sentiment Pie Chart */}
          <div style={{ padding: '20px', background: '#fff', border: '2px solid #e0e0e0', borderRadius: '12px' }}>
            <h3 style={{ marginTop: 0, fontSize: '16px', color: '#333' }}>Overall Sentiment Distribution</h3>
            {sentimentPieData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={sentimentPieData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                    {sentimentPieData.map((entry) => (
                      <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name.toLowerCase()] || '#999'} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p style={{ color: '#888', textAlign: 'center' }}>No sentiment data available</p>
            )}
          </div>

          {/* Channel comparison bar chart */}
          <div style={{ padding: '20px', background: '#fff', border: '2px solid #e0e0e0', borderRadius: '12px' }}>
            <h3 style={{ marginTop: 0, fontSize: '16px', color: '#333' }}>Comments per Channel</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={channelBarData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="comments" fill="#667eea" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Channel list */}
      {channelsData.map((ch, idx) => {
        const isExpanded = expandedChannels[ch.name] || false;
        const displayLimit = commentDisplayLimit[ch.name] || INITIAL_COMMENT_COUNT;
        const comments = ch.comments || [];
        const visibleComments = comments.slice(0, displayLimit);
        const dist = ch.sentiment_distribution || {};

        return (
          <div key={ch.name || idx} style={{ marginBottom: '24px', background: '#fff', border: '2px solid #667eea', borderRadius: '12px', overflow: 'hidden' }}>
            {/* Channel header */}
            <div
              style={{ padding: '16px 20px', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: '#fff', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              onClick={() => toggleChannel(ch.name)}
            >
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '900' }}>{ch.name}</h3>
                <span style={{ fontSize: '13px', opacity: 0.85 }}>{ch.handle}</span>
              </div>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <span style={{ fontSize: '13px', background: 'rgba(255,255,255,0.2)', padding: '4px 10px', borderRadius: '12px' }}>
                  {ch.total_comments || 0} comments
                </span>
                <span style={{ fontSize: '20px' }}>{isExpanded ? '▲' : '▼'}</span>
              </div>
            </div>

            {/* Channel summary (always visible) */}
            <div style={{ padding: '16px 20px', borderBottom: '1px solid #f0f0f0' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '12px', marginBottom: '12px' }}>
                <div style={{ textAlign: 'center', padding: '10px', background: '#e8f5e9', borderRadius: '8px' }}>
                  <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#2e7d32' }}>
                    {Math.round((dist.positive || 0) * 100)}%
                  </div>
                  <div style={{ fontSize: '11px', color: '#388e3c' }}>Positive</div>
                </div>
                <div style={{ textAlign: 'center', padding: '10px', background: '#fff3e0', borderRadius: '8px' }}>
                  <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#ef6c00' }}>
                    {Math.round((dist.neutral || 0) * 100)}%
                  </div>
                  <div style={{ fontSize: '11px', color: '#f57c00' }}>Neutral</div>
                </div>
                <div style={{ textAlign: 'center', padding: '10px', background: '#ffebee', borderRadius: '8px' }}>
                  <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#c62828' }}>
                    {Math.round((dist.negative || 0) * 100)}%
                  </div>
                  <div style={{ fontSize: '11px', color: '#d32f2f' }}>Negative</div>
                </div>
                <div style={{ textAlign: 'center', padding: '10px', background: '#f3e5f5', borderRadius: '8px' }}>
                  <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#7b1fa2' }}>
                    {ch.overall_score || 0}
                  </div>
                  <div style={{ fontSize: '11px', color: '#9c27b0' }}>Score</div>
                </div>
              </div>

              {/* External links */}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {ch.youtubeUrl && (
                  <a href={ch.youtubeUrl} target="_blank" rel="noopener noreferrer"
                    style={{ padding: '6px 12px', background: '#ff0000', color: '#fff', borderRadius: '6px', fontSize: '12px', fontWeight: 'bold', textDecoration: 'none' }}>
                    YouTube
                  </a>
                )}
              </div>
            </div>

            {/* Expanded: comments and videos */}
            {isExpanded && (
              <div style={{ padding: '16px 20px' }}>
                {/* Recent videos */}
                {ch.videos && ch.videos.length > 0 && (
                  <div style={{ marginBottom: '20px' }}>
                    <h4 style={{ color: '#667eea', marginBottom: '10px', fontSize: '14px' }}>Recent Videos</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {ch.videos.slice(0, 3).map((video, vIdx) => (
                        <div key={vIdx} style={{ padding: '10px', background: '#fafafa', borderRadius: '8px', border: '1px solid #e0e0e0' }}>
                          <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#333', marginBottom: '4px' }}>{video.title}</div>
                          <div style={{ fontSize: '11px', color: '#888', display: 'flex', gap: '12px' }}>
                            <span>Views: {(video.views || 0).toLocaleString()}</span>
                            <span>Likes: {(video.likes || 0).toLocaleString()}</span>
                            <span>Comments: {(video.comments || 0).toLocaleString()}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Comments */}
                {comments.length > 0 && (
                  <div>
                    <h4 style={{ color: '#667eea', marginBottom: '10px', fontSize: '14px' }}>
                      Comments ({comments.length} total)
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {visibleComments.map((comment, cIdx) => {
                        const sentiment = comment.sentiment || analyzeSentiment(comment.text || '');
                        const matchedKeywords = findMatchingKeywords(comment.text || '');
                        return (
                          <div key={cIdx} style={{
                            padding: '10px 12px',
                            background: '#f8f9fa',
                            borderRadius: '8px',
                            borderLeft: `3px solid ${SENTIMENT_COLORS[sentiment] || '#ccc'}`,
                          }}>
                            <div style={{ fontSize: '13px', color: '#333', marginBottom: '6px' }}>
                              {matchedKeywords.slice(0, 2).map(kw => (
                                <span key={kw} style={{ background: '#667eea', color: '#fff', padding: '1px 6px', borderRadius: '4px', fontSize: '10px', marginRight: '4px' }}>{kw}</span>
                              ))}
                              {comment.text}
                            </div>
                            <div style={{ fontSize: '11px', color: '#888', display: 'flex', gap: '12px' }}>
                              <span>Likes: {comment.likes || 0}</span>
                              {comment.country && <span>Country: {comment.country}</span>}
                              <span style={{ color: SENTIMENT_COLORS[sentiment] }}>
                                {sentiment === 'positive' ? 'Positive' : sentiment === 'negative' ? 'Negative' : 'Neutral'}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {comments.length > displayLimit && (
                      <button
                        onClick={() => loadMoreComments(ch.name)}
                        style={{ marginTop: '12px', padding: '8px 20px', background: '#667eea', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', fontSize: '13px' }}
                      >
                        Load more ({comments.length - displayLimit} remaining)
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      {/* DC Galleries section (if data present) */}
      {dcGalleries.length > 0 && (
        <div style={{ marginTop: '32px' }}>
          <h2 style={{ color: '#0253fe', marginBottom: '16px', fontWeight: '900' }}>DC Inside Gallery Monitoring</h2>
          {dcGalleries.map((gallery) => (
            <div key={gallery.gallery_id} style={{ marginBottom: '16px', padding: '16px', background: '#fff', border: '2px solid #0253fe', borderRadius: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0, color: '#0253fe' }}>{gallery.gallery_name}</h3>
                <div style={{ fontSize: '13px', color: '#666' }}>
                  Posts: {gallery.total_posts || 0} | Comments: {gallery.total_comments || 0}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* No data placeholder */}
      {channelsData.length === 0 && (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: '#888' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
          <h2>No data available for "{creatorLabel}"</h2>
          <p>Configure the crawler to collect data for this creator group.</p>
          <p style={{ fontSize: '13px' }}>
            Use keywords like: {MONITORING_KEYWORDS.slice(0, 6).join(', ')}
          </p>
        </div>
      )}
    </div>
  );
}

export default CreatorDetail;
