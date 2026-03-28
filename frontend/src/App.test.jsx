import React from 'react';
import { render, waitFor } from '@testing-library/react';
import { axe } from 'jest-axe';
import axios from 'axios';
import App from './App';

vi.mock('axios');

beforeEach(() => {
  // Stub axios methods used by child components
  axios.get = vi.fn().mockResolvedValue({ data: { sources: [], channels: [], galleries: [], creators: [], status: 'idle', api_usage: {} } });
  axios.post = vi.fn().mockResolvedValue({ data: {} });

  // Stub fetch for health check, auth/me, and monitor data endpoints
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      logged_in: false,
      auth_required: false,
      channels: [],
      galleries: [],
      creators: [],
    }),
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('App (smoke)', () => {
  it('renders without crashing', () => {
    const { container } = render(<App />);
    expect(container).toBeTruthy();
  });

  it('has no accessibility violations', async () => {
    const { container } = render(<App />);
    await waitFor(() => expect(container.querySelector('.App')).toBeTruthy());
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
