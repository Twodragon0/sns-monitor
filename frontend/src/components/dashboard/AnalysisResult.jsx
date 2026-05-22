import React from 'react';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
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
import { AiDeepAnalysisChat, renderSummaryContent } from './AiDeepAnalysisChat';
import { AiCtaButton } from './AiCtaButton';

// Re-export everything so existing imports from this file keep working
export { PLATFORMS, SENTIMENT_COLORS, sortComments, sortYoutubeComments };
export { DCInsideResultPosts, POSTS_PER_PAGE, POST_SORT_OPTIONS, sortPosts };
export { YouTubeComments };
export { ThreadsPostBlock };
export { RedditSubredditPosts, RedditPostComments };
export { TelegramMessages };
export { TwitterReplies };
export { GenericItemsAccordion };
export { AiDeepAnalysisChat, renderSummaryContent };
export { AiCtaButton };

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
