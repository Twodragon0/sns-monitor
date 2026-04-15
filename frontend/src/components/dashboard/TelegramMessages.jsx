import React, { useState, useMemo } from 'react';
import { formatNumber } from '../../constants/platforms';

/* --- Telegram Messages --- */
export function TelegramMessages({ messages, totalMessages }) {
  const [expanded, setExpanded] = useState(true);
  const [visibleCount, setVisibleCount] = useState(20);
  const [order, setOrder] = useState('등록순');
  const PAGE_SIZE = 20;

  const sorted = useMemo(() => {
    if (!messages?.length) return [];
    const list = [...messages];
    if (order === '최신순' && list.some(m => m.date)) {
      list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    }
    return list;
  }, [messages, order]);

  const label = totalMessages ? `${messages.length}건 / 전체 ${formatNumber(totalMessages)}건` : `${messages.length}건`;

  return (
    <div className="result__items">
      <div className="result__items-head">
        <h4>수집된 콘텐츠</h4>
      </div>
      <div className="result__comment-count-bar">
        <div className="result__comment-count-inner">
          <span className="result__comment-count-label">메시지 ({label})</span>
          <div className="result__comment-sort">
            {['등록순', '최신순'].map(o => (
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
        <div className="result__items-list">
          {sorted.slice(0, visibleCount).map((msg, idx) => (
            <div key={idx} className="result__item">
              <div className="result__item-text">{msg.text || ''}</div>
              <div className="result__item-meta">
                {msg.date && <span>{msg.date}</span>}
                {msg.views && <span>👁 {msg.views}</span>}
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
    </div>
  );
}
