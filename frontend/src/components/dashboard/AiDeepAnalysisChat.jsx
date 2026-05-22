import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { API_BASE } from '../../config';

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
