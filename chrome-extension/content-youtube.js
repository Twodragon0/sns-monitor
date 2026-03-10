// YouTube 페이지에서 댓글 수집

const collectYouTubeComments = (keyword) => {
  const comments = [];

  // 댓글 선택자 (YouTube 구조에 따라 변경 가능)
  const commentElements = document.querySelectorAll('ytd-comment-thread-renderer');

  commentElements.forEach((element) => {
    try {
      // 댓글 텍스트
      const textElement = element.querySelector('#content-text');
      const text = textElement ? textElement.textContent.trim() : '';

      // 키워드 필터링
      if (keyword && !text.toLowerCase().includes(keyword.toLowerCase())) {
        return;
      }

      // 작성자
      const authorElement = element.querySelector('#author-text');
      const author = authorElement ? authorElement.textContent.trim() : 'Unknown';

      // 좋아요 수
      const likeElement = element.querySelector('#vote-count-middle');
      const likes = likeElement ? parseInt(likeElement.textContent.trim()) || 0 : 0;

      // 작성 시간
      const timeElement = element.querySelector('.published-time-text a');
      const publishedTime = timeElement ? timeElement.textContent.trim() : '';

      // 대댓글 수
      const replyCountElement = element.querySelector('#more-replies span');
      const replyCount = replyCountElement ? parseInt(replyCountElement.textContent.match(/\d+/)?.[0]) || 0 : 0;

      comments.push({
        text,
        author,
        likes,
        published_time: publishedTime,
        reply_count: replyCount,
        url: window.location.href
      });

    } catch (e) {
      console.error('Comment parsing error:', e);
    }
  });

  return comments;
};

const countYouTubeComments = () => {
  const commentElements = document.querySelectorAll('ytd-comment-thread-renderer');
  return commentElements.length;
};

// 메시지 리스너
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'collect') {
    const data = collectYouTubeComments(request.keyword);
    sendResponse({ data });
  } else if (request.action === 'count') {
    const count = countYouTubeComments();
    sendResponse({ count });
  }
  return true;
});

console.log('YouTube content script loaded');
