import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { API_BASE } from '../../config';

/** Word Cloud + Gallery Comparison + Negative Alert */
export function WordCloudAndCompare({ keywords }) {
  const [compareData, setCompareData] = useState([]);
  const [selectedGallery, setSelectedGallery] = useState(null);
  const [trendData, setTrendData] = useState([]);

  useEffect(() => {
    axios.get(`${API_BASE}/api/analysis/compare`)
      .then(({ data }) => setCompareData(data.galleries || []))
      .catch(() => {});
  }, []);

  // Load trend when gallery is clicked
  useEffect(() => {
    if (!selectedGallery) { setTrendData([]); return; }
    axios.get(`${API_BASE}/api/analysis/trend?type=dcinside&id=${selectedGallery}`)
      .then(({ data }) => setTrendData(data.trend || []))
      .catch(() => setTrendData([]));
  }, [selectedGallery]);

  const maxCount = keywords.length > 0 ? Math.max(...keywords.map(k => k.count)) : 1;

  // Negative alerts: galleries with neg_pct >= 5%
  const alerts = compareData.filter(g => g.neg_pct >= 5);

  return (
    <>
      {/* Negative sentiment alert */}
      {alerts.length > 0 && (
        <div style={{
          padding: '12px 16px', marginBottom: '16px',
          backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px',
        }}>
          <strong style={{ color: '#dc2626', fontSize: '13px' }}>부정 감성 경고</strong>
          {alerts.map(g => (
            <p key={g.id} style={{ margin: '4px 0 0', fontSize: '12px', color: '#7f1d1d' }}>
              <strong>{g.name}</strong>: 부정 {g.neg_pct}% ({g.negative}건)
              {g.keywords?.length > 0 && <span style={{ color: '#9ca3af' }}> — {g.keywords.slice(0, 3).join(', ')}</span>}
            </p>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '20px' }}>
        {/* Word Cloud */}
        {keywords.length > 0 && (
          <div style={{
            flex: '1 1 340px', backgroundColor: 'white', padding: '16px',
            borderRadius: '8px', border: '1px solid #dee2e6',
          }}>
            <h4 style={{ margin: '0 0 12px', fontSize: '14px', color: '#555' }}>키워드 클라우드</h4>
            <div style={{
              display: 'flex', flexWrap: 'wrap', gap: '6px', justifyContent: 'center',
              padding: '10px', minHeight: '100px',
            }}>
              {keywords.slice(0, 25).map((kw, i) => {
                const ratio = kw.count / maxCount;
                const size = Math.max(12, Math.round(ratio * 32 + 10));
                const colors = ['#1d4ed8', '#7c3aed', '#0891b2', '#059669', '#d97706', '#dc2626', '#6366f1', '#0d9488'];
                return (
                  <span key={i} style={{
                    fontSize: `${size}px`,
                    fontWeight: ratio > 0.5 ? 700 : 400,
                    color: colors[i % colors.length],
                    lineHeight: 1.3,
                    cursor: 'default',
                  }} title={`${kw.word}: ${kw.count}회`}>
                    {kw.word}
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {/* Gallery Comparison (clickable bars) */}
        {compareData.length > 1 && (
          <div style={{
            flex: '1 1 340px', backgroundColor: 'white', padding: '16px',
            borderRadius: '8px', border: '1px solid #dee2e6',
          }}>
            <h4 style={{ margin: '0 0 4px', fontSize: '14px', color: '#555' }}>갤러리간 감성 비교</h4>
            <p style={{ margin: '0 0 8px', fontSize: '11px', color: '#9ca3af' }}>클릭하면 트렌드를 표시합니다</p>
            <ResponsiveContainer width="100%" height={compareData.length * 40 + 30}>
              <BarChart data={compareData} layout="vertical" margin={{ left: 10, right: 10, top: 5, bottom: 5 }}
                onClick={(e) => { if (e?.activePayload?.[0]?.payload?.id) setSelectedGallery(prev => prev === e.activePayload[0].payload.id ? null : e.activePayload[0].payload.id); }}
                style={{ cursor: 'pointer' }}
              >
                <XAxis type="number" tick={{ fontSize: 11 }} unit="%" />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={100} />
                <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v, name) => [v + '%', name === 'pos_pct' ? '긍정' : '부정']} />
                <Bar dataKey="pos_pct" name="긍정" stackId="s" fill="#10b981" />
                <Bar dataKey="neg_pct" name="부정" stackId="s" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Inline trend chart for clicked gallery */}
      {selectedGallery && trendData.length >= 2 && (
        <div style={{
          backgroundColor: 'white', padding: '16px', borderRadius: '8px',
          border: '1px solid #c7d2fe', marginBottom: '20px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h4 style={{ margin: 0, fontSize: '14px', color: '#4338ca' }}>
              {compareData.find(g => g.id === selectedGallery)?.name || selectedGallery} 감성 트렌드
            </h4>
            <button type="button" onClick={() => setSelectedGallery(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', fontSize: '12px' }}>닫기</button>
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={trendData.map(t => ({
              time: t.timestamp?.slice(5, 16).replace('T', ' ') || '',
              positive: t.positive,
              negative: t.negative,
            }))} margin={{ left: -10, right: 10, top: 5, bottom: 5 }}>
              <XAxis dataKey="time" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ fontSize: 11 }} />
              <Bar dataKey="positive" fill="#10b981" name="긍정" />
              <Bar dataKey="negative" fill="#ef4444" name="부정" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {selectedGallery && trendData.length < 2 && (
        <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '16px' }}>
          {compareData.find(g => g.id === selectedGallery)?.name}: 트렌드 데이터 부족 (2회 이상 수집 필요)
        </p>
      )}
    </>
  );
}

/** Daily sentiment reports list + detail view */
export function DailyReportsPanel() {
  const [reports, setReports] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    axios.get(`${API_BASE}/api/analysis/reports`).then(({ data }) => setReports(data.reports || [])).catch(() => {});
  }, []);

  const generate = async () => {
    setGenerating(true);
    try {
      const { data } = await axios.post(`${API_BASE}/api/analysis/report/generate-daily`);
      setDetail(data);
      setSelected(data.date);
      // Refresh list
      const { data: list } = await axios.get(`${API_BASE}/api/analysis/reports`);
      setReports(list.reports || []);
    } catch (err) {
      alert(err.response?.data?.error || 'Report generation failed');
    } finally {
      setGenerating(false);
    }
  };

  const viewReport = async (date) => {
    if (selected === date) { setSelected(null); setDetail(null); return; }
    try {
      const { data } = await axios.get(`${API_BASE}/api/analysis/reports/${date}`);
      setDetail(data);
      setSelected(date);
    } catch { /* ignore */ }
  };

  return (
    <div style={{
      backgroundColor: 'white', padding: '16px', borderRadius: '8px',
      border: '1px solid #dee2e6', marginTop: '20px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ margin: 0 }}>일일 감성 보고서</h3>
        <button
          type="button" onClick={generate} disabled={generating}
          style={{
            padding: '6px 14px', fontSize: '12px', fontWeight: 600,
            background: generating ? '#94a3b8' : '#6366f1', color: 'white',
            border: 'none', borderRadius: '6px', cursor: generating ? 'not-allowed' : 'pointer',
          }}
        >
          {generating ? '생성 중...' : '오늘 보고서 생성'}
        </button>
      </div>

      {/* Report list */}
      {reports.length > 0 && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
          {reports.slice(0, 14).map(r => (
            <button key={r.date} type="button" onClick={() => viewReport(r.date)}
              style={{
                padding: '4px 10px', fontSize: '12px', borderRadius: '6px', cursor: 'pointer',
                background: selected === r.date ? '#6366f1' : '#f1f5f9',
                color: selected === r.date ? 'white' : '#475569',
                border: selected === r.date ? 'none' : '1px solid #e2e8f0',
              }}
            >
              {r.date?.slice(5)} ({r.summary?.total_items || 0}건)
            </button>
          ))}
        </div>
      )}

      {reports.length === 0 && !detail && (
        <p style={{ color: '#9ca3af', fontSize: '13px' }}>보고서가 없습니다. "오늘 보고서 생성"을 클릭하세요.</p>
      )}

      {/* Report detail */}
      {detail && (
        <div>
          <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
            {[
              { label: '총 분석', value: detail.summary?.total_items || 0, color: '#3b82f6' },
              { label: '긍정', value: `${detail.summary?.pos_pct || 0}%`, color: '#10b981' },
              { label: '부정', value: `${detail.summary?.neg_pct || 0}%`, color: '#ef4444' },
              { label: '경고', value: detail.summary?.alerts || 0, color: detail.summary?.alerts > 0 ? '#dc2626' : '#9ca3af' },
            ].map((s, i) => (
              <div key={i} style={{
                flex: 1, textAlign: 'center', padding: '10px',
                backgroundColor: `${s.color}10`, borderRadius: '8px', border: `1px solid ${s.color}30`,
              }}>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: s.color }}>{s.value}</div>
                <div style={{ fontSize: '11px', color: '#6b7280' }}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Gallery breakdown */}
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                <th style={{ textAlign: 'left', padding: '6px' }}>갤러리</th>
                <th style={{ textAlign: 'right', padding: '6px' }}>분석</th>
                <th style={{ textAlign: 'right', padding: '6px' }}>긍정</th>
                <th style={{ textAlign: 'right', padding: '6px' }}>부정</th>
                <th style={{ textAlign: 'left', padding: '6px' }}>키워드</th>
              </tr>
            </thead>
            <tbody>
              {(detail.galleries || []).map(g => (
                <tr key={g.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '6px', fontWeight: 500 }}>{g.name}</td>
                  <td style={{ padding: '6px', textAlign: 'right' }}>{g.total}</td>
                  <td style={{ padding: '6px', textAlign: 'right', color: '#10b981' }}>{g.pos_pct}%</td>
                  <td style={{ padding: '6px', textAlign: 'right', color: g.neg_pct >= 5 ? '#dc2626' : '#6b7280' }}>
                    {g.neg_pct}%
                  </td>
                  <td style={{ padding: '6px', color: '#9ca3af', fontSize: '11px' }}>{g.keywords?.slice(0, 3).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <p style={{ margin: '8px 0 0', fontSize: '11px', color: '#9ca3af' }}>
            생성: {detail.generated_at?.slice(0, 19).replace('T', ' ')} | 파일: {detail.galleries?.reduce((s, g) => s + (g.files_analyzed || 0), 0)}개
          </p>
        </div>
      )}
    </div>
  );
}
