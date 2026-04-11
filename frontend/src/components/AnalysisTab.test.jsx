import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import axios from 'axios';
import AnalysisTab from './AnalysisTab';

vi.mock('axios');
vi.mock('./analysis-tab/AnalysisWidgets', async () => {
  const actual = await vi.importActual('./analysis-tab/AnalysisWidgets');
  return {
    ...actual,
    DailyReportsPanel: () => <div data-testid="daily-reports-stub">DailyReportsPanel</div>,
  };
});

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

async function renderAnalysisTab() {
  let view;
  await act(async () => {
    view = render(<AnalysisTab />);
    await Promise.resolve();
    await Promise.resolve();
  });
  return view;
}

describe('AnalysisTab (smoke)', () => {
  it('renders without crashing', async () => {
    const { container } = await renderAnalysisTab();
    expect(container).toBeTruthy();
  });

  it('renders the main heading', async () => {
    await renderAnalysisTab();
    expect(screen.getByText('수집 데이터 분석 · 요약')).toBeInTheDocument();
  });

  it('renders the back-to-dashboard button', async () => {
    await renderAnalysisTab();
    expect(screen.getByRole('button', { name: /대시보드로 돌아가기/ })).toBeInTheDocument();
  });

  it('renders the data-source selection section', async () => {
    await renderAnalysisTab();
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
      expect(screen.getByText(/오류:/)).toBeInTheDocument();
    });
  });
});

describe('AnalysisTab - back navigation', () => {
  it('back button triggers history navigation', async () => {
    const pushStateSpy = vi.spyOn(window.history, 'pushState').mockImplementation(() => {});
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent').mockImplementation(() => {});

    await renderAnalysisTab();
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

// ─── LLM connected: provider badge + logout button ───────────────────────────

describe('AnalysisTab - LLM connected states', () => {
  it('shows logged-in provider info and logout button when auth is active', async () => {
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: true, provider: 'openai', model: 'gpt-4o', auth_mode: 'api_key_session' } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: true, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [] } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /로그아웃/ })).toBeInTheDocument();
    });
  });

  it('logout button calls logout API and reloads', async () => {
    const reloadMock = vi.fn();
    Object.defineProperty(window, 'location', { configurable: true, value: { ...window.location, reload: reloadMock } });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: true, provider: 'openai', model: 'gpt-4o', auth_mode: 'api_key_session' } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: true, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [] } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByRole('button', { name: /로그아웃/ })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /로그아웃/ }));
    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(expect.stringContaining('/api/auth/logout'), {}, { withCredentials: true });
    });
  });

  it('shows auth_mode cli label in status panel', async () => {
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: true, provider: 'anthropic', model: 'claude-3', auth_mode: 'cli' } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [] } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/Docker 내부 SDK/)).toBeInTheDocument();
    });
  });

  it('shows oauth label for oauth auth_mode', async () => {
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: true, provider: 'openai', model: 'gpt-4', auth_mode: 'oauth' } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [] } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/OAuth 인증/)).toBeInTheDocument();
    });
  });
});

// ─── AI analysis flow (LLM available, no mirofish) ───────────────────────────

describe('AnalysisTab - AI analysis flow', () => {
  const mockSources = [{ type: 'youtube', id: 'ch1', name: 'Channel 1', files: 2 }];

  function buildLlmGetMock(sources = mockSources) {
    return vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: true, provider: 'openai', model: 'gpt-4o', auth_mode: 'api_key_session' } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      return Promise.resolve({ data: {} });
    });
  }

  beforeEach(() => {
    axios.get = buildLlmGetMock();
  });

  it('calls ai-summary API when LLM available and mirofish offline', async () => {
    axios.post = vi.fn().mockReturnValue(new Promise(() => {})); // never resolves - holds loading state

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());

    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => expect(screen.getByText('분석 중…')).toBeInTheDocument());

    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/ai-summary'),
      expect.objectContaining({ sources: [{ type: 'youtube', id: 'ch1' }] })
    );
  });

  it('shows AI result panel after ai-summary succeeds', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: {
        success: true,
        provider: 'openai',
        model: 'gpt-4o',
        summary: '분석 요약 텍스트입니다.',
        topics: [],
        key_opinions: [],
        insights: [],
      },
    });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(screen.getByText('AI 분석 결과')).toBeInTheDocument();
    });
    expect(screen.getByText('분석 요약 텍스트입니다.')).toBeInTheDocument();
  });

  it('shows error when ai-summary API fails', async () => {
    axios.post = vi.fn().mockRejectedValue({ message: 'AI error', response: { data: { error: 'quota exceeded' } } });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(screen.getByText(/오류:/)).toBeInTheDocument();
      expect(screen.getByText(/quota exceeded/)).toBeInTheDocument();
    });
  });

  it('shows chat interface after ai-summary completes', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: { success: true, provider: 'openai', model: 'gpt-4o', summary: 'AI summary', topics: [], key_opinions: [], insights: [] },
    });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(screen.getByText('AI 대화')).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/분석 결과에 대해 질문하세요/)).toBeInTheDocument();
    });
  });

  it('sendAiChat posts to ai-chat endpoint and shows response', async () => {
    axios.post = vi.fn()
      .mockResolvedValueOnce({
        data: { success: true, provider: 'openai', model: 'gpt-4o', summary: 'AI summary', topics: [], key_opinions: [], insights: [] },
      })
      .mockResolvedValueOnce({
        data: { success: true, response: '안녕하세요 AI 응답입니다.' },
      });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => expect(screen.getByText('AI 대화')).toBeInTheDocument());

    const chatInput = screen.getByPlaceholderText(/분석 결과에 대해 질문하세요/);
    fireEvent.change(chatInput, { target: { value: '요약해줘' } });
    fireEvent.click(screen.getByRole('button', { name: /전송/ }));

    await waitFor(() => {
      expect(screen.getByText('안녕하세요 AI 응답입니다.')).toBeInTheDocument();
    });
    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/ai-chat'),
      expect.objectContaining({ message: '요약해줘' })
    );
  });

  it('sendAiChat shows error message on API failure', async () => {
    axios.post = vi.fn()
      .mockResolvedValueOnce({
        data: { success: true, provider: 'openai', model: 'gpt-4o', summary: 'summary', topics: [], key_opinions: [], insights: [] },
      })
      .mockRejectedValueOnce({ message: 'chat failed', response: { data: { error: 'chat error' } } });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => expect(screen.getByText('AI 대화')).toBeInTheDocument());

    const chatInput = screen.getByPlaceholderText(/분석 결과에 대해 질문하세요/);
    fireEvent.change(chatInput, { target: { value: '질문' } });
    fireEvent.click(screen.getByRole('button', { name: /전송/ }));

    await waitFor(() => {
      expect(screen.getByText(/Error: chat error/)).toBeInTheDocument();
    });
  });

  it('sendAiChat on Enter key fires chat request', async () => {
    axios.post = vi.fn()
      .mockResolvedValueOnce({
        data: { success: true, provider: 'openai', model: 'gpt-4o', summary: 'summary', topics: [], key_opinions: [], insights: [] },
      })
      .mockResolvedValueOnce({ data: { success: true, response: 'Enter key response' } });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => expect(screen.getByText('AI 대화')).toBeInTheDocument());

    const chatInput = screen.getByPlaceholderText(/분석 결과에 대해 질문하세요/);
    fireEvent.change(chatInput, { target: { value: 'enter질문' } });
    fireEvent.keyDown(chatInput, { key: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText('Enter key response')).toBeInTheDocument();
    });
  });

  it('does not send chat when input is empty', async () => {
    axios.post = vi.fn().mockResolvedValue({
      data: { success: true, provider: 'openai', model: 'gpt-4o', summary: 'summary', topics: [], key_opinions: [], insights: [] },
    });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => expect(screen.getByText('AI 대화')).toBeInTheDocument());

    // Send button should be disabled when input is empty
    const sendBtn = screen.getByRole('button', { name: /전송/ });
    expect(sendBtn).toBeDisabled();
  });
});

// ─── Mirofish (SNS AI) full analysis flow ────────────────────────────────────

describe('AnalysisTab - mirofish analysis flow', () => {
  const mockSources = [{ type: 'youtube', id: 'ch1', name: 'Channel 1', files: 2 }];

  function buildMirofishGetMock() {
    return vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: true } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: mockSources } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      return Promise.resolve({ data: {} });
    });
  }

  beforeEach(() => {
    axios.get = buildMirofishGetMock();
  });

  it('calls transform then graph/build when mirofish available', async () => {
    const transformData = { project_id: 'proj-1', project_name: 'Test', simulation_id: 'sim-1' };
    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: { success: true, data: transformData } })
      .mockResolvedValueOnce({ data: { success: true, data: { task_id: 'task-123' } } });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/analysis/transform'),
        expect.objectContaining({ sources: [{ type: 'youtube', id: 'ch1' }] })
      );
    });
    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/analysis/graph/build'),
        expect.objectContaining({ project_id: 'proj-1' })
      );
    });
  });

  it('shows error when transform fails', async () => {
    axios.post = vi.fn().mockResolvedValue({ data: { success: false, error: 'Transform error msg' } });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(screen.getByText(/Transform error msg/)).toBeInTheDocument();
    });
  });

  it('shows error when graph/build fails', async () => {
    const transformData = { project_id: 'proj-1', project_name: 'Test', simulation_id: 'sim-1' };
    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: { success: true, data: transformData } })
      .mockResolvedValueOnce({ data: { success: false, error: 'Graph build error' } });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(screen.getByText(/Graph build error/)).toBeInTheDocument();
    });
  });

  it('shows "분석 완료" panel and chat when task polling completes', async () => {
    const transformData = { project_id: 'proj-1', project_name: 'My Analysis Project', simulation_id: 'sim-1' };
    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: { success: true, data: transformData } })
      .mockResolvedValueOnce({ data: { success: true, data: { task_id: 'task-abc' } } });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: true } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: mockSources } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      if (url.includes('/api/analysis/graph/task/')) {
        return Promise.resolve({ data: { data: { status: 'completed', progress: 100 } } });
      }
      return Promise.resolve({ data: {} });
    });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(screen.getByText('분석 완료')).toBeInTheDocument();
    }, { timeout: 5000 });
    expect(screen.getByText(/My Analysis Project/)).toBeInTheDocument();
  });

  it('shows error when task polling returns failed status', async () => {
    const transformData = { project_id: 'proj-1', project_name: 'Test', simulation_id: 'sim-1' };
    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: { success: true, data: transformData } })
      .mockResolvedValueOnce({ data: { success: true, data: { task_id: 'task-fail' } } });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: true } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: mockSources } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      if (url.includes('/api/analysis/graph/task/')) {
        return Promise.resolve({ data: { data: { status: 'failed', message: 'Task failed reason' } } });
      }
      return Promise.resolve({ data: {} });
    });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(screen.getByText(/Task failed reason/)).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('chat via sendChatMessage for mirofish project', async () => {
    const transformData = { project_id: 'proj-1', project_name: 'My Project', simulation_id: 'sim-1' };
    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: { success: true, data: transformData } })
      .mockResolvedValueOnce({ data: { success: true, data: { task_id: 'task-chat' } } })
      .mockResolvedValueOnce({ data: { success: true, data: { response: 'Mirofish chat reply' } } });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: true } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: mockSources } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      if (url.includes('/api/analysis/graph/task/')) {
        return Promise.resolve({ data: { data: { status: 'completed', progress: 100 } } });
      }
      return Promise.resolve({ data: {} });
    });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => expect(screen.getByText('분석 완료')).toBeInTheDocument(), { timeout: 5000 });
    await waitFor(() => expect(screen.getByText('AI 대화')).toBeInTheDocument());

    const chatInput = screen.getByPlaceholderText(/분석 결과에 대해 질문하세요/);
    fireEvent.change(chatInput, { target: { value: '분석 질문' } });
    fireEvent.click(screen.getByRole('button', { name: /전송/ }));

    await waitFor(() => {
      expect(screen.getByText('Mirofish chat reply')).toBeInTheDocument();
    });
    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/report/chat'),
      expect.objectContaining({ message: '분석 질문', simulation_id: 'sim-1' })
    );
  });
});

// ─── Progress bar ─────────────────────────────────────────────────────────────

describe('AnalysisTab - progress bar', () => {
  const mockSources = [{ type: 'youtube', id: 'ch1', name: 'Channel 1', files: 2 }];

  it('shows progress panel during transforming state', async () => {
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: mockSources } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockReturnValue(new Promise(() => {}));

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(screen.getByText(/SNS 데이터를 문서로 변환 중/)).toBeInTheDocument();
    });
  });
});

// ─── URL analysis data flow ───────────────────────────────────────────────────

describe('AnalysisTab - URL analysis data', () => {
  it('shows URL analysis context banner when urlAnalysisData loaded from sessionStorage', async () => {
    const store = {
      urlAnalysisResult: JSON.stringify({ platform: 'youtube', title: 'Test Video' }),
    };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((k) => store[k] ?? null);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((k) => { delete store[k]; });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((k, v) => { store[k] = v; });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/URL 분석 결과 → AI 심화 분석/)).toBeInTheDocument();
    });
    expect(screen.getByText(/YOUTUBE : Test Video/)).toBeInTheDocument();
  });

  it('URL analysis banner close button clears context', async () => {
    const store = {
      urlAnalysisResult: JSON.stringify({ platform: 'youtube', title: 'Test Video' }),
    };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((k) => store[k] ?? null);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((k) => { delete store[k]; });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((k, v) => { store[k] = v; });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/URL 분석 결과 → AI 심화 분석/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /닫기/ }));
    await waitFor(() => {
      expect(screen.queryByText(/URL 분석 결과 → AI 심화 분석/)).not.toBeInTheDocument();
    });
  });

  it('auto-triggers URL AI analysis when LLM is available', async () => {
    const store = {
      urlAnalysisResult: JSON.stringify({ platform: 'dcinside', title: 'DC Post', gallery_id: 'g1' }),
    };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((k) => store[k] ?? null);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((k) => { delete store[k]; });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((k, v) => { store[k] = v; });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: true, provider: 'openai', model: 'gpt-4o', auth_mode: 'api_key_session' } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({
      data: { success: true, provider: 'openai', model: 'gpt-4o', summary: 'URL AI summary', topics: [], key_opinions: [], insights: [] },
    });

    render(<AnalysisTab />);

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/analysis/ai-url-analyze'),
        expect.objectContaining({ result: expect.objectContaining({ platform: 'dcinside' }) })
      );
    });
  });

  it('sendUrlAiChat posts to ai-url-chat endpoint', async () => {
    const store = {
      urlAnalysisResult: JSON.stringify({ platform: 'youtube', title: 'Test Video' }),
    };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((k) => store[k] ?? null);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((k) => { delete store[k]; });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((k, v) => { store[k] = v; });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: true, provider: 'openai', model: 'gpt-4o', auth_mode: 'api_key_session' } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn()
      .mockResolvedValueOnce({
        data: { success: true, provider: 'openai', model: 'gpt-4o', summary: 'URL summary', topics: [], key_opinions: [], insights: [] },
      })
      .mockResolvedValueOnce({
        data: { success: true, response: 'URL chat reply' },
      });

    render(<AnalysisTab />);

    await waitFor(() => expect(screen.getByText('AI 대화')).toBeInTheDocument());

    const chatInput = screen.getByPlaceholderText(/분석 결과에 대해 질문하세요/);
    fireEvent.change(chatInput, { target: { value: 'URL 질문' } });
    fireEvent.click(screen.getByRole('button', { name: /전송/ }));

    await waitFor(() => {
      expect(screen.getByText('URL chat reply')).toBeInTheDocument();
    });
    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/ai-url-chat'),
      expect.objectContaining({ message: 'URL 질문' })
    );
  });

  it('sendUrlAiChat shows error message on failure', async () => {
    const store = {
      urlAnalysisResult: JSON.stringify({ platform: 'youtube', title: 'Test Video' }),
    };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((k) => store[k] ?? null);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((k) => { delete store[k]; });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((k, v) => { store[k] = v; });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: true, provider: 'openai', model: 'gpt-4o', auth_mode: 'api_key_session' } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn()
      .mockResolvedValueOnce({
        data: { success: true, provider: 'openai', model: 'gpt-4o', summary: 'URL summary', topics: [], key_opinions: [], insights: [] },
      })
      .mockRejectedValueOnce({ message: 'url chat fail', response: { data: { error: 'url chat error' } } });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText('AI 대화')).toBeInTheDocument());

    const chatInput = screen.getByPlaceholderText(/분석 결과에 대해 질문하세요/);
    fireEvent.change(chatInput, { target: { value: '에러 질문' } });
    fireEvent.click(screen.getByRole('button', { name: /전송/ }));

    await waitFor(() => {
      expect(screen.getByText(/Error: url chat error/)).toBeInTheDocument();
    });
  });
});

// ─── Preselect from sessionStorage ───────────────────────────────────────────

describe('AnalysisTab - analysisPreselect from sessionStorage', () => {
  it('preselects sources from sessionStorage analysisPreselect', async () => {
    const mockSources = [
      { type: 'youtube', id: 'ch1', name: 'Channel 1', files: 2 },
      { type: 'dcinside', id: 'dc1', name: 'DC Gallery', files: 1 },
    ];
    const preselect = [{ type: 'youtube', id: 'ch1' }];

    const store = { analysisPreselect: JSON.stringify(preselect) };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((k) => store[k] ?? null);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((k) => { delete store[k]; });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((k, v) => { store[k] = v; });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: mockSources } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);

    await waitFor(() => {
      // After preselect, 1 source selected → button shows "1개 소스 기본 분석"
      expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled();
    });
  });

  it('ignores invalid JSON in analysisPreselect', async () => {
    const store = { analysisPreselect: 'not valid json' };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((k) => store[k] ?? null);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((k) => { delete store[k]; });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((k, v) => { store[k] = v; });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [{ type: 'youtube', id: 'ch1', name: 'ValidChannel', files: 1 }] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/ValidChannel/)).toBeInTheDocument());
    // No sources preselected due to invalid JSON - button disabled
    expect(screen.getByRole('button', { name: /소스 선택 후 분석/ })).toBeDisabled();
  });
});

// ─── Existing projects table ──────────────────────────────────────────────────

describe('AnalysisTab - existing projects table', () => {
  it('renders projects table when mirofish available and projects exist', async () => {
    const projects = [
      {
        project_id: 'proj-1',
        name: 'Analysis Project A',
        status: 'graph_completed',
        ontology: { entity_types: ['person', 'org'], edge_types: ['knows'] },
        created_at: '2026-01-10T10:00:00Z',
      },
      {
        project_id: 'proj-2',
        name: 'Analysis Project B',
        status: 'graph_building',
        ontology: null,
        created_at: null,
      },
    ];

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: true } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [] } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: projects } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText('이전 분석')).toBeInTheDocument();
      expect(screen.getByText('Analysis Project A')).toBeInTheDocument();
      expect(screen.getByText('Analysis Project B')).toBeInTheDocument();
      expect(screen.getByText('graph_completed')).toBeInTheDocument();
      expect(screen.getByText('graph_building')).toBeInTheDocument();
    });
  });
});

// ─── Graph data view ─────────────────────────────────────────────────────────

describe('AnalysisTab - graph data view', () => {
  it('renders graph visualization when viewGraphData called', async () => {
    const mockSources = [{ type: 'youtube', id: 'ch1', name: 'Channel 1', files: 2 }];
    const transformData = {
      project_id: 'proj-1',
      project_name: 'Graph Project',
      simulation_id: 'sim-1',
      ontology: { entity_types: ['person'], edge_types: ['knows'] },
    };

    const graphData = {
      nodes: [
        { id: 'n1', name: 'Node One', type: 'person' },
        { id: 'n2', name: 'Node Two', type: 'org' },
      ],
      edges: [
        { source: 'n1', target: 'n2', source_name: 'Node One', target_name: 'Node Two', relation: 'knows' },
      ],
    };

    axios.post = vi.fn()
      .mockResolvedValueOnce({ data: { success: true, data: transformData } })
      .mockResolvedValueOnce({ data: { success: true, data: { task_id: 'task-graph' } } });

    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: true } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: mockSources } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      if (url.includes('/api/analysis/graph/task/')) {
        return Promise.resolve({
          data: { data: { status: 'completed', progress: 100, result: { graph_id: 'graph-1', node_count: 2, edge_count: 1 } } },
        });
      }
      if (url.includes('/api/analysis/graph/data/graph-1')) {
        return Promise.resolve({ data: { success: true, data: graphData } });
      }
      return Promise.resolve({ data: {} });
    });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => expect(screen.getByText('분석 완료')).toBeInTheDocument(), { timeout: 5000 });

    // Click "그래프 보기" button
    await waitFor(() => expect(screen.getByRole('button', { name: /그래프 보기/ })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /그래프 보기/ }));

    await waitFor(() => {
      expect(screen.getByText('지식 그래프')).toBeInTheDocument();
      expect(screen.getByText('Node One')).toBeInTheDocument();
      expect(screen.getByText('Node Two')).toBeInTheDocument();
    });
  });
});

// ─── Local analysis result panel ─────────────────────────────────────────────

describe('AnalysisTab - local analysis result panel', () => {
  const mockSources = [{ type: 'youtube', id: 'ch1', name: 'Channel 1', files: 2 }];

  beforeEach(() => {
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: mockSources } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      return Promise.resolve({ data: {} });
    });
  });

  it('renders LocalResultPanel after successful local-summary', async () => {
    const localResult = {
      total_items: 42,
      overall: {
        sentiment: { positive: 20, neutral: 15, negative: 7 },
        distribution: { positive: 0.476, neutral: 0.357, negative: 0.167 },
        top_keywords: [{ word: 'keyword1', count: 10 }, { word: 'keyword2', count: 5 }],
      },
      sources: [],
    };
    axios.post = vi.fn().mockResolvedValue({ data: localResult });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel 1/));
    await waitFor(() => expect(screen.getByRole('button', { name: /1개 소스/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /1개 소스/ }));

    await waitFor(() => {
      expect(screen.getByText(/로컬 분석 결과/)).toBeInTheDocument();
      expect(screen.getByText(/42건 분석/)).toBeInTheDocument();
    });
  });
});

// ─── Source button label variants ────────────────────────────────────────────

describe('AnalysisTab - source button labels', () => {
  it('renders DC prefix for dcinside sources', async () => {
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: false, provider: null, model: null } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [{ type: 'dcinside', id: 'dc1', name: 'DC Gallery', files: 3 }] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);
    await waitFor(() => {
      expect(screen.getByText(/DC DC Gallery/)).toBeInTheDocument();
    });
  });

  it('shows provider label in analysis hint when LLM connected', async () => {
    axios.get = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/analysis/status')) return Promise.resolve({ data: { mirofish_available: false } });
      if (url.includes('/api/analysis/llm/status')) return Promise.resolve({ data: { available: true, provider: 'anthropic', model: 'claude-3', auth_mode: 'api_key_session' } });
      if (url.includes('/api/auth/me')) return Promise.resolve({ data: { logged_in: false, auth_required: false } });
      if (url.includes('/api/analysis/sources')) return Promise.resolve({ data: { sources: [{ type: 'youtube', id: 'ch1', name: 'Channel', files: 1 }] } });
      if (url.includes('/api/analysis/projects')) return Promise.resolve({ data: { success: true, data: [] } });
      return Promise.resolve({ data: {} });
    });
    axios.post = vi.fn().mockResolvedValue({ data: {} });

    render(<AnalysisTab />);
    await waitFor(() => expect(screen.getByText(/Channel/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/Channel/));
    await waitFor(() => {
      expect(screen.getByText(/Claude로 AI 분석/)).toBeInTheDocument();
    });
  });
});
