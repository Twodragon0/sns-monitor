/**
 * API base URL for backend requests.
 * - Docker: same-origin (''), nginx proxies /api to backend.
 * - Local dev (npm start): default http://localhost:8888 when VITE_API_URL not set.
 * Override with VITE_API_URL in .env.
 */
export const API_BASE =
  import.meta.env.VITE_API_URL !== undefined && import.meta.env.VITE_API_URL !== ''
    ? import.meta.env.VITE_API_URL.replace(/\/$/, '')
    : import.meta.env.DEV
      ? 'http://localhost:8888'
      : '';
