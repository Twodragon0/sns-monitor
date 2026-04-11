/**
 * Single source of truth for platform metadata, formatting, and sort utilities.
 * All components should import from here instead of defining their own copies.
 */

export const PLATFORMS = {
  youtube:    { label: 'YouTube',       color: '#FF0000', icon: '\u25B6' },
  dcinside:   { label: 'DCInside',      color: '#0253fe', icon: '\uD83D\uDCCB' },
  naver_cafe: { label: '\uB124\uC774\uBC84 \uCE74\uD398', color: '#03c75a', icon: '\u2615' },
  reddit:     { label: 'Reddit',        color: '#FF4500', icon: '\uD83D\uDD17' },
  telegram:   { label: 'Telegram',      color: '#0088cc', icon: '\u2708' },
  kakao:      { label: 'Kakao',         color: '#FEE500', icon: '\uD83D\uDCAC' },
  twitter:    { label: 'X (Twitter)',   color: '#000000', icon: '\uD835\uDD4F' },
  instagram:  { label: 'Instagram',     color: '#E1306C', icon: '\uD83D\uDCF8' },
  facebook:   { label: 'Facebook',      color: '#1877F2', icon: '\uD83D\uDC65' },
  threads:    { label: 'Threads',       color: '#000000', icon: '\uD83E\uDDF5' },
  tiktok:     { label: 'TikTok',        color: '#000000', icon: '\uD83C\uDFB5' },
};

export const SENTIMENT_COLORS = {
  positive: '#10b981',
  neutral:  '#9ca3af',
  negative: '#ef4444',
};

/**
 * Format a number with K/M suffixes for compact display.
 * @param {number|string|null} num
 * @returns {string}
 */
export function formatNumber(num) {
  if (num == null) return '0';
  const n = typeof num === 'string' ? parseInt(num.replace(/[,\s]/g, ''), 10) : Number(num);
  if (isNaN(n)) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

/**
 * Sort comments by order string.
 * @param {Array} comments
 * @param {'등록순'|'최신순'|'답글순'} order
 */
export function sortComments(comments, order) {
  if (!comments?.length) return comments || [];
  const list = [...comments];
  if (order === '최신순' && list.some(c => c.date)) {
    list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  }
  return list;
}

/**
 * Sort YouTube comments by order string.
 * @param {Array} comments
 * @param {'등록순'|'최신순'|'좋아요순'} order
 */
export function sortYoutubeComments(comments, order) {
  if (!comments?.length) return comments || [];
  const list = [...comments];
  if (order === '최신순' && list.some(c => c.published_at)) {
    list.sort((a, b) => (b.published_at || '').localeCompare(a.published_at || ''));
  }
  if (order === '좋아요순') {
    list.sort((a, b) => (b.like_count ?? 0) - (a.like_count ?? 0));
  }
  return list;
}
