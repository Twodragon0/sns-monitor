import React from 'react';
import { render } from '@testing-library/react';
import axios from 'axios';
import Dashboard from './Dashboard';

jest.mock('axios');

beforeEach(() => {
  // Stub all axios methods to return resolved promises with empty data
  axios.get = jest.fn().mockResolvedValue({ data: { sources: [], channels: [], galleries: [], creators: [], status: 'idle' } });
  axios.post = jest.fn().mockResolvedValue({ data: {} });

  // Stub fetch for monitor data endpoints
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ channels: [], galleries: [], creators: [] }),
  });
});

afterEach(() => {
  jest.clearAllMocks();
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
});
