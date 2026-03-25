import {
  detectPlatform,
  trimResultForSummarize,
  formatNaverFetchReason,
  parseNaverReasonTokens,
  getNaverDiagnosticActions,
  loadResultsCache,
  saveResultsCache,
  NAVER_FETCH_STATUS_LABELS,
  NAVER_FETCH_REASON_LABELS,
} from './analysis';

// ---------------------------------------------------------------------------
// detectPlatform
// ---------------------------------------------------------------------------
describe('detectPlatform', () => {
  it('returns null for empty input', () => {
    expect(detectPlatform('')).toBeNull();
    expect(detectPlatform(null)).toBeNull();
    expect(detectPlatform(undefined)).toBeNull();
  });

  it.each([
    ['https://www.youtube.com/watch?v=abc', 'youtube'],
    ['https://youtu.be/abc', 'youtube'],
    ['https://gall.dcinside.com/mini/board/lists?id=test', 'dcinside'],
    ['https://cafe.naver.com/test', 'naver_cafe'],
    ['https://www.reddit.com/r/test', 'reddit'],
    ['https://t.me/channel', 'telegram'],
    ['https://pf.kakao.com/test', 'kakao'],
    ['https://x.com/user', 'twitter'],
    ['https://twitter.com/user', 'twitter'],
    ['https://www.instagram.com/user', 'instagram'],
    ['https://www.facebook.com/page', 'facebook'],
    ['https://fb.com/page', 'facebook'],
    ['https://www.threads.net/@user', 'threads'],
    ['https://www.threads.com/@user', 'threads'],
    ['https://www.tiktok.com/@user', 'tiktok'],
  ])('detects %s as %s', (url, expected) => {
    expect(detectPlatform(url)).toBe(expected);
  });

  it('returns null for unknown URLs', () => {
    expect(detectPlatform('https://example.com')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// trimResultForSummarize
// ---------------------------------------------------------------------------
describe('trimResultForSummarize', () => {
  it('returns null for falsy input', () => {
    expect(trimResultForSummarize(null)).toBeNull();
    expect(trimResultForSummarize(undefined)).toBeNull();
  });

  it('preserves core fields', () => {
    const result = {
      platform: 'youtube',
      title: 'Test Video',
      view_count: 1000,
      like_count: 50,
      description: 'A test video',
      analyzed_at: '2026-03-25',
    };
    const trimmed = trimResultForSummarize(result);
    expect(trimmed.platform).toBe('youtube');
    expect(trimmed.title).toBe('Test Video');
    expect(trimmed.view_count).toBe(1000);
    expect(trimmed.description).toBe('A test video');
  });

  it('truncates long description', () => {
    const result = { description: 'x'.repeat(3000) };
    const trimmed = trimResultForSummarize(result);
    expect(trimmed.description.length).toBe(2000);
  });

  it('includes comments limited to 50', () => {
    const comments = Array.from({ length: 100 }, (_, i) => ({
      text: `comment ${i}`,
      author: `user${i}`,
    }));
    const trimmed = trimResultForSummarize({ comments });
    expect(trimmed.comments).toHaveLength(50);
  });

  it('truncates comment text to 200 chars', () => {
    const result = {
      comments: [{ text: 'a'.repeat(500), author: 'user' }],
    };
    const trimmed = trimResultForSummarize(result);
    expect(trimmed.comments[0].text.length).toBe(200);
  });

  it('handles replies key', () => {
    const result = { replies: [{ text: 'reply1' }] };
    const trimmed = trimResultForSummarize(result);
    expect(trimmed.replies).toHaveLength(1);
  });

  it('includes analysis summary', () => {
    const result = {
      analysis: {
        overall: 'positive',
        sentiment: { positive: 5, neutral: 2, negative: 1 },
        top_keywords: Array.from({ length: 20 }, (_, i) => ({ word: `kw${i}` })),
      },
    };
    const trimmed = trimResultForSummarize(result);
    expect(trimmed.analysis.overall).toBe('positive');
    expect(trimmed.analysis.top_keywords).toHaveLength(10);
  });
});

// ---------------------------------------------------------------------------
// formatNaverFetchReason
// ---------------------------------------------------------------------------
describe('formatNaverFetchReason', () => {
  it('returns empty string for falsy input', () => {
    expect(formatNaverFetchReason('')).toBe('');
    expect(formatNaverFetchReason(null)).toBe('');
  });

  it('translates known tokens', () => {
    expect(formatNaverFetchReason('cookie_not_set')).toBe('로그인 쿠키 미설정');
  });

  it('handles multiple comma-separated tokens', () => {
    const result = formatNaverFetchReason('cookie_not_set,proxy_not_set');
    expect(result).toContain('로그인 쿠키 미설정');
    expect(result).toContain('프록시 미설정');
  });

  it('passes through unknown tokens', () => {
    expect(formatNaverFetchReason('unknown_reason')).toBe('unknown_reason');
  });
});

// ---------------------------------------------------------------------------
// parseNaverReasonTokens
// ---------------------------------------------------------------------------
describe('parseNaverReasonTokens', () => {
  it('returns empty array for falsy input', () => {
    expect(parseNaverReasonTokens('')).toEqual([]);
    expect(parseNaverReasonTokens(null)).toEqual([]);
  });

  it('parses comma-separated tokens', () => {
    expect(parseNaverReasonTokens('a, b, c')).toEqual(['a', 'b', 'c']);
  });

  it('filters empty tokens', () => {
    expect(parseNaverReasonTokens('a,,b')).toEqual(['a', 'b']);
  });
});

// ---------------------------------------------------------------------------
// getNaverDiagnosticActions
// ---------------------------------------------------------------------------
describe('getNaverDiagnosticActions', () => {
  it('suggests cookie setup for cookie_not_set', () => {
    const actions = getNaverDiagnosticActions(['cookie_not_set']);
    expect(actions[0]).toContain('NAVER_CAFE_COOKIE');
  });

  it('suggests proxy for proxy_not_set', () => {
    const actions = getNaverDiagnosticActions(['proxy_not_set']);
    expect(actions[0]).toContain('NAVER_CAFE_PROXY_URL');
  });

  it('suggests network check for fetch failures', () => {
    const actions = getNaverDiagnosticActions(['html_fetch_failed']);
    expect(actions[0]).toContain('네트워크');
  });

  it('gives default action for unknown tokens', () => {
    const actions = getNaverDiagnosticActions(['something_else']);
    expect(actions).toHaveLength(1);
    expect(actions[0]).toContain('다시 시도');
  });
});

// ---------------------------------------------------------------------------
// loadResultsCache / saveResultsCache
// ---------------------------------------------------------------------------
describe('cache functions', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns empty cache when nothing stored', () => {
    const cache = loadResultsCache('test-key');
    expect(cache).toEqual({ urls: [], data: {} });
  });

  it('saves and loads results', () => {
    saveResultsCache('test-key', 'https://example.com', { title: 'Test' });
    const cache = loadResultsCache('test-key');
    expect(cache.urls).toContain('https://example.com');
    expect(cache.data['https://example.com'].title).toBe('Test');
  });

  it('limits cache to maxItems', () => {
    for (let i = 0; i < 10; i++) {
      saveResultsCache('test-key', `https://example.com/${i}`, { id: i }, 5);
    }
    const cache = loadResultsCache('test-key');
    expect(cache.urls).toHaveLength(5);
  });

  it('handles corrupted localStorage gracefully', () => {
    localStorage.setItem('broken-key', 'not-json');
    const cache = loadResultsCache('broken-key');
    expect(cache).toEqual({ urls: [], data: {} });
  });
});

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
describe('constants', () => {
  it('NAVER_FETCH_STATUS_LABELS has expected keys', () => {
    expect(NAVER_FETCH_STATUS_LABELS).toHaveProperty('ok');
    expect(NAVER_FETCH_STATUS_LABELS).toHaveProperty('partial');
    expect(NAVER_FETCH_STATUS_LABELS).toHaveProperty('blocked');
  });

  it('NAVER_FETCH_REASON_LABELS has expected keys', () => {
    expect(NAVER_FETCH_REASON_LABELS).toHaveProperty('cookie_not_set');
    expect(NAVER_FETCH_REASON_LABELS).toHaveProperty('proxy_not_set');
  });
});
