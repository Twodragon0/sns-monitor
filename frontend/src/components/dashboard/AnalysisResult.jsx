import React, { useState, useCallback, useMemo, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { API_BASE } from '../../config';
import {
  NAVER_FETCH_STATUS_LABELS, NAVER_FETCH_REASON_LABELS,
  formatNaverFetchReason, parseNaverReasonTokens, getNaverDiagnosticActions,
  trimResultForSummarize,
} from '../../utils/analysis';

export const SENTIMENT_COLORS = {
  positive: '#10b981',
  neutral:  '#9ca3af',
  negative: '#ef4444',
};

export const PLATFORMS = {
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

function formatNumber(num) {
  if (num == null) return null;
  const n = typeof num === 'string' ? parseInt(num.replace(/[,\s]/g, ''), 10) : Number(num);
  if (isNaN(n)) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

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
  const items = !hasYoutubeComments ? (result.comments || result.posts || result.recent_videos || []) : [];
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
        <span className="result__platform" style={{ background: platform.color }}>{platform.label}</span>
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

      {result.description && (
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

      {/* 수집된 콘텐츠: 댓글 / 게시글 / 최근 영상 (제목·목록·미리보기 개선) */}
      {!((result.platform === 'dcinside' || result.platform === 'naver_cafe') && result.type === 'gallery') && items.length > 0 && (
        <div className="result__items">
          <div className="result__items-head">
            <h4 className="result__items-title">
              수집된 콘텐츠
              <span className="result__items-count">{result.comments ? '댓글' : result.recent_videos ? '영상' : '게시글'} {formatNumber(items.length)}건</span>
            </h4>
          </div>
          {result.platform === 'instagram' && (
            <p className="result__items-hint">게시글 내용은 og:meta로 수집됩니다. 댓글 수집은 Instagram 공식 API가 필요합니다.</p>
          )}
          <div className="result__items-list">
            {items.slice(0, (result.platform === 'dcinside' || result.platform === 'instagram') ? 50 : 15).map((item, i) => (
              <div
                key={i}
                className={`result__item ${item.url ? 'result__item--clickable' : ''}`}
                onClick={() => {
                  if (item.url) {
                    window.open(item.url, '_blank', 'noopener,noreferrer');
                  }
                }}
              >
                {result.platform === 'instagram' && result.thumbnail && i === 0 && (
                  <a href={item.url || result.url} target="_blank" rel="noopener noreferrer" className="result__item-thumb">
                    <img src={result.thumbnail} alt="" width={120} height={120} style={{ objectFit: 'cover', borderRadius: 8 }} />
                  </a>
                )}
                <div className="result__item-text">{(item.text || item.title || item.selftext || '').trim() || '(내용 없음)'}</div>
                <div className="result__item-meta">
                  {item.author && <span className="result__item-author">{item.author}</span>}
                  {(item.like_count ?? item.score ?? item.recommend) != null && <span>👍 {formatNumber(item.like_count ?? item.score ?? item.recommend ?? 0)}</span>}
                  {item.view_count != null && <span>👁 {formatNumber(item.view_count)}</span>}
                  {(item.published_at || item.date) && <span>{item.published_at || item.date}</span>}
                </div>
                {item.url && (
                  <a href={item.url} target="_blank" rel="noopener noreferrer" className="result__item-link">원문 →</a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* 댓글 정렬: 등록순(기본) | 최신순 | 답글순(동일) */
export function sortComments(comments, order) {
  if (!comments?.length) return comments || [];
  const list = [...comments];
  if (order === '최신순' && list.some(c => c.date)) {
    list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  }
  return list;
}

export const POSTS_PER_PAGE = 50;

export const POST_SORT_OPTIONS = [
  { value: 'date_desc', label: '최신순' },
  { value: 'date_asc', label: '오래된순' },
  { value: 'popular', label: '인기순' },
  { value: 'comments', label: '댓글 많은 순' },
];

export function sortYoutubeComments(comments, order) {
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

export function sortPosts(posts, sortBy) {
  if (!posts?.length) return posts || [];
  const list = [...posts];
  switch (sortBy) {
    case 'date_asc':
      list.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
      break;
    case 'date_desc':
      list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
      break;
    case 'popular':
      list.sort((a, b) => (b.recommend ?? 0) - (a.recommend ?? 0));
      break;
    case 'comments':
      list.sort((a, b) => (b.comments?.length ?? 0) - (a.comments?.length ?? 0));
      break;
    default:
      break;
  }
  return list;
}

/* DCInside·네이버 카페 갤러리 게시글 + 댓글 (접기/펼치기, 통합 댓글, 전체 댓글 N개 헤더, 50개씩 페이지네이션)
   DCInside는 목록 기준 댓글 수(comment_count)는 있지만, API 차단 등으로 실제 수집이 실패하는 경우가 있어
   클릭 시 단건 URL을 다시 /api/analyze/url로 호출하여 댓글을 재수집(on-demand)합니다. */
export function DCInsideResultPosts({ posts, totalPosts, loginVerified, isNaverCafe }) {
  const [expandedNo, setExpandedNo] = useState(null);
  const [showAllComments, setShowAllComments] = useState(false);
  const [commentSort, setCommentSort] = useState('등록순');
  const [currentPage, setCurrentPage] = useState(1);
  const [postSort, setPostSort] = useState('date_desc');
  const [localPosts, setLocalPosts] = useState(posts);
  const [loadingPostNo, setLoadingPostNo] = useState(null);

  useEffect(() => {
    setLocalPosts(posts);
  }, [posts]);

  const sortedPosts = useMemo(() => sortPosts(localPosts, postSort), [localPosts, postSort]);
  const totalPages = Math.max(1, Math.ceil(sortedPosts.length / POSTS_PER_PAGE));
  const start = (currentPage - 1) * POSTS_PER_PAGE;
  const postsOnPage = sortedPosts.slice(start, start + POSTS_PER_PAGE);

  const allComments = localPosts.reduce((acc, post) => {
    (post.comments || []).forEach((c) => {
      acc.push({ ...c, postTitle: post.text || `게시글 #${post.number ?? ''}`, postUrl: post.url });
    });
    return acc;
  }, []);

  const sortedAllComments = sortComments(allComments, commentSort);
  const totalCommentCount = allComments.length;

  const postsWithComments = localPosts.filter((p) => (p.comments?.length || 0) > 0).length;

  const listLabel = totalPosts != null && totalPosts > localPosts.length && isNaverCafe
    ? `수집 ${localPosts.length}건 / 전체 약 ${formatNumber(totalPosts)}건`
    : `${localPosts.length}건`;

  return (
    <div className="result__items">
      <div className="result__items-head">
        <h4>
          게시글 목록 ({listLabel})
          {isNaverCafe && loginVerified && (
            <span className="result__naver-login-badge" title="로그인된 상태로 수집됨">로그인됨</span>
          )}
        </h4>
        <p className="result__items-hint" aria-hidden="true">
          💬 카드 전체를 클릭하면 해당 글의 댓글이 아래에 펼쳐집니다. (댓글 있는 글 {postsWithComments}건)
        </p>
        <div className="result__items-sort" aria-label="게시글 정렬">
          <span className="result__items-sort-label">정렬:</span>
          {POST_SORT_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              className={`result__pagination-btn result__sort-btn ${postSort === value ? 'is-active' : ''}`}
              onClick={() => { setPostSort(value); setCurrentPage(1); setExpandedNo(null); }}
              aria-pressed={postSort === value}
            >
              {label}
            </button>
          ))}
        </div>
        {totalPages > 1 && (
          <div className="result__items-pagination" aria-label="게시글 페이지">
            <button
              type="button"
              className="result__pagination-btn"
              onClick={() => { setCurrentPage(p => Math.max(1, p - 1)); setExpandedNo(null); }}
              disabled={currentPage <= 1}
              aria-label="이전 페이지"
            >
              이전
            </button>
            <span className="result__pagination-info">
              {currentPage} / {totalPages} (50개씩)
            </span>
            <button
              type="button"
              className="result__pagination-btn"
              onClick={() => { setCurrentPage(p => Math.min(totalPages, p + 1)); setExpandedNo(null); }}
              disabled={currentPage >= totalPages}
              aria-label="다음 페이지"
            >
              다음
            </button>
          </div>
        )}
      </div>

      {totalCommentCount > 0 && (
        <div className="result__comment-count-bar" aria-label="전체 댓글">
          <div className="result__comment-count-inner">
            <span className="result__comment-count-label">
              전체 댓글 {totalCommentCount}개 · 클릭 시 댓글 표시
            </span>
            <div className="result__comment-sort">
              {['등록순', '최신순', '답글순'].map((order) => (
                <button
                  key={order}
                  type="button"
                  className={`result__comment-sort-btn ${commentSort === order ? 'is-active' : ''}`}
                  onClick={() => setCommentSort(order)}
                  aria-pressed={commentSort === order}
                >
                  {order}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="result__comments-toggle result__comments-toggle--all"
              onClick={() => setShowAllComments((v) => !v)}
              aria-expanded={showAllComments}
            >
              {showAllComments ? '통합 댓글 접기' : '통합 보기'}
            </button>
          </div>
        </div>
      )}

      {showAllComments && sortedAllComments.length > 0 && (
        <div className="result__all-comments" aria-label="전체 댓글 통합">
          <ul className="result__comments-sublist result__comments-sublist--all">
            {sortedAllComments.map((c, i) => (
              <li key={i} className="result__comment-item">
                <span className="result__comment-meta">
                  [{c.postTitle}]
                  {c.postUrl && (
                    <a href={c.postUrl} target="_blank" rel="noopener noreferrer" className="result__comment-post-link">
                      원문
                    </a>
                  )}{' '}
                  <span className="result__comment-author">{c.author}</span>
                  {c.date && <span className="result__comment-date">{c.date}</span>}
                </span>
                <span className="result__comment-text">{c.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="result__items-list">
        {postsOnPage.map((post, idx) => {
          const postKey = post.number ?? post.post_id ?? idx;
          const commentList = post.comments ?? [];
          const collectedCount = commentList.length;
          const listCount = post.comment_count ?? null;
          const isExpanded = expandedNo === postKey;
          const sortedPostComments = sortComments(commentList, commentSort);
          const commentLabel = listCount != null
            ? `댓글 (목록 ${listCount} / 수집 ${collectedCount})`
            : `댓글 (${collectedCount})`;
          const collectionFailed = listCount != null && listCount > 0 && collectedCount === 0;

          const toggleComments = async (e) => {
            if (e.target.closest('a')) return;
            const willExpand = !isExpanded;
            // 댓글이 목록상 1개 이상인데 아직 수집되지 않은 경우, 단건 URL로 재수집 시도
            if (willExpand && collectionFailed && post.url && !loadingPostNo) {
              try {
                setLoadingPostNo(postKey);
                const { data } = await axios.post(
                  `${API_BASE}/api/analyze/url`,
                  { url: post.url },
                  { timeout: 300000 },
                );
                const newComments = Array.isArray(data.comments) ? data.comments : [];
                setLocalPosts((prev) =>
                  prev.map((p) =>
                    (p.number ?? p.post_id ?? idx) === postKey
                      ? {
                          ...p,
                          comments: newComments,
                          comment_count:
                            typeof data.comment_count === 'number'
                              ? data.comment_count
                              : newComments.length || p.comment_count,
                        }
                      : p,
                  ),
                );
              } catch (err) {
                // 실패 시 기존 수집 실패 메시지 유지
              } finally {
                setLoadingPostNo(null);
              }
            }
            setExpandedNo(willExpand ? postKey : null);
          };

          return (
            <div
              key={postKey}
              className={`result__item result__item--dcinside ${isExpanded ? 'result__item--expanded' : ''}`}
              onClick={toggleComments}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleComments(e); } }}
              role="button"
              tabIndex={0}
              aria-expanded={isExpanded}
              aria-controls={`result-cmt-${postKey}`}
              aria-label={isExpanded ? `댓글 접기` : `댓글 ${collectedCount}개 보기`}
            >
              {post.url ? (
                <a
                  href={post.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="result__item-text result__item-text--link"
                  onClick={(e) => e.stopPropagation()}
                >
                  {post.text}
                </a>
              ) : (
                <div className="result__item-text">{post.text}</div>
              )}
              <div className="result__item-meta">
                {post.author && <span>{post.author}</span>}
                {post.view_count != null && <span>👁 {formatNumber(post.view_count)}</span>}
                {post.recommend != null && <span>👍 {formatNumber(post.recommend)}</span>}
                {post.date && <span>{post.date}</span>}
              </div>
              {post.url && (
                <a href={post.url} target="_blank" rel="noopener noreferrer" className="result__item-link" onClick={(e) => e.stopPropagation()}>
                  원문 보기 →
                </a>
              )}
              <div className="result__comment-wrap">
                <div className="result__comment-count">
                  <span className="result__comment-hint" aria-hidden="true">
                    💬 {commentLabel}
                    {collectionFailed && !loadingPostNo && (
                      <span
                        className="result__comment-fail"
                        title="목록에는 댓글이 있으나 초기 수집에 실패했습니다. 클릭 시 단건 URL로 다시 시도합니다."
                      >
                        {' '}
                        (수집 실패)
                      </span>
                    )}
                    {loadingPostNo === postKey && (
                      <span className="result__comment-fail"> (댓글 불러오는 중…)</span>
                    )}
                    {' '}{isExpanded ? '접기 ▲' : '클릭 시 보기 ▼'}
                  </span>
                </div>
                {isExpanded && (
                  <ul
                    id={`result-cmt-${postKey}`}
                    className="result__comments-sublist"
                    aria-label={`댓글 ${collectedCount}개`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {sortedPostComments.length === 0 ? (
                      <li className="result__comment-item result__comment-item--empty">
                        {collectionFailed ? (
                          <span className="result__comment-fail-hint">
                            댓글 수집에 실패했습니다. 위 <strong>원문 보기</strong>에서 댓글을 확인할 수 있습니다.
                          </span>
                        ) : (
                          '수집된 댓글이 없습니다.'
                        )}
                      </li>
                    ) : (
                      sortedPostComments.map((c, i) => (
                        <li key={i} className="result__comment-item">
                          <span className="result__comment-meta-inline">
                            <span className="result__comment-author">{c.author}</span>
                            {c.date && <span className="result__comment-date">{c.date}</span>}
                          </span>
                          <span className="result__comment-text">{c.text}</span>
                        </li>
                      ))
                    )}
                  </ul>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div className="result__items-pagination result__items-pagination--bottom" aria-label="게시글 페이지">
          <button
            type="button"
            className="result__pagination-btn"
            onClick={() => { setCurrentPage(p => Math.max(1, p - 1)); setExpandedNo(null); }}
            disabled={currentPage <= 1}
            aria-label="이전 페이지"
          >
            이전
          </button>
          <span className="result__pagination-info">
            {currentPage} / {totalPages} (50개씩)
          </span>
          <button
            type="button"
            className="result__pagination-btn"
            onClick={() => { setCurrentPage(p => Math.min(totalPages, p + 1)); setExpandedNo(null); }}
            disabled={currentPage >= totalPages}
            aria-label="다음 페이지"
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}

/* YouTube 단일 영상 댓글: 총 댓글 수 · 정렬 · 접기/펼치기 */
export function YouTubeComments({ comments, totalComments }) {
  const [expanded, setExpanded] = useState(true);
  const [order, setOrder] = useState('등록순');

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
      const sortedList = sortYoutubeComments(list, order);
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

  return (
    <div className="result__items">
      <div className="result__comment-count-bar" aria-label="YouTube 댓글">
        <div className="result__comment-count-inner">
          <div className="result__comment-count-main">
            <span className="result__comment-count-label">
              💬 {label}
            </span>
            <button
              type="button"
              className="result__comments-toggle result__comments-toggle--all"
              onClick={() => setExpanded(v => !v)}
              aria-expanded={expanded}
            >
              {expanded ? '댓글 접기' : '댓글 펼치기'}
            </button>
          </div>
          <div className="result__comment-controls">
            <span className="result__comment-sort-label">정렬</span>
            <div className="result__comment-sort">
              {['등록순', '최신순', '좋아요순'].map(o => (
                <button
                  key={o}
                  type="button"
                  className={`result__comment-sort-btn ${order === o ? 'is-active' : ''}`}
                  onClick={() => setOrder(o)}
                  aria-pressed={order === o}
                >
                  {o}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
      {expanded && (
        <div className="result__all-comments" aria-label="YouTube 댓글 목록">
          {grouped.map((group, gi) => (
            <div key={group.videoId || gi} className="result__comments-group">
              <div className="result__comments-group-head">
                <span className="result__comments-group-title">
                  [{group.title}]
                </span>
                {group.videoId && (
                  <a
                    href={`https://www.youtube.com/watch?v=${group.videoId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="result__comment-post-link"
                  >
                    원문
                  </a>
                )}
                <span className="result__comments-group-count">
                  댓글 {formatNumber(group.comments.length)}개
                </span>
              </div>
              <ul className="result__comments-sublist result__comments-sublist--all">
                {group.comments.map((c, i) => (
                  <li key={i} className="result__comment-item">
                    <span className="result__comment-meta-inline">
                      {c.author && <span className="result__comment-author">{c.author}</span>}
                      {c.published_at && <span className="result__comment-date">{c.published_at}</span>}
                      {c.like_count != null && (
                        <span className="result__comment-like">👍 {formatNumber(c.like_count)}</span>
                      )}
                    </span>
                    <span className="result__comment-text">{c.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
