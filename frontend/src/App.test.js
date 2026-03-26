import React from 'react';
import { render } from '@testing-library/react';
import axios from 'axios';
import App from './App';

jest.mock('axios');

beforeEach(() => {
  // Stub axios methods used by child components
  axios.get = jest.fn().mockResolvedValue({ data: { sources: [], channels: [], galleries: [], creators: [], status: 'idle', api_usage: {} } });
  axios.post = jest.fn().mockResolvedValue({ data: {} });

  // Stub fetch for health check, auth/me, and monitor data endpoints
  global.fetch = jest.fn().mockResolvedValue({
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
  jest.clearAllMocks();
});

describe('App (smoke)', () => {
  it('renders without crashing', () => {
    const { container } = render(<App />);
    expect(container).toBeTruthy();
  });
});
