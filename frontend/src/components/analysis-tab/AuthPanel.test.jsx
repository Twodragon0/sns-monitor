import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import { AuthPanel, providerLabel } from './AuthPanel';

vi.mock('axios');

afterEach(() => {
  vi.clearAllMocks();
});

describe('providerLabel', () => {
  it('returns "AI" for null/undefined provider', () => {
    expect(providerLabel(null)).toBe('AI');
    expect(providerLabel(undefined)).toBe('AI');
  });

  it('returns "Claude" for anthropic/claude providers', () => {
    expect(providerLabel('anthropic')).toBe('Claude');
    expect(providerLabel('claude-3')).toBe('Claude');
  });

  it('returns "ChatGPT" for openai providers', () => {
    expect(providerLabel('openai')).toBe('ChatGPT');
    expect(providerLabel('opencode')).toBe('ChatGPT');
  });

  it('returns "Gemini" for gemini providers', () => {
    expect(providerLabel('gemini')).toBe('Gemini');
    expect(providerLabel('gemini-pro')).toBe('Gemini');
  });

  it('returns uppercased CLI name for cli: prefix', () => {
    expect(providerLabel('cli:custom')).toBe('CUSTOM');
  });

  it('returns provider as-is for unknown providers', () => {
    expect(providerLabel('some-other')).toBe('some-other');
  });
});

describe('AuthPanel', () => {
  const defaultProps = {
    apiBase: 'http://localhost:8888',
    onKeySet: vi.fn(),
    openaiOAuthAvailable: false,
  };

  it('renders without crashing', () => {
    const { container } = render(<AuthPanel {...defaultProps} />);
    expect(container).toBeTruthy();
  });

  it('renders API key input and provider select', () => {
    render(<AuthPanel {...defaultProps} />);
    expect(screen.getByPlaceholderText(/sk-proj-/)).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('connect button is disabled when API key is empty', () => {
    render(<AuthPanel {...defaultProps} />);
    expect(screen.getByRole('button', { name: '연결' })).toBeDisabled();
  });

  it('connect button becomes enabled after typing a key', () => {
    render(<AuthPanel {...defaultProps} />);
    fireEvent.change(screen.getByPlaceholderText(/sk-proj-/), {
      target: { value: 'sk-proj-test123' },
    });
    expect(screen.getByRole('button', { name: '연결' })).toBeEnabled();
  });

  it('switching provider to anthropic changes placeholder', () => {
    render(<AuthPanel {...defaultProps} />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'anthropic' } });
    expect(screen.getByPlaceholderText(/sk-ant-api03-/)).toBeInTheDocument();
  });

  it('calls API on connect and invokes onKeySet on success', async () => {
    const onKeySet = vi.fn();
    axios.post = vi.fn().mockResolvedValue({ data: { ok: true } });

    render(<AuthPanel {...defaultProps} onKeySet={onKeySet} />);
    fireEvent.change(screen.getByPlaceholderText(/sk-proj-/), {
      target: { value: 'sk-proj-test123' },
    });
    fireEvent.click(screen.getByRole('button', { name: '연결' }));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        'http://localhost:8888/api/auth/apikey',
        { provider: 'openai', api_key: 'sk-proj-test123' },
        { withCredentials: true }
      );
      expect(onKeySet).toHaveBeenCalled();
    });
  });

  it('shows error message when API key submission fails', async () => {
    axios.post = vi.fn().mockRejectedValue({
      response: { data: { error: 'Invalid key' } },
      message: 'Request failed',
    });

    render(<AuthPanel {...defaultProps} />);
    fireEvent.change(screen.getByPlaceholderText(/sk-proj-/), {
      target: { value: 'sk-bad-key' },
    });
    fireEvent.click(screen.getByRole('button', { name: '연결' }));

    await waitFor(() => {
      expect(screen.getByText('Invalid key')).toBeInTheDocument();
    });
  });

  it('pressing Enter in the key input triggers submit', async () => {
    const onKeySet = vi.fn();
    axios.post = vi.fn().mockResolvedValue({ data: { ok: true } });

    render(<AuthPanel {...defaultProps} onKeySet={onKeySet} />);
    const input = screen.getByPlaceholderText(/sk-proj-/);
    fireEvent.change(input, { target: { value: 'sk-proj-test123' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalled();
    });
  });

  it('renders OAuth login buttons', () => {
    render(<AuthPanel {...defaultProps} />);
    expect(screen.getByRole('button', { name: 'Claude' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'ChatGPT' })).toBeInTheDocument();
  });
});
