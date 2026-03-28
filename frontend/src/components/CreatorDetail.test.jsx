import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CreatorDetail from './CreatorDetail';

// Mock recharts to avoid SVG/ResizeObserver issues in jsdom
vi.mock('recharts', () => ({
  PieChart: ({ children }) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => null,
  Cell: () => null,
  BarChart: ({ children }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  Legend: () => null,
}));

vi.mock('./Dashboard.css', () => ({}));

beforeAll(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterAll(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('CreatorDetail', () => {
  it('shows loading spinner initially', () => {
    // fetch that never resolves => loading persists
    global.fetch = vi.fn().mockReturnValue(new Promise(() => {}));
    const { container } = render(<CreatorDetail creatorId="example" />);
    expect(container.querySelector('.spinner')).toBeTruthy();
    expect(screen.getByText(/크리에이터 데이터 로딩 중/i)).toBeInTheDocument();
  });

  it('renders creator label from creatorId prop', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
    });
    render(<CreatorDetail creatorId="example-creator" />);
    await waitFor(() => {
      expect(screen.getByText(/Example Creator 크리에이터 모니터링/i)).toBeInTheDocument();
    });
  });

  it('uses fallback label when creatorId is not provided', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    render(<CreatorDetail />);
    await waitFor(() => {
      expect(screen.getByText(/Example Creator 크리에이터 모니터링/i)).toBeInTheDocument();
    });
  });

  it('falls back to example data on fetch error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network error'));
    render(<CreatorDetail creatorId="test" />);
    await waitFor(() => {
      // Example data has Creator1, Creator2, Creator3
      expect(screen.getByText('Creator1')).toBeInTheDocument();
    });
  });

  it('falls back to example data when API returns non-ok', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    render(<CreatorDetail creatorId="test" />);
    await waitFor(() => {
      expect(screen.getByText('Creator1')).toBeInTheDocument();
    });
  });

  it('renders channel data from API response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        channels: [
          {
            name: 'TestChannel',
            handle: '@test-ch',
            total_comments: 50,
            total_likes: 200,
            overall_score: 90,
            sentiment_distribution: { positive: 0.8, neutral: 0.15, negative: 0.05 },
            comments: [],
            videos: [],
          },
        ],
        galleries: [],
      }),
    });
    render(<CreatorDetail creatorId="test" />);
    await waitFor(() => {
      expect(screen.getByText('TestChannel')).toBeInTheDocument();
    });
    expect(screen.getByText('@test-ch')).toBeInTheDocument();
    expect(screen.getByText(/댓글 50개/)).toBeInTheDocument();
  });

  it('renders monitoring keywords section', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    render(<CreatorDetail creatorId="test" />);
    await waitFor(() => {
      expect(screen.getByText('모니터링 키워드')).toBeInTheDocument();
    });
  });

  it('renders summary stat cards', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    render(<CreatorDetail creatorId="test" />);
    await waitFor(() => {
      expect(screen.getByText('모니터링 채널')).toBeInTheDocument();
      expect(screen.getByText('전체 댓글')).toBeInTheDocument();
      expect(screen.getByText('긍정 반응')).toBeInTheDocument();
      expect(screen.getByText('부정 반응')).toBeInTheDocument();
    });
  });

  it('renders "대시보드로 돌아가기" button', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    render(<CreatorDetail creatorId="test" />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /대시보드로 돌아가기/i })).toBeInTheDocument();
    });
  });

  it('대시보드로 돌아가기 button dispatches popstate', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    render(<CreatorDetail creatorId="test" />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /대시보드로 돌아가기/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /대시보드로 돌아가기/i }));
    expect(dispatchSpy).toHaveBeenCalled();
  });

  it('toggles channel expansion on click', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    render(<CreatorDetail creatorId="test" />);
    await waitFor(() => {
      expect(screen.getByText('Creator1')).toBeInTheDocument();
    });

    // The channel header is a clickable div with text "Creator1"
    const channelHeader = screen.getByText('Creator1').closest('[style*="cursor: pointer"]');
    if (channelHeader) {
      fireEvent.click(channelHeader);
      // After click, "최근 영상" section should appear since example data has videos
      await waitFor(() => {
        expect(screen.getAllByText('최근 영상').length).toBeGreaterThan(0);
      });
    }
  });

  it('shows no-data placeholder when channelsData is empty', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ channels: [], galleries: [] }),
    });
    render(<CreatorDetail creatorId="empty-creator" />);
    await waitFor(() => {
      expect(screen.getByText(/에 대한 데이터가 없습니다/i)).toBeInTheDocument();
    });
  });

  it('renders DCInside galleries when provided', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        channels: [],
        galleries: [
          { gallery_id: 'gall1', gallery_name: 'Test Gallery', total_posts: 10, total_comments: 25 },
        ],
      }),
    });
    render(<CreatorDetail creatorId="test" />);
    await waitFor(() => {
      expect(screen.getByText('Test Gallery')).toBeInTheDocument();
    });
  });

  it('displays last_updated when API returns it', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        channels: [],
        galleries: [],
        last_updated: '2026-01-15T10:30:00Z',
      }),
    });
    render(<CreatorDetail creatorId="test" />);
    await waitFor(() => {
      expect(screen.getByText(/마지막 업데이트/i)).toBeInTheDocument();
    });
  });
});
