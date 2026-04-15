import React, { useState, useMemo } from 'react';
import { formatNumber, sortYoutubeComments } from '../../constants/platforms';

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
