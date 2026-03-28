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
    expect(screen.getByText('SNS URL 분석기')).toBeInTheDocument();
    expect(screen.getByText(/지원하는 URL을 붙여넣어/i)).toBeInTheDocument();
  });

  it('renders URL input field', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    expect(input).toBeInTheDocument();
  });

  it('can type a URL in the input field', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=test' } });
    expect(input).toHaveValue('https://www.youtube.com/watch?v=test');
  });

  it('renders platform badges list', () => {
    render(<URLAnalyzer />);
    const list = screen.getByRole('list', { name: '지원 플랫폼' });
    expect(list).toBeInTheDocument();
    const items = screen.getAllByRole('listitem');
    expect(items.length).toBeGreaterThan(0);
    expect(screen.getByText(/YouTube/)).toBeInTheDocument();
    expect(screen.getByText(/DCInside/)).toBeInTheDocument();
  });

  it('analyze button is disabled when URL is empty', () => {
    render(<URLAnalyzer />);
    const button = screen.getByRole('button', { name: '분석' });
    expect(button).toBeDisabled();
  });

  it('analyze button is enabled after typing a URL', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    const button = screen.getByRole('button', { name: '분석' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=test' } });
    expect(button).toBeEnabled();
  });

  it('shows platform badge when a recognized URL is typed', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    // platform-badge (inline) + platform-tag (list) both show "YouTube"
    expect(screen.getAllByText(/YouTube/).length).toBeGreaterThanOrEqual(1);
    const badge = document.querySelector('.platform-badge');
    expect(badge).toBeTruthy();
  });

  it('shows error message when API call fails', async () => {
    axios.post = vi.fn().mockRejectedValue({ message: 'Network Error' });
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('shows network timeout error message', async () => {
    axios.post = vi.fn().mockRejectedValue({ message: 'Network Error', code: 'ECONNABORTED' });
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      expect(screen.getByText(/서버 연결 실패/)).toBeInTheDocument();
    });
  });

  it('shows custom error message from API response', async () => {
    axios.post = vi.fn().mockRejectedValue({
      response: { data: { error: 'URL 분석 실패: 접근 차단됨' } },
    });
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      expect(screen.getByText('URL 분석 실패: 접근 차단됨')).toBeInTheDocument();
    });
  });

  it('shows loading spinner while analyzing', async () => {
    axios.post = vi.fn().mockReturnValue(new Promise(() => {}));
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      expect(screen.getByText('콘텐츠 분석 중...')).toBeInTheDocument();
    });
  });

  it('analyze button shows "분석 중..." during loading', async () => {
    axios.post = vi.fn().mockReturnValue(new Promise(() => {}));
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      expect(screen.getByText('분석 중...')).toBeInTheDocument();
    });
  });

  it('does not submit when URL is empty', async () => {
    render(<URLAnalyzer />);
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {}, { timeout: 100 });
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('shows analysis result after successful API call', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: {
        platform: 'youtube',
        title: 'Test Video Title',
        analyzed_at: '2026-03-29T00:00:00Z',
        analysis: null,
        comments: [],
      },
    });
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      // AnalysisResult will render the result
      expect(axios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/analyze/url'),
        expect.objectContaining({ url: 'https://www.youtube.com/watch?v=abc' }),
        expect.any(Object),
      );
    });
  });

  it('shows analysis history after successful analysis', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: {
        platform: 'youtube',
        title: 'Test Video',
        analyzed_at: '2026-03-29T10:00:00Z',
        analysis: null,
        comments: [],
      },
    });
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      expect(screen.getByText('최근 분석')).toBeInTheDocument();
    });
  });

  it('shows dcinside options when dcinside gallery URL is typed', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://gall.dcinside.com/board/lists?id=test' } });
    expect(screen.getByText('갤러리 목록 옵션')).toBeInTheDocument();
  });

  it('shows dcinside single post options when board/view URL typed', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://gall.dcinside.com/board/view/?id=test&no=123' } });
    expect(screen.getByText('단일글 옵션')).toBeInTheDocument();
  });

  it('toggles dcinside fetchComments checkbox', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://gall.dcinside.com/board/lists?id=test' } });
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
  });

  it('shows naver cafe search input when naver cafe URL typed', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://cafe.naver.com/test' } });
    expect(screen.getByLabelText(/카페 내 검색/i)).toBeInTheDocument();
  });

  it('can type in naver cafe search input', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://cafe.naver.com/test' } });
    const searchInput = screen.getByPlaceholderText(/검색어 입력/i);
    fireEvent.change(searchInput, { target: { value: '검색어' } });
    expect(searchInput).toHaveValue('검색어');
  });

  it('shows clear button when naver cafe search query is typed', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://cafe.naver.com/test' } });
    const searchInput = screen.getByPlaceholderText(/검색어 입력/i);
    fireEvent.change(searchInput, { target: { value: '검색어' } });
    expect(screen.getByTitle('검색어 지우기')).toBeInTheDocument();
  });

  it('clears naver cafe search query when clear button clicked', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://cafe.naver.com/test' } });
    const searchInput = screen.getByPlaceholderText(/검색어 입력/i);
    fireEvent.change(searchInput, { target: { value: '검색어' } });
    fireEvent.click(screen.getByTitle('검색어 지우기'));
    expect(searchInput).toHaveValue('');
  });

  it('naver cafe Enter key in search input triggers analyze', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: { platform: 'naver_cafe', title: 'Cafe', analysis: null },
    });
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://cafe.naver.com/test' } });
    const searchInput = screen.getByPlaceholderText(/검색어 입력/i);
    fireEvent.keyDown(searchInput, { key: 'Enter' });
    await waitFor(() => {
      expect(axios.post).toHaveBeenCalled();
    });
  });

  it('appends search query to naver cafe URL', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: { platform: 'naver_cafe', title: 'Cafe', analysis: null },
    });
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://cafe.naver.com/test' } });
    const searchInput = screen.getByPlaceholderText(/검색어 입력/i);
    fireEvent.change(searchInput, { target: { value: 'keyword' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      const callArgs = axios.post.mock.calls[0][1];
      expect(callArgs.url).toContain('q=keyword');
    });
  });

  it('shows API usage panel when apiUsage data available', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        api_usage: {
          youtube: {
            configured: true,
            daily_limit: 10000,
            used_today: 500,
            remaining: 9500,
            date: '2026-03-29',
            storage: 'memory',
          },
        },
      },
    });
    render(<URLAnalyzer />);
    await waitFor(() => {
      expect(screen.getByTitle('API 사용량 보기')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTitle('API 사용량 보기'));
    await waitFor(() => {
      expect(screen.getByText('API 사용량')).toBeInTheDocument();
    });
  });

  it('toggles API usage panel closed', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        api_usage: {
          youtube: {
            configured: true,
            daily_limit: 10000,
            used_today: 500,
            remaining: 9500,
            date: '2026-03-29',
            storage: 'memory',
          },
        },
      },
    });
    render(<URLAnalyzer />);
    await waitFor(() => {
      expect(screen.getByTitle('API 사용량 보기')).toBeInTheDocument();
    });
    const toggleBtn = screen.getByTitle('API 사용량 보기');
    fireEvent.click(toggleBtn);
    await waitFor(() => {
      expect(screen.getByText('API 사용량')).toBeInTheDocument();
    });
    fireEvent.click(toggleBtn);
    await waitFor(() => {
      expect(screen.queryByText('API 사용량')).not.toBeInTheDocument();
    });
  });

  it('shows warning banner when API usage >= 80%', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        api_usage: {
          youtube: {
            configured: true,
            daily_limit: 10000,
            used_today: 9000,
            remaining: 1000,
            date: '2026-03-29',
            storage: 'memory',
          },
        },
      },
    });
    render(<URLAnalyzer />);
    await waitFor(() => {
      expect(screen.getByText(/API 사용량 90%/)).toBeInTheDocument();
    });
  });

  it('shows API configured and Redis badge in usage panel', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        api_usage: {
          naver_search: {
            configured: true,
            daily_limit: 25000,
            used_today: 100,
            remaining: 24900,
            date: '2026-03-29',
            storage: 'redis',
          },
        },
      },
    });
    render(<URLAnalyzer />);
    await waitFor(() => {
      expect(screen.getByTitle('API 사용량 보기')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTitle('API 사용량 보기'));
    await waitFor(() => {
      expect(screen.getByText('활성')).toBeInTheDocument();
      expect(screen.getByText('(Redis)')).toBeInTheDocument();
      expect(screen.getByText('네이버 검색')).toBeInTheDocument();
    });
  });

  it('shows unconfigured badge and Memory storage in usage panel', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        api_usage: {
          reddit: {
            configured: false,
            daily_limit: 0,
            used_today: 0,
            remaining: 0,
            date: '2026-03-29',
            storage: 'memory',
          },
        },
      },
    });
    render(<URLAnalyzer />);
    await waitFor(() => {
      expect(screen.getByTitle('API 사용량 보기')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTitle('API 사용량 보기'));
    await waitFor(() => {
      expect(screen.getByText('미설정')).toBeInTheDocument();
      expect(screen.getByText('(Memory)')).toBeInTheDocument();
    });
  });

  it('clears history when delete button clicked', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: {
        platform: 'youtube',
        title: 'Video to delete from history',
        analyzed_at: '2026-03-29T10:00:00Z',
        analysis: null,
        comments: [],
      },
    });
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      expect(screen.getByText('최근 분석')).toBeInTheDocument();
    });
    const deleteBtn = screen.getByRole('button', { name: '분석 기록 전체 삭제' });
    fireEvent.click(deleteBtn);
    expect(screen.queryByText('최근 분석')).not.toBeInTheDocument();
  });

  it('opens history item on click and loads cached result', async () => {
    const historyData = [{
      url: 'https://www.youtube.com/watch?v=xyz',
      platform: 'youtube',
      title: 'Cached Video',
      analyzed_at: '2026-03-29T10:00:00Z',
    }];
    const cacheData = {
      version: 1,
      data: {
        'https://www.youtube.com/watch?v=xyz': {
          platform: 'youtube',
          title: 'Cached Video',
          analyzed_at: '2026-03-29T10:00:00Z',
        },
      },
    };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
      if (key === 'sns-analyzer-history') return JSON.stringify(historyData);
      if (key === 'sns-analyzer-results') return JSON.stringify(cacheData);
      return null;
    });
    render(<URLAnalyzer />);
    await waitFor(() => {
      expect(screen.getByText('최근 분석')).toBeInTheDocument();
    });
    const historyBtn = screen.getByRole('button', { name: 'Cached Video 분석 결과 불러오기' });
    fireEvent.click(historyBtn);
    // URL input should be updated
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    expect(input).toHaveValue('https://www.youtube.com/watch?v=xyz');
  });

  it('dcinside maxCommentPosts select changes value', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://gall.dcinside.com/board/lists?id=test' } });
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: '10' } });
    expect(selects[0]).toHaveValue('10');
  });

  it('dcinside maxComments select changes value', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://gall.dcinside.com/board/lists?id=test' } });
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[1], { target: { value: '1000' } });
    expect(selects[1]).toHaveValue('1000');
  });

  it('dcinside single-post maxComments select changes value', () => {
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://gall.dcinside.com/board/view/?id=test&no=1' } });
    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: '200' } });
    expect(select).toHaveValue('200');
  });

  it('sends dcinside options in API call', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: { platform: 'dcinside', gallery_id: 'test', analysis: null },
    });
    render(<URLAnalyzer />);
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://gall.dcinside.com/board/lists?id=test' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      expect(axios.post).toHaveBeenCalled();
      const callArgs = axios.post.mock.calls[0][1];
      expect(callArgs.options).toHaveProperty('fetch_comments');
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
    const input = screen.getByRole('textbox', { name: '분석할 URL 입력' });
    fireEvent.change(input, { target: { value: 'https://www.youtube.com/watch?v=abc' } });
    fireEvent.submit(screen.getByRole('button', { name: '분석' }).closest('form'));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
