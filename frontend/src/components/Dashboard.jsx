import React, { useState, useEffect } from 'react';
import './Dashboard.css';

// 모니터링 키워드 정의 (크리에이터브랜드/예시기업/크리에이터 중심)
const MONITORING_KEYWORDS = [
  // ★★★ 최우선순위: 보안/해킹 관련 ★★★
  '해킹', '해킹당함', '해킹됨', 'hack', 'hacked', 'hacking',
  '보안', 'security', '유출', 'leak', 'leaked', '정보유출',
  '계정탈취', '계정해킹', '비밀번호', 'password', '피싱', 'phishing',
  '사기', 'scam', '개인정보', '침해', 'DDoS', '악성코드', 'malware',
  // ★★★ 최우선순위: 크리에이터브랜드 및 예시기업 ★★★
  '크리에이터브랜드', 'creatorbrand', 'CreatorBrand', 'CREATORBRAND',
  '예시기업', 'examplecorp', 'ExampleCorp', 'EXAMPLECORP',
  // ★★★ 최우선순위: 크리에이터 이름 ★★★
  '이브닛', 'IVNIT', 'ivnit',
  '아카이브', 'AkaiV', 'akaiv', '아카이브스튜디오',
  '스코시즘', 'SKOSHISM', 'skoshism',
  '쭈쭈', '여루미', 'yeorumi',
  '벌몽', '비몽', 'bee_mong',
  '옐루', 'yell_u',
  '한결', 'hangyeol',
  '오오즈', 'owo_zzzz',
  '이로', 'irocloud',
  '니노', 'NIN0SUNDAY',
  '코요', 'KoyoTempest',
  '오토', 'otorainy',
  '로보', 'RoboFroster',
  '바라바라', 'BARABARA',
  // ★★★ 최우선순위: 굿즈/상품 ★★★
  '굿즈', '포토카드', '포카', '아크릴', '키링', '스티커', '포스터', '엽서',
  '앨범', '음반', '한정판', '시즌그리팅', '캘린더', '머치', '공식굿즈',
  // ★★ 높은 우선순위: 판매/구매 ★★
  '구매', '판매', '주문', '예약', '결제', '배송', '품절', '재입고', '가격', '할인', '이벤트', '특전',
  // ★★ 높은 우선순위: 팬 활동 ★★
  '팬싸', '영통팬싸', '응모', '당첨', '럭드', '포토타임', '생일카페', '서포트', '조공',
  // ★★ 높은 우선순위: 디지털 상품 ★★
  '음원', '다운로드', '디지털싱글', '뮤직비디오', 'MV', '티저', '커버곡', '오리지널곡',
  '멤버십', '후원', '슈퍼챗', '보이스팩', '월페이퍼', '보팩', '펀딩',
  // 활동 관련
  '버튜버', 'vtuber', '크리에이터', '유튜버', '숲', 'soop',
  // 콘텐츠 관련
  '노래', '커버', '방송', '영상', '브이로그', 'vlog', 'ASMR', '라이브', '스트리밍',
  // 반응 관련
  '좋아요', '구독', '최고', '대박', '감동', '응원', '팬', '힐링',
  // 품질 관련
  '감성', '편집', '퀄리티', '목소리', '실력'
];

// 키워드 카테고리 (우선순위 순)
const KEYWORD_CATEGORIES = {
  // ★★★ 최우선순위: 보안 ★★★
  '🚨보안/해킹': ['해킹', '해킹당함', '해킹됨', 'hack', 'hacked', 'hacking', '보안', 'security', '유출', 'leak', 'leaked', '정보유출', '계정탈취', '계정해킹', '비밀번호', 'password', '피싱', 'phishing', '사기', 'scam', '개인정보', '침해', 'DDoS', '악성코드', 'malware'],
  '크리에이터브랜드/CreatorBrand': ['크리에이터브랜드', 'creatorbrand', 'CreatorBrand', 'CREATORBRAND'],
  '예시기업/ExampleCorp': ['예시기업', 'examplecorp', 'ExampleCorp', 'EXAMPLECORP'],
  '크리에이터': [
    '이브닛', 'IVNIT', 'ivnit',
    '아카이브', 'AkaiV', 'akaiv', '아카이브스튜디오',
    '스코시즘', 'SKOSHISM', 'skoshism',
    '쭈쭈', '여루미', 'yeorumi',
    '벌몽', '비몽', 'bee_mong',
    '옐루', 'yell_u',
    '한결', 'hangyeol',
    '오오즈', 'owo_zzzz',
    '이로', 'irocloud',
    '니노', 'NIN0SUNDAY',
    '코요', 'KoyoTempest',
    '오토', 'otorainy',
    '로보', 'RoboFroster',
    '바라바라', 'BARABARA'
  ],
  '굿즈/상품': ['굿즈', '포토카드', '포카', '아크릴', '키링', '스티커', '포스터', '엽서', '앨범', '음반', '한정판', '시즌그리팅', '캘린더', '머치', '공식굿즈'],
  '판매/구매': ['구매', '판매', '주문', '예약', '결제', '배송', '품절', '재입고', '가격', '할인', '이벤트', '특전'],
  '팬활동': ['팬싸', '영통팬싸', '응모', '당첨', '럭드', '포토타임', '생일카페', '서포트', '조공'],
  '디지털상품': ['음원', '다운로드', '디지털싱글', '뮤직비디오', 'MV', '티저', '커버곡', '오리지널곡', '멤버십', '후원', '슈퍼챗', '보이스팩', '월페이퍼', '보팩', '펀딩'],
  '활동': ['버튜버', 'vtuber', '크리에이터', '유튜버', '숲', 'soop'],
  '콘텐츠': ['노래', '커버', '방송', '영상', '브이로그', 'vlog', 'ASMR', '라이브', '스트리밍'],
  '반응': ['좋아요', '구독', '최고', '대박', '감동', '응원', '팬', '힐링'],
  '품질': ['감성', '편집', '퀄리티', '목소리', '실력']
};

// 댓글에서 매칭되는 키워드 찾기
const findMatchingKeywords = (text) => {
  if (!text) return [];
  const lowerText = text.toLowerCase();
  return MONITORING_KEYWORDS.filter(keyword => lowerText.includes(keyword.toLowerCase()));
};

// 키워드 카테고리 판별
const getKeywordCategory = (keyword) => {
  for (const [category, keywords] of Object.entries(KEYWORD_CATEGORIES)) {
    if (keywords.some(k => k.toLowerCase() === keyword.toLowerCase())) {
      return category;
    }
  }
  return '기타';
};

// KST 시간 변환 함수 (현재 사용되지 않음 - 필요시 주석 해제)
// eslint-disable-next-line no-unused-vars
const toKST = (dateString) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  // UTC 시간에 9시간 추가 (KST = UTC+9)
  const kstDate = new Date(date.getTime() + 9 * 60 * 60 * 1000);
  return kstDate.toLocaleString('ko-KR', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

// eslint-disable-next-line no-unused-vars
const toKSTDate = (dateString) => {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return '';

    // 간단한 형식으로 표시 (YYYY.MM.DD)
    return date.toLocaleDateString('ko-KR', {
      timeZone: 'Asia/Seoul',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).replace(/\. /g, '.').replace(/\.$/, '');
  } catch (e) {
    return '';
  }
};

// eslint-disable-next-line no-unused-vars
const toKSTDateShort = (dateString) => {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return '';

    // 짧은 형식으로 표시 (MM.DD)
    return date.toLocaleDateString('ko-KR', {
      timeZone: 'Asia/Seoul',
      month: '2-digit',
      day: '2-digit'
    }).replace(/\. /g, '.').replace(/\.$/, '');
  } catch (e) {
    return '';
  }
};

// 감정 분석 함수
const analyzeSentiment = (text) => {
  if (!text) return 'neutral';

  const lowerText = text.toLowerCase();

  const positiveKeywords = ['좋아', '굿', '최고', '감사', '사랑', '축하', '대박', '멋지', '예쁘', '귀엽',
                           '화이팅', '응원', '존경', '멋있', '훌륭', '완벽', '최고야', 'ㄱㅇㄷ', 'ㅊㅊ',
                           '개좋', '레전드', '갓', '천재', '실화', '미쳤', '개꿀', '개이득'];
  const negativeKeywords = ['싫어', '나쁘', '최악', '욕', '비난', '혐오', '짜증', '실망', '별로',
                           '쓰레기', '망했', '노잼', '재미없', '허접', '구리', '병신', '개같', '개별로',
                           '개망', '답없', '노답', 'ㅅㅂ', 'ㅂㅅ', '꺼져', '죽어'];

  const hasPositive = positiveKeywords.some(keyword => lowerText.includes(keyword));
  const hasNegative = negativeKeywords.some(keyword => lowerText.includes(keyword));

  if (hasPositive && !hasNegative) return 'positive';
  if (hasNegative && !hasPositive) return 'negative';
  return 'neutral';
};

function Dashboard() {
  const [scans, setScans] = useState([]);
  const [channels, setChannels] = useState([]);
  // eslint-disable-next-line no-unused-vars
  const [vuddyCreators, setVuddyCreators] = useState([]);
  const [allVuddyCreators, setAllVuddyCreators] = useState([]); // 원본 데이터 보관
  const [dcinsideGalleries, setDcinsideGalleries] = useState([]); // DC인사이드 갤러리 데이터
  const [loading, setLoading] = useState(true);
  const [selectedPlatform, setSelectedPlatform] = useState('all');
  // eslint-disable-next-line no-unused-vars
  const [expandedCreators, setExpandedCreators] = useState({});
  // eslint-disable-next-line no-unused-vars
  const [showArchiveStudioCreators, setShowArchiveStudioCreators] = useState(false);
  const [expandedGalleries, setExpandedGalleries] = useState({}); // DC인사이드 갤러리 확장 상태
  const [expandedPosts, setExpandedPosts] = useState({}); // 개별 게시글 댓글 확장 상태
  const [galleryPagination, setGalleryPagination] = useState({}); // 갤러리별 페이지네이션 정보
  const [loadingMorePosts, setLoadingMorePosts] = useState({}); // 갤러리별 추가 로딩 상태
  // eslint-disable-next-line no-unused-vars
  const [twitterData, setTwitterData] = useState({ tweets: [], replies: [], lastUpdated: null, loading: false }); // 트위터 키워드 모니터링 데이터
  const [twitterKeywordSearch, setTwitterKeywordSearch] = useState(''); // 트위터 키워드 검색 입력
  // eslint-disable-next-line no-unused-vars
  const [twitterAutoMonitoring, setTwitterAutoMonitoring] = useState(true); // 자동 모니터링 활성화
  // eslint-disable-next-line no-unused-vars
  const [twitterMonitoringResults, setTwitterMonitoringResults] = useState({}); // 키워드별 모니터링 결과

  // 트위터 자동 모니터링용 크리에이터 키워드
  const TWITTER_AUTO_MONITOR_KEYWORDS = [
    '크리에이터브랜드', '예시기업', '스코시즘', '아카이브', '바라바라', '이브닛',
    'u32', '여르미', '한결', '비몽', '샤르망', '나나문'
  ];

  useEffect(() => {
    loadDashboardData();
    // 30초마다 데이터 새로고침
    const interval = setInterval(loadDashboardData, 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 트위터 자동 키워드 모니터링
  useEffect(() => {
    if (twitterAutoMonitoring) {
      loadTwitterMonitoringData();
      // 60초마다 트위터 데이터 갱신
      const twitterInterval = setInterval(loadTwitterMonitoringData, 60000);
      return () => clearInterval(twitterInterval);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [twitterAutoMonitoring]);

  const loadDashboardData = async () => {
    try {
      // 최근 스캔 로드
      const scansResponse = await fetch('/api/scans');
      if (scansResponse.ok) {
        const scansData = await scansResponse.json();
        setScans(scansData.scans || []);
      }

      // 채널 데이터 로드
      const channelsResponse = await fetch('/api/channels');
      if (channelsResponse.ok) {
        const channelsData = await channelsResponse.json();
        setChannels(channelsData.channels || []);
      }

      // CreatorBrand 크리에이터 데이터 로드 (로컬 테스트 데이터 사용)
      try {
      const vuddyResponse = await fetch('/api/vuddy/creators');
      if (vuddyResponse.ok) {
        const vuddyData = await vuddyResponse.json();
          if (vuddyData.creators && vuddyData.creators.length > 0) {
            const creators = vuddyData.creators;
            setAllVuddyCreators(creators); // 원본 데이터 저장
            // 필터링 상태에 따라 표시할 데이터 결정
            if (showArchiveStudioCreators) {
              const filtered = creators.filter(c => {
                const name = (c.name || '').toLowerCase();
                return name.includes('u32') || name.includes('여르미') || name.includes('한결') || 
                       name.includes('비몽') || name.includes('샤르망') || name.includes('akaiv');
              });
              setVuddyCreators(filtered);
            } else {
              setVuddyCreators(creators);
            }
          } else {
            // API에서 데이터가 없으면 로컬 테스트 데이터 사용
            const testData = getLocalTestData();
            setAllVuddyCreators(testData);
            if (showArchiveStudioCreators) {
              const filtered = testData.filter(c => {
                const name = (c.name || '').toLowerCase();
                return name.includes('u32') || name.includes('여르미') || name.includes('한결') || 
                       name.includes('비몽') || name.includes('샤르망') || name.includes('akaiv');
              });
              setVuddyCreators(filtered);
            } else {
              setVuddyCreators(testData);
            }
          }
        } else {
          const testData = getLocalTestData();
          setAllVuddyCreators(testData);
          if (showArchiveStudioCreators) {
            const filtered = testData.filter(c => {
              const name = (c.name || '').toLowerCase();
              return name.includes('u32') || name.includes('여르미') || name.includes('한결') || 
                     name.includes('비몽') || name.includes('샤르망') || name.includes('akaiv');
            });
            setVuddyCreators(filtered);
          } else {
            setVuddyCreators(testData);
          }
        }
      } catch (error) {
        const testData = getLocalTestData();
        setAllVuddyCreators(testData);
        if (showArchiveStudioCreators) {
          const filtered = testData.filter(c => {
            const name = (c.name || '').toLowerCase();
            return name.includes('u32') || name.includes('여르미') || name.includes('한결') || 
                   name.includes('비몽') || name.includes('샤르망') || name.includes('akaiv');
          });
          setVuddyCreators(filtered);
        } else {
          setVuddyCreators(testData);
        }
      }

      // DC인사이드 갤러리 데이터 로드 (타임아웃 설정)
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10초 타임아웃
        
        const dcinsideResponse = await fetch('/api/dcinside/galleries', {
          signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        if (dcinsideResponse.ok) {
          const dcinsideData = await dcinsideResponse.json();
          if (dcinsideData.galleries && dcinsideData.galleries.length > 0) {
            setDcinsideGalleries(dcinsideData.galleries);

            // 각 갤러리별 페이지네이션 정보 초기화
            const paginationInfo = {};
            dcinsideData.galleries.forEach(gallery => {
              const loadedPosts = gallery.posts?.length || 0;
              const totalPosts = gallery.total_posts || loadedPosts;
              paginationInfo[gallery.gallery_id] = {
                page: 1,
                totalPosts: totalPosts,
                loadedPosts: loadedPosts,
                hasMore: loadedPosts < totalPosts
              };
            });
            setGalleryPagination(paginationInfo);
          } else {
            // 갤러리 데이터가 없으면 빈 배열로 설정
            setDcinsideGalleries([]);
          }
        } else {
          console.error('DC인사이드 갤러리 로드 실패:', dcinsideResponse.status);
          setDcinsideGalleries([]);
        }
      } catch (error) {
        if (error.name === 'AbortError') {
          console.error('DC인사이드 갤러리 로드 타임아웃');
        } else {
          console.error('DC인사이드 갤러리 로드 에러:', error);
        }
        setDcinsideGalleries([]);
      }
    } catch (error) {
      // Failed to load dashboard data
    } finally {
      setLoading(false);
    }
  };

  // 트위터 자동 모니터링 데이터 로드
  const loadTwitterMonitoringData = async () => {
    setTwitterData(prev => ({ ...prev, loading: true }));

    const results = {};
    const allTweets = [];
    const allReplies = [];

    // 여러 키워드를 한 번에 검색 (API 호출 최적화)
    try {
      const response = await fetch('/api/twitter/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keywords: TWITTER_AUTO_MONITOR_KEYWORDS,
          action: 'bulk_search'
        })
      });

      if (response.ok) {
        const data = await response.json();

        if (data.results) {
          Object.entries(data.results).forEach(([keyword, result]) => {
            results[keyword] = result;
            if (result.tweets) allTweets.push(...result.tweets);
            if (result.replies) allReplies.push(...result.replies);
          });
        }
      } else {
        // 개별 키워드 검색 폴백
        for (const keyword of TWITTER_AUTO_MONITOR_KEYWORDS.slice(0, 5)) {
          try {
            const res = await fetch('/api/twitter/search', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ keyword, action: 'search' })
            });
            if (res.ok) {
              const keywordData = await res.json();
              results[keyword] = keywordData;
              if (keywordData.tweets) allTweets.push(...keywordData.tweets);
              if (keywordData.replies) allReplies.push(...keywordData.replies);
            }
          } catch (e) {
            // Failed to search keyword
          }
        }
      }
    } catch (error) {
      // scans에서 트위터 데이터 추출
      scans.filter(s => s.platform === 'twitter').forEach(scan => {
        if (scan.tweets) allTweets.push(...scan.tweets);
        if (scan.replies) allReplies.push(...scan.replies);
        if (scan.tweet_list) allTweets.push(...scan.tweet_list);
        if (scan.comment_samples) allReplies.push(...scan.comment_samples);
      });
    }

    // 중복 제거
    const uniqueTweets = allTweets.filter((tweet, index, self) =>
      index === self.findIndex(t => t.tweet_id === tweet.tweet_id)
    );
    const uniqueReplies = allReplies.filter((reply, index, self) =>
      index === self.findIndex(r => r.reply_id === reply.reply_id || r.text === reply.text)
    );

    setTwitterMonitoringResults(results);
    setTwitterData({
      tweets: uniqueTweets,
      replies: uniqueReplies,
      keyword: '자동 모니터링',
      lastUpdated: new Date().toISOString(),
      loading: false
    });
  };

  // 트위터 키워드 검색 함수
  // eslint-disable-next-line no-unused-vars
  const searchTwitterKeyword = async (keyword) => {
    if (!keyword || keyword.trim() === '') return;

    setTwitterData(prev => ({ ...prev, loading: true }));

    try {
      // Twitter crawler API 호출
      const response = await fetch('/api/twitter/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: keyword.trim(), action: 'search' })
      });

      if (response.ok) {
        const data = await response.json();

        const tweets = data.tweets || [];
        const replies = data.replies || [];

        setTwitterData({
          tweets,
          replies,
          keyword: keyword.trim(),
          lastUpdated: new Date().toISOString(),
          loading: false
        });
      } else {
        // scans에서 트위터 데이터 추출
        extractTwitterFromScans();
      }
    } catch (error) {
      // 실패 시 scans에서 트위터 데이터 추출
      extractTwitterFromScans();
    }
  };

  // scans에서 트위터 데이터 추출
  const extractTwitterFromScans = () => {
    const twitterScans = scans.filter(s => s.platform === 'twitter');
    const allTweets = [];
    const allReplies = [];

    twitterScans.forEach(scan => {
      if (scan.tweets) allTweets.push(...scan.tweets);
      if (scan.replies) allReplies.push(...scan.replies);
      if (scan.tweet_list) allTweets.push(...scan.tweet_list);
      if (scan.comment_samples) allReplies.push(...scan.comment_samples);
    });

    setTwitterData({
      tweets: allTweets,
      replies: allReplies,
      keyword: twitterKeywordSearch || '크리에이터',
      lastUpdated: new Date().toISOString(),
      loading: false
    });
  };

  // DC인사이드 게시글 더 로드하기
  const loadMorePosts = async (galleryId) => {
    // 현재 로딩 중이면 무시
    if (loadingMorePosts[galleryId]) return;

    setLoadingMorePosts(prev => ({ ...prev, [galleryId]: true }));

    try {
      // 현재 페이지 정보 가져오기
      const currentPagination = galleryPagination[galleryId] || { page: 1, hasMore: true };
      const nextPage = currentPagination.page + 1;

      const response = await fetch(`/api/dcinside/gallery/${galleryId}/posts?page=${nextPage}&limit=20`);

      if (response.ok) {
        const data = await response.json();

        // 새 게시글이 있으면 추가
        if (data.posts && data.posts.length > 0) {
          setDcinsideGalleries(prev => prev.map(gallery => {
            if (gallery.gallery_id === galleryId) {
              // 중복 제거하며 게시글 추가
              const existingPostIds = new Set(gallery.posts.map(p => p.post_id));
              const newPosts = data.posts.filter(p => !existingPostIds.has(p.post_id));

              return {
                ...gallery,
                posts: [...gallery.posts, ...newPosts]
              };
            }
            return gallery;
          }));
        }

        // 페이지네이션 정보는 항상 업데이트 (빈 응답이어도 hasMore 상태 반영)
        if (data.pagination) {
          setGalleryPagination(prev => ({
            ...prev,
            [galleryId]: {
              page: data.pagination.page,
              totalPosts: data.pagination.total_posts,
              totalPages: data.pagination.total_pages,
              hasMore: data.pagination.has_more
            }
          }));
        }
      }
    } catch (error) {
      // 에러 발생 시 무시
    } finally {
      setLoadingMorePosts(prev => ({ ...prev, [galleryId]: false }));
    }
  };

  // 트위터 키워드 모니터링용 키워드 목록
  const TWITTER_MONITORING_KEYWORDS = [
    '아카이브', 'archive', '바라바라', 'barabara', '이브닛', 'ivnit', '스코시즘', 'skoshism',
    'u32', '사미', '우사미', '여르미', '엶', '한결', '결', '비몽', '몽', '샤르망', '쭈쭈', '나나문', '쿠우',
    '크리에이터브랜드', 'creatorbrand', '예시기업', 'examplecorp', 'ExampleCorp',
    '굿즈', '포토카드', '포카', '아크릴', '키링', '스티커', '포스터', '앨범', '음반', '한정판',
    '구매', '판매', '주문', '예약', '결제', '배송', '품절', '재입고', '가격', '할인', '이벤트', '특전',
    '팬싸', '영통팬싸', '응모', '당첨', '생일카페', '서포트', '조공',
    '음원', '다운로드', '디지털싱글', '뮤직비디오', 'MV', '티저', '커버곡', '오리지널곡',
    '멤버십', '후원', '슈퍼챗', '보이스팩', '월페이퍼', '보팩', '펀딩',
    '버튜버', 'vtuber', '방송', '노래', '커버', '스트리밍'
  ];

  // 트위터 텍스트에서 매칭 키워드 찾기
  // eslint-disable-next-line no-unused-vars
  const findTwitterMatchingKeywords = (text) => {
    if (!text) return [];
    const lowerText = text.toLowerCase();
    return TWITTER_MONITORING_KEYWORDS.filter(keyword => lowerText.includes(keyword.toLowerCase()));
  };

  // 로컬 테스트 데이터
  const getLocalTestData = () => {
    return [
      {
        name: "AkaiV Studio (@AkaivStudioOfficial)",
        channel_id: "UCxxxxArchiveStudio",
        youtube_channel: "@AkaivStudioOfficial",
        vuddy_channel: "https://vuddy.io/channels/akaivstudio/home",
        total_comments: 8,
        total_likes: 141,
        overall_score: 85,
        sentiment_distribution: { positive: 0.88, neutral: 0.12, negative: 0.0 },
        country_stats: {
          KR: { comment_count: 6, total_likes: 98 },
          US: { comment_count: 1, total_likes: 28 },
          JP: { comment_count: 1, total_likes: 15 }
        },
        comments: [
          { text: "AkaiV Studio 영상 너무 좋아요! 감성 최고", likes: 42, sentiment: "positive", country: "KR", video_title: "AkaiV Studio - 추억의 영상 모음" },
          { text: "이런 감성적인 영상 처음 봐요. 구독했습니다!", likes: 35, sentiment: "positive", country: "KR", video_title: "AkaiV Studio - 추억의 영상 모음" },
          { text: "Love the nostalgic vibes! Amazing content", likes: 28, sentiment: "positive", country: "US", video_title: "AkaiV Studio - Memory Lane" },
          { text: "편집 스타일이 정말 독특하네요", likes: 18, sentiment: "positive", country: "KR", video_title: "감성 영상 모음집" },
          { text: "とても素敵な動画です！", likes: 15, sentiment: "positive", country: "JP", video_title: "AkaiV Studio - Memory Lane" },
          { text: "매주 기다려지는 채널이에요", likes: 2, sentiment: "positive", country: "KR", video_title: "AkaiV Studio - 추억의 영상 모음" },
          { text: "잘 보고 갑니다", likes: 1, sentiment: "neutral", country: "KR", video_title: "감성 영상 모음집" },
          { text: "다음 영상도 기대됩니다!", likes: 0, sentiment: "positive", country: "KR", video_title: "감성 영상 모음집" }
        ],
        videos: [
          { title: "AkaiV Studio - 추억의 영상 모음", video_id: "archive_video_001", views: 125000, likes: 8500, comments: 342 },
          { title: "감성 영상 모음집", video_id: "archive_video_002", views: 89000, likes: 6200, comments: 198 },
          { title: "AkaiV Studio - Memory Lane", video_id: "archive_video_003", views: 67000, likes: 4800, comments: 156 }
        ],
        google_links: [
          { title: "AkaiV Studio Official YouTube Channel", url: "https://www.youtube.com/@AkaivStudioOfficial", snippet: "감성적인 영상으로 추억을 되살리는 AkaiV Studio 공식 유튜브 채널" },
          { title: "AkaiV Studio - 인기 영상 모음", url: "https://example.com/archive-studio-top", snippet: "AkaiV Studio의 가장 인기 있는 감성 영상들을 모아봤습니다" },
          { title: "AkaiV Studio 팬 커뮤니티", url: "https://example.com/archive-studio-community", snippet: "AkaiV Studio 팬들의 소통 공간. 최신 영상과 리뷰 공유" }
        ],
        analysis: {
          keywords: ["감성", "추억", "Archive", "영상", "편집", "nostalgic", "memory"],
          insights: [
            "감성적인 영상 스타일로 높은 시청자 만족도",
            "독특한 편집 스타일에 대한 긍정적 피드백",
            "추억과 향수를 테마로 한 콘텐츠 선호",
            "해외 시청자층도 꾸준히 증가 중"
          ],
          trends: [
            "레트로 감성과 추억 콘텐츠 인기 증가",
            "정기적인 업로드로 충성 구독자 확보",
            "영상 미학과 스토리텔링에 대한 관심 증가"
          ]
        }
      },
      {
        name: "바라바라 (BARABARA)",
        channel_id: "UCxxxxBARABARA",
        youtube_channel: "@barabara_official",
        vuddy_channel: "https://vuddy.io/channels/barabara/home",
        total_comments: 12,
        total_likes: 238,
        overall_score: 92,
        sentiment_distribution: { positive: 0.83, neutral: 0.17, negative: 0.0 },
        country_stats: {
          KR: { comment_count: 9, total_likes: 189 },
          US: { comment_count: 2, total_likes: 35 },
          JP: { comment_count: 1, total_likes: 14 }
        },
        comments: [
          { text: "바라바라님 영상 너무 재미있어요! 매일 기다려집니다 ㅎㅎ", likes: 45, sentiment: "positive", country: "KR", video_title: "바라바라의 일상 브이로그 #23" },
          { text: "편집 퀄리티가 정말 좋네요. 구독했습니다!", likes: 38, sentiment: "positive", country: "KR", video_title: "바라바라의 일상 브이로그 #23" },
          { text: "BARABARA's content is so unique and entertaining!", likes: 28, sentiment: "positive", country: "US", video_title: "Daily Vlog with BARABARA" },
          { text: "이런 컨텐츠 너무 좋아요. 앞으로도 계속 올려주세요~", likes: 32, sentiment: "positive", country: "KR", video_title: "바라바라의 일상 브이로그 #23" },
          { text: "색감이랑 분위기가 정말 좋아요", likes: 24, sentiment: "positive", country: "KR", video_title: "감성 카페 투어" }
        ],
        videos: [
          { title: "바라바라의 일상 브이로그 #23", video_id: "bara_video_001", views: 45200, likes: 2840, comments: 156 },
          { title: "감성 카페 투어", video_id: "bara_video_002", views: 38500, likes: 2150, comments: 98 },
          { title: "Daily Vlog with BARABARA", video_id: "bara_video_003", views: 29800, likes: 1680, comments: 72 },
          { title: "홈카페 만들기 🍰", video_id: "bara_video_004", views: 52100, likes: 3240, comments: 189 }
        ],
        google_links: [
          { title: "바라바라 (BARABARA) - 인기 브이로거", url: "https://example.com/barabara-profile", snippet: "감성적인 일상 브이로그로 유명한 크리에이터 바라바라의 공식 페이지" },
          { title: "BARABARA 최신 영상 모음", url: "https://example.com/barabara-videos", snippet: "바라바라의 인기 영상과 최신 업로드를 한눈에 확인하세요" },
          { title: "바라바라 팬카페 커뮤니티", url: "https://example.com/barabara-community", snippet: "바라바라 팬들의 소통 공간. 최신 소식과 영상 리뷰 공유" },
          { title: "BARABARA Instagram Official", url: "https://instagram.com/barabara_official", snippet: "바라바라의 공식 인스타그램. 일상과 비하인드 스토리" }
        ],
        analysis: {
          keywords: ["브이로그", "일상", "감성", "카페", "편집", "vlog", "lifestyle", "aesthetic"],
          insights: [
            "감성적인 영상 스타일로 높은 시청자 만족도 확보",
            "편집 퀄리티에 대한 긍정적 피드백이 많음",
            "일상 브이로그 컨텐츠가 주요 콘텐츠로 자리잡음",
            "한국 시청자 중심이지만 해외 시청자도 꾸준히 증가 중"
          ],
          trends: [
            "홈카페, 감성 카페 투어 등 라이프스타일 콘텐츠 인기",
            "정기적인 업로드 일정으로 충성도 높은 구독자층 형성",
            "영상 편집과 색감에 대한 관심도가 높음"
          ]
        }
      },
      {
        name: "이브닛 (IVNIT)",
        channel_id: "UCxxxxIVNIT",
        youtube_channel: "@ivnit_official",
        total_comments: 15,
        total_likes: 312,
        overall_score: 89,
        sentiment_distribution: { positive: 0.87, neutral: 0.07, negative: 0.07 },
        country_stats: {
          KR: { comment_count: 11, total_likes: 256 },
          US: { comment_count: 3, total_likes: 42 },
          JP: { comment_count: 1, total_likes: 14 }
        },
        comments: [
          { text: "이브닛님 목소리 너무 좋아요! ASMR 최고 ㅠㅠ", likes: 52, sentiment: "positive", country: "KR", video_title: "밤의 힐링 ASMR 🌙" },
          { text: "매일 자기 전에 듣고 자요. 불면증에 진짜 도움돼요", likes: 48, sentiment: "positive", country: "KR", video_title: "밤의 힐링 ASMR 🌙" },
          { text: "Your ASMR content is absolutely perfect for relaxation", likes: 35, sentiment: "positive", country: "US", video_title: "Evening Relaxation ASMR" },
          { text: "이브닛님 영상은 퀄리티가 다르네요. 구독 박고 갑니다!", likes: 41, sentiment: "positive", country: "KR", video_title: "밤의 힐링 ASMR 🌙" },
          { text: "소리 잡아주시는 게 정말 좋아요. 녹음 장비도 좋으신 것 같고", likes: 28, sentiment: "positive", country: "KR", video_title: "수면 유도 ASMR" }
        ],
        videos: [
          { title: "밤의 힐링 ASMR 🌙", video_id: "ivnit_video_001", views: 78400, likes: 4250, comments: 287 },
          { title: "수면 유도 ASMR", video_id: "ivnit_video_002", views: 62100, likes: 3680, comments: 198 },
          { title: "Evening Relaxation ASMR", video_id: "ivnit_video_003", views: 51200, likes: 2940, comments: 156 },
          { title: "백색소음과 함께하는 ASMR", video_id: "ivnit_video_004", views: 89500, likes: 5120, comments: 342 },
          { title: "빗소리 ASMR 3시간", video_id: "ivnit_video_005", views: 124800, likes: 6780, comments: 421 }
        ],
        google_links: [
          { title: "이브닛 (IVNIT) - ASMR 전문 크리에이터", url: "https://example.com/ivnit-profile", snippet: "힐링과 수면 유도 ASMR 영상으로 유명한 이브닛의 공식 페이지" },
          { title: "IVNIT ASMR 인기 영상 TOP 10", url: "https://example.com/ivnit-top-videos", snippet: "이브닛의 가장 인기 있는 ASMR 영상들을 모아봤습니다" },
          { title: "이브닛 ASMR 후기 및 리뷰", url: "https://example.com/ivnit-reviews", snippet: "실제 시청자들이 남긴 이브닛 ASMR 영상 효과 후기" },
          { title: "IVNIT 수면 ASMR 플레이리스트", url: "https://example.com/ivnit-playlist", snippet: "이브닛의 수면 유도 ASMR 영상 모음 플레이리스트" },
          { title: "이브닛 장비 리뷰 - 사용하는 마이크는?", url: "https://example.com/ivnit-equipment", snippet: "이브닛이 사용하는 ASMR 녹음 장비 소개 및 리뷰" }
        ],
        analysis: {
          keywords: ["ASMR", "힐링", "수면", "relaxation", "sleep", "백색소음", "빗소리", "healing"],
          insights: [
            "ASMR 콘텐츠로 높은 시청 시간과 재생 수 기록",
            "수면 유도 효과에 대한 긍정적 피드백 다수",
            "음질과 녹음 장비에 대한 관심도가 높음",
            "정기적인 업로드로 충성 구독자층 확보"
          ],
          trends: [
            "장시간 ASMR 영상(3시간 이상)의 인기 증가",
            "빗소리, 백색소음 등 자연 사운드 콘텐츠 선호도 높음",
            "불면증 개선 및 스트레스 해소 목적의 시청자 증가",
            "해외 시청자 유입이 꾸준히 증가하는 추세"
          ]
        }
      }
    ];
  };

  // eslint-disable-next-line no-unused-vars
  const [selectedScan, setSelectedScan] = useState(null);
  const [platformSummary, setPlatformSummary] = useState(null);

  // AkaiV Studio 필터링 효과
  useEffect(() => {
    if (showArchiveStudioCreators && allVuddyCreators.length > 0) {
      const filtered = allVuddyCreators.filter(c => {
        const name = (c.name || '').toLowerCase();
        return name.includes('u32') || name.includes('여르미') || name.includes('한결') || 
               name.includes('비몽') || name.includes('샤르망') || name.includes('akaiv');
      });
      setVuddyCreators(filtered);
    } else if (!showArchiveStudioCreators && allVuddyCreators.length > 0) {
      setVuddyCreators(allVuddyCreators);
    }
  }, [showArchiveStudioCreators, allVuddyCreators]);

  // filteredScans는 더 이상 사용하지 않음 (최근 수집 데이터 섹션 제거됨)

  // 크리에이터 상세 내역 토글 함수
  // eslint-disable-next-line no-unused-vars
  const toggleCreatorDetails = (creatorName) => {
    setExpandedCreators(prev => ({
      ...prev,
      [creatorName]: !prev[creatorName]
    }));
  };

  // 플랫폼별 요약 통계 계산
  useEffect(() => {
    if (selectedPlatform === 'youtube') {
      // YouTube 플랫폼 요약 통계 (channels 데이터 사용)
      const totalKeywords = channels.length;
      const totalVideos = channels.reduce((sum, ch) => sum + (ch.videos_analyzed || 0), 0);
      const totalComments = channels.reduce((sum, ch) => sum + (ch.total_comments || 0), 0);

      setPlatformSummary({
        platform: 'youtube',
        totalItems: totalKeywords,
        totalVideos,
        totalComments,
        channels: channels
      });
    } else if (selectedPlatform === 'twitter') {
      // Twitter/X 플랫폼 요약 (검색 링크 기반)
      setPlatformSummary({
        platform: 'twitter',
        totalItems: 12, // 크리에이터 키워드 수
        isSearchLinkBased: true
      });
    } else if (selectedPlatform === 'dcinside') {
      // DC인사이드 플랫폼 요약 통계 (dcinsideGalleries 데이터 사용)
      const totalGalleries = dcinsideGalleries.length;
      const totalPosts = dcinsideGalleries.reduce((sum, gallery) => sum + (gallery.total_posts || 0), 0);
      // total_comments 필드를 우선 사용, 없으면 posts 배열의 comment_count 합산
      const totalComments = dcinsideGalleries.reduce((sum, gallery) => {
        if (gallery.total_comments !== undefined && gallery.total_comments !== null) {
          return sum + gallery.total_comments;
        }
        // total_comments가 없으면 posts 배열의 comment_count 합산
        return sum + (gallery.posts || []).reduce((commentSum, post) => {
          return commentSum + (post.comment_count || 0);
        }, 0);
      }, 0);

      // 감정 분석 집계
      let positiveCount = 0;
      let negativeCount = 0;

      dcinsideGalleries.forEach(gallery => {
        (gallery.posts || []).forEach(post => {
          const sentiment = analyzeSentiment(post.title + ' ' + (post.content || ''));
          if (sentiment === 'positive') positiveCount++;
          else if (sentiment === 'negative') negativeCount++;

          // 댓글 감정 분석
          (post.comments || []).forEach(comment => {
            const commentText = comment.text || comment.content || '';
            const commentSentiment = analyzeSentiment(commentText);
            if (commentSentiment === 'positive') positiveCount++;
            else if (commentSentiment === 'negative') negativeCount++;
          });
        });
      });

      setPlatformSummary({
        platform: 'dcinside',
        totalItems: totalGalleries,
        totalPosts,
        totalComments,
        positiveCount,
        negativeCount,
        galleries: dcinsideGalleries
      });
    } else {
      setPlatformSummary(null);
    }
  }, [selectedPlatform, scans, dcinsideGalleries, channels]);

  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>데이터 로딩 중...</p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      {/* URL 분석 바로가기 */}
      <div className="url-analyze-banner" style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderRadius: '12px',
        padding: '16px 24px',
        marginBottom: '20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        cursor: 'pointer',
        color: 'white',
      }} onClick={() => { window.history.pushState({}, '', '/analyze'); window.dispatchEvent(new PopStateEvent('popstate')); }}>
        <div>
          <h3 style={{ margin: '0 0 4px', fontSize: '16px' }}>URL Analyzer</h3>
          <p style={{ margin: 0, fontSize: '13px', opacity: 0.85 }}>YouTube, DCInside, Reddit, Telegram, Kakao URL을 붙여넣어 분석하세요</p>
        </div>
        <span style={{ fontSize: '24px' }}>→</span>
      </div>

      {/* 통계 카드 */}
      <div className="stats-section">
        <h2>📊 통계</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">📊</div>
            <div className="stat-content">
              <h3>총 수집 개수</h3>
              <p className="stat-value">
                {(() => {
                  // CreatorBrand 크리에이터 댓글 수
                  const vuddyComments = allVuddyCreators.reduce((sum, creator) =>
                    sum + (creator.comments?.length || 0), 0);

                  // DC인사이드 게시글 수 (total_posts 사용)
                  const dcPosts = dcinsideGalleries.reduce((sum, gallery) =>
                    sum + (gallery.total_posts || gallery.posts?.length || 0), 0);

                  return vuddyComments + dcPosts;
                })()}
              </p>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">💬</div>
            <div className="stat-content">
              <h3>총 댓글 수</h3>
              <p className="stat-value">
                {(() => {
                  // CreatorBrand 크리에이터 댓글 수
                  const vuddyComments = allVuddyCreators.reduce((sum, creator) =>
                    sum + (creator.comments?.length || 0), 0);

                  // DC인사이드 총 댓글 수
                  const dcComments = dcinsideGalleries.reduce((sum, gallery) =>
                    sum + (gallery.total_comments || 0), 0);

                  return vuddyComments + dcComments;
                })()}
              </p>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">📅</div>
            <div className="stat-content">
              <h3>최근 수집</h3>
              <p className="stat-value" style={{ fontSize: '0.9rem' }}>
                {(() => {
                  const dates = [];

                  // CreatorBrand 크리에이터 날짜
                  allVuddyCreators.forEach(creator => {
                    if (creator.last_crawled) dates.push(new Date(creator.last_crawled));
                  });

                  // DC인사이드 날짜 (crawled_at 사용)
                  dcinsideGalleries.forEach(gallery => {
                    if (gallery.crawled_at) dates.push(new Date(gallery.crawled_at));
                  });

                  if (dates.length === 0) return 'N/A';

                  const latestDate = new Date(Math.max(...dates));
                  return latestDate.toLocaleString('ko-KR', {
                    timeZone: 'Asia/Seoul',
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                  });
                })()}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* DC인사이드 갤러리 */}
      {dcinsideGalleries.length > 0 && (selectedPlatform === 'all' || selectedPlatform === 'dcinside') && (selectedPlatform === 'all' || selectedPlatform === 'dcinside') && (
        <div className="dcinside-section" style={{ marginBottom: '40px' }}>
          <h2 style={{ color: '#0253fe', marginBottom: '20px', fontWeight: '900', textTransform: 'uppercase' }}>
            💬 DC인사이드 갤러리 모니터링
          </h2>

          {/* 전체 댓글 요약 */}
          <div style={{
            marginBottom: '20px',
            padding: '20px',
            background: 'linear-gradient(135deg, #f0f4ff 0%, #fff 100%)',
            border: '3px solid #0253fe',
            borderRadius: '12px'
          }}>
            <h3 style={{ color: '#0253fe', marginBottom: '15px', fontSize: '16px', fontWeight: 'bold' }}>
              📊 전체 갤러리 요약
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
              <div style={{ textAlign: 'center', padding: '15px', background: '#fff', borderRadius: '8px', border: '2px solid #0253fe' }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#0253fe' }}>
                  {dcinsideGalleries.reduce((sum, g) => sum + (g.total_posts || 0), 0)}
                </div>
                <div style={{ fontSize: '12px', color: '#666' }}>📝 총 게시글</div>
              </div>
              <div style={{ textAlign: 'center', padding: '15px', background: '#fff', borderRadius: '8px', border: '2px solid #0253fe' }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#0253fe' }}>
                  {dcinsideGalleries.reduce((sum, g) => sum + (g.total_comments || 0), 0)}
                </div>
                <div style={{ fontSize: '12px', color: '#666' }}>💬 총 댓글</div>
              </div>
              <div style={{ textAlign: 'center', padding: '15px', background: '#e8f5e9', borderRadius: '8px', border: '2px solid #4caf50' }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#2e7d32' }}>
                  {dcinsideGalleries.reduce((sum, g) => sum + (g.positive_count || 0), 0)}
                </div>
                <div style={{ fontSize: '12px', color: '#388e3c' }}>😊 긍정</div>
              </div>
              <div style={{ textAlign: 'center', padding: '15px', background: '#ffebee', borderRadius: '8px', border: '2px solid #f44336' }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#c62828' }}>
                  {dcinsideGalleries.reduce((sum, g) => sum + (g.negative_count || 0), 0)}
                </div>
                <div style={{ fontSize: '12px', color: '#d32f2f' }}>😞 부정</div>
              </div>
            </div>
          </div>

          <div className="dcinside-galleries-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '20px' }}>
            {dcinsideGalleries.map((gallery) => {
              const isExpanded = expandedGalleries[gallery.gallery_id] || false;
              const visiblePosts = isExpanded ? gallery.posts : (gallery.posts || []).slice(0, 3);

              return (
              <div
                key={gallery.gallery_id}
                className="dcinside-gallery-card"
                style={{
                  background: '#FFFFFF',
                  border: '3px solid #0253fe',
                  borderRadius: '12px',
                  padding: '20px',
                  transition: 'all 0.3s ease'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <h3 style={{ color: '#0253fe', fontSize: '18px', fontWeight: '900', margin: 0 }}>
                    {gallery.gallery_name}
                  </h3>
                  <a
                    href={(() => {
                      // 미니 갤러리 ID 목록 (skoshism은 마이너갤러리)
                      const miniGalleries = ['ivnit', 'akaiv', 'soopvirtualstreamer', 'spv', 'soopstreaming'];
                      const galleryType = miniGalleries.includes(gallery.gallery_id) ? 'mini' : 'mgallery';
                      return `https://gall.dcinside.com/${galleryType}/board/lists/?id=${gallery.gallery_id}`;
                    })()}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      padding: '6px 12px',
                      background: '#0253fe',
                      color: '#cfff0b',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: 'bold',
                      textDecoration: 'none'
                    }}
                  >
                    갤러리 바로가기 →
                  </a>
                </div>

                {/* 갤러리 통계 */}
                <div style={{ marginBottom: '15px', padding: '15px', background: '#f8f9ff', borderRadius: '8px', border: '2px solid #0253fe' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '13px', fontWeight: 'bold', color: '#0253fe' }}>
                    <div>📝 게시글: {gallery.total_posts}개</div>
                    <div>💬 댓글: {gallery.total_comments}개</div>
                    <div>👍 긍정: {gallery.positive_count}개</div>
                    <div>👎 부정: {gallery.negative_count}개</div>
                  </div>
                  {gallery.crawled_at && (
                    <div style={{ marginTop: '10px', fontSize: '11px', color: '#0253fe', opacity: 0.7 }}>
                      수집 시간: {new Date(gallery.crawled_at).toLocaleString('ko-KR')}
                    </div>
                  )}
                </div>

                {/* 🔍 키워드 분석 */}
                {(() => {
                  const keywordFreq = {};
                  const categoryFreq = {};
                  let totalMatches = 0;

                  // 게시글 제목 및 댓글 분석
                  (gallery.posts || []).forEach(post => {
                    const titleMatched = findMatchingKeywords(post.title || '');
                    titleMatched.forEach(keyword => {
                      keywordFreq[keyword] = (keywordFreq[keyword] || 0) + 1;
                      const category = getKeywordCategory(keyword);
                      categoryFreq[category] = (categoryFreq[category] || 0) + 1;
                      totalMatches++;
                    });
                    (post.comments || []).forEach(comment => {
                      const text = comment.content || comment.text || '';
                      const matched = findMatchingKeywords(text);
                      matched.forEach(keyword => {
                        keywordFreq[keyword] = (keywordFreq[keyword] || 0) + 1;
                        const category = getKeywordCategory(keyword);
                        categoryFreq[category] = (categoryFreq[category] || 0) + 1;
                        totalMatches++;
                      });
                    });
                  });

                  if (totalMatches === 0) return null;

                  const topKeywords = Object.entries(keywordFreq)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 10);

                  const sortedCategories = Object.entries(categoryFreq)
                    .sort((a, b) => b[1] - a[1]);

                  const categoryColors = {
                    '크리에이터브랜드/CreatorBrand': '#9b59b6',
                    '예시기업/ExampleCorp': '#e74c3c',
                    '크리에이터': '#3498db',
                    '굿즈/상품': '#f39c12',
                    '판매/구매': '#27ae60',
                    '팬활동': '#e91e63',
                    '디지털상품': '#00bcd4',
                    '활동': '#722ed1',
                    '콘텐츠': '#d48806',
                    '반응': '#0958d9',
                    '품질': '#389e0d',
                    '기타': '#595959'
                  };

                  return (
                    <div style={{
                      marginBottom: '15px',
                      padding: '12px',
                      background: 'linear-gradient(135deg, #fff5f5 0%, #fff 100%)',
                      borderRadius: '8px',
                      border: '2px solid #ff4444'
                    }}>
                      <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#ff4444', marginBottom: '10px' }}>
                        🔍 키워드 분석 (총 {totalMatches}개 매칭)
                      </div>
                      {/* 카테고리별 */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
                        {sortedCategories.map(([category, count], idx) => (
                          <span key={idx} style={{
                            padding: '4px 10px',
                            background: 'white',
                            borderRadius: '12px',
                            border: `2px solid ${categoryColors[category] || '#666'}`,
                            fontSize: '10px',
                            fontWeight: 'bold',
                            color: categoryColors[category] || '#666'
                          }}>
                            {category} <span style={{
                              background: categoryColors[category] || '#666',
                              color: 'white',
                              padding: '1px 6px',
                              borderRadius: '8px',
                              marginLeft: '4px'
                            }}>{count}</span>
                          </span>
                        ))}
                      </div>
                      {/* 상위 키워드 */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {topKeywords.map(([keyword, count], idx) => {
                          const category = getKeywordCategory(keyword);
                          const color = categoryColors[category] || '#666';
                          return (
                            <span key={idx} style={{
                              padding: '3px 8px',
                              background: idx < 3 ? color : 'white',
                              color: idx < 3 ? 'white' : color,
                              borderRadius: '10px',
                              fontSize: '10px',
                              fontWeight: idx < 3 ? 'bold' : 'normal',
                              border: `1px solid ${color}`
                            }}>
                              {idx < 3 && '🏆'}{keyword}({count})
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()}

                {/* 최근 게시글 */}
                {gallery.posts && gallery.posts.length > 0 && (
                  <div>
                    <div style={{ fontSize: '14px', color: '#0253fe', marginBottom: '10px', fontWeight: '900', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>📌 최근 게시글 ({gallery.posts.length}개)</span>
                      {!isExpanded && gallery.posts.length > 3 && (
                        <span style={{ fontSize: '11px', color: '#888', fontWeight: 'normal' }}>
                          {gallery.posts.length - 3}개 더 있음
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {visiblePosts.map((post) => {
                        const postKey = `${gallery.gallery_id}_${post.post_id}`;
                        const isPostExpanded = expandedPosts[postKey] || false;
                        const visibleComments = isPostExpanded ? post.comments : (post.comments || []).slice(0, 2);

                        return (
                        <div key={post.post_id} style={{ marginBottom: '10px' }}>
                          <a
                            href={post.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              display: 'block',
                              padding: '12px',
                              background: '#FFFFFF',
                              border: '2px solid #0253fe',
                              borderRadius: '8px',
                              textDecoration: 'none',
                              color: '#0253fe',
                              transition: 'all 0.2s ease'
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = '#0253fe';
                              e.currentTarget.style.color = '#cfff0b';
                              e.currentTarget.style.transform = 'translateY(-2px)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = '#FFFFFF';
                              e.currentTarget.style.color = '#0253fe';
                              e.currentTarget.style.transform = 'translateY(0)';
                            }}
                          >
                            <div style={{ fontWeight: '900', marginBottom: '6px', fontSize: '13px' }}>
                              {/* 크롤러에서 찾은 키워드 */}
                              {post.matched_keyword && (
                                <span style={{
                                  background: '#0253fe',
                                  color: '#cfff0b',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  fontSize: '10px',
                                  marginRight: '6px'
                                }}>
                                  {post.matched_keyword}
                                </span>
                              )}
                              {/* 제목에서 분석한 추가 키워드 */}
                              {(() => {
                                const titleKeywords = findMatchingKeywords(post.title || '');
                                // post.matched_keyword와 중복되지 않는 키워드만 표시
                                const uniqueKeywords = titleKeywords.filter(k =>
                                  k.toLowerCase() !== (post.matched_keyword || '').toLowerCase()
                                );
                                const categoryColors = {
                                  '크리에이터브랜드/CreatorBrand': '#9b59b6',
                                  '예시기업/ExampleCorp': '#e74c3c',
                                  '크리에이터': '#3498db',
                                  '굿즈/상품': '#f39c12',
                                  '판매/구매': '#27ae60',
                                  '팬활동': '#e91e63',
                                  '디지털상품': '#00bcd4',
                                  '활동': '#722ed1',
                                  '콘텐츠': '#d48806',
                                  '반응': '#0958d9',
                                  '품질': '#389e0d',
                                  '기타': '#595959'
                                };
                                return uniqueKeywords.slice(0, 3).map((keyword, idx) => {
                                  const category = getKeywordCategory(keyword);
                                  const color = categoryColors[category] || '#666';
                                  return (
                                    <span key={idx} style={{
                                      background: color,
                                      color: 'white',
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      fontSize: '10px',
                                      marginRight: '4px'
                                    }}>
                                      {keyword}
                                    </span>
                                  );
                                });
                              })()}
                              {(() => {
                                const sentiment = analyzeSentiment(post.title + ' ' + (post.content || ''));
                                if (sentiment === 'positive') {
                                  return <span style={{ marginRight: '6px', fontSize: '14px' }}>😊</span>;
                                } else if (sentiment === 'negative') {
                                  return <span style={{ marginRight: '6px', fontSize: '14px' }}>😞</span>;
                                }
                                return null;
                              })()}
                              {post.title}
                            </div>
                            <div style={{ fontSize: '11px', opacity: 0.8, marginBottom: '4px' }}>
                              <span style={{ fontWeight: 'bold' }}>작성자:</span> {post.author} ·
                              <span style={{ fontWeight: 'bold', marginLeft: '8px' }}>작성일:</span> {post.date}
                            </div>
                            <div style={{ fontSize: '11px', opacity: 0.8, display: 'flex', justifyContent: 'space-between' }}>
                              <span>👁️ 조회 {post.view_count}</span>
                              <span>👍 추천 {post.recommend_count}</span>
                              <span>💬 댓글 {post.comment_count || 0}</span>
                            </div>
                          </a>

                          {/* 댓글 표시 - comment_count가 있거나 comments 배열이 있으면 표시 */}
                          {(post.comment_count > 0 || (post.comments && Array.isArray(post.comments) && post.comments.length > 0)) && (
                            <div style={{ marginTop: '8px', paddingLeft: '12px', borderLeft: '3px solid #0253fe' }}>
                              <div
                                style={{
                                  fontSize: '12px',
                                  color: '#0253fe',
                                  marginBottom: '6px',
                                  fontWeight: 'bold',
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center'
                                }}
                              >
                                <span>💬 댓글 {post.comments && post.comments.length > 0 ? `(${post.comments.length}개${post.comment_count > post.comments.length ? ` / 전체 ${post.comment_count}개` : ''})` : `(${post.comment_count || 0}개)`}</span>
                                {post.comments && post.comments.length > 2 && (
                                  <button
                                    onClick={(e) => {
                                      e.preventDefault();
                                      e.stopPropagation();
                                      setExpandedPosts(prev => ({
                                        ...prev,
                                        [postKey]: !prev[postKey]
                                      }));
                                    }}
                                    style={{
                                      padding: '4px 8px',
                                      background: isPostExpanded ? '#cfff0b' : '#0253fe',
                                      color: isPostExpanded ? '#0253fe' : '#cfff0b',
                                      border: '2px solid #0253fe',
                                      borderRadius: '4px',
                                      fontSize: '10px',
                                      fontWeight: 'bold',
                                      cursor: 'pointer'
                                    }}
                                  >
                                    {isPostExpanded ? '댓글 접기 ▲' : `+${post.comments.length - 2}개 더보기 ▼`}
                                  </button>
                                )}
                              </div>
                              {visibleComments.map((comment, idx) => {
                                const commentText = comment.text || comment.content || '';
                                const commentSentiment = analyzeSentiment(commentText);
                                const commentKeywords = findMatchingKeywords(commentText);
                                const commentCategoryColors = {
                                  '크리에이터브랜드/CreatorBrand': '#9b59b6',
                                  '예시기업/ExampleCorp': '#e74c3c',
                                  '크리에이터': '#3498db',
                                  '굿즈/상품': '#f39c12',
                                  '판매/구매': '#27ae60',
                                  '팬활동': '#e91e63',
                                  '디지털상품': '#00bcd4',
                                  '활동': '#722ed1',
                                  '콘텐츠': '#d48806',
                                  '반응': '#0958d9',
                                  '품질': '#389e0d',
                                  '기타': '#595959'
                                };
                                return (
                                  <div key={idx} style={{ padding: '8px', marginBottom: '6px', background: '#f8f9ff', borderRadius: '6px', fontSize: '11px' }}>
                                    <div style={{ fontWeight: 'bold', color: '#0253fe', marginBottom: '4px' }}>
                                      {commentSentiment === 'positive' && <span style={{ marginRight: '4px' }}>😊</span>}
                                      {commentSentiment === 'negative' && <span style={{ marginRight: '4px' }}>😞</span>}
                                      {commentSentiment === 'neutral' && <span style={{ marginRight: '4px' }}>😐</span>}
                                      {comment.author || '익명'} · {comment.date || ''}
                                      {/* 댓글 키워드 */}
                                      {commentKeywords.length > 0 && (
                                        <span style={{ marginLeft: '8px' }}>
                                          {commentKeywords.slice(0, 2).map((keyword, kidx) => {
                                            const category = getKeywordCategory(keyword);
                                            const color = commentCategoryColors[category] || '#666';
                                            return (
                                              <span key={kidx} style={{
                                                background: color,
                                                color: 'white',
                                                padding: '1px 4px',
                                                borderRadius: '3px',
                                                fontSize: '9px',
                                                marginLeft: '3px'
                                              }}>
                                                {keyword}
                                              </span>
                                            );
                                          })}
                                        </span>
                                      )}
                                    </div>
                                    <div style={{ color: '#333' }}>{commentText || '(댓글 내용 없음)'}</div>
                                  </div>
                                );
                              })}
                              {/* 댓글이 없지만 comment_count가 있는 경우 안내 메시지 */}
                              {(!post.comments || post.comments.length === 0) && post.comment_count > 0 && (
                                <div style={{ padding: '8px', marginTop: '6px', background: '#fff3cd', borderRadius: '6px', fontSize: '11px', color: '#856404', border: '1px solid #ffc107' }}>
                                  💬 댓글 {post.comment_count}개 (내용 수집 중 - 다음 크롤링 시 표시됩니다)
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )})}
                    </div>

                    {/* 더보기/접기 버튼 */}
                    {gallery.posts.length > 3 && (
                      <div style={{ display: 'flex', gap: '10px', marginTop: '15px' }}>
                        <button
                          onClick={() => {
                            setExpandedGalleries(prev => ({
                              ...prev,
                              [gallery.gallery_id]: !prev[gallery.gallery_id]
                            }));
                          }}
                          style={{
                            flex: 1,
                            padding: '12px',
                            background: isExpanded ? '#cfff0b' : '#0253fe',
                            color: isExpanded ? '#0253fe' : '#cfff0b',
                            border: '3px solid #0253fe',
                            borderRadius: '8px',
                            fontSize: '14px',
                            fontWeight: '900',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.transform = 'translateY(-2px)';
                            e.currentTarget.style.boxShadow = '0 4px 12px rgba(2, 83, 254, 0.3)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.transform = 'translateY(0)';
                            e.currentTarget.style.boxShadow = 'none';
                          }}
                        >
                          {isExpanded
                            ? '📌 게시글 접기 ▲'
                            : `📌 게시글 펼치기 (${gallery.posts.length - 3}개 더) ▼`
                          }
                        </button>
                      </div>
                    )}

                    {/* DB에서 더 불러오기 버튼 - 확장된 상태에서만 표시 */}
                    {isExpanded && (galleryPagination[gallery.gallery_id]?.hasMore !== false) && (
                      <button
                        onClick={() => loadMorePosts(gallery.gallery_id)}
                        disabled={loadingMorePosts[gallery.gallery_id]}
                        style={{
                          width: '100%',
                          marginTop: '10px',
                          padding: '12px',
                          background: loadingMorePosts[gallery.gallery_id] ? '#ccc' : '#28a745',
                          color: 'white',
                          border: '3px solid #28a745',
                          borderRadius: '8px',
                          fontSize: '14px',
                          fontWeight: '900',
                          cursor: loadingMorePosts[gallery.gallery_id] ? 'wait' : 'pointer',
                          transition: 'all 0.2s ease'
                        }}
                        onMouseEnter={(e) => {
                          if (!loadingMorePosts[gallery.gallery_id]) {
                            e.currentTarget.style.transform = 'translateY(-2px)';
                            e.currentTarget.style.boxShadow = '0 4px 12px rgba(40, 167, 69, 0.3)';
                          }
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = 'translateY(0)';
                          e.currentTarget.style.boxShadow = 'none';
                        }}
                      >
                        {loadingMorePosts[gallery.gallery_id]
                          ? '⏳ 로딩 중...'
                          : `💾 DB에서 게시글 더 불러오기 ${galleryPagination[gallery.gallery_id]?.totalPosts ? `(총 ${galleryPagination[gallery.gallery_id].totalPosts}개)` : ''}`
                        }
                      </button>
                    )}

                    {/* 더 이상 불러올 게시글이 없을 때 */}
                    {isExpanded && galleryPagination[gallery.gallery_id]?.hasMore === false && (
                      <div style={{
                        marginTop: '10px',
                        padding: '10px',
                        background: '#f8f9fa',
                        borderRadius: '8px',
                        textAlign: 'center',
                        fontSize: '13px',
                        color: '#666'
                      }}>
                        ✅ 모든 게시글을 불러왔습니다 ({gallery.posts.length}개)
                      </div>
                    )}
                  </div>
                )}

                {/* 게시글이 없는 경우 */}
                {(!gallery.posts || gallery.posts.length === 0) && (
                  <div style={{
                    textAlign: 'center',
                    padding: '30px',
                    background: '#f8f9ff',
                    borderRadius: '8px',
                    color: '#0253fe'
                  }}>
                    <div style={{ fontSize: '24px', marginBottom: '10px' }}>📭</div>
                    <div style={{ fontSize: '14px', fontWeight: 'bold' }}>아직 수집된 게시글이 없습니다</div>
                    <div style={{ fontSize: '12px', marginTop: '5px', opacity: 0.7 }}>
                      키워드와 일치하는 게시글이 발견되면 자동으로 표시됩니다
                    </div>
                  </div>
                )}
              </div>
            )})}
          </div>
        </div>
      )}

      {/* 🐦 트위터/X 검색 링크 */}
      <div className="twitter-search-section" style={{ marginBottom: '40px' }}>
        <h2 style={{
          color: '#1da1f2',
          fontWeight: '900',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginBottom: '20px'
        }}>
          <span style={{ fontSize: '28px' }}>🐦</span>
          트위터/X 검색
        </h2>

        {/* 트위터 검색 안내 */}
        <div style={{
          padding: '24px',
          background: 'linear-gradient(135deg, #e3f2fd 0%, #fff 100%)',
          border: '3px solid #1da1f2',
          borderRadius: '16px',
          marginBottom: '20px'
        }}>
          <p style={{ color: '#666', marginBottom: '16px', fontSize: '14px' }}>
            아래 키워드를 클릭하면 트위터에서 직접 검색할 수 있습니다.
          </p>

          {/* 키워드 입력 및 검색 */}
          <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' }}>
            <input
              type="text"
              value={twitterKeywordSearch}
              onChange={(e) => setTwitterKeywordSearch(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && twitterKeywordSearch.trim()) {
                  window.open(`https://twitter.com/search?q=${encodeURIComponent(twitterKeywordSearch)}&src=typed_query&f=live`, '_blank');
                }
              }}
              placeholder="검색할 키워드 입력... (예: 크리에이터브랜드, 굿즈)"
              style={{
                flex: 1,
                minWidth: '200px',
                padding: '14px 18px',
                fontSize: '15px',
                border: '2px solid #1da1f2',
                borderRadius: '10px',
                outline: 'none'
              }}
            />
            <button
              onClick={() => {
                if (twitterKeywordSearch.trim()) {
                  window.open(`https://twitter.com/search?q=${encodeURIComponent(twitterKeywordSearch)}&src=typed_query&f=live`, '_blank');
                }
              }}
              style={{
                padding: '14px 28px',
                background: '#1da1f2',
                color: 'white',
                border: 'none',
                borderRadius: '10px',
                fontWeight: 'bold',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              🔗 트위터에서 검색
            </button>
          </div>

          {/* 크리에이터 키워드 */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ fontSize: '13px', color: '#1da1f2', marginBottom: '10px', fontWeight: 'bold' }}>
              🎤 크리에이터 검색
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {['크리에이터브랜드', '예시기업', '스코시즘', '아카이브', '바라바라', '이브닛', 'u32', '여르미', '한결', '비몽', '샤르망', '나나문'].map((keyword) => (
                <a
                  key={keyword}
                  href={`https://twitter.com/search?q=${encodeURIComponent(keyword)}&src=typed_query&f=live`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: '10px 16px',
                    background: '#1da1f2',
                    color: 'white',
                    borderRadius: '20px',
                    fontSize: '13px',
                    fontWeight: 'bold',
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseOver={(e) => e.target.style.background = '#0d8bd9'}
                  onMouseOut={(e) => e.target.style.background = '#1da1f2'}
                >
                  🔗 {keyword}
                </a>
              ))}
            </div>
          </div>

          {/* 복합 검색 */}
          <div>
            <div style={{ fontSize: '13px', color: '#9c27b0', marginBottom: '10px', fontWeight: 'bold' }}>
              🔍 복합 검색
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {[
                { label: '여르미 굿즈', query: '여르미 굿즈' },
                { label: '한결 굿즈', query: '한결 굿즈' },
                { label: '비몽 굿즈', query: '비몽 굿즈' },
                { label: '샤르망 굿즈', query: '샤르망 굿즈' },
                { label: 'u32 굿즈', query: 'u32 굿즈' },
                { label: '나나문 굿즈', query: '나나문 굿즈' },
                { label: '스코시즘 굿즈', query: '스코시즘 굿즈' },
                { label: '크리에이터브랜드 굿즈', query: '크리에이터브랜드 굿즈' },
                { label: '이브닛 굿즈', query: '이브닛 굿즈' },
                { label: '아카이브 굿즈', query: '아카이브 굿즈' },
              ].map((item) => (
                <a
                  key={item.label}
                  href={`https://twitter.com/search?q=${encodeURIComponent(item.query)}&src=typed_query&f=live`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: '10px 16px',
                    background: '#9c27b0',
                    color: 'white',
                    borderRadius: '20px',
                    fontSize: '13px',
                    fontWeight: 'bold',
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseOver={(e) => e.target.style.background = '#7b1fa2'}
                  onMouseOut={(e) => e.target.style.background = '#9c27b0'}
                >
                  🔗 {item.label}
                </a>
              ))}
            </div>
          </div>
        </div>

        {/* 안내 메시지 */}
        <div style={{
          padding: '16px',
          background: '#fff3cd',
          border: '1px solid #ffc107',
          borderRadius: '8px',
          fontSize: '13px',
          color: '#856404'
        }}>
          <strong>💡 안내:</strong> 트위터/X는 API 사용에 유료 구독이 필요하여, 검색 링크를 통해 트위터에서 직접 검색하는 방식으로 제공됩니다.
        </div>
      </div>

      {/* YouTube 댓글 키워드 분석 - 메인 대시보드에서 제거됨 (/skoshism, /akaiv-studio 페이지에서 확인 가능) */}
      {false && allVuddyCreators.length > 0 && allVuddyCreators.some(c => c.comments && c.comments.length > 0) && (
        <div className="youtube-comments-section" style={{ marginBottom: '40px' }}>
          <h2 style={{ color: '#ff0000', marginBottom: '20px', fontWeight: '900' }}>
            📺 YouTube 댓글 키워드 분석
          </h2>

          {/* 키워드별 그룹화 */}
          {(() => {
            // 모든 댓글 수집
            const allComments = [];
            allVuddyCreators.forEach(creator => {
              (creator.comments || []).forEach(comment => {
                allComments.push({
                  ...comment,
                  creatorName: creator.name,
                  keywords: creator.analysis?.keywords || []
                });
              });
            });

            // 키워드별 그룹화
            const keywordGroups = {};
            const sentimentGroups = { positive: [], negative: [], neutral: [] };

            allComments.forEach(comment => {
              // 감정별 그룹화
              const sentiment = comment.sentiment || analyzeSentiment(comment.text);
              if (sentimentGroups[sentiment]) {
                sentimentGroups[sentiment].push(comment);
              }

              // 키워드별 그룹화
              const text = (comment.text || '').toLowerCase();
              const keywords = [
                // ★★★ 최우선순위: 크리에이터 이름 및 별명 ★★★
                '아카이브', 'archive', '바라바라', 'barabara', '이브닛', 'ivnit', '스코시즘', 'skoshism',
                'u32', '사미', '우사미',
                '여르미', '엶',
                '한결', '결',
                '비몽', '몽',
                '샤르망', '쭈쭈',
                '나나문', '쿠우',
                // ★★★ 최우선순위: 크리에이터브랜드 및 예시기업 ★★★
                '크리에이터브랜드', 'creatorbrand', '예시기업', 'examplecorp', 'ExampleCorp',
                // ★★★ 최우선순위: 굿즈/상품 ★★★
                '굿즈', '포토카드', '포카', '아크릴', '키링', '스티커', '포스터', '엽서',
                '앨범', '음반', '한정판', '시즌그리팅', '캘린더', '머치', '공식굿즈',
                // ★★ 높은 우선순위: 판매/구매 ★★
                '구매', '판매', '주문', '예약', '결제', '배송', '품절', '재입고', '가격', '할인', '이벤트', '특전',
                // ★★ 높은 우선순위: 팬 활동 ★★
                '팬싸', '영통팬싸', '응모', '당첨', '럭드', '포토타임', '생일카페', '서포트', '조공',
                // ★★ 높은 우선순위: 디지털 상품 ★★
                '음원', '다운로드', '디지털싱글', '뮤직비디오', 'MV', '티저', '커버곡', '오리지널곡',
                '멤버십', '후원', '슈퍼챗', '보이스팩', '월페이퍼', '보팩', '펀딩',
                // 활동 관련
                '버튜버', 'vtuber', '크리에이터', '유튜버', '숲',
                // 콘텐츠 관련
                '노래', '커버', '방송', '영상', '브이로그', 'vlog', 'ASMR', '라이브', '스트리밍',
                // 반응 관련
                '좋아요', '구독', '최고', '대박', '감동', '응원', '팬', '힐링',
                // 품질 관련
                '감성', '편집', '퀄리티', '목소리', '실력',
                // 성별 관련
                '남성', '여성', '남자', '여자', '남캐', '여캐', '남버튜버', '여버튜버',
                '오빠', '언니', '누나', '형'
              ];
              keywords.forEach(keyword => {
                if (text.includes(keyword.toLowerCase())) {
                  if (!keywordGroups[keyword]) keywordGroups[keyword] = [];
                  keywordGroups[keyword].push(comment);
                }
              });
            });

            return (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '20px' }}>
                {/* 감정별 요약 카드 */}
                <div style={{
                  background: 'linear-gradient(135deg, #fff5f5 0%, #fff 100%)',
                  border: '2px solid #ff4444',
                  borderRadius: '12px',
                  padding: '20px',
                  gridColumn: 'span 1'
                }}>
                  <h3 style={{ color: '#ff4444', marginBottom: '15px', fontSize: '16px', fontWeight: 'bold' }}>
                    😊 감정 분석 요약
                  </h3>
                  <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
                    <div style={{
                      background: '#e8f5e9',
                      padding: '10px 15px',
                      borderRadius: '8px',
                      flex: '1',
                      minWidth: '80px',
                      textAlign: 'center'
                    }}>
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2e7d32' }}>
                        {sentimentGroups.positive.length}
                      </div>
                      <div style={{ fontSize: '12px', color: '#388e3c' }}>😊 긍정</div>
                    </div>
                    <div style={{
                      background: '#fff3e0',
                      padding: '10px 15px',
                      borderRadius: '8px',
                      flex: '1',
                      minWidth: '80px',
                      textAlign: 'center'
                    }}>
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ef6c00' }}>
                        {sentimentGroups.neutral.length}
                      </div>
                      <div style={{ fontSize: '12px', color: '#f57c00' }}>😐 중립</div>
                    </div>
                    <div style={{
                      background: '#ffebee',
                      padding: '10px 15px',
                      borderRadius: '8px',
                      flex: '1',
                      minWidth: '80px',
                      textAlign: 'center'
                    }}>
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#c62828' }}>
                        {sentimentGroups.negative.length}
                      </div>
                      <div style={{ fontSize: '12px', color: '#d32f2f' }}>😞 부정</div>
                    </div>
                  </div>
                  <div style={{ marginTop: '15px', fontSize: '12px', color: '#666' }}>
                    총 {allComments.length}개의 댓글 분석 완료
                  </div>
                </div>

                {/* 키워드별 그룹 카드 */}
                {Object.entries(keywordGroups)
                  .filter(([_, comments]) => comments.length > 0)
                  .sort((a, b) => b[1].length - a[1].length)
                  .slice(0, 6)
                  .map(([keyword, comments]) => (
                    <div
                      key={keyword}
                      style={{
                        background: '#fff',
                        border: '2px solid #ff0000',
                        borderRadius: '12px',
                        padding: '20px',
                        transition: 'all 0.3s ease'
                      }}
                    >
                      <h3 style={{
                        color: '#ff0000',
                        marginBottom: '15px',
                        fontSize: '16px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}>
                        <span style={{
                          background: '#ff0000',
                          color: '#fff',
                          padding: '4px 10px',
                          borderRadius: '12px',
                          fontSize: '12px'
                        }}>
                          #{keyword}
                        </span>
                        <span style={{ fontSize: '13px', color: '#666', fontWeight: 'normal' }}>
                          ({comments.length}개 댓글)
                        </span>
                      </h3>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {comments.slice(0, 3).map((comment, idx) => (
                          <div
                            key={idx}
                            style={{
                              background: '#f8f9fa',
                              padding: '12px',
                              borderRadius: '8px',
                              borderLeft: `3px solid ${
                                comment.sentiment === 'positive' ? '#4caf50' :
                                comment.sentiment === 'negative' ? '#f44336' : '#ff9800'
                              }`
                            }}
                          >
                            <div style={{ fontSize: '13px', color: '#333', marginBottom: '8px' }}>
                              "{comment.text?.substring(0, 80)}{comment.text?.length > 80 ? '...' : ''}"
                            </div>
                            <div style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              fontSize: '11px',
                              color: '#888'
                            }}>
                              <span>📹 {comment.video_title?.substring(0, 25)}...</span>
                              <span>👍 {comment.likes || 0}</span>
                            </div>
                          </div>
                        ))}
                        {comments.length > 3 && (
                          <div style={{ fontSize: '11px', color: '#ff0000', textAlign: 'center' }}>
                            +{comments.length - 3}개 더보기
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                {/* 긍정 댓글 TOP */}
                {sentimentGroups.positive.length > 0 && (
                  <div style={{
                    background: 'linear-gradient(135deg, #e8f5e9 0%, #fff 100%)',
                    border: '2px solid #4caf50',
                    borderRadius: '12px',
                    padding: '20px'
                  }}>
                    <h3 style={{ color: '#2e7d32', marginBottom: '15px', fontSize: '16px', fontWeight: 'bold' }}>
                      😊 긍정 댓글 TOP {Math.min(5, sentimentGroups.positive.length)}
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {sentimentGroups.positive
                        .sort((a, b) => (b.likes || 0) - (a.likes || 0))
                        .slice(0, 5)
                        .map((comment, idx) => (
                          <div
                            key={idx}
                            style={{
                              background: '#fff',
                              padding: '12px',
                              borderRadius: '8px',
                              borderLeft: '3px solid #4caf50'
                            }}
                          >
                            <div style={{ fontSize: '13px', color: '#333', marginBottom: '8px' }}>
                              "{comment.text?.substring(0, 60)}..."
                            </div>
                            <div style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              fontSize: '11px',
                              color: '#888'
                            }}>
                              <span>👤 {comment.creatorName?.substring(0, 15)}</span>
                              <span>👍 {comment.likes || 0}</span>
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* 부정 댓글 (있을 경우) */}
                {sentimentGroups.negative.length > 0 && (
                  <div style={{
                    background: 'linear-gradient(135deg, #ffebee 0%, #fff 100%)',
                    border: '2px solid #f44336',
                    borderRadius: '12px',
                    padding: '20px'
                  }}>
                    <h3 style={{ color: '#c62828', marginBottom: '15px', fontSize: '16px', fontWeight: 'bold' }}>
                      😞 부정 댓글 ({sentimentGroups.negative.length}개)
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {sentimentGroups.negative.slice(0, 3).map((comment, idx) => (
                        <div
                          key={idx}
                          style={{
                            background: '#fff',
                            padding: '12px',
                            borderRadius: '8px',
                            borderLeft: '3px solid #f44336'
                          }}
                        >
                          <div style={{ fontSize: '13px', color: '#333', marginBottom: '8px' }}>
                            "{comment.text?.substring(0, 60)}..."
                          </div>
                          <div style={{ fontSize: '11px', color: '#888' }}>
                            👤 {comment.creatorName?.substring(0, 15)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}

      {/* 플랫폼 필터 */}
      <div className="filter-section">
        <h2>🔍 플랫폼별 데이터</h2>
        <div className="platform-filters">
          {(() => {
            // 전체 댓글 수 계산
            const youtubeComments = channels.reduce((sum, c) => sum + (c.total_comments || 0), 0);
            const dcComments = dcinsideGalleries.reduce((sum, g) => sum + (g.total_comments || 0), 0);
            const vuddyComments = allVuddyCreators.reduce((sum, creator) => sum + (creator.comments?.length || 0), 0);
            const totalComments = youtubeComments + dcComments + vuddyComments;
            
            return (
              <>
                <button
                  className={selectedPlatform === 'all' ? 'active' : ''}
                  onClick={() => setSelectedPlatform('all')}
                  title={`전체 데이터 보기 (총 ${totalComments}개 댓글)`}
                >
                  전체
                  {totalComments > 0 && (
                    <span className="filter-count">({totalComments})</span>
                  )}
                </button>
                <button
                  className={selectedPlatform === 'youtube' ? 'active' : ''}
                  onClick={() => setSelectedPlatform('youtube')}
                  title={`YouTube 댓글 데이터 (${youtubeComments}개 댓글)`}
                >
                  YouTube
                  {youtubeComments > 0 && (
                    <span className="filter-count">({youtubeComments})</span>
                  )}
                </button>
                <button
                  className={selectedPlatform === 'twitter' ? 'active' : ''}
                  onClick={() => setSelectedPlatform('twitter')}
                  title="Twitter/X 검색 링크"
                >
                  Twitter/X
                </button>
                <button
                  className={selectedPlatform === 'dcinside' ? 'active' : ''}
                  onClick={() => setSelectedPlatform('dcinside')}
                  title={`DC인사이드 데이터 (${dcinsideGalleries.reduce((sum, g) => sum + (g.total_posts || 0), 0)}개 게시글, ${dcComments}개 댓글)`}
                >
                  DC인사이드
                  {dcComments > 0 && (
                    <span className="filter-count">({dcComments})</span>
                  )}
                </button>
              </>
            );
          })()}
        </div>
        
        {/* 플랫폼별 요약 정보 */}
        {platformSummary && (
          <div className="platform-summary">
            <h3>
              {platformSummary.platform === 'youtube' && '📹'}
              {platformSummary.platform === 'telegram' && '💬'}
              {platformSummary.platform === 'rss' && '📰'}
              {platformSummary.platform === 'vuddy' && '🎭'}
              {platformSummary.platform === 'twitter' && '🐦'}
              {platformSummary.platform === 'instagram' && '📷'}
              {platformSummary.platform === 'facebook' && '👥'}
              {platformSummary.platform === 'threads' && '🧵'}
              {platformSummary.platform === 'dcinside' && '💬'}
              {' '}
              {platformSummary.platform === 'twitter' ? 'Twitter/X' :
               platformSummary.platform === 'instagram' ? 'Instagram' :
               platformSummary.platform === 'facebook' ? 'Facebook' :
               platformSummary.platform === 'threads' ? 'Threads' :
               platformSummary.platform === 'youtube' ? 'YouTube' :
               platformSummary.platform === 'telegram' ? 'Telegram' :
               platformSummary.platform === 'rss' ? 'RSS' :
               platformSummary.platform === 'vuddy' ? 'CreatorBrand' :
               platformSummary.platform === 'dcinside' ? 'DC인사이드' :
               platformSummary.platform.toUpperCase()} 플랫폼 요약
            </h3>
            {/* YouTube 플랫폼 요약 */}
            {platformSummary.platform === 'youtube' && platformSummary.totalItems > 0 && (
              <div className="summary-content">
                <div className="summary-stats" style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', marginBottom: '20px' }}>
                  <div className="summary-stat" style={{ background: '#f0f7ff', padding: '15px 20px', borderRadius: '10px' }}>
                    <span className="summary-label" style={{ color: '#666', fontSize: '13px' }}>검색 키워드</span>
                    <span className="summary-value" style={{ display: 'block', fontSize: '24px', fontWeight: 'bold', color: '#1976d2' }}>{platformSummary.totalItems}개</span>
                  </div>
                  <div className="summary-stat" style={{ background: '#fff3e0', padding: '15px 20px', borderRadius: '10px' }}>
                    <span className="summary-label" style={{ color: '#666', fontSize: '13px' }}>분석된 영상</span>
                    <span className="summary-value" style={{ display: 'block', fontSize: '24px', fontWeight: 'bold', color: '#f57c00' }}>{platformSummary.totalVideos}개</span>
                  </div>
                  <div className="summary-stat" style={{ background: '#e8f5e9', padding: '15px 20px', borderRadius: '10px' }}>
                    <span className="summary-label" style={{ color: '#666', fontSize: '13px' }}>수집된 댓글</span>
                    <span className="summary-value" style={{ display: 'block', fontSize: '24px', fontWeight: 'bold', color: '#388e3c' }}>{platformSummary.totalComments}개</span>
                  </div>
                </div>
                <div style={{ background: '#fafafa', padding: '15px', borderRadius: '8px', fontSize: '13px', color: '#666' }}>
                  <strong>📊 키워드별 데이터:</strong>
                  <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {(platformSummary.channels || []).slice(0, 10).map((ch, idx) => (
                      <span key={idx} style={{ background: '#e3f2fd', padding: '5px 10px', borderRadius: '15px', fontSize: '12px' }}>
                        {ch.channel_title || ch.channel}: {ch.total_comments || 0}개 댓글
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Twitter/X 플랫폼 요약 */}
            {platformSummary.platform === 'twitter' && (
              <div className="summary-content">
                <div style={{ background: '#e8f5fe', padding: '20px', borderRadius: '12px', marginBottom: '15px' }}>
                  <p style={{ margin: 0, color: '#1da1f2', fontWeight: 'bold', fontSize: '15px' }}>
                    🐦 Twitter/X 검색 링크 기반 모니터링
                  </p>
                  <p style={{ margin: '10px 0 0 0', color: '#666', fontSize: '13px' }}>
                    아래 키워드 버튼을 클릭하면 Twitter에서 실시간 검색 결과를 확인할 수 있습니다.
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  <div style={{ background: '#fafafa', padding: '12px', borderRadius: '8px', flex: '1', minWidth: '200px' }}>
                    <div style={{ fontSize: '12px', color: '#1da1f2', marginBottom: '8px', fontWeight: 'bold' }}>🎤 크리에이터</div>
                    <div style={{ fontSize: '13px', color: '#333' }}>크리에이터브랜드, 예시기업, 스코시즘, 아카이브, 바라바라, 이브닛, u32, 여르미, 한결, 비몽, 샤르망, 나나문</div>
                  </div>
                  <div style={{ background: '#fafafa', padding: '12px', borderRadius: '8px', flex: '1', minWidth: '200px' }}>
                    <div style={{ fontSize: '12px', color: '#9c27b0', marginBottom: '8px', fontWeight: 'bold' }}>🔍 복합 검색</div>
                    <div style={{ fontSize: '13px', color: '#333' }}>멤버 이름 + 굿즈 (예: 여르미 굿즈, 한결 굿즈 등)</div>
                  </div>
                </div>
              </div>
            )}

            {/* DC인사이드 플랫폼 요약 */}
            {platformSummary.platform === 'dcinside' && platformSummary.totalItems > 0 && (
              <div className="summary-content">
                <div className="summary-stats" style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', marginBottom: '20px' }}>
                  <div className="summary-stat" style={{ background: '#e3f2fd', padding: '15px 20px', borderRadius: '10px' }}>
                    <span className="summary-label" style={{ color: '#666', fontSize: '13px' }}>모니터링 갤러리</span>
                    <span className="summary-value" style={{ display: 'block', fontSize: '24px', fontWeight: 'bold', color: '#1565c0' }}>{platformSummary.totalItems}개</span>
                  </div>
                  <div className="summary-stat" style={{ background: '#fff3e0', padding: '15px 20px', borderRadius: '10px' }}>
                    <span className="summary-label" style={{ color: '#666', fontSize: '13px' }}>수집된 게시글</span>
                    <span className="summary-value" style={{ display: 'block', fontSize: '24px', fontWeight: 'bold', color: '#ef6c00' }}>{platformSummary.totalPosts}개</span>
                  </div>
                  <div className="summary-stat" style={{ background: '#e8f5e9', padding: '15px 20px', borderRadius: '10px' }}>
                    <span className="summary-label" style={{ color: '#666', fontSize: '13px' }}>긍정 반응</span>
                    <span className="summary-value" style={{ display: 'block', fontSize: '24px', fontWeight: 'bold', color: '#2e7d32' }}>{platformSummary.positiveCount || 0}개</span>
                  </div>
                  <div className="summary-stat" style={{ background: '#ffebee', padding: '15px 20px', borderRadius: '10px' }}>
                    <span className="summary-label" style={{ color: '#666', fontSize: '13px' }}>부정 반응</span>
                    <span className="summary-value" style={{ display: 'block', fontSize: '24px', fontWeight: 'bold', color: '#c62828' }}>{platformSummary.negativeCount || 0}개</span>
                  </div>
                </div>
              </div>
            )}

            {/* 데이터 없는 경우 */}
            {platformSummary.totalItems === 0 && !platformSummary.isSearchLinkBased && (
              <div className="summary-empty">
                <p>해당 플랫폼에서 수집된 데이터가 없습니다.</p>
                <div className="platform-guide">
                  {platformSummary.platform === 'youtube' && (
                    <p className="guide-text">
                      💡 YouTube 크롤러를 실행하여 영상과 댓글을 수집하세요.
                    </p>
                  )}
                  {platformSummary.platform === 'dcinside' && (
                    <p className="guide-text">
                      💡 DC인사이드 크롤러를 실행하여 갤러리 게시글을 수집하세요.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 상세 페이지 링크 섹션 */}
      <div style={{ marginTop: '40px', padding: '20px', textAlign: 'center', borderTop: '2px solid #e0e0e0' }}>
        <div style={{ display: 'flex', gap: '20px', justifyContent: 'center', flexWrap: 'wrap' }}>
          <a 
            href="/akaiv-studio" 
            onClick={(e) => {
              e.preventDefault();
              window.history.pushState({}, '', '/akaiv-studio');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
            style={{
              display: 'inline-block',
              padding: '12px 24px',
              background: '#667eea',
              color: '#ffffff',
              textDecoration: 'none',
              borderRadius: '8px',
              fontWeight: 'bold',
              fontSize: '16px',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 8px rgba(0,0,0,0.1)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#764ba2';
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = '0 6px 12px rgba(0,0,0,0.15)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#667eea';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
            }}
          >
            🎭 AkaiV Studio 상세 페이지 →
          </a>
          <a 
            href="/skoshism" 
            onClick={(e) => {
              e.preventDefault();
              window.history.pushState({}, '', '/skoshism');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
            style={{
              display: 'inline-block',
              padding: '12px 24px',
              background: '#0253fe',
              color: '#ffffff',
              textDecoration: 'none',
              borderRadius: '8px',
              fontWeight: 'bold',
              fontSize: '16px',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 8px rgba(0,0,0,0.1)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#0041cc';
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = '0 6px 12px rgba(0,0,0,0.15)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#0253fe';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
            }}
          >
            🎵 SKOSHISM 상세 페이지 →
          </a>
          <a
            href="/barabara"
            onClick={(e) => {
              e.preventDefault();
              window.history.pushState({}, '', '/barabara');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
            style={{
              display: 'inline-block',
              padding: '12px 24px',
              background: '#ff6b6b',
              color: '#ffffff',
              textDecoration: 'none',
              borderRadius: '8px',
              fontWeight: 'bold',
              fontSize: '16px',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 8px rgba(0,0,0,0.1)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#ee5a5a';
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = '0 6px 12px rgba(0,0,0,0.15)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#ff6b6b';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
            }}
          >
            🎤 BARABARA 상세 페이지 →
          </a>
          <a
            href="/psy-chord"
            onClick={(e) => {
              e.preventDefault();
              window.history.pushState({}, '', '/psy-chord');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
            style={{
              display: 'inline-block',
              padding: '12px 24px',
              background: '#9b59b6',
              color: '#ffffff',
              textDecoration: 'none',
              borderRadius: '8px',
              fontWeight: 'bold',
              fontSize: '16px',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 8px rgba(0,0,0,0.1)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#8e44ad';
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = '0 6px 12px rgba(0,0,0,0.15)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#9b59b6';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
            }}
          >
            🎸 PSY_CHORD 상세 페이지 →
          </a>
        </div>
      </div>
                  
    </div>
  );
}

export default Dashboard;

