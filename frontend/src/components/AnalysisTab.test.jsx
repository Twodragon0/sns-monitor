import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import AnalysisTab from './AnalysisTab';

vi.mock('axios');

// Silence console.error noise from React during tests
beforeAll(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterAll(() => {
  vi.restoreAllMocks();
});

// Helper to build a default axios.get mock with overrideable LLM status
function buildGetMock({ llmAvailable = false, llmProvider = null, llmModel = null, sources = [] } = {}) {
  return vi.fn().mockImplementation((url) => {
    if (url.includes('/api/analysis/status')) {
      return Promise.resolve({ data: { mirofish_available: false } });
    }
    if (url.includes('/api/analysis/llm/status')) {
      return Promise.resolve({ data: { available: llmAvailable, provider: llmProvider, model: llmModel } });
    }
    if (url.includes('/api/auth/me')) {
      return Promise.resolve({ data: { logged_in: false, auth_required: false } });
    }
    if (url.includes('/api/analysis/sources')) {
      return Promise.resolve({ data: { sources } });
    }
    if (url.includes('/api/analysis/projects')) {
      return Promise.resolve({ data: { success: true, data: [] } });
    }
    if (url.includes('/api/analysis/compare')) {
      return Promise.resolve({ data: { galleries: [] } });
    }
    if (url.includes('/api/analysis/trend')) {
      return Promise.resolve({ data: { trend: [] } });
    }
    return Promise.resolve({ data: {} });
  });
}

beforeEach(() => {
  // Default: status checks return "not available"
  axios.get = buildGetMock();

  axios.post = vi.fn().mockResolvedValue({ data: {} });

  // sessionStorage stub
  const store = {};
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => store[key] ?? null);
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key, val) => { store[key] = val; });
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((key) => { delete store[key]; });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe('AnalysisTab (smoke)', () => {
  it('renders without crashing', () => {
    const { container } = render(<AnalysisTab />);
    expect(container).toBeTruthy();
  });

  it('renders the main heading', () => {
    render(<AnalysisTab />);
    expect(screen.getByText('수집 데이터 분석 · 요약')).toBeInTheDocument();
  });

  it('renders the back-to-dashboard button', () => {
    render(<AnalysisTab />);
    expect(screen.getByRole('button', { name: /대시보드로 돌아가기/ })).toBeInTheDocument();
  });

  it('renders the data-source selection section', () => {
    render(<AnalysisTab />);
    expect(screen.getByText('데이터 소스 선택')).toBeInTheDocument();
  });

  it('shows "no sources" message when sources list is empty', async () => {
    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/수집된 소스가 없습니다/)).toBeInTheDocument();
    });
  });
});

describe('AnalysisTab - AI status banner', () => {
  it('shows "AI 미연결" badge when LLM is not available', async () => {
    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/AI 미연결/)).toBeInTheDocument();
    });
  });

  it('shows LLM provider badge when LLM is connected', async () => {
    axios.get = buildGetMock({ llmAvailable: true, llmProvider: 'anthropic', llmModel: 'claude-3-5-sonnet' });

    render(<AnalysisTab />);
    await waitFor(() => {
      // "Claude 연결됨" banner should appear; check the heading badge text
      expect(screen.getByText(/Claude 연결됨/)).toBeInTheDocument();
    });
  });
});

describe('AnalysisTab - source selection', () => {
  const mockSources = [
    { type: 'youtube', id: 'ch1', name: 'Channel 1', files: 5 },
    { type: 'dcinside', id: 'dc1', name: 'Gallery 1', files: 3 },
  ];

  beforeEach(() => {
    axios.get = buildGetMock({ sources: mockSources });
  });

  it('renders source buttons after sources load', async () => {
    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/Channel 1/)).toBeInTheDocument();
      expect(screen.getByText(/Gallery 1/)).toBeInTheDocument();
    });
  });

  it('analysis button is disabled with no sources selected', async () => {
    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/소스 선택 후 분석/)).toBeInTheDocument();
    });
    // The button text changes once a source is selected; when none selected it shows this text
    const btn = screen.getByRole('button', { name: /소스 선택 후 분석/ });
    expect(btn).toBeDisabled();
  });

  it('selecting a source enables the analysis button', async () => {
    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/Channel 1/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => {
      // After selecting, button label changes to "1개 소스 기본 분석"
      expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled();
    });
  });

  it('clicking selected source deselects it', async () => {
    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/Channel 1/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Channel 1/));
    // Select
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled();
    });
    // Deselect
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /소스 선택 후 분석/ })).toBeDisabled();
    });
  });
});

describe('AnalysisTab - local analysis flow', () => {
  const mockSources = [
    { type: 'youtube', id: 'ch1', name: 'Channel 1', files: 5 },
  ];

  beforeEach(() => {
    axios.get = buildGetMock({ sources: mockSources });
  });

  it('calls local-summary API when analysis starts with no LLM', async () => {
    let resolvePost;
    // Use a never-settling promise to prevent the result render from triggering
    // WordCloudAndCompare's useEffect (which calls axios.get) before cleanup
    axios.post = vi.fn().mockReturnValue(new Promise(res => { resolvePost = res; }));

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());

    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());

    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    // Wait until button transitions to "분석 중…" to confirm the call was made
    await waitFor(() => {
      expect(screen.getByText('분석 중…')).toBeInTheDocument();
    });

    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/local-summary'),
      expect.objectContaining({ sources: [{ type: 'youtube', id: 'ch1' }] })
    );
  });

  it('shows error when local analysis API fails', async () => {
    axios.post = vi.fn().mockRejectedValue({ message: 'Server Error' });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());

    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());

    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(screen.getByText(/Error:/)).toBeInTheDocument();
    });
  });
});

describe('AnalysisTab - back navigation', () => {
  it('back button triggers history navigation', async () => {
    const pushStateSpy = vi.spyOn(window.history, 'pushState').mockImplementation(() => {});
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent').mockImplementation(() => {});

    render(<AnalysisTab />);
    fireEvent.click(screen.getByRole('button', { name: /대시보드로 돌아가기/ }));

    expect(pushStateSpy).toHaveBeenCalledWith({}, '', '/');
    expect(dispatchSpy).toHaveBeenCalled();
  });
});

describe('AnalysisTab - AuthPanel integration', () => {
  it('shows AuthPanel API key input when LLM is not connected', async () => {
    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/API Key를 입력하면 AI 분석이 활성화됩니다/)).toBeInTheDocument();
    });
  });
});
