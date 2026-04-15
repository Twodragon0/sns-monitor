import React, { useState, useMemo } from 'react';
import { formatNumber } from '../../constants/platforms';

/* --- Reddit Subreddit Posts --- */
export function RedditSubredditPosts({ posts, totalPosts }) {
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
    <div className="result__items">
      <div className="result__items-head">
        <h4>Posts ({posts.length}건{totalPosts > posts.length ? ` / 전체 ${totalPosts}건` : ''})</h4>
        <p className="result__items-hint" aria-hidden="true">
          각 항목을 클릭하면 댓글이 표시됩니다. (댓글 있는 글 {postsWithComments}건)
        </p>
      </div>
      <div className="result__items-list">
        {posts.slice(0, 50).map((post, idx) => {
          const postKey = idx;
          const hasComments = post.comments?.length > 0;
          const isExpanded = expandedNo === postKey;
          return (
            <div key={postKey} className="result__item result__item--dcinside">
              {post.permalink ? (
                <a href={post.permalink} target="_blank" rel="noopener noreferrer" className="result__item-text result__item-text--link">
                  {post.text}
                </a>
              ) : (
                <div className="result__item-text">{post.text}</div>
              )}
              {post.selftext && <div className="result__item-selftext">{post.selftext}</div>}
              <div className="result__item-meta">
                {post.author && <span className="result__item-author">{post.author}</span>}
                {post.score != null && <span>⬆ {formatNumber(post.score)}</span>}
                {post.num_comments != null && <span>💬 {post.num_comments}</span>}
                {post.created_utc > 0 && (
                  <span>{new Date(post.created_utc * 1000).toLocaleString('ko-KR')}</span>
                )}
              </div>
              {post.permalink && (
                <a href={post.permalink} target="_blank" rel="noopener noreferrer" className="result__item-link">
                  View →
                </a>
              )}
              {hasComments && (
                <div className="result__comment-wrap">
                  <div className="result__comment-count">
                    <button
                      type="button"
                      className="result__comments-toggle result__comments-toggle--post"
                      onClick={() => setExpandedNo(isExpanded ? null : postKey)}
                      aria-expanded={isExpanded}
                    >
                      💬 댓글 {post.comments.length}개 {isExpanded ? '접기 ▲' : '클릭 시 보기 ▼'}
                    </button>
                  </div>
                  {isExpanded && (
                    <ul className="result__comments-sublist">
                      {post.comments.slice(0, commentVisibleCounts[postKey] || COMMENT_PAGE_SIZE).map((c, i) => (
                        <li key={i} className="result__comment-item">
                          <span className="result__comment-meta-inline">
                            <span className="result__comment-author">{c.author}</span>
                            {c.score != null && <span className="result__comment-score">⬆ {c.score}</span>}
                          </span>
                          <span className="result__comment-text">{c.text}</span>
                        </li>
                      ))}
                      {post.comments.length > (commentVisibleCounts[postKey] || COMMENT_PAGE_SIZE) && (
                        <li className="result__comment-show-more">
                          <button
                            type="button"
                            className="result__show-more-btn"
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

/* --- Reddit Post Comments --- */
export function RedditPostComments({ result }) {
  const [expanded, setExpanded] = useState(true);
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
    <div className="result__items">
      <div className="result__comment-count-bar">
        <div className="result__comment-count-inner">
          <span className="result__comment-count-label">💬 Comments ({sorted.length})</span>
          <div className="result__comment-sort">
            {['등록순', '최신순', '좋아요순'].map(o => (
              <button
                key={o}
                type="button"
                className={`result__comment-sort-btn ${order === o ? 'is-active' : ''}`}
                onClick={() => setOrder(o)}
              >
                {o}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="result__comments-toggle result__comments-toggle--all"
            onClick={() => setExpanded(v => !v)}
            aria-expanded={expanded}
          >
            {expanded ? '접기' : '펼치기'}
          </button>
        </div>
      </div>
      {expanded && (
        <ul className="result__comments-sublist">
          {sorted.slice(0, visibleCount).map((c, i) => (
            <li key={i} className="result__comment-item">
              <span className="result__comment-meta-inline">
                <span className="result__comment-author">{c.author}</span>
                {c.score != null && <span className="result__comment-score">⬆ {c.score}</span>}
                {c.created_utc > 0 && (
                  <span className="result__comment-date">{new Date(c.created_utc * 1000).toLocaleString('ko-KR')}</span>
                )}
              </span>
              <span className="result__comment-text">{c.text}</span>
            </li>
          ))}
          {sorted.length > visibleCount && (
            <li className="result__comment-show-more">
              <button
                type="button"
                className="result__show-more-btn"
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
