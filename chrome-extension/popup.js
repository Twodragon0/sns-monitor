// Popup 로직

let currentPlatform = 'unknown';
let itemsCount = 0;

// API 엔드포인트 (설정에서 가져오기)
const getApiEndpoint = () => {
  return new Promise((resolve) => {
    chrome.storage.sync.get(['apiEndpoint'], (result) => {
      resolve(result.apiEndpoint || 'https://your-api-gateway-url.amazonaws.com/dev');
    });
  });
};

// 통계 로드
const loadStats = () => {
  chrome.storage.local.get(['totalCollected', 'todayCollected', 'lastCollectedDate'], (result) => {
    const today = new Date().toDateString();
    let todayCount = result.todayCollected || 0;

    // 날짜가 바뀌면 초기화
    if (result.lastCollectedDate !== today) {
      todayCount = 0;
      chrome.storage.local.set({ todayCollected: 0, lastCollectedDate: today });
    }

    document.getElementById('total-collected').textContent = result.totalCollected || 0;
    document.getElementById('today-collected').textContent = todayCount;
  });
};

// 현재 탭 정보 가져오기
const getCurrentTab = async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
};

// 플랫폼 감지
const detectPlatform = (url) => {
  if (url.includes('youtube.com')) return 'youtube';
  if (url.includes('twitter.com') || url.includes('x.com')) return 'twitter';
  if (url.includes('instagram.com')) return 'instagram';
  if (url.includes('t.me')) return 'telegram';
  return 'unknown';
};

// 상태 메시지 표시
const showStatus = (message, type = 'info') => {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = message;
  statusDiv.className = `status ${type}`;
  statusDiv.style.display = 'block';

  if (type !== 'error') {
    setTimeout(() => {
      statusDiv.style.display = 'none';
    }, 3000);
  }
};

// 데이터 수집
const collectData = async () => {
  const collectBtn = document.getElementById('collect-btn');
  const keyword = document.getElementById('keyword-input').value.trim();

  if (!keyword) {
    showStatus('키워드를 입력해주세요', 'error');
    return;
  }

  collectBtn.disabled = true;
  collectBtn.innerHTML = '<span class="loading"></span> 수집 중...';

  try {
    const tab = await getCurrentTab();
    const platform = detectPlatform(tab.url);

    if (platform === 'unknown') {
      throw new Error('지원하지 않는 플랫폼입니다');
    }

    // Content script로 데이터 수집 요청
    const response = await chrome.tabs.sendMessage(tab.id, {
      action: 'collect',
      keyword: keyword,
      platform: platform
    });

    if (response.error) {
      throw new Error(response.error);
    }

    // API로 전송
    const apiEndpoint = await getApiEndpoint();
    const apiResponse = await fetch(`${apiEndpoint}/api/collect`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': await getApiKey()
      },
      body: JSON.stringify({
        platform: platform,
        keyword: keyword,
        data: response.data,
        url: tab.url,
        collected_at: new Date().toISOString()
      })
    });

    if (!apiResponse.ok) {
      throw new Error('API 전송 실패');
    }

    const result = await apiResponse.json();

    // 통계 업데이트
    chrome.storage.local.get(['totalCollected', 'todayCollected'], (stats) => {
      const newTotal = (stats.totalCollected || 0) + response.data.length;
      const newToday = (stats.todayCollected || 0) + response.data.length;
      const today = new Date().toDateString();

      chrome.storage.local.set({
        totalCollected: newTotal,
        todayCollected: newToday,
        lastCollectedDate: today
      });

      document.getElementById('total-collected').textContent = newTotal;
      document.getElementById('today-collected').textContent = newToday;
    });

    showStatus(`${response.data.length}개 항목 수집 완료!`, 'success');

  } catch (error) {
    console.error('Collection error:', error);
    showStatus(error.message, 'error');
  } finally {
    collectBtn.disabled = false;
    collectBtn.textContent = '데이터 수집 시작';
  }
};

// API Key 가져오기
const getApiKey = () => {
  return new Promise((resolve) => {
    chrome.storage.sync.get(['apiKey'], (result) => {
      resolve(result.apiKey || '');
    });
  });
};

// 설정 페이지로 이동
const openSettings = () => {
  chrome.runtime.openOptionsPage();
};

// 페이지 정보 업데이트
const updatePageInfo = async () => {
  try {
    const tab = await getCurrentTab();
    currentPlatform = detectPlatform(tab.url);

    const platformNames = {
      youtube: 'YouTube',
      twitter: 'Twitter/X',
      instagram: 'Instagram',
      telegram: 'Telegram',
      unknown: '알 수 없음'
    };

    document.getElementById('platform').textContent = platformNames[currentPlatform] || '알 수 없음';

    // Content script에 현재 항목 수 요청
    if (currentPlatform !== 'unknown') {
      try {
        const response = await chrome.tabs.sendMessage(tab.id, { action: 'count' });
        itemsCount = response.count || 0;
        document.getElementById('items-count').textContent = itemsCount;
      } catch (e) {
        document.getElementById('items-count').textContent = '?';
      }
    } else {
      document.getElementById('items-count').textContent = '0';
      document.getElementById('collect-btn').disabled = true;
      showStatus('지원하지 않는 플랫폼입니다', 'error');
    }

  } catch (error) {
    console.error('Page info update error:', error);
  }
};

// 저장된 키워드 로드
const loadSavedKeyword = () => {
  chrome.storage.sync.get(['lastKeyword'], (result) => {
    if (result.lastKeyword) {
      document.getElementById('keyword-input').value = result.lastKeyword;
    }
  });
};

// 키워드 저장
const saveKeyword = (keyword) => {
  chrome.storage.sync.set({ lastKeyword: keyword });
};

// 이벤트 리스너
document.getElementById('collect-btn').addEventListener('click', () => {
  const keyword = document.getElementById('keyword-input').value.trim();
  if (keyword) {
    saveKeyword(keyword);
  }
  collectData();
});

document.getElementById('settings-btn').addEventListener('click', openSettings);

document.getElementById('keyword-input').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    document.getElementById('collect-btn').click();
  }
});

// 초기화
loadStats();
updatePageInfo();
loadSavedKeyword();
