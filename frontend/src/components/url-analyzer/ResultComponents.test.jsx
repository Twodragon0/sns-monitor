import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import { PLATFORM_INFO, SENTIMENT_COLORS, ThreadsPostBlock, AnalysisResult } from './ResultComponents';

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

vi.mock('dompurify', () => ({
  default: { sanitize: (html) => html },
}));

beforeAll(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterAll(() => {
  vi.restoreAllMocks();
});

beforeEach(() => {
  axios.get = vi.fn().mockResolvedValue({ data: {} });
  axios.post = vi.fn().mockResolvedValue({ data: {} });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe('PLATFORM_INFO', () => {
  it('contains youtube entry', () => {
    expect(PLATFORM_INFO.youtube).toBeDefined();
    expect(PLATFORM_INFO.youtube.name).toBe('YouTube');
  });

  it('contains dcinside entry', () => {
    expect(PLATFORM_INFO.dcinside).toBeDefined();
  });

  it('contains reddit entry', () => {
    expect(PLATFORM_INFO.reddit).toBeDefined();
  });
});

describe('SENTIMENT_COLORS', () => {
  it('has positive, neutral, negative colors', () => {
    expect(SENTIMENT_COLORS.positive).toBeDefined();
    expect(SENTIMENT_COLORS.neutral).toBeDefined();
    expect(SENTIMENT_COLORS.negative).toBeDefined();
  });
});

describe('ThreadsPostBlock', () => {
  it('renders without crashing with no props', () => {
    const { container } = render(<ThreadsPostBlock result={null} />);
    expect(container).toBeTruthy();
  });

  it('shows fallback text when no embed and no content', () => {
    render(<ThreadsPostBlock result={null} />);
    expect(screen.getByText(/게시글 내용을 불러오지 못했습니다/i)).toBeInTheDocument();
  });

  it('shows post content when provided', () => {
    render(<ThreadsPostBlock content="Hello Threads world" result={null} />);
    expect(screen.getByText('Hello Threads world')).toBeInTheDocument();
  });

  it('shows description when content is not provided', () => {
    render(<ThreadsPostBlock description="My description" result={null} />);
    expect(screen.getByText('My description')).toBeInTheDocument();
  });

  it('shows origin link when url is provided', () => {
    render(<ThreadsPostBlock url="https://www.threads.net/t/abc" result={null} />);
    expect(screen.getByText(/Threads 원문 보기/i)).toBeInTheDocument();
  });

  it('shows replies list', () => {
    const replies = [
      { author: 'user1', date: '2026-01-01', text: 'Reply 1' },
      { author: 'user2', date: '2026-01-02', text: 'Reply 2' },
    ];
    render(<ThreadsPostBlock replies={replies} result={{ source: 'threads_api' }} />);
    expect(screen.getByText('Reply 1')).toBeInTheDocument();
    expect(screen.getByText('Reply 2')).toBeInTheDocument();
  });

  it('shows "더 보기" button when replies > 20', () => {
    const replies = Array.from({ length: 25 }, (_, i) => ({
      author: `user${i}`, text: `Reply ${i}`,
    }));
    render(<ThreadsPostBlock replies={replies} result={{ source: 'threads_api' }} />);
    expect(screen.getByText(/나머지 5개 댓글 더 보기/i)).toBeInTheDocument();
  });

  it('shows token hint when no token and no replies', () => {
    render(<ThreadsPostBlock replies={[]} result={{ source: 'other' }} />);
    expect(screen.getByText(/THREADS_ACCESS_TOKEN/i)).toBeInTheDocument();
  });
});

describe('AnalysisResult', () => {
  const baseResult = {
    platform: 'youtube',
    title: 'Test Video',
    analyzed_at: '2026-01-15T10:00:00Z',
    analysis: {
      total: 100,
      sentiment: { positive: 60, neutral: 30, negative: 10 },
      top_keywords: [{ keyword: 'test', count: 5 }],
    },
    comments: [],
    posts: [],
  };

  it('renders without crashing', () => {
    const { container } = render(<AnalysisResult result={baseResult} />);
    expect(container).toBeTruthy();
  });

  it('shows result title', () => {
    render(<AnalysisResult result={baseResult} />);
    expect(screen.getByText('Test Video')).toBeInTheDocument();
  });

  it('shows platform name', () => {
    render(<AnalysisResult result={baseResult} />);
    expect(screen.getByText('YouTube')).toBeInTheDocument();
  });

  it('shows AI 요약 button', () => {
    render(<AnalysisResult result={baseResult} />);
    expect(screen.getByRole('button', { name: /AI 요약/i })).toBeInTheDocument();
  });

  it('shows sentiment analysis section', () => {
    render(<AnalysisResult result={baseResult} />);
    expect(screen.getByText(/Sentiment Analysis/i)).toBeInTheDocument();
  });

  it('shows summary after clicking AI 요약 and API succeeds', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: { summary: 'This video has great reactions.', source: 'local' },
    });
    render(<AnalysisResult result={baseResult} />);
    fireEvent.click(screen.getByRole('button', { name: /AI 요약/i }));
    await waitFor(() => {
      expect(screen.getByText('This video has great reactions.')).toBeInTheDocument();
    });
  });

  it('shows loading state during summarize call', async () => {
    axios.post = vi.fn().mockReturnValue(new Promise(() => {})); // never resolves
    render(<AnalysisResult result={baseResult} />);
    fireEvent.click(screen.getByRole('button', { name: /AI 요약/i }));
    await waitFor(() => {
      expect(screen.getByText(/분석 중/i)).toBeInTheDocument();
    });
  });

  it('renders DCInside result with gallery name', () => {
    const result = {
      platform: 'dcinside',
      gallery_name: 'Test Gallery',
      gallery_id: 'gall123',
      analysis: {
        total: 50,
        sentiment: { positive: 30, neutral: 15, negative: 5 },
        top_keywords: [],
      },
      posts: [],
    };
    render(<AnalysisResult result={result} />);
    expect(screen.getByText('Test Gallery')).toBeInTheDocument();
    expect(screen.getByText('DCInside')).toBeInTheDocument();
  });

  it('renders reddit result', () => {
    const result = {
      platform: 'reddit',
      subreddit: 'r/test',
      analysis: {
        total: 20,
        sentiment: { positive: 10, neutral: 8, negative: 2 },
        top_keywords: [],
      },
      comments: [],
    };
    render(<AnalysisResult result={result} />);
    expect(screen.getByText('r/test')).toBeInTheDocument();
  });

  it('falls back to "Analysis Result" title when no identifiable title', () => {
    const result = {
      platform: 'kakao',
      analysis: null,
      comments: [],
    };
    render(<AnalysisResult result={result} />);
    expect(screen.getByText('Analysis Result')).toBeInTheDocument();
  });

  it('shows reddit blocked hint when fetch_status is blocked', () => {
    const result = {
      platform: 'reddit',
      fetch_status: 'blocked',
      analysis: null,
      comments: [],
    };
    render(<AnalysisResult result={result} />);
    expect(screen.getByText(/Reddit.*차단/i)).toBeInTheDocument();
  });
});
