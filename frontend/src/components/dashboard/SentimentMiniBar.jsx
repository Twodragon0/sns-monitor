/** Mini sentiment bar (CSS classes, dark mode compatible) */
export function SentimentMiniBar({ sentiment }) {
  if (!sentiment) return null;
  const { positive = 0, neutral = 0, negative = 0 } = sentiment;
  const total = positive + neutral + negative;
  if (total === 0) return null;
  const pct = (v) => Math.round((v / total) * 100);
  return (
    <div className="sentiment-mini-bar">
      <div className="sentiment-mini-bar__track">
        {positive > 0 && <div className="sentiment-mini-bar__seg--pos" style={{ width: `${pct(positive)}%` }} />}
        {neutral > 0 && <div className="sentiment-mini-bar__seg--neu" style={{ width: `${pct(neutral)}%` }} />}
        {negative > 0 && <div className="sentiment-mini-bar__seg--neg" style={{ width: `${pct(negative)}%` }} />}
      </div>
      <div className="sentiment-mini-bar__labels">
        <span className="sentiment-mini-bar__pos">+{positive}</span>
        <span>{total}건</span>
        <span className="sentiment-mini-bar__neg">-{negative}</span>
      </div>
    </div>
  );
}
