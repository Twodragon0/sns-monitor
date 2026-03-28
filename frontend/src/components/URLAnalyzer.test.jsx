import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { axe } from 'jest-axe';
import axios from 'axios';
import URLAnalyzer from './URLAnalyzer';

vi.mock('axios');

beforeEach(() => {
  axios.get = vi.fn().mockResolvedValue({ data: { api_usage: null } });
  axios.post = vi.fn().mockResolvedValue({ data: {} });

  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({}),
  });

  // localStorage stub
  const store = {};
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => store[key] ?? null);
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key, val) => { store[key] = val; });
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((key) => { delete store[key]; });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe('URLAnalyzer', () => {
  it('renders without crashing', () => {
    const { container } = render(<URLAnalyzer />);
    expect(container).toBeTruthy();
  });

  it('renders the heading and description', () => {
    render(<URLAnalyzer />);
    expect(screen.getByText('SNS URL Analyzer')).toBeInTheDocument();
    expect(screen.getByText(/Paste any supported URL/i)).toBeInTheDocument();
  });

  it('renders URL input field', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: /분석할 URL 입력/i });
    expect(input).toBeInTheDocument();
  });

  it('can type a URL in the input field', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: /분석할 URL 입력/i });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=test' } });
    expect(input).toHaveValue('https://www.youtube.com/watch?v=test');
  });

  it('renders platform badges list', () => {
    render(<URLAnalyzer />);
    const list = screen.getByRole('list', { name: /지원 플랫폼/i });
    expect(list).toBeInTheDocument();
    const items = screen.getAllByRole('listitem');
    expect(items.length).toBeGreaterThan(0);
    expect(screen.getByText(/YouTube/)).toBeInTheDocument();
    expect(screen.getByText(/DCInside/)).toBeInTheDocument();
  });

  it('analyze button is disabled when URL is empty', () => {
    render(<URLAnalyzer />);
    const button = screen.getByRole('button', { name: /Analyze/i });
    expect(button).toBeDisabled();
  });

  it('analyze button is enabled after typing a URL', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: /분석할 URL 입력/i });
    const button = screen.getByRole('button', { name: /Analyze/i });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=test' } });
    expect(button).toBeEnabled();
  });

  it('shows platform badge when a recognized URL is typed', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: /분석할 URL 입력/i });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    // platform-badge (inline) + platform-tag (list) both show "YouTube" — just confirm at least one exists
    expect(screen.getAllByText(/YouTube/).length).toBeGreaterThanOrEqual(1);
    // the inline platform-badge should appear (has class platform-badge)
    const badge = document.querySelector('.platform-badge');
    expect(badge).toBeTruthy();
  });

  it('shows error message when API call fails', async () => {
    axios.post = vi.fn().mockRejectedValue({ message: 'Network Error' });
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: /분석할 URL 입력/i });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: /Analyze/i }).closest('form'));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('has no axe violations in default state', async () => {
    const { container } = render(<URLAnalyzer />);
    await waitFor(() => {}, { timeout: 500 });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('has no axe violations when showing an error', async () => {
    axios.post = vi.fn().mockRejectedValue({ message: 'Network Error' });
    const { container } = render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: /분석할 URL 입력/i });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: /Analyze/i }).closest('form'));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
