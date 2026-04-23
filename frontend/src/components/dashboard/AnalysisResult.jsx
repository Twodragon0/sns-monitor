import React, { useState, useCallback, useEffect, useRef } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { API_BASE } from '../../config';
import {
  NAVER_FETCH_STATUS_LABELS,
  formatNaverFetchReason, parseNaverReasonTokens, getNaverDiagnosticActions,
} from '../../utils/analysis';
import {
  PLATFORMS, SENTIMENT_COLORS, formatNumber,
  sortComments, sortYoutubeComments,
} from '../../constants/platforms';

// Platform-specific components (split for maintainability)
import { DCInsideResultPosts, POSTS_PER_PAGE, POST_SORT_OPTIONS, sortPosts } from './DCInsideResultPosts';
import { YouTubeComments } from './YouTubeComments';
import { ThreadsPostBlock } from './ThreadsPostBlock';
import { RedditSubredditPosts, RedditPostComments } from './RedditComments';
import { TelegramMessages } from './TelegramMessages';
import { TwitterReplies } from './TwitterReplies';
import { GenericItemsAccordion } from './GenericItemsAccordion';

// Re-export everything so existing imports from this file keep working
export { PLATFORMS, SENTIMENT_COLORS, sortComments, sortYoutubeComments };
export { DCInsideResultPosts, POSTS_PER_PAGE, POST_SORT_OPTIONS, sortPosts };
export { YouTubeComments };
export { ThreadsPostBlock };
export { RedditSubredditPosts, RedditPostComments };
export { TelegramMessages };
export { TwitterReplies };
export { GenericItemsAccordion };

/** 요약 텍스트 표시: 줄바꿈 유지, **bold** 만 <strong>으로 렌더 (마크다운 미지원 시 가독성) */
export function renderSummaryContent(text) {
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

/** AI 심화 분석 채팅 (단일 URL 결과 대상) */
export function AiDeepAnalysisChat({ result, llmStatus }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = { role: 'user', content: input.trim() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const { data } = await axios.post(`${API_BASE}/api/analysis/ai-url-chat`, {
        result,
        message: userMsg.content,
        chat_history: messages,
      });

      if (data.success) {
        setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: `에러: ${data.error || '알 수 없는 오류'}` }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `연결 실패: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  if (!llmStatus?.available) return null;

  return (
    <div className={`result__ai-chat ${expanded ? 'is-expanded' : ''}`}>
      <button
        className="result__ai-chat-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? '🤖 AI 채팅 접기' : '🤖 AI에게 이 결과에 대해 질문하기'}
      </button>

      {expanded && (
        <div className="result__ai-chat-window">
          <div className="result__ai-chat-messages" ref={scrollRef}>
            {messages.length === 0 && (
              <p className="result__ai-chat-welcome">
                이 분석 결과에 대해 궁금한 점을 물어보세요. (예: "이 영상의 핵심 타겟은 누구야?", "부정적인 댓글들의 공통적인 불만이 뭐야?")
              </p>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`result__ai-chat-msg is-${msg.role}`}>
                <div className="result__ai-chat-bubble">
                  {renderSummaryContent(msg.content)}
                </div>
              </div>
            ))}
            {loading && (
              <div className="result__ai-chat-msg is-assistant">
                <div className="result__ai-chat-bubble is-loading">
                  <span className="dot">.</span><span className="dot">.</span><span className="dot">.</span>
                </div>
              </div>
            )}
          </div>
          <form className="result__ai-chat-form" onSubmit={handleSend}>
            <input
              type="text"
              className="result__ai-chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="질문을 입력하세요..."
              disabled={loading}
            />
            <button className="result__ai-chat-send" disabled={loading || !input.trim()}>
              전송
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

/** AI 심화 분석 버튼: 상태 확인 후 이동, 현재 결과 소스 사전 선택. authRequired 시 로그인 유도. */
export function AiCtaButton({ result, onShowError }) {
  const [loading, setLoading] = useState(false);
  const { loggedIn, authRequired, login } = useAuth();

  const goToAiAnalysis = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API_BASE}/api/analysis/status`, { timeout: 5000 });
      if (!data.mirofish_available) {
        onShowError?.('AI 분석 서비스에 연결할 수 없습니다.\n\n시작 방법:\n1. .env.mirofish 파일에 OPENAI_API_KEY 설정\n2. docker-compose --profile analysis up -d\n3. 페이지 새로고침 후 다시 시도');
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
      onShowError?.('AI 분석 상태 확인에 실패했습니다. API 서버 연결을 확인해 주세요.');
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
          OpenAI(GPT)로 로그인 후 AI 심화 분석
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
        onClick={goToAiAnalysis}
        disabled={loading}
      >
        {loading ? '확인 중…' : 'AI 심화 분석'}
      </button>
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

/* --- Analysis Result --- */
export function AnalysisResult({ result, summary, summaryLoading, onSummarize, onShowError }) {
  const platform = PLATFORMS[result.platform] || { label: result.platform, color: '#666' };
  const analysis = result.analysis;
  const sentiment = analysis?.sentiment;
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
        <span className="result__platform" style={{ '--pf-color': platform.color }}>{platform.label}</span>
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
          <span className="result__summary-src">{summary.source === 'mirofish' ? 'AI 분석' : '📊 로컬 분석'}</span>
          <div className="result__summary-text">
            {renderSummaryContent(summary.summary)}
          </div>
        </div>
      )}

      {/* AI 심화 분석 버튼 (요약/감성 아래 항상 노출) */}
      <AiCtaButton result={result} onShowError={onShowError} />

      {/* DCInside 단일 게시글 본문 */}
      {(result.platform === 'dcinside' || result.platform === 'naver_cafe') && result.type === 'post' && result.content && (
        <div className="result__desc">
          <h4>본문</h4>
          <div className="result__content-body">{result.content}</div>
        </div>
      )}

      {/* Threads 게시글 임베드 + 댓글 */}
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

      {/* Twitter/X: 트윗 댓글(리플라이) */}
      {(hasTwitterComments || (result.platform === 'twitter' && result.type === 'tweet' && (result.reply_count > 0 || result.comment_count > 0))) && (
        <TwitterReplies
          comments={result.comments || []}
          replyCount={result.reply_count || result.comment_count || (result.comments || []).length}
        />
      )}

      {/* Reddit: 서브레딧 게시글 목록 */}
      {result.platform === 'reddit' && result.type === 'subreddit' && result.posts?.length > 0 && (
        <RedditSubredditPosts posts={result.posts} totalPosts={result.total_posts} />
      )}

      {/* Reddit: 단일 게시글 댓글 */}
      {result.platform === 'reddit' && result.type === 'post' && result.comments?.length > 0 && (
        <RedditPostComments result={result} />
      )}

      {/* Telegram: 채널 메시지 */}
      {result.platform === 'telegram' && (result.posts?.length > 0 || result.comments?.length > 0) && (
        <TelegramMessages
          messages={result.posts?.length > 0 ? result.posts : result.comments}
          totalMessages={result.total_messages}
        />
      )}

      {/* Generic fallback: 기타 플랫폼 콘텐츠 */}
      {!((result.platform === 'dcinside' || result.platform === 'naver_cafe') && result.type === 'gallery') && !(result.platform === 'reddit' && (result.type === 'subreddit' || result.type === 'post')) && !(result.platform === 'telegram') && !(result.platform === 'threads' && result.type === 'post') && !(result.platform === 'twitter' && result.type === 'tweet') && items.length > 0 && (
        <GenericItemsAccordion items={items} result={result} />
      )}
    </div>
  );
}
