import React from 'react';
import { render, waitFor, act, fireEvent, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import axios from 'axios';
import Dashboard from './Dashboard';

vi.mock('axios');

// Mock AuthContext so AnalysisResult (which uses useAuth) doesn't throw
vi.mock('../contexts/AuthContext', () => ({
  AuthProvider: ({ children }) => children,
  useAuth: () => ({ loggedIn: false, authRequired: false, login: vi.fn(), logout: vi.fn() }),
}));

beforeEach(() => {
  // Stub all axios methods to return resolved promises with empty data
  axios.get = vi.fn().mockResolvedValue({ data: { sources: [], channels: [], galleries: [], creators: [], status: 'idle' } });
  axios.post = vi.fn().mockResolvedValue({ data: {} });

  // Stub fetch for monitor data endpoints
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ channels: [], galleries: [], creators: [] }),
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('Dashboard loadMonitorData errors', () => {
  it('calls onShowError when all 3 monitor endpoints fail', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/channels'))
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      if (url.includes('/api/dcinside/galleries'))
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      if (url.includes('/api/vuddy/creators'))
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
    });

    const onShowError = vi.fn();
    render(<Dashboard onShowError={onShowError} />);

    await waitFor(() => {
      expect(onShowError).toHaveBeenCalledTimes(1);
    }, { timeout: 3000 });

    const msg = onShowError.mock.calls[0][0];
    expect(
      msg.includes('모니터링 데이터 로드 실패') ||
      msg.includes('YouTube') ||
      msg.includes('DCInside')
    ).toBe(true);
  });

  it('does not call onShowError when only some endpoints fail', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/channels'))
        return Promise.resolve({ ok: true, json: async () => ({ channels: [] }) });
      if (url.includes('/api/dcinside/galleries'))
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      if (url.includes('/api/vuddy/creators'))
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    const onShowError = vi.fn();
    render(<Dashboard onShowError={onShowError} />);

    await new Promise((resolve) => setTimeout(resolve, 200));
    expect(onShowError).not.toHaveBeenCalled();
  });

  it('does not spam onShowError on repeated failed polls', async () => {
    global.fetch = vi.fn().mockImplementation(() =>
      Promise.reject(new Error('Network Error'))
    );

    const onShowError = vi.fn();
    render(<Dashboard onShowError={onShowError} />);

    await waitFor(() => {
      expect(onShowError).toHaveBeenCalledTimes(1);
    }, { timeout: 3000 });

    // Allow any additional async work to settle
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should still only be called once (ref guard prevents spam)
    expect(onShowError).toHaveBeenCalledTimes(1);
  });

  it('re-notifies onShowError after recovery cycle: 3/3 fail → 2/3 fail → 3/3 fail', async () => {
    // Stub AbortSignal.timeout so fake timers don't interfere with it
    const abortStub = vi.spyOn(AbortSignal, 'timeout').mockReturnValue(new AbortController().signal);

    // Helper: flush the microtask queue (Promise chains) without touching timers.
    // Promise.resolve() microtasks are NOT controlled by fake timers.
    const flushMicrotasks = async () => {
      for (let i = 0; i < 20; i++) await Promise.resolve();
    };

    vi.useFakeTimers();
    let unmount;
    try {
      const onShowError = vi.fn();

      // --- Cycle 1: mount triggers loadMonitorData — all 3 fail → toast fires ---
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });
      ({ unmount } = render(<Dashboard onShowError={onShowError} />));

      // Flush the fetch promises from the mount-time loadMonitorData call
      await flushMicrotasks();

      expect(onShowError).toHaveBeenCalledTimes(1);
      expect(onShowError.mock.calls[0][0]).toContain('모니터링 데이터 로드 실패');

      // --- Cycle 2: 60s tick — channels OK, others fail → flag resets, NO new toast ---
      global.fetch = vi.fn().mockImplementation((url) => {
        if (url.includes('/api/channels')) {
          return Promise.resolve({ ok: true, status: 200, json: async () => ({ channels: [] }) });
        }
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      });

      // Advance clock synchronously — this fires the setInterval callback which calls loadMonitorData
      vi.advanceTimersByTime(60000);
      // Flush the resulting fetch promise chain
      await flushMicrotasks();

      // Partial failure: flag reset but no new toast
      expect(onShowError).toHaveBeenCalledTimes(1);

      // --- Cycle 3: 60s tick — all 3 fail again → toast fires again ---
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });

      vi.advanceTimersByTime(60000);
      await flushMicrotasks();

      expect(onShowError).toHaveBeenCalledTimes(2);
      expect(onShowError.mock.calls[1][0]).toContain('모니터링 데이터 로드 실패');
    } finally {
      unmount?.();
      vi.useRealTimers();
      abortStub.mockRestore();
    }
  });
});

describe('Dashboard (smoke)', () => {
  it('renders without crashing', () => {
    const { container } = render(<Dashboard onShowError={() => {}} />);
    expect(container).toBeTruthy();
  });

  it('shows main content without throwing', () => {
    const { container } = render(<Dashboard onShowError={() => {}} />);
    expect(container.firstChild).toBeTruthy();
  });

  it('has no accessibility violations', async () => {
    const { container } = render(<Dashboard onShowError={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.dashboard')).toBeTruthy(), { timeout: 3000 }).catch(() => {});
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

/* ============================================================
   Dashboard interactions
   ============================================================ */
describe('Dashboard interactions', () => {
  // Helper: build a minimal valid analysis result
  const makeYoutubeResult = (overrides = {}) => ({
    platform: 'youtube',
    title: 'Test Video',
    analyzed_at: '2024-01-01T12:00:00Z',
    comment_count: 10,
    comments: [{ text: 'Nice!', author: 'user1', published_at: '2024-01-01' }],
    analysis: {
      overall: 'positive',
      total: 1,
      sentiment: { positive: 1, neutral: 0, negative: 0 },
      top_keywords: [],
    },
    ...overrides,
  });

  const makeDCResult = (overrides = {}) => ({
    platform: 'dcinside',
    gallery_id: 'test_gallery',
    gallery_name: 'Test Gallery',
    analyzed_at: '2024-01-01T12:00:00Z',
    total_posts: 5,
    posts: [],
    type: 'gallery',
    analysis: {
      overall: 'neutral',
      total: 0,
      sentiment: { positive: 0, neutral: 0, negative: 0 },
      top_keywords: [],
    },
    ...overrides,
  });

  // Clear localStorage before each interaction test to prevent state bleed
  beforeEach(() => {
    localStorage.clear();
  });

  // Helper: find the URL input reliably regardless of aria-label lookup mode
  const getUrlInput = (container) => container.querySelector('input[aria-label="분석할 URL"]');

  // Render dashboard and wait for monitor data to settle
  const renderDashboard = async (props = {}) => {
    let result;
    await act(async () => {
      result = render(<Dashboard onShowError={vi.fn()} {...props} />);
    });
    return result;
  };

  /* ── URL input & successful analyze ── */
  it('shows analysisResult after successful YouTube analyze', async () => {
    axios.post = vi.fn().mockResolvedValue({ data: makeYoutubeResult() });

    const { getByLabelText, getByText } = await renderDashboard();

    const input = getByLabelText('분석할 URL');
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=test123' } });

    const btn = getByText('분석');
    await act(async () => { fireEvent.click(btn); });

    await waitFor(() => {
      expect(getByText('Test Video')).toBeTruthy();
    }, { timeout: 3000 });

    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/analyze/url'),
      { url: 'https://www.youtube.com/watch?v=test123' },
      expect.objectContaining({ timeout: 300000 }),
    );
  });

  /* ── Platform badge appears when URL typed ── */
  it('shows YouTube platform badge when YouTube URL is typed', async () => {
    const { getByLabelText, container } = await renderDashboard();

    const input = getByLabelText('분석할 URL');
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });

    await waitFor(() => {
      const badge = container.querySelector('.dash__search-badge');
      expect(badge).toBeTruthy();
      expect(badge.textContent).toContain('YouTube');
    });
  });

  it('shows DCInside platform badge when DCInside URL is typed', async () => {
    const { getByLabelText, container } = await renderDashboard();

    const input = getByLabelText('분석할 URL');
    fireEvent.change(input, { target: { value: 'https://gall.dcinside.com/mgallery/board/list/?id=test' } });

    await waitFor(() => {
      const badge = container.querySelector('.dash__search-badge');
      expect(badge).toBeTruthy();
      expect(badge.textContent).toContain('DCInside');
    });
  });

  it('shows no badge when URL does not match any platform', async () => {
    const { getByLabelText, container } = await renderDashboard();

    const input = getByLabelText('분석할 URL');
    fireEvent.change(input, { target: { value: 'https://example.com/some/page' } });

    const badge = container.querySelector('.dash__search-badge');
    expect(badge).toBeNull();
  });

  /* ── Analyze button disabled when input empty ── */
  it('analyze button is disabled when URL input is empty', async () => {
    const { getByText } = await renderDashboard();
    const btn = getByText('분석');
    expect(btn).toBeDisabled();
  });

  it('analyze button is enabled after typing a URL', async () => {
    const { getByLabelText, getByText } = await renderDashboard();
    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://youtube.com/watch?v=x' } });
    const btn = getByText('분석');
    expect(btn).not.toBeDisabled();
  });

  /* ── Error paths ── */
  it('shows network error message when axios rejects with ERR_NETWORK', async () => {
    const err = new Error('Network Error');
    err.code = 'ERR_NETWORK';
    axios.post = vi.fn().mockRejectedValue(err);

    const { getByLabelText, getByText, getByRole } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://youtube.com/watch?v=x' } });
    await act(async () => { fireEvent.click(getByText('분석')); });

    await waitFor(() => {
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('API 서버에 연결할 수 없습니다');
    });
  });

  it('shows timeout error message when axios rejects with ECONNABORTED', async () => {
    const err = new Error('timeout of 300000ms exceeded');
    err.code = 'ECONNABORTED';
    axios.post = vi.fn().mockRejectedValue(err);

    const { getByLabelText, getByText, getByRole } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://youtube.com/watch?v=x' } });
    await act(async () => { fireEvent.click(getByText('분석')); });

    await waitFor(() => {
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('요청 시간이 초과');
    });
  });

  it('shows 429 rate-limit error message', async () => {
    const err = new Error('Too Many Requests');
    err.response = { status: 429, data: { error: 'rate limited' } };
    axios.post = vi.fn().mockRejectedValue(err);

    const { getByLabelText, getByText, getByRole } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://youtube.com/watch?v=x' } });
    await act(async () => { fireEvent.click(getByText('분석')); });

    await waitFor(() => {
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('요청이 너무 많습니다');
    });
  });

  it('shows 500 server error message', async () => {
    const err = new Error('Internal Server Error');
    err.response = { status: 500, data: { error: '서버 오류' } };
    axios.post = vi.fn().mockRejectedValue(err);

    const { getByLabelText, getByText, getByRole } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://youtube.com/watch?v=x' } });
    await act(async () => { fireEvent.click(getByText('분석')); });

    await waitFor(() => {
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('서버 오류 (500)');
    });
  });

  it('shows generic error message for other errors', async () => {
    const err = new Error('알 수 없는 오류');
    err.response = { status: 400, data: { error: '잘못된 URL' } };
    axios.post = vi.fn().mockRejectedValue(err);

    const { getByLabelText, getByText, getByRole } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://youtube.com/watch?v=x' } });
    await act(async () => { fireEvent.click(getByText('분석')); });

    await waitFor(() => {
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('잘못된 URL');
    });
  });

  /* ── Error clears on next input change ── */
  it('clears error message when user types into input after an error', async () => {
    const err = new Error('Network Error');
    err.code = 'ERR_NETWORK';
    axios.post = vi.fn().mockRejectedValue(err);

    const { getByLabelText, getByText, getByRole, queryByRole } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://youtube.com/watch?v=x' } });
    await act(async () => { fireEvent.click(getByText('분석')); });
    await waitFor(() => expect(getByRole('alert')).toBeTruthy());

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://youtube.com/watch?v=y' } });
    expect(queryByRole('alert')).toBeNull();
  });

  /* ── History management ── */
  it('adds entry to history after successful analyze', async () => {
    axios.post = vi.fn().mockResolvedValue({ data: makeYoutubeResult({ title: 'My Video' }) });

    const { getByLabelText, getByText, container } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://www.youtube.com/watch?v=hist1' } });
    await act(async () => { fireEvent.click(getByText('분석')); });

    await waitFor(() => expect(getByText('My Video')).toBeTruthy());

    // Clear result to see history (history shows only when no analysisResult)
    // history is persisted in localStorage; reload component to show history list
    // The current render shows the result card, not history. Verify localStorage was set.
    const stored = JSON.parse(localStorage.getItem('sns-monitor-history') || '[]');
    expect(stored.length).toBeGreaterThan(0);
    expect(stored[0].url).toBe('https://www.youtube.com/watch?v=hist1');
  });

  it('shows history list when history exists and no analysisResult', async () => {
    localStorage.setItem('sns-monitor-history', JSON.stringify([
      { url: 'https://youtube.com/watch?v=abc', platform: 'youtube', title: '과거 영상', analyzed_at: '2024-01-01T10:00:00Z' },
    ]));

    const { getByText } = await renderDashboard();

    await waitFor(() => {
      expect(getByText('최근 분석')).toBeTruthy();
      expect(getByText('과거 영상')).toBeTruthy();
    });
  });

  it('clicking history item loads the cached result', async () => {
    const cached = makeYoutubeResult({ title: '캐시된 영상' });
    const cacheKey = 'sns-monitor-results';
    localStorage.setItem(cacheKey, JSON.stringify({
      urls: ['https://youtube.com/watch?v=cached'],
      data: { 'https://youtube.com/watch?v=cached': cached },
    }));
    localStorage.setItem('sns-monitor-history', JSON.stringify([
      { url: 'https://youtube.com/watch?v=cached', platform: 'youtube', title: '캐시된 영상', analyzed_at: '2024-01-01T10:00:00Z' },
    ]));

    const { getByText } = await renderDashboard();

    await waitFor(() => expect(getByText('캐시된 영상')).toBeTruthy());

    await act(async () => {
      fireEvent.click(getByText('캐시된 영상'));
    });

    // After clicking history item the result should render (title appears in AnalysisResult)
    await waitFor(() => {
      // The cached title should appear in the rendered result card
      const allInstances = document.querySelectorAll('*');
      const found = Array.from(allInstances).some(el => el.textContent.includes('캐시된 영상'));
      expect(found).toBe(true);
    });
  });

  it('clears history when 삭제 button is clicked', async () => {
    localStorage.setItem('sns-monitor-history', JSON.stringify([
      { url: 'https://youtube.com/watch?v=abc', platform: 'youtube', title: '삭제할 영상', analyzed_at: '2024-01-01T10:00:00Z' },
    ]));

    const { getByText, queryByText } = await renderDashboard();

    await waitFor(() => expect(getByText('삭제할 영상')).toBeTruthy());

    await act(async () => {
      fireEvent.click(getByText('삭제'));
    });

    await waitFor(() => {
      expect(queryByText('삭제할 영상')).toBeNull();
    });

    expect(JSON.parse(localStorage.getItem('sns-monitor-history') || '[]')).toHaveLength(0);
  });

  /* ── Platform auto-tab switch ── */
  it('switches to YouTube tab after successful YouTube analyze', async () => {
    axios.post = vi.fn().mockResolvedValue({ data: makeYoutubeResult() });

    const { getByLabelText, getByText, container } = await renderDashboard();

    // Ensure we start on overview
    const overviewTab = getByText('전체 개요');
    expect(overviewTab.getAttribute('aria-selected')).toBe('true');

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://www.youtube.com/watch?v=test' } });
    await act(async () => { fireEvent.click(getByText('분석')); });

    await waitFor(() => {
      const ytTab = container.querySelector('[id="tab-youtube"]');
      expect(ytTab?.getAttribute('aria-selected')).toBe('true');
    }, { timeout: 3000 });
  });

  it('switches to DCInside tab after successful DCInside analyze', async () => {
    axios.post = vi.fn().mockResolvedValue({ data: makeDCResult() });

    const { getByLabelText, getByText, container } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), {
      target: { value: 'https://gall.dcinside.com/mgallery/board/list/?id=test' },
    });
    await act(async () => { fireEvent.click(getByText('분석')); });

    await waitFor(() => {
      const dcTab = container.querySelector('[id="tab-dcinside"]');
      expect(dcTab?.getAttribute('aria-selected')).toBe('true');
    }, { timeout: 3000 });
  });

  /* ── Tab switching ── */
  it('switches to DCInside tab when DCInside tab is clicked', async () => {
    const { getByText, container } = await renderDashboard();

    await waitFor(() => expect(container.querySelector('#tab-dcinside')).toBeTruthy());

    await act(async () => {
      fireEvent.click(container.querySelector('#tab-dcinside'));
    });

    expect(container.querySelector('#tab-dcinside')?.getAttribute('aria-selected')).toBe('true');
    expect(container.querySelector('#tab-overview')?.getAttribute('aria-selected')).toBe('false');
  });

  it('switches to X (Twitter) tab when clicked', async () => {
    const { container } = await renderDashboard();

    await waitFor(() => expect(container.querySelector('#tab-twitter')).toBeTruthy());

    await act(async () => {
      fireEvent.click(container.querySelector('#tab-twitter'));
    });

    expect(container.querySelector('#tab-twitter')?.getAttribute('aria-selected')).toBe('true');
  });

  it('switches to social tab when clicked', async () => {
    const { container } = await renderDashboard();

    await waitFor(() => expect(container.querySelector('#tab-social')).toBeTruthy());

    await act(async () => {
      fireEvent.click(container.querySelector('#tab-social'));
    });

    expect(container.querySelector('#tab-social')?.getAttribute('aria-selected')).toBe('true');
  });

  it('switches to YouTube tab when clicked', async () => {
    const { container } = await renderDashboard();

    await waitFor(() => expect(container.querySelector('#tab-youtube')).toBeTruthy());

    await act(async () => {
      fireEvent.click(container.querySelector('#tab-youtube'));
    });

    expect(container.querySelector('#tab-youtube')?.getAttribute('aria-selected')).toBe('true');
  });

  /* ── Summarize button ── */
  it('calls summarize endpoint and renders summary when AI 요약 clicked', async () => {
    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: makeYoutubeResult({ title: 'Summary Test' }) })
      .mockResolvedValueOnce({ data: { summary: 'AI가 생성한 요약입니다.', source: 'local' } });

    const { getByLabelText, getByText } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://www.youtube.com/watch?v=sum1' } });
    await act(async () => { fireEvent.click(getByText('분석')); });

    await waitFor(() => expect(getByText('Summary Test')).toBeTruthy());

    // Click AI 요약 button
    await act(async () => {
      fireEvent.click(getByText('🤖 AI 요약'));
    });

    await waitFor(() => {
      expect(getByText('AI가 생성한 요약입니다.')).toBeTruthy();
    }, { timeout: 3000 });

    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/analyze/summarize'),
      expect.objectContaining({ result: expect.any(Object) }),
      expect.objectContaining({ timeout: 60000 }),
    );
  });

  it('shows summarize timeout error message', async () => {
    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: makeYoutubeResult() })
      .mockRejectedValueOnce(Object.assign(new Error('timeout'), { code: 'ECONNABORTED' }));

    const { getByLabelText, getByText, getByRole } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://www.youtube.com/watch?v=sum2' } });
    await act(async () => { fireEvent.click(getByText('분석')); });
    await waitFor(() => expect(getByText('Test Video')).toBeTruthy());

    await act(async () => { fireEvent.click(getByText('🤖 AI 요약')); });

    await waitFor(() => {
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('요약 요청 시간이 초과');
    });
  });

  it('shows summarize network error message', async () => {
    const netErr = Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' });
    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: makeYoutubeResult() })
      .mockRejectedValueOnce(netErr);

    const { getByLabelText, getByText, getByRole } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://www.youtube.com/watch?v=sum3' } });
    await act(async () => { fireEvent.click(getByText('분석')); });
    await waitFor(() => expect(getByText('Test Video')).toBeTruthy());

    await act(async () => { fireEvent.click(getByText('🤖 AI 요약')); });

    await waitFor(() => {
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('API 서버에 연결할 수 없습니다');
    });
  });

  it('shows 413 payload too large error for summarize', async () => {
    const err = Object.assign(new Error('Payload Too Large'), { response: { status: 413, data: {} } });
    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: makeYoutubeResult() })
      .mockRejectedValueOnce(err);

    const { getByLabelText, getByText, getByRole } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://www.youtube.com/watch?v=sum4' } });
    await act(async () => { fireEvent.click(getByText('분석')); });
    await waitFor(() => expect(getByText('Test Video')).toBeTruthy());

    await act(async () => { fireEvent.click(getByText('🤖 AI 요약')); });

    await waitFor(() => {
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('요청 크기가 서버 제한을 초과');
    });
  });

  it('shows 429 rate-limit error for summarize', async () => {
    const err = Object.assign(new Error('Too Many Requests'), { response: { status: 429, data: {} } });
    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: makeYoutubeResult() })
      .mockRejectedValueOnce(err);

    const { getByLabelText, getByText, getByRole } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://www.youtube.com/watch?v=sum5' } });
    await act(async () => { fireEvent.click(getByText('분석')); });
    await waitFor(() => expect(getByText('Test Video')).toBeTruthy());

    await act(async () => { fireEvent.click(getByText('🤖 AI 요약')); });

    await waitFor(() => {
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('요청이 너무 많습니다');
    });
  });

  /* ── Stat boxes render with monitor data ── */
  it('renders StatBox values when monitor data is loaded', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/channels')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            channels: [{ id: 'ch1', name: '테스트채널', total_comments: 1500 }],
          }),
        });
      }
      if (url.includes('/api/dcinside/galleries')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            galleries: [{ id: 'g1', total_posts: 200, total_comments: 300, positive_count: 100, negative_count: 50 }],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({ creators: [] }) });
    });

    const { container } = await renderDashboard();

    await waitFor(() => {
      const statBoxes = container.querySelectorAll('.dash__stat-box');
      expect(statBoxes.length).toBeGreaterThan(0);
    }, { timeout: 3000 });

    // After data loads, total = ytComments(1500) + dcComments(300) = 1800
    await waitFor(() => {
      const statValues = Array.from(container.querySelectorAll('.dash__stat-value')).map(el => el.textContent);
      // At least one stat should show a non-zero formatted number
      const hasData = statValues.some(v => v !== '0');
      expect(hasData).toBe(true);
    }, { timeout: 3000 });
  });

  /* ── Hero section renders correctly ── */
  it('renders the hero section with title and description', async () => {
    const { getByText } = await renderDashboard();
    expect(getByText('URL 검색 · 분석')).toBeTruthy();
    expect(getByText(/지원 플랫폼의 URL을 입력하면/)).toBeTruthy();
  });

  it('renders the monitoring section with title', async () => {
    const { getByText } = await renderDashboard();
    expect(getByText('플랫폼별 모니터링')).toBeTruthy();
  });

  it('renders platform tags in hero section', async () => {
    const { container } = await renderDashboard();
    const tags = container.querySelectorAll('.dash__platform-tag');
    expect(tags.length).toBeGreaterThan(0);
  });

  it('shows monitoring hint when stats total is 0', async () => {
    const { getAllByRole } = await renderDashboard();
    await waitFor(() => {
      const hints = getAllByRole('status');
      const match = hints.find(h => h.textContent.includes('URL 검색으로 단일 URL을 즉시 분석'));
      expect(match).toBeTruthy();
    }, { timeout: 3000 });
  });

  /* ── monitoring analysis CTA ── */
  it('shows recent URL analysis info in monitoring section after analyze', async () => {
    axios.post = vi.fn().mockResolvedValue({ data: makeYoutubeResult({ title: 'CTA Test Video' }) });

    const { getByLabelText, getByText } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://www.youtube.com/watch?v=cta1' } });
    await act(async () => { fireEvent.click(getByText('분석')); });

    await waitFor(() => expect(getByText('CTA Test Video')).toBeTruthy());

    await waitFor(() => {
      expect(getByText(/최근 URL 분석:/)).toBeTruthy();
    });
  });

  /* ── Creator section ── */
  it('renders creator cards when creators data is loaded', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/vuddy/creators')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            creators: [
              { name: '크리에이터A', youtube_channel: '@creatorA', comments: [], total_likes: 100 },
            ],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({ channels: [], galleries: [] }) });
    });

    const { container } = await renderDashboard();

    await waitFor(() => {
      const creatorCards = container.querySelectorAll('.dash__creator-card');
      expect(creatorCards.length).toBeGreaterThan(0);
    }, { timeout: 3000 });

    await waitFor(() => {
      expect(container.querySelector('.dash__creator-card strong').textContent).toBe('크리에이터A');
    });
  });

  /* ── OverviewPanel shows with data ── */
  it('overview tab is active by default', async () => {
    const { container } = await renderDashboard();
    const overviewTab = container.querySelector('#tab-overview');
    expect(overviewTab?.getAttribute('aria-selected')).toBe('true');
  });

  /* ── Form submit with empty URL does nothing ── */
  it('does not call axios.post when form submitted with whitespace-only URL', async () => {
    axios.post = vi.fn();

    const { getByLabelText, container } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: '   ' } });

    const form = container.querySelector('form.dash__search');
    await act(async () => { fireEvent.submit(form); });

    expect(axios.post).not.toHaveBeenCalled();
  });

  /* ── Loading state disables input during analyze ── */
  it('disables input while analysis is in progress', async () => {
    let resolveAnalyze;
    axios.post = vi.fn().mockReturnValue(new Promise(resolve => { resolveAnalyze = resolve; }));

    const { getByLabelText, getByText } = await renderDashboard();

    fireEvent.change(getByLabelText('분석할 URL'), { target: { value: 'https://youtube.com/watch?v=loading' } });

    act(() => { fireEvent.click(getByText('분석')); });

    await waitFor(() => {
      expect(getByLabelText('분석할 URL')).toBeDisabled();
      expect(getByText('분석 중…')).toBeTruthy();
    });

    // Resolve to clean up
    await act(async () => {
      resolveAnalyze({ data: makeYoutubeResult() });
    });
  });
});
