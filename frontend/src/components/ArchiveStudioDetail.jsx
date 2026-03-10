import React, { useState, useEffect } from 'react';
import './Dashboard.css';

// 감정 분석 함수 (Dashboard.jsx와 동일)
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

// 모니터링 키워드 (Dashboard.jsx와 동일)
const MONITORING_KEYWORDS = [
  // ★★★ 최우선순위: 보안/해킹 관련 ★★★
  '해킹', '해킹당함', '해킹됨', 'hack', 'hacked', 'hacking',
  '보안', 'security', '유출', 'leak', 'leaked', '정보유출',
  '계정탈취', '계정해킹', '비밀번호', 'password', '피싱', 'phishing',
  '사기', 'scam', '개인정보', '침해', 'DDoS', '악성코드', 'malware',
  // ★★★ 최우선순위: 크리에이터 이름 및 별명 ★★★
  '아카이브', 'archive', '바라바라', 'barabara', '이브닛', 'ivnit', '스코시즘', 'skoshism',
  'u32', '사미', '우사미',
  '여르미', '엶',
  '한결', '결',
  '비몽', '몽',
  '샤르망', '쭈쭈',
  '나나문', '쿠우',
  // ★★★ 최우선순위: 버디 및 레벨스 ★★★
  '버디', 'vuddy', '레벨스', 'levvels', 'Levvels',
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
  // 성별 관련 키워드
  '남성', '여성', '남자', '여자', '남캐', '여캐', '남버튜버', '여버튜버',
  '오빠', '언니', '누나', '형'
];

// 키워드 카테고리 (우선순위 순)
const KEYWORD_CATEGORIES = {
  // ★★★ 최우선순위: 보안 ★★★
  '🚨보안/해킹': ['해킹', '해킹당함', '해킹됨', 'hack', 'hacked', 'hacking', '보안', 'security', '유출', 'leak', 'leaked', '정보유출', '계정탈취', '계정해킹', '비밀번호', 'password', '피싱', 'phishing', '사기', 'scam', '개인정보', '침해', 'DDoS', '악성코드', 'malware'],
  // ★★★ 최우선순위 카테고리 ★★★
  '크리에이터': ['아카이브', 'archive', '바라바라', 'barabara', '이브닛', 'ivnit', '스코시즘', 'skoshism', 'u32', '사미', '우사미', '여르미', '엶', '한결', '결', '비몽', '몽', '샤르망', '쭈쭈', '나나문', '쿠우'],
  '버디/레벨스': ['버디', 'vuddy', '레벨스', 'levvels', 'Levvels'],
  '굿즈/상품': ['굿즈', '포토카드', '포카', '아크릴', '키링', '스티커', '포스터', '엽서', '앨범', '음반', '한정판', '시즌그리팅', '캘린더', '머치', '공식굿즈'],
  // ★★ 높은 우선순위 카테고리 ★★
  '판매/구매': ['구매', '판매', '주문', '예약', '결제', '배송', '품절', '재입고', '가격', '할인', '이벤트', '특전'],
  '팬활동': ['팬싸', '영통팬싸', '응모', '당첨', '럭드', '포토타임', '생일카페', '서포트', '조공'],
  '디지털상품': ['음원', '다운로드', '디지털싱글', '뮤직비디오', 'MV', '티저', '커버곡', '오리지널곡', '멤버십', '후원', '슈퍼챗', '보이스팩', '월페이퍼', '보팩', '펀딩'],
  // 일반 카테고리
  '활동': ['버튜버', 'vtuber', '크리에이터', '유튜버', '숲'],
  '콘텐츠': ['노래', '커버', '방송', '영상', '브이로그', 'vlog', 'ASMR', '라이브', '스트리밍'],
  '반응': ['좋아요', '구독', '최고', '대박', '감동', '응원', '팬', '힐링'],
  '품질': ['감성', '편집', '퀄리티', '목소리', '실력'],
  '성별': ['남성', '여성', '남자', '여자', '남캐', '여캐', '남버튜버', '여버튜버', '오빠', '언니', '누나', '형']
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

// 감성 분포 계산 (SKOSHISM 스타일)
const calculateSentimentDistribution = (commentSamples) => {
  if (!commentSamples || commentSamples.length === 0) return { positive: 0, neutral: 0, negative: 0 };

  const sentiments = commentSamples.map(c => analyzeSentiment(c.text));
  const total = sentiments.length;
  if (total === 0) return { positive: 0, neutral: 0, negative: 0 };

  return {
    positive: sentiments.filter(s => s === 'positive').length / total,
    neutral: sentiments.filter(s => s === 'neutral').length / total,
    negative: sentiments.filter(s => s === 'negative').length / total
  };
};

function ArchiveStudioDetail() {
  const [vuddyCreators, setVuddyCreators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedCreators, setExpandedCreators] = useState({});
  const [lastCrawled, setLastCrawled] = useState('');
  const [commentDisplayLimit, setCommentDisplayLimit] = useState({});  // 크리에이터별 댓글 표시 개수
  const INITIAL_COMMENT_COUNT = 5;  // 초기 표시 댓글 수
  const LOAD_MORE_COUNT = 10;  // 더보기 시 추가 댓글 수

  useEffect(() => {
    loadArchiveStudioCreators();
  }, []);

  const loadArchiveStudioCreators = async () => {
    setLoading(true);
    try {
      // 캐시 무효화를 위한 타임스탬프 추가
      const timestamp = new Date().getTime();
      const vuddyResponse = await fetch(`/api/akaiv-studio/members?_t=${timestamp}`, {
        cache: 'no-cache',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      });

      if (vuddyResponse.ok) {
        const vuddyData = await vuddyResponse.json();

        // 수집 날짜 저장
        if (vuddyData.last_crawled) {
          setLastCrawled(vuddyData.last_crawled);
        }

        if (vuddyData.creators && vuddyData.creators.length > 0) {
          // 모든 크리에이터 직접 사용 (이미 5명만 반환됨)
          const archiveCreators = vuddyData.creators;

          setVuddyCreators(archiveCreators);
        } else {
          setVuddyCreators([]);
        }
      } else {
        setVuddyCreators([]);
      }
    } catch (error) {
      setVuddyCreators([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleCreatorDetails = (creatorName) => {
    setExpandedCreators(prev => ({
      ...prev,
      [creatorName]: !prev[creatorName]
    }));
  };

  // 크리에이터별 현재 표시 댓글 수 가져오기
  const getCommentDisplayLimit = (creatorName) => {
    return commentDisplayLimit[creatorName] || INITIAL_COMMENT_COUNT;
  };

  // 댓글 더보기
  const loadMoreComments = (creatorName, totalComments) => {
    setCommentDisplayLimit(prev => {
      const current = prev[creatorName] || INITIAL_COMMENT_COUNT;
      const newLimit = Math.min(current + LOAD_MORE_COUNT, totalComments);
      return {
        ...prev,
        [creatorName]: newLimit
      };
    });
  };

  // 타임존 정보가 없는 경우 UTC로 간주하여 파싱
  const parseAsUTC = (dateString) => {
    if (!dateString) return null;
    // 이미 타임존 정보가 있으면 그대로 사용
    if (dateString.includes('+') || dateString.includes('Z') || dateString.includes('-', 10)) {
      return new Date(dateString);
    }
    // 타임존 정보가 없으면 UTC로 간주
    return new Date(dateString + 'Z');
  };

  const toKSTDate = (dateString) => {
    if (!dateString) return '';
    try {
      const date = parseAsUTC(dateString);
      if (!date || isNaN(date.getTime())) return '';

      // 더 자세한 날짜 형식으로 표시
      return date.toLocaleString('ko-KR', {
        timeZone: 'Asia/Seoul',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      });
    } catch (e) {
      return '';
    }
  };

  const toKSTDateShort = (dateString) => {
    if (!dateString) return '';
    try {
      const date = parseAsUTC(dateString);
      if (!date || isNaN(date.getTime())) return '';

      // 간단한 날짜 형식 (YYYY.MM.DD HH:MM)
      return date.toLocaleString('ko-KR', {
        timeZone: 'Asia/Seoul',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      }).replace(/\. /g, '.').replace(/\.$/, '');
    } catch (e) {
      return '';
    }
  };

  // URL에서 플랫폼 감지
  const getPlatformInfo = (url) => {
    if (!url) return { name: 'Link', badge: 'link', icon: '🔗', color: '#666' };

    const urlLower = url.toLowerCase();

    if (urlLower.includes('namu.wiki')) {
      return { name: '나무위키', badge: 'namuwiki', icon: '🌿', color: '#00a495' };
    }
    if (urlLower.includes('youtube.com') || urlLower.includes('youtu.be')) {
      return { name: 'YouTube', badge: 'youtube', icon: '📺', color: '#ff0000' };
    }
    if (urlLower.includes('twitter.com') || urlLower.includes('x.com')) {
      return { name: 'Twitter', badge: 'twitter', icon: '🐦', color: '#1da1f2' };
    }
    if (urlLower.includes('naver.com')) {
      return { name: 'Naver', badge: 'naver', icon: '🟢', color: '#03c75a' };
    }
    if (urlLower.includes('cafe.naver.com')) {
      return { name: '네이버 카페', badge: 'naver-cafe', icon: '☕', color: '#03c75a' };
    }
    if (urlLower.includes('soop.gg')) {
      return { name: 'SOOP', badge: 'soop', icon: '🎮', color: '#5865f2' };
    }
    if (urlLower.includes('chzzk.naver.com')) {
      return { name: 'CHZZK', badge: 'chzzk', icon: '📡', color: '#00ff7f' };
    }

    return { name: 'Google', badge: 'google', icon: '🔍', color: '#4285f4' };
  };

  // 크리에이터 이름에서 AkaiV 제거 (검색용)
  const cleanCreatorNameForSearch = (creatorName) => {
    if (!creatorName) return '';
    
    // AkaiV 관련 키워드 제거
    let cleaned = creatorName
      .replace(/AkaiV\s*Studio/gi, '')
      .replace(/AkaiV/gi, '')
      .replace(/akaiv/gi, '')
      .replace(/AKAIV/gi, '')
      .replace(/아카이브\s*스튜디오/gi, '')
      .replace(/아카이브스튜디오/gi, '')
      .replace(/\s+/g, ' ')
      .trim();
    
    // 멤버 이름 매핑
    const memberMapping = {
      '여르미': '여르미',
      '한결': '한결',
      '비몽': '비몽',
      '샤르망': '샤르망',
      'u32': 'u32',
      '우사미': 'u32'
    };
    
    // 매핑된 이름 찾기
    for (const [key, value] of Object.entries(memberMapping)) {
      if (cleaned.includes(key) || creatorName.includes(key)) {
        return value;
      }
    }
    
    return cleaned || creatorName;
  };

  // 크리에이터별 직접 링크 매핑
  const getCreatorDirectLinks = (creatorName) => {
    const nameMapping = {
      '한결': {
        namuwiki: 'https://namu.wiki/w/%ED%95%9C%EA%B2%B0(%EC%9D%B8%ED%84%B0%EB%84%B7%20%EB%B0%A9%EC%86%A1%EC%9D%B8)',
        'naver-cafe': 'https://cafe.naver.com/hangyeol62nono.cafe?utm_source=akaiv&utm_medium=social&utm_campaign=hangyeol&utm_content=Cafe'
      },
      '비몽': {
        namuwiki: 'https://namu.wiki/w/%EB%B9%84%EB%AA%BD(%EC%9D%B8%ED%84%B0%EB%84%B7%20%EB%B0%A9%EC%86%A1%EC%9D%B8)',
        'naver-cafe': 'https://cafe.naver.com/catcloudmong.cafe?utm_source=akaiv&utm_medium=social&utm_campaign=beemong&utm_content=Cafe'
      },
      'u32': {
        'naver-cafe': 'https://cafe.naver.com/u32rabbithole.cafe?utm_source=akaiv&utm_medium=social&utm_campaign=u32&utm_content=Cafe'
      },
      '우사미': {
        'naver-cafe': 'https://cafe.naver.com/u32rabbithole.cafe?utm_source=akaiv&utm_medium=social&utm_campaign=u32&utm_content=Cafe'
      },
      '여르미': {
        'naver-cafe': 'https://cafe.naver.com/yeorumirium.cafe?utm_source=akaiv&utm_medium=social&utm_campaign=yeorumi&utm_content=Cafe'
      },
      '샤르망': {
        'naver-cafe': 'https://cafe.naver.com/owozzz.cafe?utm_source=akaiv&utm_medium=social&utm_campaign=charmante&utm_content=Cafe'
      }
    };

    // 크리에이터 이름 매칭
    for (const [key, links] of Object.entries(nameMapping)) {
      if (creatorName.includes(key) || key.includes(creatorName)) {
        return links;
      }
    }
    return {};
  };

  // 플랫폼별 검색 URL 생성
  const getPlatformSearchUrl = (platformKey, creatorName) => {
    // 먼저 직접 링크가 있는지 확인
    const directLinks = getCreatorDirectLinks(creatorName);
    if (directLinks[platformKey]) {
      return directLinks[platformKey];
    }

    // 직접 링크가 없으면 검색 URL 생성
    const cleanedName = cleanCreatorNameForSearch(creatorName);
    const encodedName = encodeURIComponent(cleanedName);
    
    switch (platformKey) {
      case 'youtube':
        return `https://www.youtube.com/results?search_query=${encodedName}`;
      case 'twitter':
        return `https://twitter.com/search?q=${encodedName}`;
      case 'naver':
      case 'naver-cafe':
        return `https://search.naver.com/search.naver?query=${encodedName}`;
      case 'namuwiki':
        return `https://namu.wiki/w/${encodedName}`;
      default:
        return `https://www.google.com/search?q=${encodedName}`;
    }
  };

  return (
    <div className="akaiv-studio-detail-page" style={{ padding: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* 헤더 섹션 */}
      <div className="dashboard-header" style={{ 
        background: 'linear-gradient(135deg, #0253fe 0%, #0041cc 100%)',
        padding: '32px 40px',
        borderRadius: '16px',
        marginBottom: '32px',
        boxShadow: '0 8px 24px rgba(2, 83, 254, 0.25)',
        color: 'white',
        position: 'relative',
        overflow: 'hidden'
      }}>
        {/* 배경 장식 */}
        <div style={{
          position: 'absolute',
          top: '-50%',
          right: '-10%',
          width: '300px',
          height: '300px',
          background: 'rgba(255, 255, 255, 0.1)',
          borderRadius: '50%',
          filter: 'blur(60px)'
        }}></div>
        <div style={{
          position: 'absolute',
          bottom: '-30%',
          left: '-5%',
          width: '200px',
          height: '200px',
          background: 'rgba(255, 255, 255, 0.08)',
          borderRadius: '50%',
          filter: 'blur(40px)'
        }}></div>

        <div style={{ position: 'relative', zIndex: 1 }}>
          {/* 상단: 제목과 버튼 */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'flex-start',
            marginBottom: '24px',
            flexWrap: 'wrap',
            gap: '16px'
          }}>
            <div style={{ flex: 1, minWidth: '300px' }}>
              <h1 style={{ 
                margin: '0 0 12px 0', 
                fontSize: '32px', 
                fontWeight: '800',
                color: '#ffffff',
                lineHeight: '1.2',
                textShadow: '0 2px 8px rgba(0,0,0,0.2)'
              }}>
                🎭 AkaiV Studio 소속 크리에이터 종합 분석
              </h1>
              <p style={{ 
                margin: '0', 
                fontSize: '16px', 
                color: 'rgba(255,255,255,0.95)',
                lineHeight: '1.6',
                fontWeight: '500'
              }}>
                {vuddyCreators.length > 0 ? `${vuddyCreators.length}명의 크리에이터` : '5명의 크리에이터'} (u32, 여르미, 한결, 비몽, 샤르망) 수집 및 분석 데이터
              </p>
            </div>
            <button 
              className="btn-back"
              onClick={() => {
                window.history.pushState({}, '', '/');
                window.dispatchEvent(new PopStateEvent('popstate'));
              }}
              style={{
                background: 'rgba(255, 255, 255, 0.2)',
                color: 'white',
                border: '2px solid rgba(255, 255, 255, 0.3)',
                padding: '12px 24px',
                borderRadius: '10px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '700',
                transition: 'all 0.3s ease',
                backdropFilter: 'blur(10px)',
                whiteSpace: 'nowrap',
                boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.3)';
                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.5)';
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 6px 16px rgba(0,0,0,0.2)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)';
                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.3)';
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
              }}
            >
              ← 대시보드로 돌아가기
            </button>
          </div>

          {/* 하단: 날짜 정보 */}
          {lastCrawled && (
            <div style={{ 
              display: 'inline-flex',
              alignItems: 'center',
              padding: '12px 20px',
              background: 'rgba(255, 255, 255, 0.15)',
              borderRadius: '10px',
              fontSize: '14px',
              color: 'rgba(255,255,255,0.95)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              fontWeight: '500',
              backdropFilter: 'blur(10px)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
            }}>
              <span style={{ 
                marginRight: '10px', 
                fontSize: '18px',
                filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.2))'
              }}>
                📅
              </span>
              <span style={{ fontWeight: '600', marginRight: '8px' }}>마지막 수집 날짜:</span>
              <span style={{ fontWeight: '700', fontSize: '15px' }}>{toKSTDate(lastCrawled)}</span>
            </div>
          )}
        </div>
      </div>

      {loading ? (
        <div className="dashboard-loading">
          <div className="spinner"></div>
          <p>AkaiV Studio 크리에이터 데이터를 불러오는 중...</p>
          <p style={{ fontSize: '12px', color: '#666', marginTop: '10px' }}>
            브라우저 콘솔에서 로딩 상태를 확인할 수 있습니다.
          </p>
        </div>
      ) : vuddyCreators && vuddyCreators.length > 0 ? (
        <div className="creators-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '24px' }}>
          {vuddyCreators.map((creator, index) => {
            // SKOSHISM 스타일: 실제 댓글에서 감정 분석 계산
            const sentimentDist = calculateSentimentDistribution(creator.comment_samples);
            const overallSentiment = sentimentDist.positive > sentimentDist.negative ? 'positive' :
                                    sentimentDist.negative > sentimentDist.positive ? 'negative' : 'neutral';
            const overallScore = Math.round((sentimentDist.positive * 100) + (sentimentDist.neutral * 50) + (sentimentDist.negative * 0));

            return (
            <div key={index} className="creator-card" style={{
              background: '#ffffff',
              border: '2px solid #e0e0e0',
              borderRadius: '12px',
              padding: '24px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              transition: 'all 0.3s ease'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}>
              {/* 크리에이터 헤더 */}
              <div style={{ marginBottom: '20px', paddingBottom: '16px', borderBottom: '2px solid #f0f0f0' }}>
                <h3 style={{ 
                  margin: '0 0 8px 0', 
                  fontSize: '22px', 
                  fontWeight: 'bold',
                  color: '#333'
                }}>
                  {creator.name}
                </h3>
                {creator.last_crawled && (
                  <p style={{ fontSize: '12px', color: '#888', margin: '0 0 12px 0' }}>
                    📅 수집: {toKSTDateShort(creator.last_crawled)}
                  </p>
                )}
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  {creator.vuddy_channel && (
                    <a
                      href={creator.vuddy_channel}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        padding: '6px 12px',
                        background: '#667eea',
                        color: 'white',
                        textDecoration: 'none',
                        borderRadius: '6px',
                        fontSize: '13px',
                        fontWeight: 'bold',
                        transition: 'all 0.2s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#5568d3';
                        e.currentTarget.style.transform = 'scale(1.05)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = '#667eea';
                        e.currentTarget.style.transform = 'scale(1)';
                      }}
                    >
                      🛍️ Vuddy 채널
                    </a>
                  )}
                </div>
              </div>

              {/* 통계 섹션 */}
              <div className="creator-stats" style={{ marginBottom: '20px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px', marginBottom: '12px' }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px',
                    background: '#f8f9fa',
                    borderRadius: '8px',
                    border: '1px solid #e9ecef'
                  }}>
                    <span style={{ fontSize: '24px' }}>💬</span>
                    <div>
                      <div style={{ fontSize: '11px', color: '#666', marginBottom: '2px' }}>댓글</div>
                      <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#333' }}>
                        {creator.total_comments || 0}
                      </div>
                    </div>
                  </div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px',
                    background: '#f8f9fa',
                    borderRadius: '8px',
                    border: '1px solid #e9ecef'
                  }}>
                    <span style={{ fontSize: '24px' }}>👍</span>
                    <div>
                      <div style={{ fontSize: '11px', color: '#666', marginBottom: '2px' }}>좋아요</div>
                      <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#333' }}>
                        {creator.total_likes || 0}
                      </div>
                    </div>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px',
                    background: '#f8f9fa',
                    borderRadius: '8px',
                    border: '1px solid #e9ecef'
                  }}>
                    <span style={{ fontSize: '24px' }}>📰</span>
                    <div>
                      <div style={{ fontSize: '11px', color: '#666', marginBottom: '2px' }}>블로그</div>
                      <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#333' }}>
                        {creator.total_blog_posts || 0}
                      </div>
                    </div>
                  </div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px',
                    background: '#f8f9fa',
                    borderRadius: '8px',
                    border: '1px solid #e9ecef'
                  }}>
                    <span style={{ fontSize: '24px' }}>🔍</span>
                    <div>
                      <div style={{ fontSize: '11px', color: '#666', marginBottom: '2px' }}>구글 결과</div>
                      <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#333' }}>
                        {creator.total_google_results || 0}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 플랫폼 바로가기 링크 */}
              {(() => {
                // Google 링크에서 플랫폼 그룹화
                const platformGroups = {};
                if (creator.google_links && creator.google_links.length > 0) {
                  creator.google_links.slice(0, 10).forEach((link) => {
                    const platform = getPlatformInfo(link.url);
                    const platformKey = platform.badge;
                    if (!platformGroups[platformKey]) {
                      platformGroups[platformKey] = { name: platform.name, links: [] };
                    }
                    platformGroups[platformKey].links.push(link);
                  });
                }

                // 크리에이터별 직접 링크 추가
                const directLinks = getCreatorDirectLinks(creator.name);
                
                // 나무위키 직접 링크가 있으면 추가
                if (directLinks.namuwiki && !platformGroups.namuwiki) {
                  platformGroups.namuwiki = { 
                    name: '나무위키', 
                    links: [{ url: directLinks.namuwiki, title: `${creator.name} - 나무위키` }] 
                  };
                }
                
                // 네이버 카페 직접 링크가 있으면 추가
                if (directLinks['naver-cafe'] && !platformGroups['naver-cafe']) {
                  platformGroups['naver-cafe'] = { 
                    name: '네이버 카페', 
                    links: [{ url: directLinks['naver-cafe'], title: `${creator.name} - 네이버 카페` }] 
                  };
                }

                const platformDisplayNames = {
                  'youtube': 'YouTube',
                  'twitter': 'Twitter (X)',
                  'naver': '네이버',
                  'naver-cafe': '네이버 카페',
                  'namuwiki': '나무위키',
                  'soop': 'SOOP',
                  'chzzk': 'CHZZK',
                  'google': 'Google',
                  'link': 'Link'
                };

                const platformOrder = ['youtube', 'twitter', 'namuwiki', 'naver-cafe', 'naver', 'soop', 'chzzk', 'google', 'link'];
                const availablePlatforms = platformOrder.filter(key => platformGroups[key]);

                if (availablePlatforms.length > 0) {
                  return (
                    <div style={{
                      marginBottom: '20px',
                      padding: '20px',
                      background: '#ffffff',
                      borderRadius: '8px',
                      border: '2px solid #e9ecef',
                      boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                    }}>
                      <div style={{ 
                        fontSize: '14px', 
                        color: '#333', 
                        marginBottom: '16px', 
                        fontWeight: 'bold',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}>
                        <span style={{ fontSize: '18px' }}>🔗</span>
                        플랫폼 바로가기
                      </div>
                      <div style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '10px'
                      }}>
                        {availablePlatforms.map((platformKey) => {
                          const displayName = platformDisplayNames[platformKey] || platformGroups[platformKey].name;
                          const searchUrl = getPlatformSearchUrl(platformKey, creator.name);
                          const platformInfo = getPlatformInfo(platformGroups[platformKey].links[0]?.url || '');

                          return (
                            <a
                              key={platformKey}
                              href={searchUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '10px 16px',
                                background: platformInfo.color || '#667eea',
                                color: 'white',
                                textDecoration: 'none',
                                borderRadius: '8px',
                                fontSize: '13px',
                                fontWeight: '600',
                                transition: 'all 0.2s ease',
                                boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                                border: '1px solid rgba(255,255,255,0.2)'
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.transform = 'translateY(-2px)';
                                e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)';
                                e.currentTarget.style.opacity = '0.9';
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.transform = 'translateY(0)';
                                e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                                e.currentTarget.style.opacity = '1';
                              }}
                            >
                              <span style={{ fontSize: '16px' }}>{platformInfo.icon || '🔗'}</span>
                              <span>{displayName}</span>
                            </a>
                          );
                        })}
                      </div>
                    </div>
                  );
                }
                return null;
              })()}

              {/* 상태 배지 */}
              <div style={{ 
                display: 'flex', 
                gap: '8px', 
                marginBottom: '20px',
                flexWrap: 'wrap'
              }}>
                <span style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  background: creator.youtube_search_status === 'success' ? '#d4edda' : '#fff3cd',
                  color: creator.youtube_search_status === 'success' ? '#155724' : '#856404',
                  border: `1px solid ${creator.youtube_search_status === 'success' ? '#c3e6cb' : '#ffeaa7'}`
                }}>
                  YouTube {creator.youtube_search_status === 'success' ? '✓' : '○'}
                </span>
                <span style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  background: creator.blog_search_status === 'success' ? '#d4edda' : '#fff3cd',
                  color: creator.blog_search_status === 'success' ? '#155724' : '#856404',
                  border: `1px solid ${creator.blog_search_status === 'success' ? '#c3e6cb' : '#ffeaa7'}`
                }}>
                  블로그 {creator.blog_search_status === 'success' ? '✓' : '○'}
                </span>
                <span style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  background: creator.google_search_status === 'success' ? '#d4edda' : '#fff3cd',
                  color: creator.google_search_status === 'success' ? '#155724' : '#856404',
                  border: `1px solid ${creator.google_search_status === 'success' ? '#c3e6cb' : '#ffeaa7'}`
                }}>
                  구글 {creator.google_search_status === 'success' ? '✓' : '○'}
                </span>
              </div>

              {/* 토글 버튼 */}
              <div style={{ marginTop: '20px' }}>
                <button
                  onClick={() => toggleCreatorDetails(creator.name)}
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: expandedCreators[creator.name] ? '#667eea' : '#f8f9fa',
                    color: expandedCreators[creator.name] ? 'white' : '#667eea',
                    border: `2px solid ${expandedCreators[creator.name] ? '#667eea' : '#667eea'}`,
                    borderRadius: '8px',
                    fontSize: '14px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    transition: 'all 0.3s ease'
                  }}
                  onMouseEnter={(e) => {
                    if (!expandedCreators[creator.name]) {
                      e.currentTarget.style.background = '#667eea';
                      e.currentTarget.style.color = 'white';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!expandedCreators[creator.name]) {
                      e.currentTarget.style.background = '#f8f9fa';
                      e.currentTarget.style.color = '#667eea';
                    }
                  }}
                >
                  {expandedCreators[creator.name] ? '▲ 상세 내역 숨기기' : '▼ 상세 내역 보기'}
                </button>
              </div>

              {/* 댓글 분석 및 요약 - 항상 표시 */}
              <div className="creator-analysis" style={{ 
                display: expandedCreators[creator.name] ? 'block' : 'none',
                marginTop: '24px',
                paddingTop: '24px',
                borderTop: '2px solid #f0f0f0'
              }}>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '24px',
                  paddingBottom: '16px',
                  borderBottom: '2px solid #f0f0f0'
                }}>
                  <h4 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', color: '#333' }}>
                    📊 댓글 분석 및 요약
                  </h4>
                  <div style={{
                    padding: '8px 16px',
                    borderRadius: '20px',
                    fontSize: '14px',
                    fontWeight: 'bold',
                    background: overallScore >= 70 ? '#d4edda' : overallScore >= 40 ? '#fff3cd' : '#f8d7da',
                    color: overallScore >= 70 ? '#155724' : overallScore >= 40 ? '#856404' : '#721c24',
                    border: `2px solid ${overallScore >= 70 ? '#c3e6cb' : overallScore >= 40 ? '#ffeaa7' : '#f5c6cb'}`
                  }}>
                    {overallScore}점
                  </div>
                </div>

                {/* 감성 분석 - SKOSHISM 스타일 */}
                <div style={{
                  marginBottom: '24px',
                  padding: '16px',
                  background: '#f8f9fa',
                  borderRadius: '8px',
                  border: '1px solid #e9ecef'
                }}>
                  <div style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '12px', color: '#333' }}>
                    감성 분석
                  </div>
                  <div style={{
                    display: 'inline-block',
                    padding: '8px 16px',
                    borderRadius: '20px',
                    fontSize: '13px',
                    fontWeight: 'bold',
                    marginBottom: '12px',
                    background: overallSentiment === 'positive' ? '#d4edda' : overallSentiment === 'negative' ? '#f8d7da' : '#e2e3e5',
                    color: overallSentiment === 'positive' ? '#155724' : overallSentiment === 'negative' ? '#721c24' : '#383d41',
                    border: `2px solid ${overallSentiment === 'positive' ? '#c3e6cb' : overallSentiment === 'negative' ? '#f5c6cb' : '#d6d8db'}`
                  }}>
                    {overallSentiment === 'positive' ? '😊 긍정적' : overallSentiment === 'negative' ? '😢 부정적' : '😐 중립적'}
                  </div>
                  <div>
                    <div style={{
                      display: 'flex',
                      height: '24px',
                      borderRadius: '12px',
                      overflow: 'hidden',
                      marginBottom: '8px',
                      border: '1px solid #dee2e6'
                    }}>
                      <div style={{
                        width: `${Math.round(sentimentDist.positive * 100)}%`,
                        background: '#28a745',
                        transition: 'width 0.3s ease'
                      }}></div>
                      <div style={{
                        width: `${Math.round(sentimentDist.neutral * 100)}%`,
                        background: '#6c757d',
                        transition: 'width 0.3s ease'
                      }}></div>
                      <div style={{
                        width: `${Math.round(sentimentDist.negative * 100)}%`,
                        background: '#dc3545',
                        transition: 'width 0.3s ease'
                      }}></div>
                    </div>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '12px',
                      color: '#666'
                    }}>
                      <span>긍정 {Math.round(sentimentDist.positive * 100)}%</span>
                      <span>중립 {Math.round(sentimentDist.neutral * 100)}%</span>
                      <span>부정 {Math.round(sentimentDist.negative * 100)}%</span>
                    </div>
                  </div>
                </div>

                {/* 모니터링 키워드 분석 - SKOSHISM 스타일 */}
                {creator.comment_samples && creator.comment_samples.length > 0 && (
                  <div style={{
                    marginBottom: '24px',
                    padding: '16px',
                    background: 'linear-gradient(135deg, #fff5f5 0%, #fff 100%)',
                    borderRadius: '8px',
                    border: '2px solid #ff4444'
                  }}>
                    <div style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '16px', color: '#ff4444' }}>
                      🔍 모니터링 키워드 분석
                    </div>
                    {(() => {
                      // 모든 댓글에서 키워드 빈도 계산
                      const keywordFreq = {};
                      const categoryFreq = {};
                      let totalMatches = 0;

                      creator.comment_samples.forEach(comment => {
                        const matched = findMatchingKeywords(comment.text);
                        matched.forEach(keyword => {
                          keywordFreq[keyword] = (keywordFreq[keyword] || 0) + 1;
                          const category = getKeywordCategory(keyword);
                          categoryFreq[category] = (categoryFreq[category] || 0) + 1;
                          totalMatches++;
                        });
                      });

                      const topKeywords = Object.entries(keywordFreq)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 10);

                      const sortedCategories = Object.entries(categoryFreq)
                        .sort((a, b) => b[1] - a[1]);

                      if (totalMatches === 0) {
                        return <p style={{ margin: 0, fontSize: '13px', color: '#999' }}>매칭된 키워드가 없습니다.</p>;
                      }

                      return (
                        <>
                          {/* 카테고리별 통계 */}
                          <div style={{ marginBottom: '16px' }}>
                            <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
                              카테고리별 키워드 빈도 (총 {totalMatches}개 매칭)
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                              {sortedCategories.map(([category, count], idx) => {
                                const categoryColors = {
                                  '🚨보안/해킹': '#dc3545',
                                  '성별': '#c41d7f',
                                  '크리에이터': '#1d39c4',
                                  '버디/레벨스': '#e74c3c',
                                  '굿즈/상품': '#f39c12',
                                  '판매/구매': '#27ae60',
                                  '팬활동': '#e91e63',
                                  '디지털상품': '#0277bd',
                                  '콘텐츠': '#d48806',
                                  '반응': '#0958d9',
                                  '활동': '#722ed1',
                                  '품질': '#8e44ad',
                                  '기타': '#595959'
                                };
                                return (
                                  <div key={idx} style={{
                                    padding: '8px 12px',
                                    background: 'white',
                                    borderRadius: '8px',
                                    border: `2px solid ${categoryColors[category] || '#666'}`,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px'
                                  }}>
                                    <span style={{ fontWeight: 'bold', color: categoryColors[category] || '#666' }}>
                                      {category}
                                    </span>
                                    <span style={{
                                      background: categoryColors[category] || '#666',
                                      color: 'white',
                                      padding: '2px 8px',
                                      borderRadius: '10px',
                                      fontSize: '11px',
                                      fontWeight: 'bold'
                                    }}>
                                      {count}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>

                          {/* 상위 키워드 */}
                          {topKeywords.length > 0 && (
                            <div>
                              <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
                                상위 키워드
                              </div>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                {topKeywords.map(([keyword, count], idx) => {
                                  const category = getKeywordCategory(keyword);
                                  const categoryColors = {
                                    '🚨보안/해킹': { bg: '#fff5f5', color: '#dc3545', border: '#f5c6cb' },
                                    '성별': { bg: '#fff0f6', color: '#c41d7f', border: '#ffadd2' },
                                    '크리에이터': { bg: '#f0f5ff', color: '#1d39c4', border: '#adc6ff' },
                                    '버디/레벨스': { bg: '#fff0f0', color: '#e74c3c', border: '#ffcccb' },
                                    '굿즈/상품': { bg: '#fff8e1', color: '#f39c12', border: '#ffe082' },
                                    '판매/구매': { bg: '#e8f5e9', color: '#27ae60', border: '#a5d6a7' },
                                    '팬활동': { bg: '#fce4ec', color: '#e91e63', border: '#f8bbd9' },
                                    '디지털상품': { bg: '#e1f5fe', color: '#0277bd', border: '#81d4fa' },
                                    '콘텐츠': { bg: '#fffbe6', color: '#d48806', border: '#ffe58f' },
                                    '반응': { bg: '#e6f7ff', color: '#0958d9', border: '#91caff' },
                                    '활동': { bg: '#f9f0ff', color: '#722ed1', border: '#d3adf7' },
                                    '품질': { bg: '#f3e5f5', color: '#8e44ad', border: '#ce93d8' },
                                    '기타': { bg: '#f5f5f5', color: '#595959', border: '#d9d9d9' }
                                  };
                                  const colors = categoryColors[category] || categoryColors['기타'];
                                  return (
                                    <span key={idx} style={{
                                      padding: '4px 10px',
                                      background: colors.bg,
                                      color: colors.color,
                                      borderRadius: '12px',
                                      fontSize: '11px',
                                      fontWeight: 'bold',
                                      border: `1px solid ${colors.border}`,
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      gap: '4px'
                                    }}>
                                      {keyword}
                                      <span style={{
                                        background: colors.color,
                                        color: 'white',
                                        padding: '1px 5px',
                                        borderRadius: '8px',
                                        fontSize: '9px'
                                      }}>
                                        {count}
                                      </span>
                                    </span>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>
                )}
                
              </div>

              {/* 댓글 요약 및 링크 */}
              <div className="creator-resources" style={{ 
                display: expandedCreators[creator.name] ? 'block' : 'none',
                marginTop: '24px',
                paddingTop: '24px',
                borderTop: '2px solid #f0f0f0'
              }}>
                <div style={{
                  marginBottom: '24px',
                  paddingBottom: '16px',
                  borderBottom: '2px solid #f0f0f0'
                }}>
                  <h4 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', color: '#333' }}>
                    📝 댓글 요약 및 관련 자료
                  </h4>
                </div>

                {/* 댓글 요약 - 비디오별 그룹화 */}
                {creator.comment_samples && creator.comment_samples.length > 0 ? (() => {
                  const displayLimit = getCommentDisplayLimit(creator.name);
                  const totalComments = creator.comment_samples.length;
                  const hasMore = displayLimit < totalComments;

                  // 댓글을 비디오별로 그룹화
                  const groupCommentsByVideo = (comments) => {
                    const groups = {};
                    comments.forEach(comment => {
                      const videoKey = comment.video_title || '기타 댓글';
                      if (!groups[videoKey]) {
                        groups[videoKey] = {
                          title: comment.video_title || '기타 댓글',
                          video_url: comment.video_url || '',
                          video_id: comment.video_id || '',
                          comments: [],
                          keywords: {}
                        };
                      }
                      // video_id나 video_url이 없으면 현재 댓글에서 업데이트
                      if (!groups[videoKey].video_id && comment.video_id) {
                        groups[videoKey].video_id = comment.video_id;
                      }
                      if (!groups[videoKey].video_url && comment.video_url) {
                        groups[videoKey].video_url = comment.video_url;
                      }
                      // video_id가 있지만 video_url이 없으면 생성
                      if (groups[videoKey].video_id && !groups[videoKey].video_url) {
                        groups[videoKey].video_url = `https://www.youtube.com/watch?v=${groups[videoKey].video_id}`;
                      }
                      groups[videoKey].comments.push(comment);

                      // 해당 비디오의 키워드 집계
                      const matchedKeywords = findMatchingKeywords(comment.text);
                      matchedKeywords.forEach(kw => {
                        groups[videoKey].keywords[kw] = (groups[videoKey].keywords[kw] || 0) + 1;
                      });
                    });
                    return Object.values(groups).sort((a, b) => b.comments.length - a.comments.length);
                  };

                  const videoGroups = groupCommentsByVideo(creator.comment_samples.slice(0, displayLimit));
                  const allVideoGroups = groupCommentsByVideo(creator.comment_samples);

                  return (
                  <div style={{
                    marginBottom: '24px',
                    padding: '16px',
                    background: '#f8f9fa',
                    borderRadius: '8px',
                    border: '1px solid #e9ecef'
                  }}>
                    <div style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '16px', color: '#333' }}>
                      💬 댓글 요약 ({displayLimit}/{totalComments}개 표시중) - {allVideoGroups.length}개 영상
                    </div>

                    {/* 비디오별 그룹화된 댓글 표시 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                      {videoGroups.map((videoGroup, groupIdx) => {
                        // 비디오 URL 생성
                        let videoUrl = videoGroup.video_url;
                        if (!videoUrl && videoGroup.video_id) {
                          videoUrl = `https://www.youtube.com/watch?v=${videoGroup.video_id}`;
                        }

                        // 비디오 제목 정리
                        const cleanVideoTitle = (videoGroup.title || '')
                          .replace(/AkaiV\s*Studio/gi, '')
                          .replace(/AkaiV/gi, '')
                          .replace(/akaiv/gi, '')
                          .replace(/AKAIV/gi, '')
                          .replace(/아카이브\s*스튜디오/gi, '')
                          .replace(/아카이브스튜디오/gi, '')
                          .replace(/\s+/g, ' ')
                          .trim() || '기타 댓글';

                        // 상위 키워드 추출
                        const topKeywords = Object.entries(videoGroup.keywords)
                          .sort((a, b) => b[1] - a[1])
                          .slice(0, 5);

                        return (
                          <div key={groupIdx} style={{
                            background: 'white',
                            borderRadius: '12px',
                            border: '2px solid #e9ecef',
                            overflow: 'hidden'
                          }}>
                            {/* 비디오 헤더 */}
                            <div style={{
                              padding: '16px',
                              background: 'linear-gradient(135deg, #ff000015 0%, #cc000010 100%)',
                              borderBottom: '2px solid #ff0000',
                              borderLeft: '4px solid #ff0000'
                            }}>
                              <div style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'flex-start',
                                flexWrap: 'wrap',
                                gap: '12px'
                              }}>
                                <div style={{ flex: 1, minWidth: '200px' }}>
                                  {/* YouTube 배지 */}
                                  <div style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    marginBottom: '8px',
                                    padding: '4px 10px',
                                    background: '#ff0000',
                                    color: 'white',
                                    borderRadius: '4px',
                                    fontSize: '11px',
                                    fontWeight: 'bold'
                                  }}>
                                    ▶ YouTube 영상
                                  </div>
                                  {/* 영상 제목 */}
                                  {videoUrl ? (
                                    <a href={videoUrl} target="_blank" rel="noopener noreferrer" style={{
                                      color: '#1a1a1a',
                                      textDecoration: 'none',
                                      fontWeight: 'bold',
                                      fontSize: '16px',
                                      lineHeight: '1.4',
                                      display: 'block',
                                      marginTop: '4px'
                                    }}
                                    onMouseEnter={(e) => {
                                      e.currentTarget.style.color = '#ff0000';
                                      e.currentTarget.style.textDecoration = 'underline';
                                    }}
                                    onMouseLeave={(e) => {
                                      e.currentTarget.style.color = '#1a1a1a';
                                      e.currentTarget.style.textDecoration = 'none';
                                    }}>
                                      📹 {cleanVideoTitle || '제목 없음'}
                                    </a>
                                  ) : (
                                    <span style={{ fontWeight: 'bold', fontSize: '16px', color: '#333', display: 'block', marginTop: '4px' }}>
                                      📹 {cleanVideoTitle || '제목 없음'}
                                    </span>
                                  )}
                                  {/* 영상 링크 표시 */}
                                  {videoUrl && (
                                    <div style={{
                                      marginTop: '6px',
                                      fontSize: '12px',
                                      color: '#666'
                                    }}>
                                      🔗 <a href={videoUrl} target="_blank" rel="noopener noreferrer" style={{
                                        color: '#666',
                                        textDecoration: 'none'
                                      }}
                                      onMouseEnter={(e) => e.currentTarget.style.textDecoration = 'underline'}
                                      onMouseLeave={(e) => e.currentTarget.style.textDecoration = 'none'}>
                                        {videoUrl.length > 60 ? videoUrl.substring(0, 60) + '...' : videoUrl}
                                      </a>
                                    </div>
                                  )}
                                </div>
                                <span style={{
                                  padding: '6px 14px',
                                  background: '#667eea',
                                  color: 'white',
                                  borderRadius: '16px',
                                  fontSize: '13px',
                                  fontWeight: 'bold',
                                  boxShadow: '0 2px 4px rgba(102, 126, 234, 0.3)'
                                }}>
                                  💬 {videoGroup.comments.length}개 댓글
                                </span>
                              </div>

                              {/* 비디오별 키워드 분석 */}
                              {topKeywords.length > 0 && (
                                <div style={{
                                  marginTop: '12px',
                                  display: 'flex',
                                  flexWrap: 'wrap',
                                  gap: '6px'
                                }}>
                                  {topKeywords.map(([keyword, count], kidx) => {
                                    const category = getKeywordCategory(keyword);
                                    const categoryColors = {
                                      '버디/레벨스': { bg: '#fff0f0', color: '#e74c3c', border: '#ffcccb' },
                                      '굿즈/상품': { bg: '#fff8e1', color: '#f39c12', border: '#ffe082' },
                                      '크리에이터': { bg: '#f0f5ff', color: '#1d39c4', border: '#adc6ff' },
                                      '판매/구매': { bg: '#e8f5e9', color: '#27ae60', border: '#a5d6a7' },
                                      '팬활동': { bg: '#fce4ec', color: '#e91e63', border: '#f8bbd9' },
                                      '디지털상품': { bg: '#e1f5fe', color: '#0277bd', border: '#81d4fa' },
                                      '성별': { bg: '#fff0f6', color: '#c41d7f', border: '#ffadd2' },
                                      '콘텐츠': { bg: '#fffbe6', color: '#d48806', border: '#ffe58f' },
                                      '반응': { bg: '#e6f7ff', color: '#0958d9', border: '#91caff' },
                                      '기타': { bg: '#f5f5f5', color: '#595959', border: '#d9d9d9' }
                                    };
                                    const colors = categoryColors[category] || categoryColors['기타'];
                                    return (
                                      <span key={kidx} style={{
                                        padding: '3px 10px',
                                        background: colors.bg,
                                        color: colors.color,
                                        borderRadius: '12px',
                                        fontSize: '11px',
                                        fontWeight: 'bold',
                                        border: `1px solid ${colors.border}`,
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '4px'
                                      }}>
                                        {keyword}
                                        <span style={{
                                          background: colors.color,
                                          color: 'white',
                                          padding: '1px 5px',
                                          borderRadius: '8px',
                                          fontSize: '9px'
                                        }}>
                                          {count}
                                        </span>
                                      </span>
                                    );
                                  })}
                                </div>
                              )}
                            </div>

                            {/* 댓글 목록 */}
                            <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                              {videoGroup.comments.map((comment, idx) => {
                                // sentiment가 없으면 analyzeSentiment 함수 사용
                                const sentiment = comment.sentiment || analyzeSentiment(comment.text);
                                return (
                                <div key={idx} style={{
                                  padding: '12px',
                                  background: '#fafafa',
                                  borderRadius: '8px',
                                  border: '1px solid #eee',
                                  transition: 'all 0.2s ease'
                                }}
                                onMouseEnter={(e) => {
                                  e.currentTarget.style.background = '#f0f0ff';
                                  e.currentTarget.style.borderColor = '#667eea';
                                }}
                                onMouseLeave={(e) => {
                                  e.currentTarget.style.background = '#fafafa';
                                  e.currentTarget.style.borderColor = '#eee';
                                }}>
                                  <div style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    marginBottom: '6px'
                                  }}>
                                    <span style={{ fontWeight: 'bold', fontSize: '12px', color: '#333' }}>
                                      {comment.author || '익명'}
                                    </span>
                                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                                      <span style={{
                                        padding: '3px 8px',
                                        borderRadius: '10px',
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        background: sentiment === 'positive' ? '#d4edda' : sentiment === 'negative' ? '#f8d7da' : '#e2e3e5',
                                        color: sentiment === 'positive' ? '#155724' : sentiment === 'negative' ? '#721c24' : '#383d41'
                                      }}>
                                        {sentiment === 'positive' ? '😊' : sentiment === 'negative' ? '😢' : '😐'}
                                      </span>
                                      {comment.like_count > 0 && (
                                        <span style={{ fontSize: '11px', color: '#666' }}>
                                          👍 {comment.like_count}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  <p style={{
                                    margin: '0 0 8px 0',
                                    fontSize: '13px',
                                    lineHeight: '1.5',
                                    color: '#444'
                                  }}>
                                    {comment.text}
                                  </p>
                                  {/* 매칭된 키워드 표시 (컴팩트) */}
                                  {(() => {
                                    const matchedKeywords = findMatchingKeywords(comment.text);
                                    if (matchedKeywords.length > 0) {
                                      return (
                                        <div style={{
                                          display: 'flex',
                                          flexWrap: 'wrap',
                                          gap: '3px',
                                          marginBottom: '6px'
                                        }}>
                                          {matchedKeywords.slice(0, 4).map((keyword, kidx) => {
                                            const category = getKeywordCategory(keyword);
                                            const categoryColors = {
                                              '버디/레벨스': { bg: '#fff0f0', color: '#e74c3c' },
                                              '굿즈/상품': { bg: '#fff8e1', color: '#f39c12' },
                                              '크리에이터': { bg: '#f0f5ff', color: '#1d39c4' },
                                              '기타': { bg: '#f5f5f5', color: '#595959' }
                                            };
                                            const colors = categoryColors[category] || categoryColors['기타'];
                                            return (
                                              <span key={kidx} style={{
                                                padding: '2px 6px',
                                                background: colors.bg,
                                                color: colors.color,
                                                borderRadius: '8px',
                                                fontSize: '9px',
                                                fontWeight: 'bold'
                                              }}>
                                                {keyword}
                                              </span>
                                            );
                                          })}
                                        </div>
                                      );
                                    }
                                    return null;
                                  })()}
                                  {(comment.published_at || comment.publishedAt) && (
                                    <span style={{ fontSize: '10px', color: '#999' }}>
                                      📅 {toKSTDate(comment.published_at || comment.publishedAt)}
                                    </span>
                                  )}
                                </div>
                              );
                              })}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* 댓글 더보기 버튼 */}
                    {hasMore ? (
                      <button
                        onClick={() => loadMoreComments(creator.name, totalComments)}
                        style={{
                          width: '100%',
                          marginTop: '16px',
                          padding: '12px',
                          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                          color: 'white',
                          border: 'none',
                          borderRadius: '8px',
                          fontSize: '14px',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                          transition: 'all 0.3s ease',
                          boxShadow: '0 2px 8px rgba(102, 126, 234, 0.3)'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = 'translateY(-2px)';
                          e.currentTarget.style.boxShadow = '0 4px 12px rgba(102, 126, 234, 0.4)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = 'translateY(0)';
                          e.currentTarget.style.boxShadow = '0 2px 8px rgba(102, 126, 234, 0.3)';
                        }}
                      >
                        💬 댓글 더보기 ({totalComments - displayLimit}개 남음)
                      </button>
                    ) : (
                      <div style={{
                        textAlign: 'center',
                        marginTop: '16px',
                        padding: '12px',
                        background: '#e8f5e9',
                        borderRadius: '8px',
                        color: '#2e7d32',
                        fontSize: '14px',
                        fontWeight: 'bold'
                      }}>
                        ✅ 모든 댓글을 불러왔습니다 ({totalComments}개)
                      </div>
                    )}
                  </div>
                );})() : (
                  <div className="resources-section">
                    <div className="analysis-label">댓글 요약</div>
                    <div className="empty-state">
                      <p>댓글 요약이 없습니다.</p>
                    </div>
                  </div>
                )}

                {/* 관련 영상 링크 - 키워드별 분류 */}
                {creator.video_links && creator.video_links.length > 0 && (
                  <div className="resources-section" style={{ marginBottom: '24px' }}>
                    <div style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '16px', color: '#333' }}>
                      📹 관련 영상 ({creator.video_links.length}개)
                    </div>

                    {/* 키워드별 영상 분류 - 비즈니스 키워드 우선 */}
                    {(() => {
                      // 영상 키워드 분류 (우선순위 순서대로)
                      const videoKeywords = [
                        // ★★★ 최우선순위: 비즈니스/플랫폼 ★★★
                        { name: '레벨스/Levvels', keywords: ['레벨스', 'levvels', 'Levvels', 'LEVVELS'], color: { bg: '#fff0f0', border: '#e74c3c', icon: '🏆' } },
                        { name: 'Vuddy/버디', keywords: ['vuddy', 'Vuddy', 'VUDDY', '버디'], color: { bg: '#f0f0ff', border: '#9b59b6', icon: '💜' } },
                        { name: '굿즈/상품', keywords: ['굿즈', '포카', '포토카드', '키링', '아크릴', '앨범', '머치', '한정판', '시즌그리팅'], color: { bg: '#fff8e1', border: '#f39c12', icon: '🛍️' } },
                        // ★★ 높은 우선순위: 이벤트/팬활동 ★★
                        { name: '이벤트/팬싸', keywords: ['팬싸', '영통', '이벤트', '응모', '당첨', '생일카페', '서포트'], color: { bg: '#e8f5e9', border: '#27ae60', icon: '🎉' } },
                        { name: '데뷔/신곡', keywords: ['데뷔', '신곡', '컴백', '발매', '첫', 'debut', '오리지널'], color: { bg: '#fce4ec', border: '#e91e63', icon: '✨' } },
                        // ★ 일반 콘텐츠 ★
                        { name: '노래/음악', keywords: ['노래', '커버', 'cover', '가창', '보컬', 'song', 'music', '뮤비', 'mv'], color: { bg: '#fff0f5', border: '#ff69b4', icon: '🎵' } },
                        { name: '라이브/방송', keywords: ['라이브', 'live', '방송', '생방', '스트리밍', 'stream'], color: { bg: '#f0f8ff', border: '#4169e1', icon: '📺' } },
                        { name: '게임', keywords: ['게임', 'game', '플레이', '마크', '마인크래프트'], color: { bg: '#f0fff0', border: '#32cd32', icon: '🎮' } },
                        { name: 'ASMR/힐링', keywords: ['asmr', '힐링', '수면', '잠', '편안'], color: { bg: '#f5f0ff', border: '#9370db', icon: '💤' } },
                        { name: '기타', keywords: [], color: { bg: '#f5f5f5', border: '#888', icon: '📁' } }
                      ];

                      const categorizedVideos = {};
                      videoKeywords.forEach(cat => {
                        categorizedVideos[cat.name] = [];
                      });

                      creator.video_links.forEach(link => {
                        const titleLower = (link.title || '').toLowerCase();
                        let categorized = false;

                        for (const category of videoKeywords) {
                          if (category.name === '기타') continue;
                          for (const keyword of category.keywords) {
                            if (titleLower.includes(keyword.toLowerCase())) {
                              categorizedVideos[category.name].push(link);
                              categorized = true;
                              break;
                            }
                          }
                          if (categorized) break;
                        }

                        if (!categorized) {
                          categorizedVideos['기타'].push(link);
                        }
                      });

                      const categoryColors = {};
                      videoKeywords.forEach(cat => {
                        categoryColors[cat.name] = cat.color;
                      });

                      return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                          {Object.entries(categorizedVideos)
                            .filter(([_, videos]) => videos.length > 0)
                            .map(([category, videos]) => {
                              const colors = categoryColors[category];
                              return (
                                <div key={category} style={{
                                  background: colors.bg,
                                  border: `2px solid ${colors.border}`,
                                  borderRadius: '12px',
                                  padding: '16px',
                                  transition: 'all 0.3s ease'
                                }}>
                                  <div style={{
                                    fontSize: '14px',
                                    fontWeight: 'bold',
                                    marginBottom: '12px',
                                    color: colors.border,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px'
                                  }}>
                                    <span style={{ fontSize: '18px' }}>{colors.icon}</span>
                                    {category} ({videos.length}개)
                                  </div>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    {videos.slice(0, 10).map((link, idx) => {
                                      const cleanVideoTitle = (link.title || '')
                                        .replace(/AkaiV\s*Studio/gi, '')
                                        .replace(/AkaiV/gi, '')
                                        .replace(/akaiv/gi, '')
                                        .replace(/AKAIV/gi, '')
                                        .replace(/아카이브\s*스튜디오/gi, '')
                                        .replace(/아카이브스튜디오/gi, '')
                                        .replace(/\s+/g, ' ')
                                        .trim();
                                      return (
                                        <a
                                          key={idx}
                                          href={link.url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '10px',
                                            padding: '10px 12px',
                                            background: 'white',
                                            borderRadius: '8px',
                                            textDecoration: 'none',
                                            color: '#333',
                                            border: '1px solid #e0e0e0',
                                            transition: 'all 0.2s ease'
                                          }}
                                          onMouseEnter={(e) => {
                                            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
                                            e.currentTarget.style.transform = 'translateX(4px)';
                                          }}
                                          onMouseLeave={(e) => {
                                            e.currentTarget.style.boxShadow = 'none';
                                            e.currentTarget.style.transform = 'translateX(0)';
                                          }}
                                        >
                                          <span style={{
                                            background: '#ff0000',
                                            color: 'white',
                                            padding: '2px 6px',
                                            borderRadius: '4px',
                                            fontSize: '10px',
                                            fontWeight: 'bold'
                                          }}>
                                            YouTube
                                          </span>
                                          <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{
                                              fontSize: '13px',
                                              fontWeight: '600',
                                              overflow: 'hidden',
                                              textOverflow: 'ellipsis',
                                              whiteSpace: 'nowrap'
                                            }}>
                                              {cleanVideoTitle}
                                            </div>
                                            <div style={{
                                              fontSize: '11px',
                                              color: '#666',
                                              marginTop: '2px'
                                            }}>
                                              {link.channel} • {link.published_at ? toKSTDateShort(link.published_at) : ''}
                                            </div>
                                          </div>
                                          <span style={{ color: '#667eea', fontSize: '16px' }}>→</span>
                                        </a>
                                      );
                                    })}
                                    {videos.length > 10 && (
                                      <div style={{
                                        textAlign: 'center',
                                        padding: '8px',
                                        fontSize: '12px',
                                        color: '#666'
                                      }}>
                                        + {videos.length - 10}개 더 있음
                                      </div>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      );
                    })()}
                  </div>
                )}
                

              </div>
            </div>
            );
          })}
        </div>
      ) : (
        <div className="empty-state">
          <p>AkaiV Studio 소속 크리에이터 데이터가 없습니다.</p>
          <p style={{ fontSize: '14px', color: '#666', marginTop: '10px' }}>
            크롤러를 실행하여 데이터를 수집해주세요.
          </p>
          <p style={{ fontSize: '12px', color: '#999', marginTop: '10px' }}>
            브라우저 콘솔(F12)에서 필터링 로그를 확인할 수 있습니다.
          </p>
          <button 
            onClick={loadArchiveStudioCreators}
            style={{
              marginTop: '20px',
              padding: '10px 20px',
              background: '#667eea',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer'
            }}
          >
            다시 시도
          </button>
        </div>
      )}
    </div>
  );
}

export default ArchiveStudioDetail;

