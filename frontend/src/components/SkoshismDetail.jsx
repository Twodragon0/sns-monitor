import React, { useState, useEffect } from 'react';
import './Dashboard.css';

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

// 모니터링 키워드 (SKOSHISM 맞춤)
const MONITORING_KEYWORDS = [
  // ★★★ 최우선순위: 보안/해킹 관련 ★★★
  '해킹', '해킹당함', '해킹됨', 'hack', 'hacked', 'hacking',
  '보안', 'security', '유출', 'leak', 'leaked', '정보유출',
  '계정탈취', '계정해킹', '비밀번호', 'password', '피싱', 'phishing',
  '사기', 'scam', '개인정보', '침해', 'DDoS', '악성코드', 'malware',
  // ★★★ 최우선순위: 크리에이터 이름 및 별명 ★★★
  '스코시즘', 'skoshism', '니노', '선데이', '코요', '템페스트', '이로', '클라우드',
  '오토', '레이니', '로보', '프로스터', 'nino', 'koyo', 'iro', 'oto', 'robo',
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
  '버튜버', 'vtuber', '크리에이터', '유튜버', '치지직', 'chzzk',
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
  '크리에이터': ['스코시즘', 'skoshism', '니노', '선데이', '코요', '템페스트', '이로', '클라우드', '오토', '레이니', '로보', '프로스터', 'nino', 'koyo', 'iro', 'oto', 'robo'],
  '크리에이터브랜드/예시기업': ['크리에이터브랜드', 'creatorbrand', '예시기업', 'examplecorp', 'ExampleCorp'],
  '굿즈/상품': ['굿즈', '포토카드', '포카', '아크릴', '키링', '스티커', '포스터', '엽서', '앨범', '음반', '한정판', '시즌그리팅', '캘린더', '머치', '공식굿즈'],
  // ★★ 높은 우선순위 카테고리 ★★
  '판매/구매': ['구매', '판매', '주문', '예약', '결제', '배송', '품절', '재입고', '가격', '할인', '이벤트', '특전'],
  '팬활동': ['팬싸', '영통팬싸', '응모', '당첨', '럭드', '포토타임', '생일카페', '서포트', '조공'],
  '디지털상품': ['음원', '다운로드', '디지털싱글', '뮤직비디오', 'MV', '티저', '커버곡', '오리지널곡', '멤버십', '후원', '슈퍼챗', '보이스팩', '월페이퍼', '보팩', '펀딩'],
  // 일반 카테고리
  '활동': ['버튜버', 'vtuber', '크리에이터', '유튜버', '치지직', 'chzzk'],
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

// 채널 정보 정의
const CHANNELS = [
  { name: '니노 선데이', handle: '@NIN0SUNDAY', youtubeUrl: 'https://www.youtube.com/@NIN0SUNDAY', chzzkUrl: 'https://chzzk.naver.com/4f6ad6a51d2e3b9f6ce0537a0c45500b' },
  { name: '코요 템페스트', handle: '@KoyoTempest', youtubeUrl: 'https://www.youtube.com/@KoyoTempest', chzzkUrl: 'https://chzzk.naver.com/5f9ef7fa895bbda3b5c06552aa1e1299' },
  { name: '이로 클라우드', handle: '@irocloud_', youtubeUrl: 'https://www.youtube.com/@IroCloud', chzzkUrl: 'https://chzzk.naver.com/e532a51d5458a0b28fb53b8a7499c215' },
  { name: '오토 레이니', handle: '@otorainy', youtubeUrl: 'https://www.youtube.com/@otorainy', chzzkUrl: 'https://chzzk.naver.com/1bf34c2eaeb9e47a365203ac62ee10f3' },
  { name: '로보 프로스터', handle: '@RoboFroster', youtubeUrl: 'https://www.youtube.com/@RoboFroster', chzzkUrl: 'https://chzzk.naver.com/29760212cba8459abacbbcc6dfbbd828' }
];

function SkoshismDetail() {
  const [channelsData, setChannelsData] = useState({});
  const [loading, setLoading] = useState(true);
  const [expandedChannels, setExpandedChannels] = useState({});
  const [lastCrawled, setLastCrawled] = useState('');
  const [commentDisplayLimit, setCommentDisplayLimit] = useState({});  // 채널별 댓글 표시 개수
  const [videoDisplayLimit, setVideoDisplayLimit] = useState({});  // 채널별/카테고리별 영상 표시 개수
  const INITIAL_COMMENT_COUNT = 5;  // 초기 표시 댓글 수
  const LOAD_MORE_COUNT = 10;  // 더보기 시 추가 댓글 수
  const INITIAL_VIDEO_COUNT = 5;  // 초기 표시 영상 수
  const VIDEO_LOAD_MORE_COUNT = 10;  // 더보기 시 추가 영상 수

  useEffect(() => {
    loadAllChannelsData();
  }, []);

  const loadAllChannelsData = async () => {
    setLoading(true);
    const channelsDataMap = {};

    try {
      const timestamp = new Date().getTime();

      // 전체 SKOSHISM 채널 데이터를 한 번에 가져오기 (빠름)
      const response = await fetch(`/api/skoshism/channel?_t=${timestamp}`, {
        cache: 'no-cache',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      });

      if (response.ok) {
        const data = await response.json();
        const apiChannels = data.channels || [];

        // API에서 받은 채널 데이터를 채널 이름으로 매핑
        CHANNELS.forEach(channelInfo => {
          // API 데이터에서 해당 채널 찾기 (handle 또는 title로 매칭)
          const apiChannel = apiChannels.find(ch =>
            ch.channel_handle === channelInfo.handle ||
            ch.channel_handle === channelInfo.handle.replace('@', '') ||
            ch.channel_title === channelInfo.name
          );

          if (apiChannel) {
            channelsDataMap[channelInfo.name] = {
              ...channelInfo,
              channel_title: apiChannel.channel_title || channelInfo.name,
              channel_id: apiChannel.channel_id || '',
              videos: apiChannel.videos || [],
              total_comments: apiChannel.total_comments || 0,
              total_vtuber_comments: apiChannel.total_vtuber_comments || 0,
              total_vtuber_likes: apiChannel.total_vtuber_likes || 0,
              statistics: apiChannel.statistics || {},
              comment_samples: apiChannel.comment_samples || [],
              last_crawled: apiChannel.analysis_date || data.last_crawled || ''
            };
          } else {
            // API에서 채널을 못 찾으면 빈 구조 생성
            channelsDataMap[channelInfo.name] = {
              ...channelInfo,
              channel_title: channelInfo.name,
              channel_id: '',
              videos: [],
              total_comments: 0,
              total_vtuber_comments: 0,
              total_vtuber_likes: 0,
              statistics: {},
              comment_samples: [],
              last_crawled: ''
            };
          }
        });

        // 수집 날짜 설정
        if (data.last_crawled) {
          setLastCrawled(data.last_crawled);
        }
      } else {
        // API 실패 시 모든 채널에 빈 구조 생성
        CHANNELS.forEach(channelInfo => {
          channelsDataMap[channelInfo.name] = {
            ...channelInfo,
            channel_title: channelInfo.name,
            channel_id: '',
            videos: [],
            total_comments: 0,
            total_vtuber_comments: 0,
            total_vtuber_likes: 0,
            statistics: {},
            comment_samples: [],
            last_crawled: ''
          };
        });
      }

      setChannelsData(channelsDataMap);
    } catch (error) {
      // Error loading channels data - 빈 구조 생성
      CHANNELS.forEach(channelInfo => {
        channelsDataMap[channelInfo.name] = {
          ...channelInfo,
          channel_title: channelInfo.name,
          channel_id: '',
          videos: [],
          total_comments: 0,
          total_vtuber_comments: 0,
          total_vtuber_likes: 0,
          statistics: {},
          comment_samples: [],
          last_crawled: ''
        };
      });
      setChannelsData(channelsDataMap);
    } finally {
      setLoading(false);
    }
  };

  const toggleChannelDetails = (channelName) => {
    setExpandedChannels(prev => ({
      ...prev,
      [channelName]: !prev[channelName]
    }));
  };

  // 채널별 현재 표시 댓글 수 가져오기
  const getCommentDisplayLimit = (channelName) => {
    return commentDisplayLimit[channelName] || INITIAL_COMMENT_COUNT;
  };

  // 댓글 더보기
  const loadMoreComments = (channelName, totalComments) => {
    setCommentDisplayLimit(prev => {
      const current = prev[channelName] || INITIAL_COMMENT_COUNT;
      const newLimit = Math.min(current + LOAD_MORE_COUNT, totalComments);
      return {
        ...prev,
        [channelName]: newLimit
      };
    });
  };

  // 채널별/카테고리별 현재 표시 영상 수 가져오기
  const getVideoDisplayLimit = (channelName, category) => {
    const key = `${channelName}_${category}`;
    return videoDisplayLimit[key] || INITIAL_VIDEO_COUNT;
  };

  // 영상 더보기
  const loadMoreVideos = (channelName, category, totalVideos) => {
    const key = `${channelName}_${category}`;
    setVideoDisplayLimit(prev => {
      const current = prev[key] || INITIAL_VIDEO_COUNT;
      const newLimit = Math.min(current + VIDEO_LOAD_MORE_COUNT, totalVideos);
      return {
        ...prev,
        [key]: newLimit
      };
    });
  };

  // 타임존 정보가 없는 경우 UTC로 간주하여 KST로 변환
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

  // 감성 분포 계산
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

  return (
    <div className="skoshism-detail-page" style={{ 
      padding: '20px', 
      maxWidth: '1400px', 
      margin: '0 auto',
      minHeight: '100vh',
      background: '#f5f7fa'
    }}>
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
                🎵 SKOSHISM 소속 크리에이터 종합 분석
              </h1>
              <p style={{ 
                margin: '0', 
                fontSize: '16px', 
                color: 'rgba(255,255,255,0.95)',
                lineHeight: '1.6',
                fontWeight: '500'
              }}>
                {CHANNELS.length}명의 크리에이터 (니노 선데이, 코요 템페스트, 이로 클라우드, 오토 레이니, 로보 프로스터) 수집 및 분석 데이터
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
        <div className="dashboard-loading" style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 20px',
          background: '#ffffff',
          borderRadius: '12px',
          border: '2px solid #e9ecef',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
        }}>
          <div className="spinner" style={{
            width: '50px',
            height: '50px',
            border: '4px solid #f3f3f3',
            borderTop: '4px solid #0253fe',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            marginBottom: '20px'
          }}></div>
          <p style={{ fontSize: '16px', color: '#666', fontWeight: '500' }}>
            SKOSHISM 크리에이터 데이터를 불러오는 중...
          </p>
        </div>
      ) : Object.keys(channelsData).length > 0 ? (
        <div className="channels-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '24px' }}>
          {CHANNELS.map((channelInfo, index) => {
            const channel = channelsData[channelInfo.name] || {
              ...channelInfo,
              channel_title: channelInfo.name,
              channel_id: '',
              videos: [],
              total_comments: 0,
              total_vtuber_comments: 0,
              total_vtuber_likes: 0,
              statistics: {},
              comment_samples: [],
              last_crawled: ''
            };
            
            const sentimentDist = calculateSentimentDistribution(channel.comment_samples);
            const overallSentiment = sentimentDist.positive > sentimentDist.negative ? 'positive' : 
                                    sentimentDist.negative > sentimentDist.positive ? 'negative' : 'neutral';
            const overallScore = Math.round((sentimentDist.positive * 100) + (sentimentDist.neutral * 50) + (sentimentDist.negative * 0));
            const isExpanded = expandedChannels[channel.name];

            return (
              <div key={index} className="channel-card" style={{
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
                {/* 채널 헤더 */}
                <div style={{ marginBottom: '20px', paddingBottom: '16px', borderBottom: '2px solid #f0f0f0' }}>
                  <h3 style={{ 
                    margin: '0 0 8px 0', 
                    fontSize: '22px', 
                    fontWeight: 'bold',
                    color: '#333'
                  }}>
                    {channel.name}
                  </h3>
                  {channel.last_crawled && (
                    <p style={{ fontSize: '12px', color: '#888', margin: '0 0 12px 0' }}>
                      📅 수집: {toKSTDateShort(channel.last_crawled)}
                    </p>
                  )}
                  <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <a
                      href={channelInfo.youtubeUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        padding: '6px 12px',
                        background: channelInfo.note ? '#999' : '#ff0000',
                        color: 'white',
                        textDecoration: 'none',
                        borderRadius: '6px',
                        fontSize: '13px',
                        fontWeight: 'bold',
                        transition: 'all 0.2s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = channelInfo.note ? '#777' : '#cc0000';
                        e.currentTarget.style.transform = 'scale(1.05)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = channelInfo.note ? '#999' : '#ff0000';
                        e.currentTarget.style.transform = 'scale(1)';
                      }}
                    >
                      📹 YouTube
                    </a>
                    {channelInfo.chzzkUrl && (
                      <a
                        href={channelInfo.chzzkUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          padding: '6px 12px',
                          background: '#00c73c',
                          color: 'white',
                          textDecoration: 'none',
                          borderRadius: '6px',
                          fontSize: '13px',
                          fontWeight: 'bold',
                          transition: 'all 0.2s ease'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#00a032';
                          e.currentTarget.style.transform = 'scale(1.05)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = '#00c73c';
                          e.currentTarget.style.transform = 'scale(1)';
                        }}
                      >
                        치지직
                      </a>
                    )}
                    {channelInfo.note && (
                      <span style={{ fontSize: '11px', color: '#ff9800', fontWeight: 'bold' }}>
                        ⚠️ {channelInfo.note}
                      </span>
                    )}
                  </div>
                </div>

                {/* 통계 섹션 */}
                <div className="channel-stats" style={{ marginBottom: '20px' }}>
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
                          {channel.total_comments || 0}
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
                      <span style={{ fontSize: '24px' }}>📹</span>
                      <div>
                        <div style={{ fontSize: '11px', color: '#666', marginBottom: '2px' }}>영상</div>
                        <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#333' }}>
                          {channel.videos?.length || 0}
                        </div>
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                    {channel.statistics?.subscriberCount && (
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '12px',
                        background: '#f8f9fa',
                        borderRadius: '8px',
                        border: '1px solid #e9ecef'
                      }}>
                        <span style={{ fontSize: '24px' }}>👥</span>
                        <div>
                          <div style={{ fontSize: '11px', color: '#666', marginBottom: '2px' }}>구독자</div>
                          <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#333' }}>
                            {parseInt(channel.statistics.subscriberCount).toLocaleString()}
                          </div>
                        </div>
                      </div>
                    )}
                    {channel.statistics?.viewCount && (
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '12px',
                        background: '#f8f9fa',
                        borderRadius: '8px',
                        border: '1px solid #e9ecef'
                      }}>
                        <span style={{ fontSize: '24px' }}>👁️</span>
                        <div>
                          <div style={{ fontSize: '11px', color: '#666', marginBottom: '2px' }}>조회수</div>
                          <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#333' }}>
                            {parseInt(channel.statistics.viewCount).toLocaleString()}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* 토글 버튼 */}
                <div style={{ marginTop: '20px' }}>
                  <button
                    onClick={() => toggleChannelDetails(channel.name)}
                    style={{
                      width: '100%',
                      padding: '12px',
                      background: isExpanded ? '#0253fe' : '#f8f9fa',
                      color: isExpanded ? 'white' : '#0253fe',
                      border: '2px solid #0253fe',
                      borderRadius: '8px',
                      fontSize: '14px',
                      fontWeight: 'bold',
                      cursor: 'pointer',
                      transition: 'all 0.3s ease'
                    }}
                    onMouseEnter={(e) => {
                      if (!isExpanded) {
                        e.currentTarget.style.background = '#0253fe';
                        e.currentTarget.style.color = 'white';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isExpanded) {
                        e.currentTarget.style.background = '#f8f9fa';
                        e.currentTarget.style.color = '#0253fe';
                      }
                    }}
                  >
                    {isExpanded ? '▲ 상세 내역 숨기기' : '▼ 상세 내역 보기'}
                  </button>
                </div>

                {/* 상세 분석 - 토글 표시 */}
                <div className="channel-analysis" style={{ 
                  display: isExpanded ? 'block' : 'none',
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
                  
                  {/* 감성 분석 */}
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

                  {/* 모니터링 키워드 분석 */}
                  {channel.comment_samples && channel.comment_samples.length > 0 && (
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

                        channel.comment_samples.forEach(comment => {
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
                                    '성별': '#c41d7f',
                                    '크리에이터': '#1d39c4',
                                    '플랫폼': '#389e0d',
                                    '콘텐츠': '#d48806',
                                    '반응': '#0958d9',
                                    '활동': '#722ed1',
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
                            <div>
                              <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
                                상위 키워드
                              </div>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                {topKeywords.map(([keyword, count], idx) => {
                                  const category = getKeywordCategory(keyword);
                                  const categoryColors = {
                                    '성별': { bg: '#fff0f6', color: '#c41d7f', border: '#ffadd2' },
                                    '크리에이터': { bg: '#f0f5ff', color: '#1d39c4', border: '#adc6ff' },
                                    '플랫폼': { bg: '#f6ffed', color: '#389e0d', border: '#b7eb8f' },
                                    '콘텐츠': { bg: '#fffbe6', color: '#d48806', border: '#ffe58f' },
                                    '반응': { bg: '#e6f7ff', color: '#0958d9', border: '#91caff' },
                                    '활동': { bg: '#f9f0ff', color: '#722ed1', border: '#d3adf7' },
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
                          </>
                        );
                      })()}
                    </div>
                  )}

                  {/* 댓글 요약 - 비디오별 그룹화 */}
                  {channel.comment_samples && channel.comment_samples.length > 0 && (() => {
                    const displayLimit = getCommentDisplayLimit(channel.name);
                    const totalComments = channel.comment_samples.length;
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
                        groups[videoKey].comments.push(comment);

                        // 해당 비디오의 키워드 집계
                        const matchedKeywords = findMatchingKeywords(comment.text);
                        matchedKeywords.forEach(kw => {
                          groups[videoKey].keywords[kw] = (groups[videoKey].keywords[kw] || 0) + 1;
                        });
                      });
                      return Object.values(groups).sort((a, b) => b.comments.length - a.comments.length);
                    };

                    const videoGroups = groupCommentsByVideo(channel.comment_samples.slice(0, displayLimit));
                    const allVideoGroups = groupCommentsByVideo(channel.comment_samples);

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
                                background: 'linear-gradient(135deg, #0253fe15 0%, #0041cc15 100%)',
                                borderBottom: '1px solid #e9ecef'
                              }}>
                                <div style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  flexWrap: 'wrap',
                                  gap: '8px'
                                }}>
                                  <div style={{ flex: 1, minWidth: '200px' }}>
                                    {videoUrl ? (
                                      <a href={videoUrl} target="_blank" rel="noopener noreferrer" style={{
                                        color: '#0253fe',
                                        textDecoration: 'none',
                                        fontWeight: 'bold',
                                        fontSize: '14px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '6px'
                                      }}
                                      onMouseEnter={(e) => e.currentTarget.style.textDecoration = 'underline'}
                                      onMouseLeave={(e) => e.currentTarget.style.textDecoration = 'none'}>
                                        📹 {videoGroup.title}
                                      </a>
                                    ) : (
                                      <span style={{ fontWeight: 'bold', fontSize: '14px', color: '#333' }}>
                                        📹 {videoGroup.title}
                                      </span>
                                    )}
                                  </div>
                                  <span style={{
                                    padding: '4px 12px',
                                    background: '#0253fe',
                                    color: 'white',
                                    borderRadius: '12px',
                                    fontSize: '12px',
                                    fontWeight: 'bold'
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
                                        '크리에이터브랜드/예시기업': { bg: '#fff0f0', color: '#e74c3c', border: '#ffcccb' },
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
                                  const sentiment = analyzeSentiment(comment.text);
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
                                      e.currentTarget.style.borderColor = '#0253fe';
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
                                                  '크리에이터브랜드/예시기업': { bg: '#fff0f0', color: '#e74c3c' },
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
                                      {comment.published_at && (
                                        <span style={{ fontSize: '10px', color: '#999' }}>
                                          📅 {toKSTDateShort(comment.published_at)}
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
                          onClick={() => loadMoreComments(channel.name, totalComments)}
                          style={{
                            width: '100%',
                            marginTop: '16px',
                            padding: '12px',
                            background: 'linear-gradient(135deg, #0253fe 0%, #0041cc 100%)',
                            color: 'white',
                            border: 'none',
                            borderRadius: '8px',
                            fontSize: '14px',
                            fontWeight: 'bold',
                            cursor: 'pointer',
                            transition: 'all 0.3s ease',
                            boxShadow: '0 2px 8px rgba(2, 83, 254, 0.3)'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.transform = 'translateY(-2px)';
                            e.currentTarget.style.boxShadow = '0 4px 12px rgba(2, 83, 254, 0.4)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.transform = 'translateY(0)';
                            e.currentTarget.style.boxShadow = '0 2px 8px rgba(2, 83, 254, 0.3)';
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
                  );})()}

                  {/* 영상 목록 - 키워드별 분류 */}
                  {channel.videos && channel.videos.length > 0 && (
                    <div style={{ marginBottom: '24px' }}>
                      <div style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '16px', color: '#333' }}>
                        📹 영상 목록 ({channel.videos.length}개) - 키워드별 분류
                      </div>

                      {/* 키워드별 영상 분류 - 비즈니스 키워드 우선 */}
                      {(() => {
                        // 영상 키워드 분류 (우선순위 순서대로)
                        const videoKeywords = [
                          // ★★★ 최우선순위: 비즈니스/플랫폼 ★★★
                          { name: '예시기업/ExampleCorp', keywords: ['예시기업', 'examplecorp', 'ExampleCorp', 'EXAMPLECORP'], color: { bg: '#fff0f0', border: '#e74c3c', icon: '🏆' } },
                          { name: 'CreatorBrand/크리에이터브랜드', keywords: ['creatorbrand', 'CreatorBrand', 'CREATORBRAND', '크리에이터브랜드'], color: { bg: '#f0f0ff', border: '#9b59b6', icon: '💜' } },
                          { name: '굿즈/상품', keywords: ['굿즈', '포카', '포토카드', '키링', '아크릴', '앨범', '머치', '한정판', '시즌그리팅'], color: { bg: '#fff8e1', border: '#f39c12', icon: '🛍️' } },
                          // ★★ 높은 우선순위: 이벤트/팬활동 ★★
                          { name: '이벤트/팬싸', keywords: ['팬싸', '영통', '이벤트', '응모', '당첨', '생일카페', '서포트'], color: { bg: '#e8f5e9', border: '#27ae60', icon: '🎉' } },
                          { name: '콜라보/합방', keywords: ['콜라보', '합방', '같이', '함께', '합동', 'collab'], color: { bg: '#e3f2fd', border: '#2196f3', icon: '🤝' } },
                          // ★ 일반 콘텐츠 ★
                          { name: '노래/음악', keywords: ['노래', '커버', 'cover', '가창', '보컬', 'song', 'music', '뮤비', 'mv', '부르기'], color: { bg: '#fff0f5', border: '#ff69b4', icon: '🎵' } },
                          { name: '라이브/방송', keywords: ['라이브', 'live', '방송', '생방', '스트리밍', 'stream', '허허블판'], color: { bg: '#f0f8ff', border: '#4169e1', icon: '📺' } },
                          { name: '게임', keywords: ['게임', 'game', '플레이', '마크', '마인크래프트', '돈스타브'], color: { bg: '#f0fff0', border: '#32cd32', icon: '🎮' } },
                          { name: 'ASMR/힐링', keywords: ['asmr', '힐링', '수면', '잠', '편안', '소통'], color: { bg: '#f5f0ff', border: '#9370db', icon: '💤' } },
                          { name: '기타', keywords: [], color: { bg: '#f5f5f5', border: '#888', icon: '📁' } }
                        ];

                        const categorizedVideos = {};
                        videoKeywords.forEach(cat => {
                          categorizedVideos[cat.name] = [];
                        });

                        channel.videos.forEach(video => {
                          const titleLower = (video.title || '').toLowerCase();
                          let categorized = false;

                          for (const category of videoKeywords) {
                            if (category.name === '기타') continue;
                            for (const keyword of category.keywords) {
                              if (titleLower.includes(keyword.toLowerCase())) {
                                categorizedVideos[category.name].push(video);
                                categorized = true;
                                break;
                              }
                            }
                            if (categorized) break;
                          }

                          if (!categorized) {
                            categorizedVideos['기타'].push(video);
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
                                const videoLimit = getVideoDisplayLimit(channel.name, category);
                                const hasMoreVideos = videoLimit < videos.length;
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
                                      {category} ({videoLimit}/{videos.length}개 표시중)
                                    </div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                      {videos.slice(0, videoLimit).map((video, idx) => (
                                        <a
                                          key={video.video_id || idx}
                                          href={`https://www.youtube.com/watch?v=${video.video_id}`}
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
                                              {video.title || '제목 없음'}
                                            </div>
                                            <div style={{
                                              fontSize: '11px',
                                              color: '#666',
                                              marginTop: '2px'
                                            }}>
                                              {video.published_at ? toKSTDateShort(video.published_at) : ''}
                                              {video.view_count ? ` • 👁️ ${parseInt(video.view_count).toLocaleString()}` : ''}
                                              {video.comments ? ` • 💬 ${video.comments.length}` : ''}
                                            </div>
                                          </div>
                                          <span style={{ color: '#0253fe', fontSize: '16px' }}>→</span>
                                        </a>
                                      ))}
                                      {hasMoreVideos ? (
                                        <button
                                          onClick={() => loadMoreVideos(channel.name, category, videos.length)}
                                          style={{
                                            width: '100%',
                                            padding: '10px',
                                            background: colors.border,
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: '8px',
                                            fontSize: '13px',
                                            fontWeight: 'bold',
                                            cursor: 'pointer',
                                            transition: 'all 0.3s ease',
                                            marginTop: '8px'
                                          }}
                                          onMouseEnter={(e) => {
                                            e.currentTarget.style.opacity = '0.9';
                                            e.currentTarget.style.transform = 'translateY(-2px)';
                                          }}
                                          onMouseLeave={(e) => {
                                            e.currentTarget.style.opacity = '1';
                                            e.currentTarget.style.transform = 'translateY(0)';
                                          }}
                                        >
                                          📹 영상 더보기 ({videos.length - videoLimit}개 남음)
                                        </button>
                                      ) : videos.length > INITIAL_VIDEO_COUNT && (
                                        <div style={{
                                          textAlign: 'center',
                                          padding: '8px',
                                          background: '#e8f5e9',
                                          borderRadius: '8px',
                                          color: '#2e7d32',
                                          fontSize: '12px',
                                          fontWeight: 'bold',
                                          marginTop: '8px'
                                        }}>
                                          ✅ 모든 영상 표시 완료 ({videos.length}개)
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
        <div className="empty-state" style={{
          textAlign: 'center',
          padding: '60px 20px',
          background: '#ffffff',
          borderRadius: '12px',
          border: '2px solid #e9ecef',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
        }}>
          <div style={{ fontSize: '64px', marginBottom: '20px' }}>📺</div>
          <h2 style={{ 
            fontSize: '24px', 
            color: '#333', 
            marginBottom: '12px',
            fontWeight: 'bold'
          }}>
            SKOSHISM 크리에이터 데이터가 없습니다
          </h2>
          <p style={{ fontSize: '16px', color: '#666', marginBottom: '8px', lineHeight: '1.6' }}>
            YouTube 크롤러를 실행하여 데이터를 수집해주세요.
          </p>
          <button 
            onClick={loadAllChannelsData}
            style={{
              padding: '12px 24px',
              background: '#0253fe',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: 'bold',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow: '0 2px 8px rgba(2, 83, 254, 0.3)',
              marginTop: '24px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#0041cc';
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(2, 83, 254, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#0253fe';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 2px 8px rgba(2, 83, 254, 0.3)';
            }}
          >
            🔄 다시 시도
          </button>
        </div>
      )}
    </div>
  );
}

export default SkoshismDetail;
