import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import { renderSummaryContent, AiCtaButton, AnalysisResult } from './AnalysisResult';
import { AuthProvider } from '../../contexts/AuthContext';

vi.mock('axios');

vi.mock('recharts', () => ({
  PieChart: ({ children }) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => null,
  Cell: () => null,
  BarChart: ({ children }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  Legend: () => null,
}));

beforeAll(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterAll(() => {
  vi.restoreAllMocks();
});

beforeEach(() => {
  axios.get = vi.fn().mockImplementation((url) => {
    if (url.includes('/api/auth/me')) {
      return Promise.resolve({ data: { logged_in: false, auth_required: false } });
    }
    if (url.includes('/api/analysis/status')) {
      return Promise.resolve({ data: { mirofish_available: false } });
    }
    return Promise.resolve({ data: {} });
  });
  axios.post = vi.fn().mockResolvedValue({ data: {} });

  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ logged_in: false, auth_required: false }),
  });

  const store = {};
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation((k) => store[k] ?? null);
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation((k, v) => { store[k] = v; });
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((k) => { delete store[k]; });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

function renderWithAuth(ui) {
  return render(<AuthProvider>{ui}</AuthProvider>);
}

describe('renderSummaryContent', () => {
  it('returns null for falsy input', () => {
    expect(renderSummaryContent(null)).toBeNull();
    expect(renderSummaryContent('')).toBeNull();
  });

  it('returns plain string unchanged', () => {
    const result = renderSummaryContent('Plain text');
    expect(result).toBe('Plain text');
  });

  it('wraps **bold** in strong element', () => {
    const result = renderSummaryContent('Hello **world**!');
    expect(Array.isArray(result)).toBe(true);
    const strongEl = result.find(r => r?.type === 'strong');
    expect(strongEl).toBeDefined();
    expect(strongEl.props.children).toBe('world');
  });
});

describe('AiCtaButton', () => {
  const baseResult = { platform: 'youtube', channel_id: 'ch1' };

  it('renders without crashing', async () => {
    const { container } = renderWithAuth(<AiCtaButton result={baseResult} />);
    expect(container).toBeTruthy();
  });

  it('shows AI 심화 분석 button when not auth-required', async () => {
    renderWithAuth(<AiCtaButton result={baseResult} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /AI 심화 분석/i })).toBeInTheDocument();
    });
  });

  it('shows loading state during click', async () => {
    axios.get = vi.fn().mockReturnValue(new Promise(() => {}));
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ logged_in: false, auth_required: false }),
    });
    renderWithAuth(<AiCtaButton result={baseResult} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /AI 심화 분석/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /AI 심화 분석/i }));
    await waitFor(() => {
      expect(screen.getByText(/확인 중/i)).toBeInTheDocument();
    });
  });
});

describe('AnalysisResult (dashboard)', () => {
  const baseResult = {
    platform: 'youtube',
    title: 'My Video',
    analyzed_at: '2026-01-15T10:00:00Z',
    view_count: 5000,
    like_count: 200,
    comment_count: 80,
    analysis: {
      total: 80,
      sentiment: { positive: 50, neutral: 25, negative: 5 },
      top_keywords: [
        { keyword: 'great', count: 10 },
        { keyword: 'nice', count: 8 },
      ],
    },
    comments: [],
    url: 'https://youtube.com/watch?v=test',
  };

  it('renders without crashing', async () => {
    const { container } = renderWithAuth(
      <AnalysisResult result={baseResult} onSummarize={() => {}} />
    );
    expect(container).toBeTruthy();
  });

  it('shows result title', async () => {
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={() => {}} />);
    expect(screen.getByText('My Video')).toBeInTheDocument();
  });

  it('shows platform badge', async () => {
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={() => {}} />);
    expect(screen.getByText('YouTube')).toBeInTheDocument();
  });

  it('shows stats: view_count, like_count, comment_count', () => {
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={() => {}} />);
    expect(screen.getByText('5.0K')).toBeInTheDocument(); // formatNumber(5000)
    expect(screen.getByText('200')).toBeInTheDocument();
    expect(screen.getByText('80')).toBeInTheDocument();
  });

  it('shows AI 요약 button', () => {
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={() => {}} />);
    expect(screen.getByRole('button', { name: /AI 요약/i })).toBeInTheDocument();
  });

  it('calls onSummarize when 요약 button clicked', () => {
    const onSummarize = vi.fn();
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={onSummarize} />);
    fireEvent.click(screen.getByRole('button', { name: /AI 요약/i }));
    expect(onSummarize).toHaveBeenCalled();
  });

  it('shows summarize loading state', () => {
    renderWithAuth(
      <AnalysisResult result={baseResult} summaryLoading={true} onSummarize={() => {}} />
    );
    expect(screen.getByText(/요약 생성 중/i)).toBeInTheDocument();
  });

  it('shows summary when provided', () => {
    const summary = { summary: 'Great video summary here.', source: 'local' };
    renderWithAuth(
      <AnalysisResult result={baseResult} summary={summary} onSummarize={() => {}} />
    );
    expect(screen.getByText('Great video summary here.')).toBeInTheDocument();
  });

  it('shows origin link when url is provided', () => {
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={() => {}} />);
    expect(screen.getByText(/원문 보기/i)).toBeInTheDocument();
  });

  it('shows sentiment analysis section when analysis present', () => {
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={() => {}} />);
    expect(screen.getByText(/감성 분석/i)).toBeInTheDocument();
  });

  it('renders dcinside gallery result', async () => {
    const result = {
      platform: 'dcinside',
      gallery_name: 'Gallery Test',
      gallery_id: 'g1',
      analysis: {
        total: 30,
        sentiment: { positive: 20, neutral: 8, negative: 2 },
        top_keywords: [],
      },
      posts: [],
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('Gallery Test')).toBeInTheDocument();
    expect(screen.getByText('DCInside')).toBeInTheDocument();
  });

  it('renders naver_cafe result with non-ok fetch_status', async () => {
    const result = {
      platform: 'naver_cafe',
      type: 'post',
      title: 'Naver Post',
      fetch_status: 'login_required',
      fetch_reason: 'login',
      analysis: null,
      comments: [],
      url: 'https://cafe.naver.com/test',
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('Naver Post')).toBeInTheDocument();
  });
});
