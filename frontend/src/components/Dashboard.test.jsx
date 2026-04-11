import React from 'react';
import { render, waitFor } from '@testing-library/react';
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
