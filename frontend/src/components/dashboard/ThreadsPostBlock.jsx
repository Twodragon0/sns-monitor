import React, { useState, useEffect, useRef } from 'react';
import DOMPurify from 'dompurify';
import { formatNumber } from '../../constants/platforms';

/* --- Threads Post Block --- */
export function ThreadsPostBlock({ embedHtml, url, replies, description, content, result }) {
  const embedRef = useRef(null);
  const [showAllReplies, setShowAllReplies] = useState(false);

  useEffect(() => {
    if (!embedHtml) return;
    const container = embedRef.current;
    if (!container) return;
    if (container.querySelector('[data-text-post-permalink]')) return;
    const sanitized = DOMPurify.sanitize(embedHtml, {
      ADD_TAGS: ['blockquote'],
      ADD_ATTR: ['data-text-post-permalink', 'data-text-post-version', 'class', 'style', 'cite'],
      FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form'],
    });
    container.innerHTML = sanitized;
    const existing = document.querySelector('script[src="https://www.threads.com/embed.js"]');
    if (!existing) {
      const script = document.createElement('script');
      script.src = 'https://www.threads.com/embed.js';
      script.async = true;
      document.body.appendChild(script);
    }
  }, [embedHtml]);

  const replyList = Array.isArray(replies) ? replies : [];
  const hasEmbed = !!embedHtml?.trim();
  const postContent = content || description || '';
  const displayReplies = showAllReplies ? replyList : replyList.slice(0, 20);
  const hasToken = result?.source === 'threads_api';

  return (
    <div className="result__desc result__threads-block">
      <h4>게시글</h4>
      {hasEmbed ? (
        <div ref={embedRef} className="result__threads-embed" />
      ) : postContent ? (
        <div className="result__threads-content">
          <p className="result__threads-text">{postContent}</p>
        </div>
      ) : (
        <p className="result__threads-no-embed">게시글 내용을 불러오지 못했습니다. 원문 링크에서 확인해 주세요.</p>
      )}
      {url && (
        <a href={url} target="_blank" rel="noopener noreferrer" className="result__link" style={{ display: 'inline-block', marginTop: 8 }}>
          Threads 원문 보기 →
        </a>
      )}
      <h4>
        댓글 {replyList.length > 0
          ? `(${replyList.length}${result?.reply_count > replyList.length ? ` / ${result.reply_count}` : ''})`
          : result?.reply_count > 0 ? `(${result.reply_count}건)` : ''}
      </h4>
      {replyList.length > 0 ? (
        <>
          <ul className="result__comments-sublist">
            {displayReplies.map((r, i) => (
              <li key={i} className="result__comment-item">
                <span className="result__comment-meta-inline">
                  {r.author && <span className="result__comment-author">{r.author}</span>}
                  {r.date && <span className="result__comment-date">{r.date}</span>}
                </span>
                <span className="result__comment-text">{r.text || r.title || ''}</span>
              </li>
            ))}
          </ul>
          {replyList.length > 20 && !showAllReplies && (
            <button className="result__show-more-btn" onClick={() => setShowAllReplies(true)}>
              나머지 {replyList.length - 20}개 댓글 더 보기
            </button>
          )}
        </>
      ) : !hasToken ? (
        <div className="result__threads-hint">
          <p>THREADS_ACCESS_TOKEN을 설정하면 댓글(답글)을 수집할 수 있습니다.</p>
          <p className="result__threads-hint-detail">
            Meta Developer 앱에서 Threads API 권한(threads_basic, threads_read_replies)을 활성화하고,
            발급받은 Access Token을 .env에 설정하세요.
          </p>
        </div>
      ) : (
        <p className="result__threads-hint">이 게시글에 댓글이 없습니다.</p>
      )}
    </div>
  );
}
