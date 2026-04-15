import React, { useState, useMemo } from 'react';
import { formatNumber } from '../../constants/platforms';

/* --- Twitter Replies --- */
export function TwitterReplies({ comments, replyCount }) {
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
    <div className="result__items">
      <div className="result__comment-count-bar">
        <div className="result__comment-count-inner">
          <span className="result__comment-count-label">💬 댓글 ({replyCount}건 중 {comments.length}건 수집)</span>
          <select
            className="result__comment-sort-select"
            value={sortOrder}
            onChange={e => setSortOrder(e.target.value)}
          >
            <option value="좋아요순">좋아요순</option>
            <option value="최신순">최신순</option>
            <option value="등록순">등록순</option>
          </select>
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
        <div className="result__items-list">
          {sorted.slice(0, visibleCount).map((c, idx) => (
            <div key={idx} className="result__item">
              <div className="result__item-text">{c.text}</div>
              <div className="result__item-meta">
                {c.author && <span className="result__item-author">{c.author}</span>}
                {c.like_count != null && <span>👍 {formatNumber(c.like_count)}</span>}
                {c.date && <span>{c.date}</span>}
              </div>
            </div>
          ))}
          {sorted.length > visibleCount && (
            <button
              type="button"
              className="result__show-more-btn"
              onClick={() => setVisibleCount(v => v + PAGE_SIZE)}
              style={{ margin: '12px auto', display: 'block' }}
            >
              더 보기 ({visibleCount}/{sorted.length})
            </button>
          )}
        </div>
      )}
      {!comments.length && replyCount > 0 && (
        <div className="result__twitter-hint" role="status">
          <p><strong>댓글을 수집하려면 TWITTER_BEARER_TOKEN이 필요합니다.</strong></p>
          <p>.env에 <code>TWITTER_BEARER_TOKEN</code>을 설정하고 재시작하면 트윗의 댓글(리플라이)이 함께 수집됩니다.</p>
        </div>
      )}
    </div>
  );
}
