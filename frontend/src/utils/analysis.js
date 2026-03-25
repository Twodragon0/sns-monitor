/**
 * Shared analysis utilities used by both URLAnalyzer and Dashboard.
 */

export const NAVER_FETCH_STATUS_LABELS = {
  ok: '정상',
  partial: '부분 수집',
  blocked: '수집 제한',
};

export const NAVER_FETCH_REASON_LABELS = {
  html_fetch_failed: 'HTML 수집 실패',
  api_fetch_failed: 'API 수집 실패',
  mobile_fetch_failed: '모바일 수집 실패',
  no_posts_detected: '게시글 미감지',
  posts_found_but_comments_unavailable: '게시글만 수집, 댓글 미수집',
  content_and_comments_unavailable: '본문/댓글 모두 미수집',
  content_found_but_comments_unavailable: '본문 수집, 댓글 미수집',
  cookie_not_set: '로그인 쿠키 미설정',
  proxy_not_set: '프록시 미설정',
  no_search_results: '검색 결과 없음',
};

const DEFAULT_CACHE_MAX = 5;

export function loadResultsCache(cacheKey) {
  try {
    const raw = localStorage.getItem(cacheKey);
    if (!raw) return { urls: [], data: {} };
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed?.urls) && parsed.data && typeof parsed.data === 'object'
      ? parsed
      : { urls: [], data: {} };
  } catch {
    return { urls: [], data: {} };
  }
}

export function saveResultsCache(cacheKey, url, result, maxItems = DEFAULT_CACHE_MAX) {
  const prev = loadResultsCache(cacheKey);
  const urls = [url, ...prev.urls.filter(u => u !== url)].slice(0, maxItems);
  const data = { ...prev.data, [url]: result };
  const trimmed = {};
  urls.forEach(u => { if (data[u]) trimmed[u] = data[u]; });
  localStorage.setItem(cacheKey, JSON.stringify({ urls, data: trimmed }));
}

export function trimResultForSummarize(result) {
  if (!result) return null;
  const statKeys = ['view_count', 'like_count', 'comment_count', 'subscriber_count', 'follower_count', 'tweet_count', 'total_posts', 'score'];
  const stats = {};
  statKeys.forEach(k => { if (result[k] != null) stats[k] = result[k]; });
  const base = {
    platform: result.platform,
    title: result.title,
    gallery_id: result.gallery_id,
    gallery_name: result.gallery_name,
    subreddit: result.subreddit,
    username: result.username,
    analyzed_at: result.analyzed_at,
    source_url: result.source_url,
    description: result.description ? String(result.description).slice(0, 2000) : undefined,
    fetch_status: result.fetch_status,
    fetch_reason: result.fetch_reason,
    content: result.content ? String(result.content).slice(0, 3000) : undefined,
    analysis: result.analysis ? {
      overall: result.analysis.overall,
      sentiment: result.analysis.sentiment,
      top_keywords: (result.analysis.top_keywords || []).slice(0, 10),
    } : undefined,
    ...stats,
  };
  const items = result.comments || result.replies || result.posts || result.recent_videos;
  if (Array.isArray(items) && items.length > 0) {
    const key = result.comments ? 'comments' : (result.replies ? 'replies' : (result.posts ? 'posts' : 'recent_videos'));
    base[key] = items.slice(0, 50).map(item => ({
      text: (item.text || item.title || item.selftext || '').slice(0, 200),
      author: item.author,
      date: item.date || item.published_at,
    }));
  }
  return base;
}

export function detectPlatform(url) {
  if (!url) return null;
  const l = url.toLowerCase();
  if (l.includes('youtube.com') || l.includes('youtu.be')) return 'youtube';
  if (l.includes('dcinside.com')) return 'dcinside';
  if (l.includes('cafe.naver.com')) return 'naver_cafe';
  if (l.includes('reddit.com')) return 'reddit';
  if (l.includes('t.me/')) return 'telegram';
  if (l.includes('kakao.com')) return 'kakao';
  if (l.includes('x.com') || l.includes('twitter.com')) return 'twitter';
  if (l.includes('instagram.com')) return 'instagram';
  if (l.includes('facebook.com') || l.includes('fb.com')) return 'facebook';
  if (l.includes('threads.net') || l.includes('threads.com')) return 'threads';
  if (l.includes('tiktok.com')) return 'tiktok';
  return null;
}

export function formatNaverFetchReason(reason) {
  if (!reason) return '';
  return reason
    .split(',')
    .map(token => token.trim())
    .filter(Boolean)
    .map(token => NAVER_FETCH_REASON_LABELS[token] || token)
    .join(', ');
}

export function parseNaverReasonTokens(reason) {
  if (!reason) return [];
  return reason
    .split(',')
    .map(token => token.trim())
    .filter(Boolean);
}

export function getNaverDiagnosticActions(tokens) {
  const actions = [];
  if (tokens.includes('cookie_not_set')) {
    actions.push('.env에 NAVER_CAFE_COOKIE를 추가하고 docker-compose up -d --build로 재시작하세요.');
  }
  if (tokens.includes('proxy_not_set')) {
    actions.push('사내망 환경이면 NAVER_CAFE_PROXY_URL을 설정하고 필요 시 사용자/비밀번호를 함께 지정하세요.');
  }
  if (tokens.includes('posts_found_but_comments_unavailable') || tokens.includes('content_found_but_comments_unavailable')) {
    actions.push('공개 글/댓글 허용 게시글 URL로 재시도하고 단건 URL(ArticleRead) 기준으로 확인하세요.');
  }
  if (tokens.includes('html_fetch_failed') || tokens.includes('api_fetch_failed') || tokens.includes('mobile_fetch_failed')) {
    actions.push('네트워크/차단 상태를 점검하고, 프록시 사용 시 인증 정보를 확인하세요.');
  }
  if (actions.length === 0) {
    actions.push('URL 접근 권한과 네트워크 상태를 확인한 뒤 다시 시도하세요.');
  }
  return actions;
}
