// Twitter/X 페이지에서 트윗 수집

const collectTwitterTweets = (keyword) => {
  const tweets = [];

  // Twitter/X의 트윗 선택자 (플랫폼 구조에 따라 변경 가능)
  const tweetElements = document.querySelectorAll('article[data-testid="tweet"]');

  tweetElements.forEach((element) => {
    try {
      // 트윗 텍스트
      const textElement = element.querySelector('[data-testid="tweetText"]');
      const text = textElement ? textElement.textContent.trim() : '';

      // 키워드 필터링
      if (keyword && !text.toLowerCase().includes(keyword.toLowerCase())) {
        return;
      }

      // 작성자
      const authorElement = element.querySelector('[data-testid="User-Name"]');
      const author = authorElement ? authorElement.textContent.trim() : 'Unknown';

      // 작성자 username
      const usernameElement = element.querySelector('a[role="link"][href^="/"]');
      const username = usernameElement ? usernameElement.getAttribute('href').substring(1).split('/')[0] : '';

      // 작성 시간
      const timeElement = element.querySelector('time');
      const timestamp = timeElement ? timeElement.getAttribute('datetime') : '';

      // 좋아요, 리트윗, 답글 수
      let likes = 0;
      let retweets = 0;
      let replies = 0;

      // 상호작용 버튼들
      const buttons = element.querySelectorAll('button[data-testid]');
      buttons.forEach(button => {
        const testId = button.getAttribute('data-testid');
        const countText = button.textContent.trim();
        const count = parseInt(countText.replace(/[^0-9]/g, '')) || 0;

        if (testId && testId.includes('like')) {
          likes = count;
        } else if (testId && testId.includes('retweet')) {
          retweets = count;
        } else if (testId && testId.includes('reply')) {
          replies = count;
        }
      });

      // 트윗 URL
      const tweetLinkElement = element.querySelector('a[href*="/status/"]');
      const tweetUrl = tweetLinkElement ? 'https://twitter.com' + tweetLinkElement.getAttribute('href') : '';

      // 미디어 (이미지, 비디오) 체크
      const mediaElements = element.querySelectorAll('img[src*="media"], video');
      const hasMedia = mediaElements.length > 0;

      tweets.push({
        text,
        author,
        username,
        timestamp,
        likes,
        retweets,
        replies,
        url: tweetUrl,
        has_media: hasMedia,
        collected_from: window.location.href
      });

    } catch (e) {
      console.error('Tweet parsing error:', e);
    }
  });

  return tweets;
};

const countTwitterTweets = () => {
  const tweetElements = document.querySelectorAll('article[data-testid="tweet"]');
  return tweetElements.length;
};

// 메시지 리스너
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'collect') {
    const data = collectTwitterTweets(request.keyword);
    sendResponse({ data });
  } else if (request.action === 'count') {
    const count = countTwitterTweets();
    sendResponse({ count });
  }
  return true;
});

console.log('Twitter content script loaded');
