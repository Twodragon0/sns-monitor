import React, { useState, useMemo, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../../config';
import { formatNumber, sortComments } from '../../constants/platforms';

export const POSTS_PER_PAGE = 50;

export const POST_SORT_OPTIONS = [
  { value: 'date_desc', label: '최신순' },
  { value: 'date_asc', label: '오래된순' },
  { value: 'popular', label: '인기순' },
  { value: 'comments', label: '댓글 많은 순' },
];

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
  // 단건 URL 재수집 진행 중인 postKey 집합 (Set<key>): 게시글별 독립 single-flight
  const [loadingPostKeys, setLoadingPostKeys] = useState(() => new Set());
  // 단건 URL 재수집을 게시글당 1회로 제한 (실패한 경우 해머링 방지)
  // 값: 'done'(성공/실패 관계없이 시도 완료) 또는 에러 메시지
  const [refetchState, setRefetchState] = useState(() => new Map());

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
          // Fix 1: use post.url as primary stable key; fall back to post_id/number/page+idx
          const postKey = post.url ?? post.post_id ?? post.number ?? `page${currentPage}-idx${idx}`;
          const commentList = post.comments ?? [];
          const collectedCount = commentList.length;
          const listCount = post.comment_count ?? null;
          const isExpanded = expandedNo === postKey;
          const sortedPostComments = sortComments(commentList, commentSort);
          const commentLabel = listCount != null
            ? `댓글 (목록 ${listCount} / 수집 ${collectedCount})`
            : `댓글 (${collectedCount})`;
          const collectionFailed = listCount != null && listCount > 0 && collectedCount === 0;

          const refetchInfo = refetchState.get(postKey);
          const alreadyAttempted = refetchInfo !== undefined;
          const refetchErrorMsg = typeof refetchInfo === 'string' && refetchInfo !== 'done' ? refetchInfo : null;
          // Fix 2: per-post loading check (Set-based, not scalar)
          const isLoadingThis = loadingPostKeys.has(postKey);

          const toggleComments = async (e) => {
            if (e.target.closest('a')) return;
            const willExpand = !isExpanded;
            // 댓글이 목록상 1개 이상인데 아직 수집되지 않은 경우, 단건 URL로 재수집 시도
            // - 게시글당 최대 1회만 재시도 (alreadyAttempted 가드)로 해머링 방지
            // Fix 2: guard per-post, not global — allows parallel refetches for different posts
            if (willExpand && collectionFailed && post.url && !isLoadingThis && !alreadyAttempted) {
              try {
                setLoadingPostKeys((prev) => new Set(prev).add(postKey));
                const { data } = await axios.post(
                  `${API_BASE}/api/analyze/url`,
                  { url: post.url },
                  { timeout: 300000 },
                );
                const newComments = Array.isArray(data.comments) ? data.comments : [];
                // Fix 1: match by p.url — avoids closure-idx footgun
                // Fix 3: drop || p.comment_count so empty refetch returns 0, not stale count
                setLocalPosts((prev) =>
                  prev.map((p) =>
                    p.url === post.url
                      ? {
                          ...p,
                          comments: newComments,
                          comment_count:
                            typeof data.comment_count === 'number'
                              ? data.comment_count
                              : newComments.length,
                        }
                      : p,
                  ),
                );
                setRefetchState((prev) => new Map(prev).set(postKey, 'done'));
              } catch (err) {
                // 실패 메시지를 인라인 표시하여 침묵 실패 방지
                const msg = err?.response?.data?.error || err?.message || '댓글 재수집 실패';
                setRefetchState((prev) => new Map(prev).set(postKey, msg));
              } finally {
                setLoadingPostKeys((prev) => { const s = new Set(prev); s.delete(postKey); return s; });
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
                    {collectionFailed && !isLoadingThis && (
                      <span
                        className="result__comment-fail"
                        title="목록에는 댓글이 있으나 초기 수집에 실패했습니다. 클릭 시 단건 URL로 다시 시도합니다."
                      >
                        {' '}
                        (수집 실패)
                      </span>
                    )}
                    {isLoadingThis && (
                      <span className="result__comment-fail"> (댓글 불러오는 중…)</span>
                    )}
                    {refetchErrorMsg && !isLoadingThis && (
                      <span
                        className="result__comment-fail"
                        title={refetchErrorMsg}
                      >
                        {' '}(재수집 실패: {refetchErrorMsg})
                      </span>
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
