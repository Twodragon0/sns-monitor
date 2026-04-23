import { useState, useEffect } from 'react';
import axios from 'axios';
import {
  XAxis, YAxis,
  Tooltip, ResponsiveContainer,
  LineChart, Line,
} from 'recharts';
import { API_BASE } from '../../config';
import { SentimentMiniBar } from './SentimentMiniBar';

/** Custom tooltip that respects CSS variable colours */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div style={{
      background: 'var(--c-surface)',
      border: '1px solid var(--c-border)',
      borderRadius: 8,
      padding: '6px 10px',
      fontSize: 11,
      color: 'var(--c-text)',
      boxShadow: 'var(--shadow-md)',
    }}>
      <p style={{ margin: '0 0 4px', color: 'var(--c-text-secondary)', fontSize: 10 }}>{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} style={{ margin: '2px 0', color: entry.color, fontWeight: 600 }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
}

/** Trend mini chart for a single gallery */
export function GalleryTrendChart({ galleryId }) {
  const [trend, setTrend] = useState(null);
  useEffect(() => {
    axios.get(`${API_BASE}/api/analysis/trend?type=dcinside&id=${galleryId}`)
      .then(({ data }) => setTrend(data.trend || []))
      .catch(() => setTrend([]));
  }, [galleryId]);

  if (!trend || trend.length < 2) return (
    <p className="panel-card__hint" style={{ margin: '4px 0', fontStyle: 'italic' }}>
      트렌드 데이터 부족 — 크롤러가 2회 이상 수집한 후 표시됩니다
    </p>
  );

  const chartData = trend.map(t => ({
    time: t.timestamp?.slice(5, 16).replace('T', ' ') || '',
    pos: t.positive,
    neg: t.negative,
    total: t.total,
  }));

  return (
    <div style={{ marginTop: 6 }}>
      <ResponsiveContainer width="100%" height={80}>
        <LineChart data={chartData} margin={{ top: 2, right: 4, bottom: 0, left: -20 }}>
          <XAxis dataKey="time" tick={{ fontSize: 9, fill: 'var(--c-text-secondary)' }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 9, fill: 'var(--c-text-secondary)' }} />
          <Tooltip content={<ChartTooltip />} />
          <Line type="monotone" dataKey="pos" stroke="#10b981" strokeWidth={2} dot={false} name="긍정" animationDuration={800} />
          <Line type="monotone" dataKey="neg" stroke="#ef4444" strokeWidth={2} dot={false} name="부정" animationDuration={800} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function GalleryMonitorPanel() {
  const [dcSources, setDcSources] = useState([]);
  const [sentiments, setSentiments] = useState({});
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null); // gallery ID for trend chart

  useEffect(() => {
    axios.get(`${API_BASE}/api/analysis/sources`)
      .then(({ data }) => {
        const dc = (data.sources || []).filter(s => s.type === 'dcinside' && !s.id.startsWith('example'));
        setDcSources(dc);
        if (dc.length > 0) {
          axios.post(`${API_BASE}/api/analysis/local-summary`, {
            sources: dc.map(s => ({ type: 'dcinside', id: s.id })),
          }).then(({ data: result }) => {
            const map = {};
            (result.sources || []).forEach(s => { map[s.id] = s.sentiment?.sentiment; });
            setSentiments(map);
          }).catch(() => {});
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function parseLatestDate(latest) {
    if (!latest) return '—';
    const m = latest.match(/^(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})/);
    if (m) return `${m[2]}.${m[3]} ${m[4]}:${m[5]}`;
    return latest.replace('.json', '');
  }

  function goAnalysis(source) {
    try {
      sessionStorage.setItem('analysisPreselect', JSON.stringify([{ type: 'dcinside', id: source.id }]));
    } catch (_) { /* ignore */ }
    window.history.pushState({}, '', '/analysis');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }

  if (loading) return null;
  if (dcSources.length === 0) return (
    <div className="gallery-monitor" style={{ marginTop: 20 }}>
      <h4 className="dash__section-title" style={{ marginBottom: 10 }}>DCInside 갤러리 모니터링</h4>
      <div style={{
        padding: '20px 18px',
        background: 'var(--c-bg)',
        border: '1.5px dashed var(--c-border)',
        borderRadius: 10,
        textAlign: 'center',
        color: 'var(--c-text-secondary)',
        fontSize: '0.85rem',
        lineHeight: 1.6,
      }}>
        <span style={{ fontSize: 28, display: 'block', marginBottom: 8 }} aria-hidden="true">📋</span>
        <strong style={{ color: 'var(--c-text)', display: 'block', marginBottom: 4 }}>수집된 갤러리 없음</strong>
        DCInside 크롤러를 실행하거나 상단 URL 검색에서 갤러리 URL을 입력하면 여기에 모니터링 카드가 표시됩니다.
      </div>
    </div>
  );

  // Detect negative sentiment alerts (neg > 5% of total)
  const alerts = Object.entries(sentiments)
    .map(([id, s]) => {
      if (!s) return null;
      const total = (s.positive || 0) + (s.neutral || 0) + (s.negative || 0);
      const negPct = total > 0 ? Math.round((s.negative || 0) / total * 100) : 0;
      return negPct >= 5 ? { id, name: dcSources.find(d => d.id === id)?.name || id, negPct, negative: s.negative } : null;
    })
    .filter(Boolean);

  return (
    <div className="gallery-monitor">
      <h4 className="dash__section-title" style={{ marginBottom: 12 }}>DCInside 갤러리 모니터링</h4>

      {alerts.length > 0 && (
        <div className="gallery-monitor__alert">
          <strong className="gallery-monitor__alert-title">부정 감성 경고</strong>
          {alerts.map(a => (
            <span key={a.id} className="gallery-monitor__alert-item">
              {a.name}:{' '}
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                background: 'rgba(239,68,68,0.12)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 12,
                padding: '1px 7px',
                fontSize: 11,
                fontWeight: 700,
                color: 'var(--c-danger)',
                marginLeft: 4,
              }}>
                {a.negPct}% · {a.negative}건
              </span>
            </span>
          ))}
        </div>
      )}
      <div className="gallery-monitor__grid">
        {dcSources.map(src => (
          <div key={src.id} className="panel-card gallery-monitor__card">
            <div className="gallery-monitor__card-head">
              <h5 className="panel-card__title gallery-monitor__card-title">{src.name || src.id}</h5>
              <button
                type="button"
                className="gallery-monitor__trend-btn"
                onClick={() => setExpanded(expanded === src.id ? null : src.id)}
              >
                {expanded === src.id ? '닫기' : '트렌드'}
              </button>
            </div>
            <div className="panel-card__body gallery-monitor__meta">
              <span>수집 {src.files || 0}회</span>
              <span>{parseLatestDate(src.latest)}</span>
            </div>
            <SentimentMiniBar sentiment={sentiments[src.id]} />
            {expanded === src.id && <GalleryTrendChart galleryId={src.id} />}
            <button
              type="button"
              className="gallery-monitor__analyze-btn"
              onClick={() => goAnalysis(src)}
            >
              분석
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
