import React from 'react';
import { render, waitFor } from '@testing-library/react';
import { axe } from 'jest-axe';
import axios from 'axios';
import App from './App';

vi.mock('axios');
vi.mock('./contexts/AuthContext', () => ({
  AuthProvider: ({ children }) => children,
  useAuth: () => ({ loggedIn: false, authRequired: false, loading: false, login: vi.fn(), logout: vi.fn() }),
}));
vi.mock('./components/Dashboard', () => ({
  default: () => <div data-testid="dashboard-stub">Dashboard</div>,
}));
vi.mock('./components/CreatorDetail', () => ({
  default: () => <div data-testid="creator-stub">CreatorDetail</div>,
}));
vi.mock('./components/AnalysisTab', () => ({
  default: () => <div data-testid="analysis-stub">AnalysisTab</div>,
}));

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
  it('renders without crashing', async () => {
    const { container } = render(<App />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/health')));
    expect(container).toBeTruthy();
  });

  it('has no accessibility violations', async () => {
    const { container } = render(<App />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/health')));
    await waitFor(() => expect(container.querySelector('.App')).toBeTruthy());
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
