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
