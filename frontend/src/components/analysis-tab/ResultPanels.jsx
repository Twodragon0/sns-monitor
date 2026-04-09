import React from 'react';
import { providerLabel } from './AuthPanel';

export function LocalResultPanel({ localResult }) {
  return (
    <div style={{
      backgroundColor: 'white',
      padding: '20px',
      borderRadius: '8px',
      border: '1px solid #dee2e6',
      marginBottom: '20px',
    }}>
      <h3 style={{ marginTop: 0, marginBottom: '16px' }}>로컬 분석 결과 ({localResult.total_items}건 분석)</h3>

      {/* Overall sentiment */}
      {localResult.overall && (
        <div style={{ marginBottom: '20px' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>전체 감성 분포</h4>
          <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
            {['positive', 'neutral', 'negative'].map(key => {
              const count = localResult.overall.sentiment?.[key] || 0;
              const pct = localResult.overall.distribution?.[key] || 0;
              const colors = { positive: '#10b981', neutral: '#9ca3af', negative: '#ef4444' };
              const labels = { positive: '긍정', neutral: '중립', negative: '부정' };
              return (
                <div key={key} style={{
                  flex: 1, textAlign: 'center', padding: '12px',
                  backgroundColor: `${colors[key]}15`, borderRadius: '8px',
                  border: `1px solid ${colors[key]}40`,
                }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: colors[key] }}>
                    {Math.round(pct * 100)}%
                  </div>
                  <div style={{ fontSize: '12px', color: '#666' }}>
                    {labels[key]} ({count}건)
                  </div>
                </div>
              );
            })}
          </div>
          {/* Sentiment bar */}
          <div style={{ display: 'flex', height: '8px', borderRadius: '4px', overflow: 'hidden' }}>
            {['positive', 'neutral', 'negative'].map(key => {
              const pct = (localResult.overall.distribution?.[key] || 0) * 100;
              const colors = { positive: '#10b981', neutral: '#9ca3af', negative: '#ef4444' };
              return <div key={key} style={{ width: `${pct}%`, backgroundColor: colors[key] }} />;
            })}
          </div>
        </div>
      )}

      {/* Top keywords */}
      {localResult.overall?.top_keywords?.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>주요 키워드</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {localResult.overall.top_keywords.slice(0, 15).map((kw, i) => (
              <span key={kw.word} style={{
                padding: '4px 10px', borderRadius: '12px',
                backgroundColor: i < 3 ? '#dbeafe' : '#f1f5f9',
                color: i < 3 ? '#1d4ed8' : '#475569',
                fontSize: '13px', fontWeight: i < 3 ? '600' : '400',
              }}>
                {kw.word} <span style={{ color: '#999', fontSize: '11px' }}>({kw.count})</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Per-source breakdown */}
      {localResult.sources?.length > 1 && (
        <div>
          <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>소스별 분석</h4>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {localResult.sources.map((src, i) => (
              <div key={src.name ? `${src.type}-${src.name}` : i} style={{
                flex: '1 1 280px', padding: '12px',
                backgroundColor: '#f8f9fa', borderRadius: '6px',
                border: '1px solid #e2e8f0',
              }}>
                <div style={{ fontWeight: 'bold', marginBottom: '6px', fontSize: '13px' }}>
                  {src.type === 'youtube' ? 'YT' : 'DC'} {src.name}
                  <span style={{ fontWeight: 'normal', color: '#888', marginLeft: '6px' }}>({src.item_count}건)</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', fontSize: '12px' }}>
                  {['positive', 'neutral', 'negative'].map(key => {
                    const count = src.sentiment?.sentiment?.[key] || 0;
                    const labels = { positive: '긍정', neutral: '중립', negative: '부정' };
                    const colors = { positive: '#10b981', neutral: '#9ca3af', negative: '#ef4444' };
                    return (
                      <span key={key} style={{ color: colors[key] }}>
                        {labels[key]}: {count}
                      </span>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <p style={{ marginTop: '16px', marginBottom: 0, fontSize: '12px', color: '#999' }}>
        Kiwi 형태소 분석 기반. API Key 설정 시 AI 심화 분석이 가능합니다.
      </p>
    </div>
  );
}

export function AiResultPanel({ aiResult }) {
  return (
    <div style={{
      backgroundColor: 'white',
      padding: '20px',
      borderRadius: '8px',
      border: '1px solid #dee2e6',
      marginBottom: '20px',
    }}>
      <h3 style={{ marginTop: 0, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        AI 분석 결과
        <span style={{
          fontSize: '11px', padding: '2px 8px', borderRadius: '12px',
          backgroundColor: '#e3f2fd', color: '#1565c0',
        }}>
          {providerLabel(aiResult.provider)} ({aiResult.model})
        </span>
      </h3>

      {/* Summary */}
      {aiResult.summary && (
        <div style={{
          padding: '14px', backgroundColor: '#f8f9fa', borderRadius: '8px',
          marginBottom: '16px', lineHeight: '1.7', whiteSpace: 'pre-wrap',
        }}>
          {aiResult.summary}
        </div>
      )}

      {/* Sentiment from AI */}
      {aiResult.sentiment && (
        <div style={{ marginBottom: '16px' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>AI 감성 분석</h4>
          <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
            {[
              { key: 'positive_pct', label: '긍정', color: '#10b981' },
              { key: 'neutral_pct', label: '중립', color: '#9ca3af' },
              { key: 'negative_pct', label: '부정', color: '#ef4444' },
            ].map(({ key, label, color }) => (
              <div key={key} style={{
                flex: 1, textAlign: 'center', padding: '12px',
                backgroundColor: `${color}15`, borderRadius: '8px',
                border: `1px solid ${color}40`,
              }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color }}>
                  {aiResult.sentiment[key] || 0}%
                </div>
                <div style={{ fontSize: '12px', color: '#666' }}>{label}</div>
              </div>
            ))}
          </div>
          {aiResult.sentiment.positive_keywords?.length > 0 && (
            <div style={{ fontSize: '13px', marginTop: '8px' }}>
              <span style={{ color: '#10b981', fontWeight: '600' }}>긍정 키워드:</span>{' '}
              {aiResult.sentiment.positive_keywords.join(', ')}
            </div>
          )}
          {aiResult.sentiment.negative_keywords?.length > 0 && (
            <div style={{ fontSize: '13px', marginTop: '4px' }}>
              <span style={{ color: '#ef4444', fontWeight: '600' }}>부정 키워드:</span>{' '}
              {aiResult.sentiment.negative_keywords.join(', ')}
            </div>
          )}
        </div>
      )}

      {/* Topics */}
      {aiResult.topics?.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>주요 토픽</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {aiResult.topics.map((t, i) => (
              <div key={t.topic ? `${t.topic}-${i}` : i} style={{
                padding: '8px 14px', borderRadius: '8px',
                backgroundColor: i < 3 ? '#dbeafe' : '#f1f5f9',
                border: `1px solid ${i < 3 ? '#93c5fd' : '#e2e8f0'}`,
              }}>
                <div style={{ fontWeight: '600', fontSize: '13px', color: i < 3 ? '#1d4ed8' : '#475569' }}>
                  {t.topic} {t.count ? `(${t.count})` : ''}
                </div>
                {t.description && (
                  <div style={{ fontSize: '12px', color: '#666', marginTop: '2px' }}>{t.description}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Key Opinions */}
      {aiResult.key_opinions?.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>주요 의견</h4>
          {aiResult.key_opinions.map((op, i) => (
            <div key={op.text ? `${op.text.slice(0,20)}-${i}` : i} style={{
              padding: '10px 14px', marginBottom: '6px', borderRadius: '6px',
              backgroundColor: op.type === 'positive' ? '#f0fdf4' : op.type === 'negative' ? '#fef2f2' : '#f8f9fa',
              borderLeft: `3px solid ${op.type === 'positive' ? '#10b981' : op.type === 'negative' ? '#ef4444' : '#9ca3af'}`,
              fontSize: '13px',
            }}>
              {op.text}
              {op.support && <span style={{ color: '#999', marginLeft: '8px', fontSize: '11px' }}>({op.support}건)</span>}
            </div>
          ))}
        </div>
      )}

      {/* Insights */}
      {aiResult.insights?.length > 0 && (
        <div>
          <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>인사이트</h4>
          {aiResult.insights.map((ins, i) => (
            <div key={typeof ins === 'string' ? `${ins.slice(0,20)}-${i}` : i} style={{
              padding: '8px 12px', marginBottom: '4px', fontSize: '13px',
              color: '#374151', lineHeight: '1.5',
            }}>
              {ins}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
