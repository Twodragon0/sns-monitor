import React, { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './Dashboard.css';
import './CreatorDetail.css';
import { API_BASE } from '../config';

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
  '크리에이터': ['ExampleCreator', 'examplecreator'],
  '브랜드': ['CreatorBrand', 'creatorbrand'],
  '기업': ['ExampleCorp', 'examplecorp'],
  '보안': ['hack', 'hacked', 'hacking', 'security', 'leak', 'leaked', 'scam', 'phishing', 'malware'],
  '콘텐츠': ['creator', 'vtuber', 'streamer', 'youtube', 'live', 'stream'],
  '굿즈': ['merch', 'goods', 'album', 'cover', 'original'],
  '팬 활동': ['fan', 'subscribe', 'membership'],
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
      const response = await fetch(`${API_BASE}/api/creator/${encodeURIComponent(creatorId || 'example')}?_t=${timestamp}`, {
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
        <p>크리에이터 데이터 로딩 중...</p>
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
    { name: '긍정', value: totalPositive },
    { name: '중립', value: totalNeutral },
    { name: '부정', value: totalNegative },
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
          className="creator-detail__back-btn"
        >
          대시보드로 돌아가기
        </button>
        <div>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: '900' }}>{creatorLabel} 크리에이터 모니터링</h1>
          {lastUpdated && (
            <p className="creator-detail__last-updated">
              마지막 업데이트: {new Date(lastUpdated).toLocaleString('ko-KR')}
            </p>
          )}
        </div>
      </div>

      {/* Summary stats */}
      <div className="stats-grid" style={{ marginBottom: '32px' }}>
        {[
          { icon: '📊', label: '모니터링 채널', value: channelsData.length },
          { icon: '💬', label: '전체 댓글', value: channelsData.reduce((s, c) => s + (c.total_comments || 0), 0) },
          { icon: '😊', label: '긍정 반응', value: totalPositive },
          { icon: '😞', label: '부정 반응', value: totalNegative },
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
      <div className="creator-detail__keywords">
        <h2 className="creator-detail__keywords-title">모니터링 키워드</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
          {Object.entries(KEYWORD_CATEGORIES).map(([category, keywords]) => (
            <div key={category} style={{ marginBottom: '8px' }}>
              <span className="creator-detail__keyword-category">{category}:</span>
              {keywords.slice(0, 3).map(kw => (
                <span key={kw} className="creator-detail__keyword-tag">
                  {kw}
                </span>
              ))}
            </div>
          ))}
        </div>
        <p className="creator-detail__keyword-meta">
          {Object.keys(KEYWORD_CATEGORIES).length}개 카테고리에서 {MONITORING_KEYWORDS.length}개 키워드 추적 중
        </p>
      </div>

      {/* Charts: Sentiment + Channel comparison */}
      {channelsData.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px', marginBottom: '32px' }}>
          {/* Sentiment Pie Chart */}
          <div className="creator-detail__chart-card">
            <h3 className="creator-detail__chart-title">전체 감성 분포</h3>
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
              <p className="creator-detail__chart-empty">감성 데이터가 없습니다</p>
            )}
          </div>

          {/* Channel comparison bar chart */}
          <div className="creator-detail__chart-card">
            <h3 className="creator-detail__chart-title">채널별 댓글 수</h3>
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
          <div key={ch.name || idx} className="creator-detail__channel">
            {/* Channel header */}
            <div
              className="creator-detail__channel-header"
              onClick={() => toggleChannel(ch.name)}
            >
              <div>
                <h3 className="creator-detail__channel-name">{ch.name}</h3>
                <span className="creator-detail__channel-handle">{ch.handle}</span>
              </div>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <span className="creator-detail__channel-badge">
                  댓글 {ch.total_comments || 0}개
                </span>
                <span style={{ fontSize: '20px' }}>{isExpanded ? '▲' : '▼'}</span>
              </div>
            </div>

            {/* Channel summary (always visible) */}
            <div className="creator-detail__channel-summary">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '12px', marginBottom: '12px' }}>
                <div className="creator-detail__sentiment-box creator-detail__sentiment-box--positive">
                  <div className="creator-detail__sentiment-value--positive">
                    {Math.round((dist.positive || 0) * 100)}%
                  </div>
                  <div className="creator-detail__sentiment-label--positive">긍정</div>
                </div>
                <div className="creator-detail__sentiment-box creator-detail__sentiment-box--neutral">
                  <div className="creator-detail__sentiment-value--neutral">
                    {Math.round((dist.neutral || 0) * 100)}%
                  </div>
                  <div className="creator-detail__sentiment-label--neutral">중립</div>
                </div>
                <div className="creator-detail__sentiment-box creator-detail__sentiment-box--negative">
                  <div className="creator-detail__sentiment-value--negative">
                    {Math.round((dist.negative || 0) * 100)}%
                  </div>
                  <div className="creator-detail__sentiment-label--negative">부정</div>
                </div>
                <div className="creator-detail__sentiment-box creator-detail__sentiment-box--score">
                  <div className="creator-detail__sentiment-value--score">
                    {ch.overall_score || 0}
                  </div>
                  <div className="creator-detail__sentiment-label--score">점수</div>
                </div>
              </div>

              {/* External links */}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {ch.youtubeUrl && (
                  <a href={ch.youtubeUrl} target="_blank" rel="noopener noreferrer"
                    className="creator-detail__yt-link">
                    YouTube
                  </a>
                )}
              </div>
            </div>

            {/* Expanded: comments and videos */}
            {isExpanded && (
              <div className="creator-detail__expanded">
                {/* Recent videos */}
                {ch.videos && ch.videos.length > 0 && (
                  <div style={{ marginBottom: '20px' }}>
                    <h4 className="creator-detail__section-title">최근 영상</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {ch.videos.slice(0, 3).map((video, vIdx) => (
                        <div key={vIdx} className="creator-detail__video">
                          <div className="creator-detail__video-title">{video.title}</div>
                          <div className="creator-detail__video-meta">
                            <span>조회수: {(video.views || 0).toLocaleString()}</span>
                            <span>좋아요: {(video.likes || 0).toLocaleString()}</span>
                            <span>댓글: {(video.comments || 0).toLocaleString()}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Comments */}
                {comments.length > 0 && (
                  <div>
                    <h4 className="creator-detail__section-title">
                      댓글 (총 {comments.length}개)
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {visibleComments.map((comment, cIdx) => {
                        const sentiment = comment.sentiment || analyzeSentiment(comment.text || '');
                        const matchedKeywords = findMatchingKeywords(comment.text || '');
                        return (
                          <div key={cIdx} className="creator-detail__comment" style={{
                            borderLeft: `3px solid ${SENTIMENT_COLORS[sentiment] || '#ccc'}`,
                          }}>
                            <div className="creator-detail__comment-text">
                              {matchedKeywords.slice(0, 2).map(kw => (
                                <span key={kw} className="creator-detail__comment-keyword">{kw}</span>
                              ))}
                              {comment.text}
                            </div>
                            <div className="creator-detail__comment-meta">
                              <span>좋아요: {comment.likes || 0}</span>
                              {comment.country && <span>국가: {comment.country}</span>}
                              <span style={{ color: SENTIMENT_COLORS[sentiment] }}>
                                {sentiment === 'positive' ? '긍정' : sentiment === 'negative' ? '부정' : '중립'}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {comments.length > displayLimit && (
                      <button
                        onClick={() => loadMoreComments(ch.name)}
                        className="creator-detail__load-more-btn"
                      >
                        더 불러오기 ({comments.length - displayLimit}개 남음)
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
          <h2 className="creator-detail__dc-title">DCInside 갤러리 모니터링</h2>
          {dcGalleries.map((gallery) => (
            <div key={gallery.gallery_id} className="creator-detail__dc-gallery">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 className="creator-detail__dc-gallery-name">{gallery.gallery_name}</h3>
                <div className="creator-detail__dc-gallery-meta">
                  게시글: {gallery.total_posts || 0} | 댓글: {gallery.total_comments || 0}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* No data placeholder */}
      {channelsData.length === 0 && (
        <div className="creator-detail__empty">
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
          <h2>"{creatorLabel}"에 대한 데이터가 없습니다</h2>
          <p>크롤러를 구성하여 이 크리에이터 그룹의 데이터를 수집하세요.</p>
          <p className="creator-detail__empty-keyword-hint">
            사용 키워드 예시: {MONITORING_KEYWORDS.slice(0, 6).join(', ')}
          </p>
        </div>
      )}
    </div>
  );
}

export default CreatorDetail;
