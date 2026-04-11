import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import {
  MiniStat,
  SentimentMiniBar,
  GalleryTrendChart,
  GalleryMonitorPanel,
  OverviewPanel,
  YouTubePanel,
  DCInsidePanel,
  TwitterPanel,
  SocialPanel,
  ScanHistoryPanel,
  EmptyHint,
} from './MonitorPanels';

vi.mock('axios');

vi.mock('recharts', () => ({
  LineChart: ({ children }) => <div data-testid="line-chart">{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
}));

beforeAll(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterAll(() => {
  vi.restoreAllMocks();
});

beforeEach(() => {
  axios.get = vi.fn().mockResolvedValue({ data: { sources: [] } });
  axios.post = vi.fn().mockResolvedValue({ data: { sources: [] } });
  const store = {};
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation((k) => store[k] ?? null);
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation((k, v) => { store[k] = v; });
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((k) => { delete store[k]; });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe('MiniStat', () => {
  it('renders icon, value and label', () => {
    render(<MiniStat icon="▶" value="1.2K" label="댓글" />);
    expect(screen.getByText('▶')).toBeInTheDocument();
    expect(screen.getByText('1.2K')).toBeInTheDocument();
    expect(screen.getByText('댓글')).toBeInTheDocument();
  });
});

describe('SentimentMiniBar', () => {
  it('renders nothing when sentiment is null', () => {
    const { container } = render(<SentimentMiniBar sentiment={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when all counts are zero', () => {
    const { container } = render(
      <SentimentMiniBar sentiment={{ positive: 0, neutral: 0, negative: 0 }} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders sentiment bar with counts', () => {
    render(<SentimentMiniBar sentiment={{ positive: 10, neutral: 5, negative: 3 }} />);
    // shows total count
    expect(screen.getByText('18건')).toBeInTheDocument();
    expect(screen.getByText('+10')).toBeInTheDocument();
    expect(screen.getByText('-3')).toBeInTheDocument();
  });
});

describe('GalleryTrendChart', () => {
  it('shows insufficient data message when trend is empty', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { trend: [] } });
    render(<GalleryTrendChart galleryId="test-gallery" />);
    await waitFor(() => {
      expect(screen.getByText(/트렌드 데이터 부족/i)).toBeInTheDocument();
    });
  });

  it('shows insufficient data message when trend has only 1 item', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: { trend: [{ timestamp: '2026-01-01T10:00', positive: 5, negative: 2, total: 7 }] },
    });
    render(<GalleryTrendChart galleryId="test-gallery" />);
    await waitFor(() => {
      expect(screen.getByText(/트렌드 데이터 부족/i)).toBeInTheDocument();
    });
  });

  it('renders chart when trend has 2+ items', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        trend: [
          { timestamp: '2026-01-01T10:00', positive: 5, negative: 2, total: 7 },
          { timestamp: '2026-01-02T10:00', positive: 8, negative: 1, total: 9 },
        ],
      },
    });
    render(<GalleryTrendChart galleryId="test-gallery" />);
    await waitFor(() => {
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });
  });

  it('shows insufficient data message on API error', async () => {
    axios.get = vi.fn().mockRejectedValue(new Error('network'));
    render(<GalleryTrendChart galleryId="err-gallery" />);
    await waitFor(() => {
      expect(screen.getByText(/트렌드 데이터 부족/i)).toBeInTheDocument();
    });
  });
});

describe('GalleryMonitorPanel', () => {
  it('renders nothing when no dc sources', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { sources: [] } });
    const { container } = render(<GalleryMonitorPanel />);
    await waitFor(() => {
      // should render nothing (null)
      expect(container.firstChild).toBeNull();
    });
  });

  it('renders gallery cards for dc sources', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        sources: [{ type: 'dcinside', id: 'gall1', name: 'Test Gallery', files: 3, latest: '2026-01-15-10-30' }],
      },
    });
    axios.post = vi.fn().mockResolvedValue({ data: { sources: [] } });
    render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(screen.getByText('Test Gallery')).toBeInTheDocument();
    });
    expect(screen.getByText('수집 3회')).toBeInTheDocument();
  });

  it('filters out example-prefixed sources', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        sources: [
          { type: 'dcinside', id: 'example-gall', name: 'Example Gallery', files: 1 },
          { type: 'dcinside', id: 'real-gall', name: 'Real Gallery', files: 2 },
        ],
      },
    });
    axios.post = vi.fn().mockResolvedValue({ data: { sources: [] } });
    render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(screen.getByText('Real Gallery')).toBeInTheDocument();
    });
    expect(screen.queryByText('Example Gallery')).not.toBeInTheDocument();
  });
});

describe('OverviewPanel', () => {
  const defaultStats = {
    total: 0,
    ytComments: 0,
    galleryCount: 0,
    dcPosts: 0,
    dcPositive: 0,
    dcNegative: 0,
  };

  it('renders without crashing', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { sources: [] } });
    const { container } = render(<OverviewPanel stats={defaultStats} channels={[]} />);
    await waitFor(() => {
      expect(axios.get).toHaveBeenCalled();
    });
    expect(container).toBeTruthy();
  });

  it('shows empty hint when total is 0', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { sources: [] } });
    render(<OverviewPanel stats={defaultStats} channels={[]} />);
    await waitFor(() => {
      expect(screen.getByText(/수집 데이터가 없습니다/i)).toBeInTheDocument();
    });
  });

  it('renders YouTube, DCInside, Twitter panel cards', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { sources: [] } });
    render(<OverviewPanel stats={defaultStats} channels={[]} />);
    await waitFor(() => {
      expect(screen.getByText('YouTube')).toBeInTheDocument();
      expect(screen.getByText('DCInside')).toBeInTheDocument();
      expect(screen.getByText('X (Twitter)')).toBeInTheDocument();
    });
  });

  it('renders analysis navigation button', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { sources: [] } });
    render(<OverviewPanel stats={defaultStats} channels={[]} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /분석 페이지로 이동/i })).toBeInTheDocument();
    });
  });

  it('navigates to analysis page on button click', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { sources: [] } });
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    render(<OverviewPanel stats={defaultStats} channels={[]} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /분석 페이지로 이동/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /분석 페이지로 이동/i }));
    expect(dispatchSpy).toHaveBeenCalled();
  });
});

describe('YouTubePanel', () => {
  it('renders channels when provided', () => {
    const channels = [{ channel_title: 'Test Channel', videos_analyzed: 5, total_comments: 100 }];
    render(<YouTubePanel channels={channels} creators={[]} />);
    expect(screen.getByText('Test Channel')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('renders empty hint when no channels or creators', () => {
    render(<YouTubePanel channels={[]} creators={[]} />);
    expect(screen.getByText(/YouTube 수집 데이터 없음/i)).toBeInTheDocument();
  });

  it('renders creator data when provided', () => {
    const creators = [{
      name: 'CreatorA',
      comments: [1, 2, 3],
      total_likes: 500,
      sentiment_distribution: { positive: 0.7, neutral: 0.2, negative: 0.1 },
    }];
    render(<YouTubePanel channels={[]} creators={creators} />);
    expect(screen.getByText('CreatorA')).toBeInTheDocument();
    expect(screen.getByText('500')).toBeInTheDocument();
  });
});

describe('DCInsidePanel', () => {
  it('renders empty hint when no galleries', () => {
    render(<DCInsidePanel galleries={[]} />);
    expect(screen.getByText(/DCInside 갤러리 데이터 없음/i)).toBeInTheDocument();
  });

  it('renders gallery data', () => {
    const galleries = [{
      gallery_id: 'g1',
      gallery_name: 'Test Gall',
      total_posts: 20,
      total_comments: 50,
      positive_count: 12,
      negative_count: 5,
      posts: [
        { title: 'Post 1', author: 'user1', date: '2026-01-01', view_count: 100, recommend_count: 5, url: '/post/1' },
        { title: 'Post 2', author: 'user2', date: '2026-01-02', view_count: 80, recommend_count: 3, url: '/post/2' },
      ],
    }];
    render(<DCInsidePanel galleries={galleries} />);
    expect(screen.getByText('Test Gall')).toBeInTheDocument();
    expect(screen.getByText('Post 1')).toBeInTheDocument();
  });

  it('shows load more button when posts exceed 3', () => {
    const posts = Array.from({ length: 5 }, (_, i) => ({
      title: `Post ${i + 1}`, author: 'user', date: '2026-01-01',
      view_count: 10, recommend_count: 1, url: `/post/${i + 1}`,
    }));
    const galleries = [{
      gallery_id: 'g1', gallery_name: 'Big Gallery',
      total_posts: 5, total_comments: 20, positive_count: 3, negative_count: 1, posts,
    }];
    render(<DCInsidePanel galleries={galleries} />);
    expect(screen.getByText(/2개 더 보기/i)).toBeInTheDocument();
  });

  it('expands all posts on toggle click', () => {
    const posts = Array.from({ length: 5 }, (_, i) => ({
      title: `Post ${i + 1}`, author: 'user', date: '2026-01-01',
      view_count: 10, recommend_count: 1, url: `/post/${i + 1}`,
    }));
    const galleries = [{
      gallery_id: 'g1', gallery_name: 'Big Gallery',
      total_posts: 5, total_comments: 20, positive_count: 3, negative_count: 1, posts,
    }];
    render(<DCInsidePanel galleries={galleries} />);
    fireEvent.click(screen.getByText(/2개 더 보기/i));
    expect(screen.getByText('Post 5')).toBeInTheDocument();
  });
});

describe('TwitterPanel', () => {
  it('renders without crashing', () => {
    const { container } = render(<TwitterPanel />);
    expect(container).toBeTruthy();
  });

  it('renders quick keyword buttons', () => {
    render(<TwitterPanel />);
    expect(screen.getByText('유튜브 클립')).toBeInTheDocument();
    expect(screen.getByText('SNS 이슈')).toBeInTheDocument();
  });

  it('renders search input', () => {
    render(<TwitterPanel />);
    expect(screen.getByPlaceholderText(/검색할 키워드/i)).toBeInTheDocument();
  });

  it('updates input value on typing', () => {
    render(<TwitterPanel />);
    const input = screen.getByPlaceholderText(/검색할 키워드/i);
    fireEvent.change(input, { target: { value: 'testquery' } });
    expect(input).toHaveValue('testquery');
  });

  it('opens twitter search on X에서 검색 button click with keyword', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {});
    render(<TwitterPanel />);
    const input = screen.getByPlaceholderText(/검색할 키워드/i);
    fireEvent.change(input, { target: { value: 'test query' } });
    fireEvent.click(screen.getByRole('button', { name: /X에서 검색/i }));
    expect(openSpy).toHaveBeenCalledWith(
      expect.stringContaining('twitter.com/search'),
      '_blank'
    );
  });
});

describe('SocialPanel', () => {
  it('renders without crashing', () => {
    const { container } = render(<SocialPanel />);
    expect(container).toBeTruthy();
  });

  it('renders Instagram, Facebook, Threads cards', () => {
    render(<SocialPanel />);
    expect(screen.getByText('Instagram')).toBeInTheDocument();
    expect(screen.getByText('Facebook')).toBeInTheDocument();
    expect(screen.getByText('Threads')).toBeInTheDocument();
  });

  it('shows URL examples for each platform', () => {
    render(<SocialPanel />);
    expect(screen.getByText(/instagram.com\/username/i)).toBeInTheDocument();
    expect(screen.getByText(/facebook.com\/page/i)).toBeInTheDocument();
    expect(screen.getByText(/threads.net\/@username/i)).toBeInTheDocument();
  });
});

describe('EmptyHint', () => {
  it('renders with custom title and description', () => {
    render(<EmptyHint title="No Data" description="Please add data" />);
    expect(screen.getByText('No Data')).toBeInTheDocument();
    expect(screen.getByText('Please add data')).toBeInTheDocument();
  });

  it('uses default title when not provided', () => {
    render(<EmptyHint />);
    expect(screen.getByText('데이터 없음')).toBeInTheDocument();
  });

  it('falls back to text prop when description is missing', () => {
    render(<EmptyHint text="Fallback text" />);
    expect(screen.getByText('Fallback text')).toBeInTheDocument();
  });

  it('uses default body when neither description nor text given', () => {
    render(<EmptyHint title="Empty" />);
    expect(screen.getByText(/상단 URL 검색으로 즉시 분석/)).toBeInTheDocument();
  });
});

describe('ScanHistoryPanel', () => {
  function mockFetch(data, ok = true, status = 200) {
    global.fetch = vi.fn().mockResolvedValue({
      ok,
      status,
      json: () => Promise.resolve(data),
    });
  }

  afterEach(() => {
    delete global.fetch;
  });

  it('renders loading state then scan list', async () => {
    mockFetch({
      scans: [
        { id: '1', platform: 'youtube', title: 'Test Video', url: 'https://youtube.com/1', analyzed_at: '2026-01-01T10:00:00Z' },
        { id: '2', platform: 'dcinside', title: 'Test Post', url: 'https://gall.dcinside.com/2', analyzed_at: '2026-01-02T10:00:00Z' },
      ],
      total: 2,
    });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText('Test Video')).toBeInTheDocument();
      expect(screen.getByText('Test Post')).toBeInTheDocument();
    });
    expect(
      screen.getByText((_, element) =>
        element?.classList.contains('scan-history__count') && element.textContent === '총 2건'
      )
    ).toBeInTheDocument();
  });

  it('shows empty state when no scans', async () => {
    mockFetch({ scans: [], total: 0 });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText(/스캔 기록이 없습니다/)).toBeInTheDocument();
    });
  });

  it('shows error state on fetch failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({}),
    });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/데이터를 불러오지 못했습니다/)).toBeInTheDocument();
    });
  });

  it('shows error on network failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText(/Network error/)).toBeInTheDocument();
    });
  });

  it('filters by platform', async () => {
    mockFetch({ scans: [], total: 0 });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText(/스캔 기록이 없습니다/)).toBeInTheDocument();
    });
    const select = screen.getByLabelText('플랫폼 필터');
    fireEvent.change(select, { target: { value: 'youtube' } });
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('platform=youtube'));
    });
  });

  it('renders pagination when totalPages > 1', async () => {
    const scans = Array.from({ length: 10 }, (_, i) => ({
      id: `${i}`, platform: 'youtube', title: `Scan ${i}`, analyzed_at: '2026-01-01T10:00:00Z',
    }));
    mockFetch({ scans, total: 25 });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText('Scan 0')).toBeInTheDocument();
    });
    // pagination visible: 이전/다음 buttons
    expect(screen.getByRole('button', { name: '이전' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '다음' })).toBeEnabled();
  });

  it('navigates to next page on 다음 click', async () => {
    const scans = Array.from({ length: 10 }, (_, i) => ({
      id: `${i}`, platform: 'youtube', title: `Scan ${i}`, analyzed_at: '2026-01-01T10:00:00Z',
    }));
    mockFetch({ scans, total: 25 });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText('Scan 0')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: '다음' }));
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('page=2'));
    });
  });

  it('renders page number buttons with ellipsis for many pages', async () => {
    const scans = Array.from({ length: 10 }, (_, i) => ({
      id: `${i}`, platform: 'youtube', title: `Scan ${i}`, analyzed_at: '2026-01-01T10:00:00Z',
    }));
    mockFetch({ scans, total: 100 }); // 10 pages
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText('Scan 0')).toBeInTheDocument();
    });
    // page 1 is active, page 2 visible, page 10 (last) visible, ellipsis between
    expect(screen.getByRole('button', { name: '1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '2' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '10' })).toBeInTheDocument();
    expect(screen.getByText('…')).toBeInTheDocument();
  });

  it('handles scan with url different from title', async () => {
    mockFetch({
      scans: [{ id: '1', platform: 'youtube', title: 'My Video', url: 'https://youtube.com/watch?v=abc', analyzed_at: '2026-01-01T10:00:00Z' }],
      total: 1,
    });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText('My Video')).toBeInTheDocument();
      expect(screen.getByText('https://youtube.com/watch?v=abc')).toBeInTheDocument();
    });
  });

  it('shows (제목 없음) when scan has no title or url', async () => {
    mockFetch({
      scans: [{ id: '1', platform: 'youtube', analyzed_at: '2026-01-01T10:00:00Z' }],
      total: 1,
    });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText('(제목 없음)')).toBeInTheDocument();
    });
  });

  it('uses created_at when analyzed_at is missing', async () => {
    mockFetch({
      scans: [{ id: '1', platform: 'youtube', title: 'Test', created_at: '2026-06-15T14:30:00Z' }],
      total: 1,
    });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText('Test')).toBeInTheDocument();
    });
  });

  it('shows — for missing date', async () => {
    mockFetch({
      scans: [{ id: '1', platform: 'youtube', title: 'No Date' }],
      total: 1,
    });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText('—')).toBeInTheDocument();
    });
  });

  it('renders unknown platform with default badge', async () => {
    mockFetch({
      scans: [{ id: '1', platform: 'unknown_platform', title: 'Unknown', analyzed_at: '2026-01-01T10:00:00Z' }],
      total: 1,
    });
    render(<ScanHistoryPanel />);
    await waitFor(() => {
      expect(screen.getByText('Unknown')).toBeInTheDocument();
    });
  });
});

describe('GalleryMonitorPanel - interactions', () => {
  it('calls goAnalysis on 분석 button click', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        sources: [{ type: 'dcinside', id: 'gall1', name: 'Test Gallery', files: 3 }],
      },
    });
    axios.post = vi.fn().mockResolvedValue({ data: { sources: [] } });
    const pushStateSpy = vi.spyOn(window.history, 'pushState');
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(screen.getByText('Test Gallery')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: '분석' }));
    expect(pushStateSpy).toHaveBeenCalledWith({}, '', '/analysis');
    expect(dispatchSpy).toHaveBeenCalled();
    expect(Storage.prototype.setItem).toHaveBeenCalledWith(
      'analysisPreselect',
      expect.stringContaining('gall1')
    );
  });

  it('toggles trend chart on 트렌드 button click', async () => {
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/sources')) {
        return Promise.resolve({
          data: { sources: [{ type: 'dcinside', id: 'gall1', name: 'Gallery', files: 2 }] },
        });
      }
      if (url.includes('/trend')) {
        return Promise.resolve({ data: { trend: [] } });
      }
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: { sources: [] } });
    render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(screen.getByText('Gallery')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: '트렌드' }));
    await waitFor(() => {
      expect(screen.getByText(/트렌드 데이터 부족/)).toBeInTheDocument();
    });
    // click again to close
    fireEvent.click(screen.getByRole('button', { name: '닫기' }));
    expect(screen.queryByText(/트렌드 데이터 부족/)).not.toBeInTheDocument();
  });

  it('shows sentiment alerts when negPct >= 5', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        sources: [{ type: 'dcinside', id: 'gall1', name: 'Alert Gallery', files: 5 }],
      },
    });
    axios.post = vi.fn().mockResolvedValue({
      data: {
        sources: [{
          id: 'gall1',
          sentiment: { sentiment: { positive: 10, neutral: 5, negative: 10 } },
        }],
      },
    });
    render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(screen.getByText(/부정 감성 경고/)).toBeInTheDocument();
    });
    expect(
      screen.getByText((_, element) =>
        element?.classList.contains('gallery-monitor__alert-item') && element.textContent?.includes('Alert Gallery')
      )
    ).toBeInTheDocument();
  });

  it('does not show alerts when negPct < 5', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        sources: [{ type: 'dcinside', id: 'gall1', name: 'Safe Gallery', files: 5 }],
      },
    });
    axios.post = vi.fn().mockResolvedValue({
      data: {
        sources: [{
          id: 'gall1',
          sentiment: { sentiment: { positive: 90, neutral: 8, negative: 1 } },
        }],
      },
    });
    render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(screen.getByText('Safe Gallery')).toBeInTheDocument();
    });
    expect(screen.queryByText(/부정 감성 경고/)).not.toBeInTheDocument();
  });

  it('handles POST error gracefully', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        sources: [{ type: 'dcinside', id: 'gall1', name: 'Fallback Gallery', files: 1 }],
      },
    });
    axios.post = vi.fn().mockRejectedValue(new Error('POST failed'));
    render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(screen.getByText('Fallback Gallery')).toBeInTheDocument();
    });
  });

  it('handles GET error gracefully', async () => {
    axios.get = vi.fn().mockRejectedValue(new Error('GET failed'));
    const { container } = render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(container.querySelector('.gallery-monitor')).toBeNull();
    });
  });

  it('parseLatestDate formats date correctly', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        sources: [{ type: 'dcinside', id: 'gall1', name: 'G', files: 1, latest: '2026-03-15-14-30' }],
      },
    });
    axios.post = vi.fn().mockResolvedValue({ data: { sources: [] } });
    render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(screen.getByText('03.15 14:30')).toBeInTheDocument();
    });
  });

  it('parseLatestDate returns — for null', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        sources: [{ type: 'dcinside', id: 'gall1', name: 'G', files: 1 }],
      },
    });
    axios.post = vi.fn().mockResolvedValue({ data: { sources: [] } });
    render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(screen.getByText('—')).toBeInTheDocument();
    });
  });

  it('parseLatestDate strips .json for non-matching format', async () => {
    axios.get = vi.fn().mockResolvedValue({
      data: {
        sources: [{ type: 'dcinside', id: 'gall1', name: 'G', files: 1, latest: 'somefile.json' }],
      },
    });
    axios.post = vi.fn().mockResolvedValue({ data: { sources: [] } });
    render(<GalleryMonitorPanel />);
    await waitFor(() => {
      expect(screen.getByText('somefile')).toBeInTheDocument();
    });
  });
});

describe('OverviewPanel - additional', () => {
  it('hides empty hint when total > 0', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { sources: [] } });
    const stats = { total: 10, ytComments: 5, galleryCount: 2, dcPosts: 3, dcPositive: 1, dcNegative: 1 };
    render(<OverviewPanel stats={stats} channels={[]} />);
    await waitFor(() => {
      expect(screen.queryByText(/수집 데이터가 없습니다/)).not.toBeInTheDocument();
    });
  });
});

describe('YouTubePanel - additional', () => {
  it('renders channel fallback name when channel_title missing', () => {
    const channels = [{ channel: 'fallback-ch', videos_analyzed: 2, total_comments: 10 }];
    render(<YouTubePanel channels={channels} creators={[]} />);
    expect(screen.getByText('fallback-ch')).toBeInTheDocument();
  });

  it('renders creator without sentiment_distribution', () => {
    const creators = [{ name: 'NoSentiment', comments: [1], total_likes: 10 }];
    render(<YouTubePanel channels={[]} creators={creators} />);
    expect(screen.getByText('NoSentiment')).toBeInTheDocument();
    expect(screen.queryByText(/긍정/)).not.toBeInTheDocument();
  });
});

describe('TwitterPanel - additional', () => {
  it('opens search on Enter key with keyword', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {});
    render(<TwitterPanel />);
    const input = screen.getByPlaceholderText(/검색할 키워드/i);
    fireEvent.change(input, { target: { value: 'enter test' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(openSpy).toHaveBeenCalledWith(expect.stringContaining('twitter.com/search'), '_blank');
  });

  it('does not open search on Enter with empty keyword', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {});
    render(<TwitterPanel />);
    const input = screen.getByPlaceholderText(/검색할 키워드/i);
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('does not open search on button click with empty keyword', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {});
    render(<TwitterPanel />);
    fireEvent.click(screen.getByRole('button', { name: /X에서 검색/i }));
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('opens quick keyword search', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {});
    render(<TwitterPanel />);
    fireEvent.click(screen.getByText('커뮤니티 반응'));
    expect(openSpy).toHaveBeenCalledWith(expect.stringContaining(encodeURIComponent('커뮤니티 반응')), '_blank');
  });
});

describe('DCInsidePanel - additional', () => {
  it('does not show load more for exactly 3 posts', () => {
    const posts = Array.from({ length: 3 }, (_, i) => ({
      title: `Post ${i}`, author: 'user', date: '2026-01-01',
      view_count: 10, recommend_count: 1, url: `/post/${i}`,
    }));
    const galleries = [{
      gallery_id: 'g1', gallery_name: 'G', total_posts: 3, total_comments: 10,
      positive_count: 1, negative_count: 0, posts,
    }];
    render(<DCInsidePanel galleries={galleries} />);
    expect(screen.queryByText(/더 보기/)).not.toBeInTheDocument();
  });

  it('handles missing comment_count gracefully', () => {
    const galleries = [{
      gallery_id: 'g1', gallery_name: 'G', total_posts: 1, total_comments: 5,
      positive_count: 0, negative_count: 0,
      posts: [{ title: 'P', author: 'a', date: 'd', view_count: 1, recommend_count: 0, url: '/p' }],
    }];
    render(<DCInsidePanel galleries={galleries} />);
    expect(screen.getByText(/💬 0/)).toBeInTheDocument();
  });
});
