/**
 * API base URL for backend requests.
 * - Docker: same-origin (''), nginx proxies /api to backend.
 * - Local dev (npm start): default http://localhost:8888 when REACT_APP_API_URL not set.
 * Override with REACT_APP_API_URL in .env.
 */
export const API_BASE =
  process.env.REACT_APP_API_URL !== undefined && process.env.REACT_APP_API_URL !== ''
    ? process.env.REACT_APP_API_URL.replace(/\/$/, '')
    : process.env.NODE_ENV === 'development'
      ? 'http://localhost:8888'
      : '';
