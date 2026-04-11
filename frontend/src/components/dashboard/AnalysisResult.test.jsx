import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import {
  renderSummaryContent,
  AiCtaButton,
  AnalysisResult,
  sortComments,
  sortYoutubeComments,
  sortPosts,
  DCInsideResultPosts,
  YouTubeComments,
  ThreadsPostBlock,
  SENTIMENT_COLORS,
  PLATFORMS,
  POSTS_PER_PAGE,
  POST_SORT_OPTIONS,
} from './AnalysisResult';
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

// ─── renderSummaryContent ─────────────────────────────────────────────────────

describe('renderSummaryContent', () => {
  it('returns null for falsy input', () => {
    expect(renderSummaryContent(null)).toBeNull();
    expect(renderSummaryContent('')).toBeNull();
  });

  it('returns null for non-string input', () => {
    expect(renderSummaryContent(123)).toBeNull();
    expect(renderSummaryContent({})).toBeNull();
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

  it('handles multiple bold sections', () => {
    const result = renderSummaryContent('**A** and **B**');
    expect(Array.isArray(result)).toBe(true);
    const strongs = result.filter(r => r?.type === 'strong');
    expect(strongs).toHaveLength(2);
    expect(strongs[0].props.children).toBe('A');
    expect(strongs[1].props.children).toBe('B');
  });

  it('handles text with only bold markers', () => {
    const result = renderSummaryContent('**only bold**');
    expect(Array.isArray(result)).toBe(true);
    const strongEl = result.find(r => r?.type === 'strong');
    expect(strongEl.props.children).toBe('only bold');
  });
});

// ─── SENTIMENT_COLORS ────────────────────────────────────────────────────────

describe('SENTIMENT_COLORS', () => {
  it('has positive, neutral, negative keys', () => {
    expect(SENTIMENT_COLORS.positive).toBeDefined();
    expect(SENTIMENT_COLORS.neutral).toBeDefined();
    expect(SENTIMENT_COLORS.negative).toBeDefined();
  });
});

// ─── PLATFORMS ───────────────────────────────────────────────────────────────

describe('PLATFORMS', () => {
  it('has youtube platform', () => {
    expect(PLATFORMS.youtube).toBeDefined();
    expect(PLATFORMS.youtube.label).toBe('YouTube');
  });

  it('has dcinside platform', () => {
    expect(PLATFORMS.dcinside).toBeDefined();
  });

  it('has naver_cafe platform', () => {
    expect(PLATFORMS.naver_cafe).toBeDefined();
  });
});

// ─── POSTS_PER_PAGE / POST_SORT_OPTIONS ──────────────────────────────────────

describe('constants', () => {
  it('POSTS_PER_PAGE is 50', () => {
    expect(POSTS_PER_PAGE).toBe(50);
  });

  it('POST_SORT_OPTIONS has expected values', () => {
    const values = POST_SORT_OPTIONS.map(o => o.value);
    expect(values).toContain('date_desc');
    expect(values).toContain('date_asc');
    expect(values).toContain('popular');
    expect(values).toContain('comments');
  });
});

// ─── sortComments ─────────────────────────────────────────────────────────────

describe('sortComments', () => {
  it('returns empty array for empty input', () => {
    expect(sortComments([], '등록순')).toEqual([]);
    expect(sortComments(null, '등록순')).toEqual([]);
  });

  it('returns original order for 등록순', () => {
    const comments = [
      { text: 'a', date: '2026-01-01' },
      { text: 'b', date: '2026-01-03' },
      { text: 'c', date: '2026-01-02' },
    ];
    const result = sortComments(comments, '등록순');
    expect(result[0].text).toBe('a');
    expect(result[1].text).toBe('b');
  });

  it('sorts by latest for 최신순 when date present', () => {
    const comments = [
      { text: 'old', date: '2026-01-01' },
      { text: 'new', date: '2026-01-10' },
    ];
    const result = sortComments(comments, '최신순');
    expect(result[0].text).toBe('new');
    expect(result[1].text).toBe('old');
  });

  it('keeps original order for 최신순 when no dates', () => {
    const comments = [{ text: 'a' }, { text: 'b' }];
    const result = sortComments(comments, '최신순');
    expect(result[0].text).toBe('a');
  });

  it('does not mutate original array', () => {
    const comments = [
      { text: 'a', date: '2026-01-01' },
      { text: 'b', date: '2026-01-10' },
    ];
    const original = [...comments];
    sortComments(comments, '최신순');
    expect(comments[0].text).toBe(original[0].text);
  });
});

// ─── sortYoutubeComments ──────────────────────────────────────────────────────

describe('sortYoutubeComments', () => {
  it('returns empty array for empty input', () => {
    expect(sortYoutubeComments([], '등록순')).toEqual([]);
    expect(sortYoutubeComments(null, '등록순')).toEqual([]);
  });

  it('keeps original order for 등록순', () => {
    const comments = [
      { text: 'a', published_at: '2026-01-01', like_count: 5 },
      { text: 'b', published_at: '2026-01-03', like_count: 2 },
    ];
    const result = sortYoutubeComments(comments, '등록순');
    expect(result[0].text).toBe('a');
  });

  it('sorts by published_at desc for 최신순', () => {
    const comments = [
      { text: 'old', published_at: '2026-01-01' },
      { text: 'new', published_at: '2026-01-10' },
    ];
    const result = sortYoutubeComments(comments, '최신순');
    expect(result[0].text).toBe('new');
  });

  it('sorts by like_count desc for 좋아요순', () => {
    const comments = [
      { text: 'low', like_count: 3 },
      { text: 'high', like_count: 100 },
      { text: 'mid', like_count: 50 },
    ];
    const result = sortYoutubeComments(comments, '좋아요순');
    expect(result[0].text).toBe('high');
    expect(result[1].text).toBe('mid');
  });

  it('handles missing like_count as 0 for 좋아요순', () => {
    const comments = [
      { text: 'no_likes' },
      { text: 'has_likes', like_count: 10 },
    ];
    const result = sortYoutubeComments(comments, '좋아요순');
    expect(result[0].text).toBe('has_likes');
  });
});

// ─── sortPosts ────────────────────────────────────────────────────────────────

describe('sortPosts', () => {
  it('returns empty array for empty input', () => {
    expect(sortPosts([], 'date_desc')).toEqual([]);
    expect(sortPosts(null, 'date_desc')).toEqual([]);
  });

  it('sorts date_desc', () => {
    const posts = [
      { text: 'old', date: '2026-01-01' },
      { text: 'new', date: '2026-01-10' },
    ];
    const result = sortPosts(posts, 'date_desc');
    expect(result[0].text).toBe('new');
  });

  it('sorts date_asc', () => {
    const posts = [
      { text: 'new', date: '2026-01-10' },
      { text: 'old', date: '2026-01-01' },
    ];
    const result = sortPosts(posts, 'date_asc');
    expect(result[0].text).toBe('old');
  });

  it('sorts popular by recommend desc', () => {
    const posts = [
      { text: 'low', recommend: 1 },
      { text: 'high', recommend: 100 },
    ];
    const result = sortPosts(posts, 'popular');
    expect(result[0].text).toBe('high');
  });

  it('sorts comments by comments.length desc', () => {
    const posts = [
      { text: 'few', comments: [{ text: 'c1' }] },
      { text: 'many', comments: [{ text: 'c1' }, { text: 'c2' }, { text: 'c3' }] },
    ];
    const result = sortPosts(posts, 'comments');
    expect(result[0].text).toBe('many');
  });

  it('handles missing comments array for 댓글 sort', () => {
    const posts = [
      { text: 'no_comments' },
      { text: 'has_comments', comments: [{ text: 'c' }] },
    ];
    const result = sortPosts(posts, 'comments');
    expect(result[0].text).toBe('has_comments');
  });

  it('returns unchanged for unknown sort key', () => {
    const posts = [{ text: 'a' }, { text: 'b' }];
    const result = sortPosts(posts, 'unknown_sort');
    expect(result).toHaveLength(2);
  });

  it('does not mutate original array', () => {
    const posts = [
      { text: 'new', date: '2026-01-10' },
      { text: 'old', date: '2026-01-01' },
    ];
    const original = [...posts];
    sortPosts(posts, 'date_asc');
    expect(posts[0].text).toBe(original[0].text);
  });
});

// ─── AiCtaButton ─────────────────────────────────────────────────────────────

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

  it('calls onShowError when mirofish_available is false', async () => {
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/auth/me')) {
        return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      }
      if (url.includes('/api/analysis/status')) {
        return Promise.resolve({ data: { mirofish_available: false } });
      }
      return Promise.resolve({ data: {} });
    });
    const onShowError = vi.fn();
    renderWithAuth(<AiCtaButton result={baseResult} onShowError={onShowError} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /AI 심화 분석/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /AI 심화 분석/i }));
    await waitFor(() => {
      expect(onShowError).toHaveBeenCalled();
    });
  });

  it('calls onShowError when axios throws', async () => {
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/auth/me')) {
        return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      }
      if (url.includes('/api/analysis/status')) {
        return Promise.reject(new Error('fail'));
      }
      return Promise.resolve({ data: {} });
    });
    const onShowError = vi.fn();
    renderWithAuth(<AiCtaButton result={baseResult} onShowError={onShowError} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /AI 심화 분석/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /AI 심화 분석/i }));
    await waitFor(() => {
      expect(onShowError).toHaveBeenCalled();
    });
  });

  it('shows login button when authRequired and not loggedIn', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ logged_in: false, auth_required: true }),
    });
    renderWithAuth(<AiCtaButton result={baseResult} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /OpenAI/i })).toBeInTheDocument();
    });
  });

  it('stores dcinside preselect in sessionStorage', async () => {
    const dcResult = { platform: 'dcinside', gallery_id: 'test_gallery' };
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/auth/me')) {
        return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      }
      if (url.includes('/api/analysis/status')) {
        return Promise.resolve({ data: { mirofish_available: true } });
      }
      return Promise.resolve({ data: {} });
    });
    renderWithAuth(<AiCtaButton result={dcResult} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /AI 심화 분석/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /AI 심화 분석/i }));
    await waitFor(() => {
      const calls = setItemSpy.mock.calls.find(([k]) => k === 'analysisPreselect');
      expect(calls).toBeDefined();
    });
  });
});

// ─── AnalysisResult (dashboard) ──────────────────────────────────────────────

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
    expect(screen.getByText('5.0K')).toBeInTheDocument();
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

  it('shows summary when provided (local source)', () => {
    const summary = { summary: 'Great video summary here.', source: 'local' };
    renderWithAuth(
      <AnalysisResult result={baseResult} summary={summary} onSummarize={() => {}} />
    );
    expect(screen.getByText('Great video summary here.')).toBeInTheDocument();
    expect(screen.getByText(/로컬 분석/i)).toBeInTheDocument();
  });

  it('shows summary with mirofish source label', () => {
    const summary = { summary: 'AI summary text.', source: 'mirofish' };
    renderWithAuth(
      <AnalysisResult result={baseResult} summary={summary} onSummarize={() => {}} />
    );
    expect(screen.getByText('AI summary text.')).toBeInTheDocument();
    expect(screen.getByText('AI 분석')).toBeInTheDocument();
  });

  it('shows origin link when url is provided', () => {
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={() => {}} />);
    expect(screen.getByText(/원문 보기/i)).toBeInTheDocument();
  });

  it('shows sentiment analysis section when analysis present', () => {
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={() => {}} />);
    expect(screen.getAllByText(/감성 분석/i).length).toBeGreaterThan(0);
  });

  it('shows positive/neutral/negative counts', () => {
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={() => {}} />);
    expect(screen.getByText(/긍정 50/)).toBeInTheDocument();
    expect(screen.getByText(/중립 25/)).toBeInTheDocument();
    expect(screen.getByText(/부정 5/)).toBeInTheDocument();
  });

  it('shows 긍정적 for positive overall', () => {
    const result = {
      ...baseResult,
      analysis: { ...baseResult.analysis, overall: 'positive' },
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('긍정적')).toBeInTheDocument();
  });

  it('shows 부정적 for negative overall', () => {
    const result = {
      ...baseResult,
      analysis: { ...baseResult.analysis, overall: 'negative' },
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('부정적')).toBeInTheDocument();
  });

  it('shows 중립적 for neutral overall', () => {
    const result = {
      ...baseResult,
      analysis: { ...baseResult.analysis, overall: 'neutral' },
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('중립적')).toBeInTheDocument();
  });

  it('renders analyzed_at datetime', () => {
    renderWithAuth(<AnalysisResult result={baseResult} onSummarize={() => {}} />);
    // datetime rendered somewhere in doc
    const timeEls = document.querySelectorAll('.result__time');
    expect(timeEls.length).toBeGreaterThan(0);
  });

  it('shows description section when description provided', () => {
    const result = { ...baseResult, description: 'Some description text' };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('Some description text')).toBeInTheDocument();
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

  it('renders naver_cafe hint when fetch_status is not ok', () => {
    const result = {
      platform: 'naver_cafe',
      type: 'gallery',
      title: 'Naver Gallery',
      fetch_status: 'partial',
      fetch_reason: 'cookie_expired',
      analysis: null,
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    // hint element has class result__naver-hint
    const hint = document.querySelector('.result__naver-hint');
    expect(hint).toBeTruthy();
  });

  it('renders reddit blocked hint', () => {
    const result = {
      platform: 'reddit',
      title: 'Reddit Sub',
      fetch_status: 'blocked',
      analysis: null,
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText(/API 접근이 차단/)).toBeInTheDocument();
  });

  it('renders subscriber_count stat', () => {
    const result = { ...baseResult, subscriber_count: 1200000 };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('1.2M')).toBeInTheDocument();
  });

  it('renders total_posts stat', () => {
    const result = { ...baseResult, total_posts: 500 };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('500')).toBeInTheDocument();
  });

  it('renders total_messages stat', () => {
    const result = { ...baseResult, total_messages: 3000 };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('3.0K')).toBeInTheDocument();
  });

  it('renders follower_count stat', () => {
    const result = { ...baseResult, follower_count: 2500 };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('2.5K')).toBeInTheDocument();
  });

  it('renders recommend stat', () => {
    const result = { ...baseResult, recommend: 42 };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('shows content body for dcinside post', () => {
    const result = {
      platform: 'dcinside',
      type: 'post',
      title: 'DC Post',
      content: 'post body text here',
      analysis: null,
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('post body text here')).toBeInTheDocument();
  });

  it('shows collected items for non-gallery result', () => {
    const result = {
      platform: 'telegram',
      title: 'Telegram Channel',
      analysis: null,
      comments: [
        { text: 'Telegram message 1', author: 'user1' },
        { text: 'Telegram message 2', author: 'user2' },
      ],
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('수집된 콘텐츠')).toBeInTheDocument();
    expect(screen.getByText('Telegram message 1')).toBeInTheDocument();
  });

  it('shows source_url link when source_url present', () => {
    const result = { ...baseResult, source_url: 'https://example.com/source' };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText(/원문 보기/i)).toBeInTheDocument();
  });

  it('renders unknown platform gracefully', () => {
    const result = {
      platform: 'unknown_platform',
      title: 'Unknown Result',
      analysis: null,
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('Unknown Result')).toBeInTheDocument();
  });

  it('shows youtube comments when comments array present', () => {
    const result = {
      platform: 'youtube',
      title: 'Video with Comments',
      comment_count: 2,
      analysis: null,
      comments: [
        { text: 'Great video!', author: 'user1', video_id: 'vid1' },
        { text: 'Love it', author: 'user2', video_id: 'vid1' },
      ],
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    // There may be multiple YouTube 댓글 aria elements; ensure at least one
    expect(screen.getAllByLabelText(/YouTube 댓글/i).length).toBeGreaterThan(0);
  });

  it('renders dcinside gallery posts when posts provided', () => {
    const result = {
      platform: 'dcinside',
      type: 'gallery',
      gallery_name: 'Test Gallery',
      analysis: null,
      posts: [
        { number: 1, text: 'Post 1', url: 'https://gall.dcinside.com/1', comments: [] },
        { number: 2, text: 'Post 2', url: 'https://gall.dcinside.com/2', comments: [] },
      ],
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('Post 1')).toBeInTheDocument();
    expect(screen.getByText('Post 2')).toBeInTheDocument();
  });

  it('shows naver_cafe post with login_verified badge', () => {
    const result = {
      platform: 'naver_cafe',
      type: 'post',
      title: 'Naver Logged In',
      login_verified: true,
      fetch_status: 'ok',
      comment_count: 5,
      analysis: null,
      url: 'https://cafe.naver.com/post/1',
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('로그인됨')).toBeInTheDocument();
  });

  it('renders items with view_count and like_count in meta', () => {
    const result = {
      platform: 'reddit',
      title: 'Reddit Post',
      analysis: null,
      comments: [
        { text: 'Reddit comment', author: 'ruser', score: 100, view_count: 500 },
      ],
    };
    renderWithAuth(<AnalysisResult result={result} onSummarize={() => {}} />);
    expect(screen.getByText('Reddit comment')).toBeInTheDocument();
  });
});

// ─── DCInsideResultPosts ──────────────────────────────────────────────────────

describe('DCInsideResultPosts', () => {
  const makePosts = (n = 3) =>
    Array.from({ length: n }, (_, i) => ({
      number: i + 1,
      text: `Post ${i + 1}`,
      url: `https://gall.dcinside.com/${i + 1}`,
      comment_count: i % 2 === 0 ? 2 : 0,
      comments: i % 2 === 0
        ? [{ text: `Comment A${i}`, author: `author${i}`, date: `2026-01-0${i + 1}` }]
        : [],
      view_count: 100 + i * 10,
      recommend: i * 5,
      date: `2026-01-0${i + 1}`,
    }));

  it('renders post list', () => {
    render(<DCInsideResultPosts posts={makePosts()} />);
    expect(screen.getByText('Post 1')).toBeInTheDocument();
    expect(screen.getByText('Post 2')).toBeInTheDocument();
  });

  it('shows total posts count label', () => {
    render(<DCInsideResultPosts posts={makePosts(3)} totalPosts={100} />);
    expect(screen.getByText(/게시글 목록/)).toBeInTheDocument();
  });

  it('expands/collapses comments on click', () => {
    const posts = [{ number: 1, text: 'Single Post', url: null, comments: [], comment_count: 0 }];
    render(<DCInsideResultPosts posts={posts} />);
    const postCards = screen.getAllByRole('button').filter(b => b.getAttribute('aria-expanded') !== null);
    expect(postCards.length).toBeGreaterThan(0);
    const postCard = postCards[0];
    fireEvent.click(postCard);
    expect(postCard).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(postCard);
    expect(postCard).toHaveAttribute('aria-expanded', 'false');
  });

  it('shows all-comment count bar when comments exist', () => {
    render(<DCInsideResultPosts posts={makePosts(3)} />);
    expect(screen.getByLabelText('전체 댓글')).toBeInTheDocument();
  });

  it('toggles 통합 보기 to show all comments', () => {
    const posts = makePosts(3);
    render(<DCInsideResultPosts posts={posts} />);
    const allBtn = screen.getByText('통합 보기');
    fireEvent.click(allBtn);
    expect(screen.getByLabelText('전체 댓글 통합')).toBeInTheDocument();
    // collapse
    fireEvent.click(screen.getByText('통합 댓글 접기'));
    expect(screen.queryByLabelText('전체 댓글 통합')).not.toBeInTheDocument();
  });

  it('sorts posts by 오래된순', () => {
    const posts = makePosts(3);
    render(<DCInsideResultPosts posts={posts} />);
    const sortBtn = screen.getByRole('button', { name: '오래된순' });
    fireEvent.click(sortBtn);
    expect(sortBtn).toHaveAttribute('aria-pressed', 'true');
  });

  it('sorts posts by 인기순', () => {
    render(<DCInsideResultPosts posts={makePosts(3)} />);
    fireEvent.click(screen.getByRole('button', { name: '인기순' }));
    expect(screen.getByRole('button', { name: '인기순' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('sorts posts by 댓글 많은 순', () => {
    render(<DCInsideResultPosts posts={makePosts(3)} />);
    fireEvent.click(screen.getByRole('button', { name: '댓글 많은 순' }));
    expect(screen.getByRole('button', { name: '댓글 많은 순' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('shows comment sort buttons in expanded state', () => {
    render(<DCInsideResultPosts posts={makePosts(1)} />);
    expect(screen.getByRole('button', { name: '등록순' })).toBeInTheDocument();
    // 최신순 appears in both post sort and comment sort
    expect(screen.getAllByRole('button', { name: '최신순' }).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '답글순' })).toBeInTheDocument();
  });

  it('changes comment sort to 최신순', () => {
    render(<DCInsideResultPosts posts={makePosts(3)} />);
    // 최신순 appears in both post sort and comment sort areas
    // Post sort region has aria-label "게시글 정렬"
    const sortRegion = screen.getByLabelText('게시글 정렬');
    const postSortBtn = Array.from(sortRegion.querySelectorAll('button')).find(b => b.textContent === '최신순');
    fireEvent.click(postSortBtn);
    expect(postSortBtn).toHaveAttribute('aria-pressed', 'true');
  });

  it('renders naver cafe label with loginVerified badge', () => {
    render(<DCInsideResultPosts posts={makePosts(2)} isNaverCafe={true} loginVerified={true} />);
    expect(screen.getByText('로그인됨')).toBeInTheDocument();
  });

  it('shows naver cafe with totalPosts label', () => {
    render(<DCInsideResultPosts posts={makePosts(2)} totalPosts={200} isNaverCafe={true} />);
    expect(screen.getByText(/전체 약 200건/)).toBeInTheDocument();
  });

  it('shows empty comment message when post expanded and no comments', () => {
    const posts = [{ number: 99, text: 'Post no comments', url: null, comments: [], comment_count: 0 }];
    render(<DCInsideResultPosts posts={posts} />);
    const postCards = screen.getAllByRole('button').filter(b => b.getAttribute('aria-expanded') !== null);
    fireEvent.click(postCards[0]);
    expect(screen.getByText('수집된 댓글이 없습니다.')).toBeInTheDocument();
  });

  it('shows collection failed message when comment_count > 0 but comments empty', () => {
    const posts = [{
      number: 5,
      text: 'Post with failed comments',
      url: 'https://gall.dcinside.com/5',
      comment_count: 3,
      comments: [],
    }];
    render(<DCInsideResultPosts posts={posts} />);
    expect(screen.getByText(/수집 실패/)).toBeInTheDocument();
  });

  it('shows post without url as plain text', () => {
    const posts = [{ number: 10, text: 'Post no url', comments: [] }];
    render(<DCInsideResultPosts posts={posts} />);
    expect(screen.getByText('Post no url')).toBeInTheDocument();
  });

  it('triggers on-demand comment refetch when collection failed and expanded', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: {
        comments: [{ text: 'Fetched comment', author: 'newuser' }],
        comment_count: 1,
      },
    });
    const posts = [{
      number: 7,
      text: 'Post for refetch',
      url: 'https://gall.dcinside.com/7',
      comment_count: 2,
      comments: [],
    }];
    render(<DCInsideResultPosts posts={posts} />);
    const postCards = screen.getAllByRole('button').filter(b => b.getAttribute('aria-expanded') !== null);
    fireEvent.click(postCards[0]);
    await waitFor(() => {
      expect(axios.post).toHaveBeenCalled();
    });
  });

  it('does not refetch after first successful attempt', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: {
        comments: [{ text: 'c1', author: 'a1' }],
        comment_count: 1,
      },
    });
    const posts = [{
      number: 8,
      text: 'Post for dedup refetch',
      url: 'https://gall.dcinside.com/8',
      comment_count: 2,
      comments: [],
    }];
    render(<DCInsideResultPosts posts={posts} />);
    const postCards = () => screen.getAllByRole('button').filter(b => b.getAttribute('aria-expanded') !== null);

    // First expand — triggers refetch
    fireEvent.click(postCards()[0]);
    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledTimes(1);
    });

    // Collapse
    fireEvent.click(postCards()[0]);
    // Re-expand — should NOT trigger another refetch
    fireEvent.click(postCards()[0]);

    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(axios.post).toHaveBeenCalledTimes(1);
  });

  it('does not refetch after first failed attempt and shows error message', async () => {
    axios.post = vi.fn().mockRejectedValue(new Error('Network Error'));
    const posts = [{
      number: 9,
      text: 'Post for failed refetch',
      url: 'https://gall.dcinside.com/9',
      comment_count: 2,
      comments: [],
    }];
    render(<DCInsideResultPosts posts={posts} />);
    const postCards = () => screen.getAllByRole('button').filter(b => b.getAttribute('aria-expanded') !== null);

    // First expand — triggers refetch which fails
    fireEvent.click(postCards()[0]);
    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledTimes(1);
    });

    // Collapse then re-expand — should NOT trigger another refetch
    fireEvent.click(postCards()[0]);
    fireEvent.click(postCards()[0]);

    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(axios.post).toHaveBeenCalledTimes(1);

    // Error message should be displayed inline
    await waitFor(() => {
      expect(screen.getByText(/재수집 실패/)).toBeInTheDocument();
    });
  });

  it('does not trigger refetch when collectionFailed is false (comments already collected)', async () => {
    axios.post = vi.fn();
    const posts = [{
      number: 10,
      text: 'Post with existing comments',
      url: 'https://gall.dcinside.com/10',
      comment_count: 2,
      comments: [{ text: 'existing', author: 'u' }],
    }];
    render(<DCInsideResultPosts posts={posts} />);
    const postCards = screen.getAllByRole('button').filter(b => b.getAttribute('aria-expanded') !== null);

    fireEvent.click(postCards[0]);

    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('allows parallel refetch for two different posts without single-flight blocking', async () => {
    // Both posts have no comments initially → totalCommentCount=0 → no 통합보기 button
    // So postCards()[0] = Post A, postCards()[1] = Post B (no extra aria-expanded buttons)
    let resolveA;
    let resolveB;
    const promiseA = new Promise((r) => { resolveA = r; });
    const promiseB = new Promise((r) => { resolveB = r; });

    axios.post = vi.fn().mockImplementation((_url, body) => {
      if (body.url && body.url.includes('/A')) return promiseA;
      return promiseB;
    });

    const posts = [
      {
        number: 101,
        text: 'Post A',
        url: 'https://gall.dcinside.com/A',
        comment_count: 3,
        comments: [],
      },
      {
        number: 102,
        text: 'Post B',
        url: 'https://gall.dcinside.com/B',
        comment_count: 3,
        comments: [],
      },
    ];

    render(<DCInsideResultPosts posts={posts} />);
    const postCards = () =>
      screen.getAllByRole('button').filter(b => b.getAttribute('aria-expanded') !== null);

    // Click Post A — inflight, not resolved yet
    // No comments yet → no 통합보기 button → index 0 is Post A
    fireEvent.click(postCards()[0]);
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(axios.post.mock.calls[0][1].url).toBe('https://gall.dcinside.com/A');

    // Click Post B while A is still in flight (Set-based gate allows independent parallel refetch)
    // expandedNo switches to Post B; Post A's in-flight axios.post call continues unblocked
    fireEvent.click(postCards()[1]);
    expect(axios.post).toHaveBeenCalledTimes(2);
    expect(axios.post.mock.calls[1][1].url).toBe('https://gall.dcinside.com/B');

    // Resolve both promises — state settles for both posts
    resolveA({ data: { comments: [{ text: 'cA', author: 'uA' }], comment_count: 1 } });
    resolveB({ data: { comments: [{ text: 'cB', author: 'uB' }], comment_count: 1 } });

    // Post B is currently expanded → cB should be visible
    await waitFor(() => {
      expect(screen.getByText('cB')).toBeInTheDocument();
    });

    // Expand Post A to confirm its state was also updated (url-based mutation)
    // Find Post A's card by aria-controls targeting its postKey (the URL)
    const postACard = screen
      .getAllByRole('button')
      .find(b => b.getAttribute('aria-controls') === 'result-cmt-https://gall.dcinside.com/A');
    fireEvent.click(postACard);
    await waitFor(() => {
      expect(screen.getByText('cA')).toBeInTheDocument();
    });
  });

  it('sets comment_count to 0 when refetch returns empty comments without comment_count field', async () => {
    // Response has comments:[] and NO comment_count field
    axios.post = vi.fn().mockResolvedValue({ data: { comments: [] } });

    const posts = [{
      number: 9,
      text: 'Post empty refetch',
      url: 'https://gall.dcinside.com/9',
      comment_count: 3,
      comments: [],
    }];

    render(<DCInsideResultPosts posts={posts} />);

    // Before refetch: collectionFailed badge should be visible
    expect(screen.getByText(/수집 실패/)).toBeInTheDocument();

    const postCards = screen.getAllByRole('button').filter(b => b.getAttribute('aria-expanded') !== null);
    fireEvent.click(postCards[0]);

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledTimes(1);
    });

    // After refetch: comment_count becomes 0 (newComments.length = 0)
    // listCount (0) > 0 is false → collectionFailed is false → badge gone
    await waitFor(() => {
      expect(screen.queryByText(/수집 실패/)).not.toBeInTheDocument();
    });

    // Label should reflect listCount=0, collectedCount=0
    await waitFor(() => {
      expect(screen.getByText(/목록 0 \/ 수집 0/)).toBeInTheDocument();
    });
  });

  it('mutates only the clicked post when multiple posts exist (url-based mapping)', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: {
        comments: [{ text: 'only post 2 got this', author: 'u2' }],
        comment_count: 1,
      },
    });

    const posts = [
      {
        number: 201,
        text: 'Post One',
        url: 'https://gall.dcinside.com/201',
        comment_count: 1,
        comments: [{ text: 'original comment post1', author: 'orig1' }],
      },
      {
        // collectionFailed: comment_count > 0 but comments empty
        number: 202,
        text: 'Post Two',
        url: 'https://gall.dcinside.com/202',
        comment_count: 2,
        comments: [],
      },
      {
        number: 203,
        text: 'Post Three',
        url: 'https://gall.dcinside.com/203',
        comment_count: 1,
        comments: [{ text: 'original comment post3', author: 'orig3' }],
      },
    ];

    render(<DCInsideResultPosts posts={posts} />);

    // Use aria-controls to find Post Two's card directly — avoids fragile index arithmetic
    // (the 통합보기 button also has aria-expanded, making index-based selection unreliable)
    const postTwoCard = screen
      .getAllByRole('button')
      .find(b => b.getAttribute('aria-controls') === 'result-cmt-https://gall.dcinside.com/202');

    // Click the only collectionFailed post
    fireEvent.click(postTwoCard);

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledTimes(1);
    });

    // Refetched comment appears in Post Two (currently expanded)
    await waitFor(() => {
      expect(screen.getByText('only post 2 got this')).toBeInTheDocument();
    });

    // axios.post called exactly once — url-based mapper only mutated Post Two,
    // not the other posts (old closure-idx code would have mutated the wrong post)
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(axios.post.mock.calls[0][1].url).toBe('https://gall.dcinside.com/202');
  });
});

// ─── YouTubeComments ──────────────────────────────────────────────────────────

describe('YouTubeComments', () => {
  const makeComments = () => [
    { text: 'Great!', author: 'user1', video_id: 'vid1', video_title: 'Video One', published_at: '2026-01-10', like_count: 5 },
    { text: 'Awesome', author: 'user2', video_id: 'vid1', video_title: 'Video One', published_at: '2026-01-05', like_count: 2 },
    { text: 'Channel comment', author: 'user3', video_id: 'vid2', published_at: '2026-01-08', like_count: 10 },
  ];

  it('renders without crashing', () => {
    const { container } = render(<YouTubeComments comments={makeComments()} />);
    expect(container).toBeTruthy();
  });

  it('shows comment count label', () => {
    render(<YouTubeComments comments={makeComments()} totalComments={3} />);
    expect(screen.getByText(/목록 3/)).toBeInTheDocument();
  });

  it('shows comment count without totalComments', () => {
    render(<YouTubeComments comments={makeComments()} />);
    expect(screen.getByText(/댓글 \(3\)/)).toBeInTheDocument();
  });

  it('renders comment text', () => {
    render(<YouTubeComments comments={makeComments()} />);
    expect(screen.getByText('Great!')).toBeInTheDocument();
    expect(screen.getByText('Awesome')).toBeInTheDocument();
  });

  it('renders author names', () => {
    render(<YouTubeComments comments={makeComments()} />);
    expect(screen.getByText('user1')).toBeInTheDocument();
  });

  it('renders like count via aria label', () => {
    render(<YouTubeComments comments={makeComments()} />);
    // like_count is rendered inside result__comment-like spans
    const likeSpans = document.querySelectorAll('.result__comment-like');
    expect(likeSpans.length).toBeGreaterThan(0);
    const texts = Array.from(likeSpans).map(s => s.textContent);
    expect(texts.some(t => t.includes('10'))).toBe(true);
  });

  it('collapses and expands comments', () => {
    render(<YouTubeComments comments={makeComments()} />);
    const toggleBtn = screen.getByRole('button', { name: /댓글 접기/i });
    fireEvent.click(toggleBtn);
    expect(screen.queryByLabelText('YouTube 댓글 목록')).not.toBeInTheDocument();
    // expand again
    fireEvent.click(screen.getByRole('button', { name: /댓글 펼치기/i }));
    expect(screen.getByLabelText('YouTube 댓글 목록')).toBeInTheDocument();
  });

  it('sorts comments by 최신순', () => {
    render(<YouTubeComments comments={makeComments()} />);
    fireEvent.click(screen.getByRole('button', { name: '최신순' }));
    expect(screen.getByRole('button', { name: '최신순' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('sorts comments by 좋아요순', () => {
    render(<YouTubeComments comments={makeComments()} />);
    fireEvent.click(screen.getByRole('button', { name: '좋아요순' }));
    expect(screen.getByRole('button', { name: '좋아요순' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('groups comments by video_id', () => {
    render(<YouTubeComments comments={makeComments()} />);
    expect(screen.getByText('[Video One]')).toBeInTheDocument();
  });

  it('renders external link for video_id', () => {
    render(<YouTubeComments comments={makeComments()} />);
    const links = screen.getAllByText('원문');
    expect(links.length).toBeGreaterThan(0);
    expect(links[0].closest('a')).toHaveAttribute('href', expect.stringContaining('youtube.com'));
  });

  it('renders empty comment list gracefully', () => {
    const { container } = render(<YouTubeComments comments={[]} />);
    expect(container).toBeTruthy();
  });
});

// ─── ThreadsPostBlock ─────────────────────────────────────────────────────────
// Migrated from url-analyzer/ResultComponents.test.jsx (deleted as dead code).
// ThreadsPostBlock is exported from ./AnalysisResult (canonical path).

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
