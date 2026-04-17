<!-- Parent: ../AGENTS.md -->

# Frontend (React 19 Dashboard)

Generated: 2026-04-08

## Purpose

React 19 single-page application (SPA) for SNS content analysis. Provides URL analyzer, sentiment visualization with Recharts, LLM-powered data analysis (MiroFish), and creator monitoring dashboard.

## Tech Stack

- **Framework:** React 19.2.4 with React DOM
- **Build Tool:** Vite 8.0.3 with @vitejs/plugin-react 6.0.1
- **HTTP Client:** Axios 1.13.6
- **Charting:** Recharts 3.8.1 (sentiment trends, statistics visualization)
- **Security:** DOMPurify 3.3.3 (HTML sanitization)
- **Testing:** Vitest 3.2.4, @testing-library/react 16.3.2, @testing-library/jest-dom 6.9.1
- **Dev Server:** Port 3000 (configured in vite.config.js); proxies `/api` to backend at http://localhost:8888

## Key Files

- `vite.config.js` — Build and dev server config, test environment setup
- `package.json` — Dependencies, scripts (start, build, test, test:coverage)
- `index.html` — Vite entry point
- `.env.example` — Environment variables template
- `src/config.js` — `API_BASE` configuration (backend URL resolution)
- `src/index.jsx` — React entry point
- `src/App.jsx` — Root component and routing
- `src/setupTests.js` — Vitest setup (jsdom, globals)

## Directory Structure

```
src/
├── App.jsx                              # Root component, router, error boundary
├── config.js                            # API_BASE URL configuration
├── contexts/
│   └── AuthContext.jsx                  # useAuth() hook, OAuth login/logout
├── components/
│   ├── Dashboard.jsx                    # Main monitoring dashboard
│   ├── URLAnalyzer.jsx                  # URL input, platform detection, analysis
│   ├── AnalysisTab.jsx                  # MiroFish LLM analysis interface
│   ├── CreatorDetail.jsx                # Creator profile detail pages
│   ├── ErrorBoundary.jsx                # React error boundary
│   ├── Toast.jsx                        # Notification messages
│   ├── EmptyState.jsx                   # Empty state UI
│   ├── LoadingSkeleton.jsx              # Loading placeholder
│   ├── analysis-tab/
│   │   ├── AnalysisWidgets.jsx          # LLM task widgets, progress indicators
│   │   ├── AuthPanel.jsx                # Login/logout UI for analysis features
│   │   └── ResultPanels.jsx             # Analysis result cards and charts
│   ├── dashboard/
│   │   ├── AnalysisResult.jsx           # Result card with metadata
│   │   └── MonitorPanels.jsx            # Creator monitoring panels
│   └── url-analyzer/
│       └── ResultComponents.jsx         # Platform-specific result UI (YouTube, DCInside, Reddit, Telegram, Threads, Twitter)
├── utils/
│   └── analysis.js                      # Cache management, platform detection, data trimming
├── constants/
│   └── platforms.js                     # Platform metadata (icons, names, colors)
└── public/                              # Static assets
```

## API Endpoints (Backend Integration)

All requests use `API_BASE` (configured via `VITE_API_URL` env var or defaults):

| Method | Endpoint | Usage |
|--------|----------|-------|
| POST | `/api/analyze/url` | Analyze URL (YouTube, DCInside, Reddit, Telegram, Kakao, Naver Cafe, Threads, Twitter) |
| GET | `/api/platforms` | List supported platforms, API usage stats |
| GET | `/api/auth/me` | Check auth status (OAuth) |
| GET | `/api/auth/openai` | OAuth login redirect |
| POST | `/api/auth/logout` | Logout and clear session |
| GET | `/api/analysis/status` | MiroFish analysis task status |
| GET | `/api/analysis/sources` | Available data sources |
| POST | `/api/analysis/transform` | Transform analysis data |
| POST | `/api/analysis/graph/build` | Build analysis graph |
| GET | `/api/analysis/graph/task/<id>` | Get graph task result |
| GET | `/api/analysis/graph/data/<id>` | Get graph data |
| POST | `/api/analysis/report/chat` | LLM chat on analysis results |

## Context & Hooks

**AuthContext** (`src/contexts/AuthContext.jsx`):
- `useAuth()` — Returns `{ loggedIn, user, authRequired, loading, login(), logout(), refreshAuth() }`
- Used by AnalysisTab and AuthPanel for OAuth login

## Component Architecture

**URLAnalyzer:**
- Detects platform from URL input (auto-completes platform badge)
- Submits URL to `/api/analyze/url` with platform-specific options
- Displays results via ResultComponents (platform-specific rendering)
- Caches results in localStorage (key: `sns-analyzer-results`)
- Shows API usage stats and 80% quota warnings

**AnalysisTab (MiroFish):**
- Checks auth status via `useAuth()`
- Submits analysis tasks to `/api/analysis/graph/build`
- Polls graph task status and renders results
- AuthPanel gates login for restricted features

**Dashboard:**
- Renders creator monitoring panels
- Integrates AnalysisResult cards
- Shows statistics and trends via Recharts

## State Management

- **Local state:** Component-level via `useState()`
- **Auth state:** React Context (`AuthContext`)
- **Cache:** localStorage (`sns-analyzer-results`, `sns-analyzer-history`)

## Testing

- **Unit tests:** Individual components and utilities (`.test.jsx` files)
- **Setup:** `src/setupTests.js` configures jsdom and globals
- **Run:** `npm test` (watch mode), `npm run test:coverage` (with coverage)
- **Coverage target:** 80%+

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_URL` | `http://localhost:8888` (dev) or `` (prod) | Backend API base URL |

## For AI Agents

When modifying components:
- Use `API_BASE` from `src/config.js` for all backend calls
- Get auth state via `useAuth()` hook from AuthContext
- Import components with ES module named imports
- Test with `npm run test:coverage` before committing
- Follow immutable patterns (spread operator for state updates)
- Use DOMPurify for HTML rendering: `dangerouslySetInnerHTML: { __html: DOMPurify.sanitize(html) }`
- Detect platforms via `detectPlatform(url)` utility
- Dev server port: 3000; backend proxy: /api → http://localhost:8888
