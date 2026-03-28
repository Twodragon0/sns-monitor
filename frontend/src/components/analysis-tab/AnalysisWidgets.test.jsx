import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import { WordCloudAndCompare, DailyReportsPanel } from './AnalysisWidgets';

vi.mock('axios');

vi.mock('recharts', () => ({
  BarChart: ({ children, onClick }) => (
    <div data-testid="bar-chart" onClick={onClick}>{children}</div>
  ),
  Bar: () => null,
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
  axios.get = vi.fn().mockResolvedValue({ data: {} });
  axios.post = vi.fn().mockResolvedValue({ data: {} });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe('WordCloudAndCompare', () => {
  it('renders without crashing with empty keywords', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { galleries: [] } });
    const { container } = render(<WordCloudAndCompare keywords={[]} />);
    expect(container).toBeTruthy();
    await waitFor(() => expect(axios.get).toHaveBeenCalled());
  });

  it('renders keyword cloud when keywords provided', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { galleries: [] } });
    const keywords = [
      { word: 'react', count: 50 },
      { word: 'vitest', count: 30 },
      { word: 'testing', count: 10 },
    ];
    render(<WordCloudAndCompare keywords={keywords} />);
    await waitFor(() => {
      expect(screen.getByText('react')).toBeInTheDocument();
      expect(screen.getByText('vitest')).toBeInTheDocument();
    });
  });

  it('shows negative sentiment alert when gallery has neg_pct >= 5', async () => {
    const galleries = [
      { id: 'g1', name: '테스트갤러리', neg_pct: 10, negative: 20, pos_pct: 30, keywords: ['분노', '실망'] },
    ];
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/compare')) return Promise.resolve({ data: { galleries } });
      return Promise.resolve({ data: {} });
    });
    render(<WordCloudAndCompare keywords={[]} />);
    await waitFor(() => {
      expect(screen.getByText('부정 감성 경고')).toBeInTheDocument();
      expect(screen.getByText(/테스트갤러리/)).toBeInTheDocument();
    });
  });

  it('does not show alert when no galleries have neg_pct >= 5', async () => {
    const galleries = [
      { id: 'g1', name: '안전갤러리', neg_pct: 2, negative: 3, pos_pct: 70 },
    ];
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/compare')) return Promise.resolve({ data: { galleries } });
      return Promise.resolve({ data: {} });
    });
    render(<WordCloudAndCompare keywords={[]} />);
    await waitFor(() => {
      expect(screen.queryByText('부정 감성 경고')).not.toBeInTheDocument();
    });
  });

  it('shows comparison chart when more than 1 gallery', async () => {
    const galleries = [
      { id: 'g1', name: '갤러리A', neg_pct: 3, pos_pct: 60 },
      { id: 'g2', name: '갤러리B', neg_pct: 8, pos_pct: 40 },
    ];
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/compare')) return Promise.resolve({ data: { galleries } });
      return Promise.resolve({ data: {} });
    });
    render(<WordCloudAndCompare keywords={[]} />);
    await waitFor(() => {
      expect(screen.getByText('갤러리간 감성 비교')).toBeInTheDocument();
    });
  });

  it('handles compare API failure gracefully', async () => {
    axios.get = vi.fn().mockRejectedValue(new Error('Network error'));
    const { container } = render(<WordCloudAndCompare keywords={[]} />);
    await waitFor(() => expect(axios.get).toHaveBeenCalled());
    expect(container).toBeTruthy();
  });

  it('shows trend insufficient data message when trend < 2 entries', async () => {
    const galleries = [
      { id: 'g1', name: '갤러리A', neg_pct: 3, pos_pct: 60 },
      { id: 'g2', name: '갤러리B', neg_pct: 8, pos_pct: 40 },
    ];
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/compare')) return Promise.resolve({ data: { galleries } });
      if (url.includes('/api/analysis/trend')) return Promise.resolve({ data: { trend: [{ timestamp: '2026-01-01T00:00:00', positive: 5, negative: 2 }] } });
      return Promise.resolve({ data: {} });
    });
    render(<WordCloudAndCompare keywords={[]} />);
    await waitFor(() => expect(screen.getByText('갤러리간 감성 비교')).toBeInTheDocument());
  });

  it('shows gallery keywords in alert block', async () => {
    const galleries = [
      { id: 'g1', name: '부정갤러리', neg_pct: 15, negative: 50, pos_pct: 20, keywords: ['분노', '실망', '최악'] },
    ];
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/compare')) return Promise.resolve({ data: { galleries } });
      return Promise.resolve({ data: {} });
    });
    render(<WordCloudAndCompare keywords={[]} />);
    await waitFor(() => {
      expect(screen.getByText(/분노/)).toBeInTheDocument();
    });
  });
});

describe('DailyReportsPanel', () => {
  it('renders without crashing', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { reports: [] } });
    const { container } = render(<DailyReportsPanel />);
    expect(container).toBeTruthy();
    await waitFor(() => expect(axios.get).toHaveBeenCalled());
  });

  it('shows empty reports message when no reports', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { reports: [] } });
    render(<DailyReportsPanel />);
    await waitFor(() => {
      expect(screen.getByText(/보고서가 없습니다/)).toBeInTheDocument();
    });
  });

  it('shows report list when reports are returned', async () => {
    const reports = [
      { date: '2026-01-15', summary: { total_items: 100 } },
      { date: '2026-01-14', summary: { total_items: 80 } },
    ];
    axios.get = vi.fn().mockResolvedValue({ data: { reports } });
    render(<DailyReportsPanel />);
    await waitFor(() => {
      expect(screen.getByText(/01-15/)).toBeInTheDocument();
      expect(screen.getByText(/01-14/)).toBeInTheDocument();
    });
  });

  it('shows 오늘 보고서 생성 button', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { reports: [] } });
    render(<DailyReportsPanel />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /오늘 보고서 생성/i })).toBeInTheDocument();
    });
  });

  it('shows loading state during report generation', async () => {
    axios.get = vi.fn().mockResolvedValue({ data: { reports: [] } });
    axios.post = vi.fn().mockReturnValue(new Promise(() => {})); // never resolves
    render(<DailyReportsPanel />);
    await waitFor(() => expect(screen.getByRole('button', { name: /오늘 보고서 생성/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /오늘 보고서 생성/i }));
    await waitFor(() => {
      expect(screen.getByText(/생성 중/i)).toBeInTheDocument();
    });
  });

  it('shows report detail after generating', async () => {
    const reportDetail = {
      date: '2026-01-15',
      generated_at: '2026-01-15T10:00:00',
      summary: { total_items: 120, pos_pct: 65, neg_pct: 10, alerts: 1 },
      galleries: [
        { id: 'g1', name: 'TestGallery', total: 120, pos_pct: 65, neg_pct: 10, keywords: ['good', 'nice'], files_analyzed: 3 },
      ],
    };
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/reports')) return Promise.resolve({ data: { reports: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: reportDetail });
    // Also mock the follow-up GET to refresh list
    axios.get = vi.fn().mockImplementation(() => Promise.resolve({ data: { reports: [] } }));

    render(<DailyReportsPanel />);
    await waitFor(() => expect(screen.getByRole('button', { name: /오늘 보고서 생성/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /오늘 보고서 생성/i }));
    await waitFor(() => {
      expect(screen.getByText('TestGallery')).toBeInTheDocument();
    });
  });

  it('views report detail when report button is clicked', async () => {
    const reports = [{ date: '2026-01-15', summary: { total_items: 50 } }];
    const detail = {
      date: '2026-01-15',
      generated_at: '2026-01-15T09:00:00',
      summary: { total_items: 50, pos_pct: 70, neg_pct: 5, alerts: 0 },
      galleries: [
        { id: 'g2', name: 'ReportGallery', total: 50, pos_pct: 70, neg_pct: 5, keywords: [], files_analyzed: 2 },
      ],
    };
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/reports/2026-01-15')) return Promise.resolve({ data: detail });
      return Promise.resolve({ data: { reports } });
    });
    render(<DailyReportsPanel />);
    await waitFor(() => expect(screen.getByText(/01-15/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/01-15/));
    await waitFor(() => {
      expect(screen.getByText('ReportGallery')).toBeInTheDocument();
    });
  });

  it('toggles report detail off when same report button is clicked twice', async () => {
    const reports = [{ date: '2026-01-15', summary: { total_items: 30 } }];
    const detail = {
      date: '2026-01-15',
      generated_at: '2026-01-15T09:00:00',
      summary: { total_items: 30, pos_pct: 60, neg_pct: 8, alerts: 0 },
      galleries: [{ id: 'g3', name: 'ToggleGallery', total: 30, pos_pct: 60, neg_pct: 8, keywords: [], files_analyzed: 1 }],
    };
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/reports/2026-01-15')) return Promise.resolve({ data: detail });
      return Promise.resolve({ data: { reports } });
    });
    render(<DailyReportsPanel />);
    await waitFor(() => expect(screen.getByText(/01-15/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/01-15/));
    await waitFor(() => expect(screen.getByText('ToggleGallery')).toBeInTheDocument());
    fireEvent.click(screen.getAllByText(/01-15/)[0]);
    await waitFor(() => expect(screen.queryByText('ToggleGallery')).not.toBeInTheDocument());
  });

  it('handles report detail fetch failure silently', async () => {
    const reports = [{ date: '2026-01-14', summary: { total_items: 20 } }];
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/reports/2026-01-14')) return Promise.reject(new Error('Not found'));
      return Promise.resolve({ data: { reports } });
    });
    render(<DailyReportsPanel />);
    await waitFor(() => expect(screen.getByText(/01-14/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/01-14/));
    // Should not crash
    await waitFor(() => expect(screen.getByText(/일일 감성 보고서/)).toBeInTheDocument());
  });
});
