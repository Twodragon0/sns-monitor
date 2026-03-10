#!/usr/bin/env python3
"""
스코시즘(SKOSHISM) 최신 댓글 데이터 수집 및 업데이트
"""
import json
import os
import sys
from datetime import datetime

# requests는 Docker 컨테이너 내에서만 사용
try:
    import requests
except ImportError:
    requests = None

# 경로 설정
# Docker 컨테이너 내에서 실행되는 경우
if os.path.exists('/app/local-data'):
    BASE_DIR = '/app'
    VUDDY_FILE = '/app/local-data/vuddy/comprehensive_analysis/vuddy-creators.json'
else:
    # 로컬에서 실행되는 경우
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    VUDDY_FILE = os.path.join(BASE_DIR, 'local-data/vuddy/comprehensive_analysis/vuddy-creators.json')

YOUTUBE_CRAWLER_ENDPOINT = os.environ.get('YOUTUBE_CRAWLER_ENDPOINT', 'http://youtube-crawler:5000')
GOOGLE_SEARCH_API_KEY = os.environ.get('GOOGLE_SEARCH_API_KEY', '')
GOOGLE_SEARCH_ENGINE_ID = os.environ.get('GOOGLE_SEARCH_ENGINE_ID', '')

def search_youtube_by_channel(channel_handle):
    """YouTube 채널로 댓글 수집"""
    if not requests:
        print("❌ requests 모듈을 사용할 수 없습니다. Docker 컨테이너 내에서 실행하세요.")
        return {'status': 'error', 'error': 'requests module not available'}
    
    try:
        payload = {
            'type': 'channel',
            'channel_handle': channel_handle,
            'max_videos': 10,
            'max_comments_per_video': 100
        }
        
        print(f"📹 YouTube 크롤러 호출: {channel_handle}")
        response = requests.post(
            f"{YOUTUBE_CRAWLER_ENDPOINT}/invoke",
            json=payload,
            timeout=300
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, dict) and 'body' in result:
                body = json.loads(result.get('body', '{}'))
            else:
                body = result
            
            return {
                'status': 'success',
                'data': body.get('results', body.get('videos', []))
            }
        else:
            print(f"❌ YouTube 크롤러 오류: HTTP {response.status_code}")
            return {
                'status': 'error',
                'error': f"HTTP {response.status_code}"
            }
    except Exception as e:
        print(f"❌ YouTube 크롤러 예외: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

def search_google_by_creator_name(creator_name):
    """Google 검색으로 추가 정보 수집"""
    results = {
        'status': 'success',
        'data': [],
        'total_results': 0
    }
    
    if not requests:
        print("⚠️ requests 모듈을 사용할 수 없습니다. Google 검색을 건너뜁니다.")
        return results
    
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        print("⚠️ Google Search API 키가 설정되지 않았습니다.")
        return results
    
    try:
        search_url = 'https://www.googleapis.com/customsearch/v1'
        search_query = f'"{creator_name}" OR "SKOSHISM"'
        
        priority_countries = [
            {'gl': 'kr', 'hl': 'ko', 'name': '한국'},
            {'gl': 'us', 'hl': 'en', 'name': '미국'},
            {'gl': 'jp', 'hl': 'ja', 'name': '일본'}
        ]
        
        all_results = []
        for country in priority_countries:
            try:
                params = {
                    'key': GOOGLE_SEARCH_API_KEY,
                    'cx': GOOGLE_SEARCH_ENGINE_ID,
                    'q': search_query,
                    'num': 10,
                    'gl': country['gl'],
                    'hl': country['hl']
                }
                
                response = requests.get(search_url, params=params, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    for item in items:
                        link = item.get('link', '')
                        if not any(r['link'] == link for r in all_results):
                            all_results.append({
                                'title': item.get('title', ''),
                                'link': link,
                                'snippet': item.get('snippet', ''),
                                'display_link': item.get('displayLink', ''),
                                'source': 'google_search',
                                'country': country['gl'],
                                'country_name': country['name']
                            })
                    
                    print(f"✅ {country['name']}에서 {len(items)}개 결과 발견")
            except Exception as e:
                print(f"⚠️ {country['name']} 검색 오류: {e}")
        
        results['data'] = all_results
        results['total_results'] = len(all_results)
        return results
        
    except Exception as e:
        print(f"❌ Google 검색 오류: {e}")
        results['status'] = 'error'
        results['error'] = str(e)
        return results

def analyze_comments(youtube_data):
    """댓글 데이터 분석"""
    if youtube_data.get('status') != 'success':
        return {
            'total_comments': 0,
            'total_likes': 0,
            'comment_samples': [],
            'country_stats': {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}},
            'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 1.0}
        }
    
    videos = youtube_data.get('data', [])
    total_comments = 0
    total_likes = 0
    all_comments = []
    country_stats = {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}}
    sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
    
    for video in videos:
        comments = video.get('comments', [])
        total_comments += len(comments)
        
        for comment in comments:
            like_count = comment.get('like_count', 0)
            total_likes += like_count
            
            country = comment.get('country', 'Other')
            if country in country_stats:
                country_stats[country]['comments'] += 1
                country_stats[country]['likes'] += like_count
            else:
                country_stats['Other']['comments'] += 1
                country_stats['Other']['likes'] += like_count
            
            sentiment = comment.get('sentiment', 'neutral')
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
            
            all_comments.append(comment)
    
    # 상위 댓글 샘플 (좋아요 순)
    all_comments.sort(key=lambda x: x.get('like_count', 0), reverse=True)
    comment_samples = all_comments[:20]  # 상위 20개
    
    # 감성 분포 계산
    total_sentiment = sum(sentiment_counts.values())
    if total_sentiment > 0:
        sentiment_distribution = {
            'positive': sentiment_counts['positive'] / total_sentiment,
            'negative': sentiment_counts['negative'] / total_sentiment,
            'neutral': sentiment_counts['neutral'] / total_sentiment
        }
    else:
        sentiment_distribution = {'positive': 0.0, 'negative': 0.0, 'neutral': 1.0}
    
    return {
        'total_comments': total_comments,
        'total_likes': total_likes,
        'comment_samples': comment_samples,
        'country_stats': country_stats,
        'sentiment_distribution': sentiment_distribution,
        'total_videos': len(videos)
    }

def update_skoshism_data():
    """스코시즘 데이터 업데이트"""
    print("=" * 70)
    print("🎸 스코시즘(SKOSHISM) 최신 데이터 수집 시작")
    print("=" * 70)
    
    # 기존 데이터 로드
    if not os.path.exists(VUDDY_FILE):
        print(f"❌ 파일을 찾을 수 없습니다: {VUDDY_FILE}")
        return
    
    with open(VUDDY_FILE, 'r', encoding='utf-8') as f:
        vuddy_data = json.load(f)
    
    # 백업 생성
    backup_file = VUDDY_FILE + '.backup_skoshism_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(vuddy_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 백업 생성: {backup_file}\n")
    
    # 스코시즘 크리에이터 찾기
    creators = vuddy_data.get('creators', [])
    skoshism_index = None
    skoshism_data = None
    
    for i, creator in enumerate(creators):
        if '스코시즘' in creator.get('name', '') or 'SKOSHISM' in creator.get('name', '').upper():
            skoshism_index = i
            skoshism_data = creator
            break
    
    if not skoshism_data:
        print("❌ 스코시즘 데이터를 찾을 수 없습니다.")
        return
    
    print(f"✅ 기존 데이터 발견: {skoshism_data.get('name')}")
    print(f"   - 총 댓글: {skoshism_data.get('total_comments', 0)}개")
    print(f"   - 총 좋아요: {skoshism_data.get('total_likes', 0)}개\n")
    
    # 1. YouTube 데이터 수집
    print("📹 YouTube 댓글 수집 중...")
    youtube_channel = skoshism_data.get('youtube_channel', '@SKOSHISM')
    youtube_result = search_youtube_by_channel(youtube_channel)
    
    if youtube_result.get('status') == 'success':
        print(f"✅ YouTube 데이터 수집 완료")
        analysis = analyze_comments(youtube_result)
        print(f"   - 총 댓글: {analysis['total_comments']}개")
        print(f"   - 총 좋아요: {analysis['total_likes']:,}개")
        print(f"   - 동영상: {analysis['total_videos']}개")
        print(f"   - 국가별: KR {analysis['country_stats']['KR']['comments']}개, US {analysis['country_stats']['US']['comments']}개, JP {analysis['country_stats']['JP']['comments']}개")
    else:
        print(f"❌ YouTube 데이터 수집 실패: {youtube_result.get('error', 'Unknown error')}")
        analysis = {
            'total_comments': 0,
            'total_likes': 0,
            'comment_samples': [],
            'country_stats': {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}},
            'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 1.0},
            'total_videos': 0
        }
    
    # 2. Google 검색
    print("\n🔍 Google 검색 중...")
    google_result = search_google_by_creator_name("스코시즘 SKOSHISM")
    google_links = google_result.get('data', [])
    print(f"✅ Google 검색 완료: {len(google_links)}개 결과")
    
    # 3. 데이터 업데이트
    print("\n📝 데이터 업데이트 중...")
    
    # 기본 정보 유지하면서 업데이트
    updated_data = {
        **skoshism_data,
        'total_comments': analysis['total_comments'],
        'total_likes': analysis['total_likes'],
        'comment_samples': analysis['comment_samples'],
        'country_stats': analysis['country_stats'],
        'sentiment_distribution': analysis['sentiment_distribution'],
        'google_links': google_links,
        'total_google_results': len(google_links),
        'youtube_search_status': 'success' if youtube_result.get('status') == 'success' else 'error',
        'google_search_status': 'success' if google_result.get('status') == 'success' else 'error',
        'updated_at': datetime.now().isoformat()
    }
    
    # 동영상 수 업데이트
    if analysis['total_videos'] > 0:
        updated_data['total_videos'] = analysis['total_videos']
    
    # 크리에이터 목록 업데이트
    creators[skoshism_index] = updated_data
    vuddy_data['creators'] = creators
    vuddy_data['updated_at'] = datetime.now().isoformat()
    
    # 파일 저장
    with open(VUDDY_FILE, 'w', encoding='utf-8') as f:
        json.dump(vuddy_data, f, ensure_ascii=False, indent=2)
    
    print("✅ 데이터 업데이트 완료!")
    print(f"\n📊 업데이트된 통계:")
    print(f"   - 총 댓글: {updated_data['total_comments']}개 (이전: {skoshism_data.get('total_comments', 0)}개)")
    print(f"   - 총 좋아요: {updated_data['total_likes']:,}개 (이전: {skoshism_data.get('total_likes', 0):,}개)")
    print(f"   - Google 검색 결과: {len(google_links)}개")
    print(f"   - 댓글 샘플: {len(updated_data['comment_samples'])}개")
    print(f"\n✅ 완료! 파일: {VUDDY_FILE}")

if __name__ == '__main__':
    update_skoshism_data()

