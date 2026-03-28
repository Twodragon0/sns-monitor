import React from 'react';
import { render, screen } from '@testing-library/react';
import { LocalResultPanel, AiResultPanel } from './ResultPanels';

beforeAll(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterAll(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('LocalResultPanel', () => {
  const baseResult = {
    total_items: 42,
    overall: {
      sentiment: { positive: 20, neutral: 15, negative: 7 },
      distribution: { positive: 0.48, neutral: 0.36, negative: 0.16 },
      top_keywords: [
        { word: 'keyword1', count: 10 },
        { word: 'keyword2', count: 7 },
        { word: 'keyword3', count: 5 },
      ],
    },
    sources: [],
  };

  it('renders without crashing', () => {
    const { container } = render(<LocalResultPanel localResult={baseResult} />);
    expect(container).toBeTruthy();
  });

  it('shows total_items count', () => {
    render(<LocalResultPanel localResult={baseResult} />);
    expect(screen.getByText(/42건 분석/i)).toBeInTheDocument();
  });

  it('shows sentiment distribution percentages', () => {
    render(<LocalResultPanel localResult={baseResult} />);
    expect(screen.getByText('48%')).toBeInTheDocument();
    expect(screen.getByText('36%')).toBeInTheDocument();
    expect(screen.getByText('16%')).toBeInTheDocument();
  });

  it('shows top keywords', () => {
    render(<LocalResultPanel localResult={baseResult} />);
    expect(screen.getByText(/keyword1/i)).toBeInTheDocument();
    expect(screen.getByText(/keyword2/i)).toBeInTheDocument();
  });

  it('renders without overall sentiment', () => {
    const result = { total_items: 0, sources: [] };
    const { container } = render(<LocalResultPanel localResult={result} />);
    expect(container).toBeTruthy();
  });

  it('renders per-source breakdown when multiple sources', () => {
    const result = {
      ...baseResult,
      sources: [
        {
          name: 'Source A',
          type: 'youtube',
          item_count: 20,
          sentiment: { sentiment: { positive: 15, neutral: 4, negative: 1 } },
        },
        {
          name: 'Source B',
          type: 'dcinside',
          item_count: 22,
          sentiment: { sentiment: { positive: 10, neutral: 8, negative: 4 } },
        },
      ],
    };
    render(<LocalResultPanel localResult={result} />);
    expect(screen.getByText(/Source A/i)).toBeInTheDocument();
    expect(screen.getByText(/Source B/i)).toBeInTheDocument();
  });
});

describe('AiResultPanel', () => {
  const baseAiResult = {
    provider: 'openai',
    model: 'gpt-4o',
    summary: 'This is the AI summary.',
    sentiment: {
      positive_pct: 60,
      neutral_pct: 30,
      negative_pct: 10,
      positive_keywords: ['great', 'amazing'],
      negative_keywords: ['bad'],
    },
    topics: [
      { topic: 'Topic A', count: 5, description: 'First topic' },
      { topic: 'Topic B', count: 3 },
    ],
  };

  it('renders without crashing', () => {
    const { container } = render(<AiResultPanel aiResult={baseAiResult} />);
    expect(container).toBeTruthy();
  });

  it('shows AI 분석 결과 heading', () => {
    render(<AiResultPanel aiResult={baseAiResult} />);
    expect(screen.getByText('AI 분석 결과')).toBeInTheDocument();
  });

  it('shows provider and model info', () => {
    render(<AiResultPanel aiResult={baseAiResult} />);
    // providerLabel('openai') => 'ChatGPT'
    expect(screen.getByText(/ChatGPT/i)).toBeInTheDocument();
    expect(screen.getByText(/gpt-4o/i)).toBeInTheDocument();
  });

  it('displays summary text', () => {
    render(<AiResultPanel aiResult={baseAiResult} />);
    expect(screen.getByText('This is the AI summary.')).toBeInTheDocument();
  });

  it('shows sentiment percentages', () => {
    render(<AiResultPanel aiResult={baseAiResult} />);
    expect(screen.getByText(/60%/)).toBeInTheDocument();
    expect(screen.getByText(/30%/)).toBeInTheDocument();
    expect(screen.getByText(/10%/)).toBeInTheDocument();
  });

  it('shows positive and negative keywords', () => {
    render(<AiResultPanel aiResult={baseAiResult} />);
    expect(screen.getByText(/great, amazing/i)).toBeInTheDocument();
    expect(screen.getByText(/bad/i)).toBeInTheDocument();
  });

  it('shows topics', () => {
    render(<AiResultPanel aiResult={baseAiResult} />);
    expect(screen.getByText(/Topic A/)).toBeInTheDocument();
    expect(screen.getByText('First topic')).toBeInTheDocument();
    expect(screen.getByText(/Topic B/)).toBeInTheDocument();
  });

  it('renders without sentiment or topics', () => {
    const aiResult = { provider: 'anthropic', model: 'claude-3', summary: 'Summary only.' };
    const { container } = render(<AiResultPanel aiResult={aiResult} />);
    expect(container).toBeTruthy();
    expect(screen.getByText('Summary only.')).toBeInTheDocument();
  });

  it('handles claude provider label', () => {
    const aiResult = { provider: 'anthropic', model: 'claude-3-sonnet', summary: '' };
    render(<AiResultPanel aiResult={aiResult} />);
    expect(screen.getByText(/Claude/i)).toBeInTheDocument();
  });
});
