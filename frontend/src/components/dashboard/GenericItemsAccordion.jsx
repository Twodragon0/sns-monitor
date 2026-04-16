import React, { useState } from 'react';
import { formatNumber } from '../../constants/platforms';

/* --- Generic Items Accordion (fallback) --- */
export function GenericItemsAccordion({ items, result }) {
  const [expanded, setExpanded] = useState(result.platform === 'reddit');
  const [visibleCount, setVisibleCount] = useState(20);
  const PAGE_SIZE = 20;

  const label = result.platform === 'dcinside' && result.type === 'post'
    ? `댓글 (${items.length})`
    : result.replies
      ? `댓글 (${items.length})`
      : `${result.comments ? '댓글' : result.recent_videos ? '최근 영상' : '게시글'} (${items.length})`;

  return (
    <div className="result__items">
      <div className="result__comment-count-bar">
        <div className="result__comment-count-inner">
          <span className="result__comment-count-label">💬 {label}</span>
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
          {items.slice(0, visibleCount).map((item, idx) => (
            <div key={idx} className="result__item">
              <div className="result__item-text">{item.text || item.title || item.selftext || ''}</div>
              <div className="result__item-meta">
                {item.author && <span className="result__item-author">{item.author}</span>}
                {(item.like_count != null || item.score != null || item.recommend != null) && (
                  <span>👍 {formatNumber(item.like_count ?? item.score ?? item.recommend ?? 0)}</span>
                )}
                {item.view_count != null && <span>👁 {formatNumber(item.view_count)}</span>}
                {item.num_comments != null && <span>💬 {item.num_comments}</span>}
                {(item.published_at || item.date) && <span>{item.published_at || item.date}</span>}
                {item.views && <span>👁 {item.views}</span>}
              </div>
              {(item.permalink || item.url) && (
                <a href={item.permalink || item.url} target="_blank" rel="noopener noreferrer" className="result__item-link">
                  View →
                </a>
              )}
            </div>
          ))}
          {items.length > visibleCount && (
            <button
              type="button"
              className="result__show-more-btn"
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
