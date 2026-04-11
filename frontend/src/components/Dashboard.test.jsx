import React from 'react';
import { render, waitFor, act } from '@testing-library/react';
import { axe } from 'jest-axe';
import axios from 'axios';
import Dashboard from './Dashboard';

vi.mock('axios');

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
