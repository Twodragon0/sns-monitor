"""
YouTube API v3 최적화 모듈
- Redis 캐싱으로 중복 요청 방지
- 배치 처리로 API 호출 최소화
- Search API 사용 최소화 (100 quota → Channels/Videos API 1 quota)
- Exponential backoff with jitter
- 쿼터 관리 및 우선순위 설정
"""

import json
import os
import time
import random
import hashlib
from datetime import datetime, timedelta
from googleapiclient.errors import HttpError

# Redis 클라이언트 (선택적)
try:
    import redis
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2
    )
    # Redis 연결 테스트
    redis_client.ping()
    REDIS_AVAILABLE = True
    print("✅ Redis cache enabled")
except Exception as e:
    print(f"⚠️  Redis not available, caching disabled: {e}")
    redis_client = None
    REDIS_AVAILABLE = False

# API 호출 통계
api_stats = {
    'search': {'calls': 0, 'quota': 0, 'errors': 0, 'cache_hits': 0},
    'videos': {'calls': 0, 'quota': 0, 'errors': 0, 'cache_hits': 0},
    'channels': {'calls': 0, 'quota': 0, 'errors': 0, 'cache_hits': 0},
    'commentThreads': {'calls': 0, 'quota': 0, 'errors': 0, 'cache_hits': 0},
    'playlistItems': {'calls': 0, 'quota': 0, 'errors': 0, 'cache_hits': 0}
}

# 쿼터 코스트 (YouTube API v3 공식 문서 기준)
QUOTA_COSTS = {
    'search': 100,
    'videos': 1,
    'channels': 1,
    'commentThreads': 1,
    'playlistItems': 1
}

# 캐시 TTL (초)
CACHE_TTL = {
    'search': 3600,  # 1시간
    'videos': 1800,  # 30분
    'channels': 7200,  # 2시간
    'commentThreads': 600,  # 10분 (댓글은 자주 변경될 수 있음)
    'playlistItems': 1800  # 30분
}

def get_cache_key(api_name, params):
    """캐시 키 생성 (보안 강화: SHA-256 사용)"""
    # 파라미터를 정렬하여 일관된 키 생성
    sorted_params = json.dumps(params, sort_keys=True)
    hash_value = hashlib.sha256(sorted_params.encode()).hexdigest()
    return f"youtube_api:{api_name}:{hash_value}"

def get_from_cache(api_name, params):
    """캐시에서 데이터 가져오기"""
    if not REDIS_AVAILABLE:
        return None

    try:
        cache_key = get_cache_key(api_name, params)
        cached_data = redis_client.get(cache_key)

        if cached_data:
            api_stats[api_name]['cache_hits'] += 1
            print(f"✅ Cache hit for {api_name} (saved {QUOTA_COSTS.get(api_name, 1)} quota)")
            return json.loads(cached_data)

        return None
    except Exception as e:
        print(f"⚠️  Cache read error: {e}")
        return None

def save_to_cache(api_name, params, data):
    """캐시에 데이터 저장"""
    if not REDIS_AVAILABLE:
        return

    try:
        cache_key = get_cache_key(api_name, params)
        ttl = CACHE_TTL.get(api_name, 1800)
        redis_client.setex(
            cache_key,
            ttl,
            json.dumps(data, ensure_ascii=False)
        )
    except Exception as e:
        print(f"⚠️  Cache write error: {e}")

def execute_with_retry_and_cache(api_call, api_name, params, max_retries=3, backoff_base=2.0):
    """
    캐시를 확인하고 API 호출을 재시도 로직과 함께 실행

    Args:
        api_call: 실행할 API 호출 함수 (callable)
        api_name: API 이름 (search, videos, channels 등)
        params: API 파라미터 (캐싱용)
        max_retries: 최대 재시도 횟수
        backoff_base: 지수 백오프 베이스

    Returns:
        API 응답 결과
    """
    # 1. 캐시 확인
    cached_result = get_from_cache(api_name, params)
    if cached_result:
        return cached_result

    # 2. API 호출
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            # Jitter 추가: 랜덤 지연으로 동시 요청 분산
            if attempt > 0:
                delay = (backoff_base ** attempt) + random.uniform(0, 1)
                print(f"🔄 Retrying {api_name} after {delay:.2f}s (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(delay)
            elif attempt == 0:
                # 첫 요청 전 기본 딜레이 + jitter
                base_delay = float(os.environ.get('API_REQUEST_DELAY', '0.5'))
                jitter = random.uniform(0, 0.2)
                time.sleep(base_delay + jitter)

            # API 호출 실행
            result = api_call()

            # 통계 업데이트
            api_stats[api_name]['calls'] += 1
            api_stats[api_name]['quota'] += QUOTA_COSTS.get(api_name, 1)

            # 캐시에 저장
            save_to_cache(api_name, params, result)

            return result

        except HttpError as e:
            last_exception = e
            api_stats[api_name]['errors'] += 1

            error_code = e.resp.status if hasattr(e, 'resp') else None
            error_reason = None

            try:
                error_data = json.loads(e.content.decode('utf-8'))
                error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', '')
            except:
                pass

            # 403 Forbidden
            if error_code == 403:
                if error_reason in ['quotaExceeded', 'dailyLimitExceeded']:
                    print(f"⚠️  YouTube API quota exceeded. Reason: {error_reason}")
                    if attempt < max_retries:
                        # 할당량 초과 시 더 긴 대기 + jitter
                        wait_time = (backoff_base ** (attempt + 2)) * 10 + random.uniform(0, 5)
                        print(f"Waiting {wait_time:.0f} seconds before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"YouTube API quota exceeded after {max_retries + 1} attempts")
                elif error_reason == 'commentsDisabled':
                    print(f"Comments disabled for this video/channel")
                    return None
                else:
                    print(f"403 Forbidden error: {error_reason or 'Unknown reason'}")
                    if attempt < max_retries:
                        continue
                    else:
                        raise

            # 429 Too Many Requests
            elif error_code == 429:
                print(f"⚠️  Rate limit exceeded (429). Attempt {attempt + 1}/{max_retries + 1}")
                if attempt < max_retries:
                    # Rate limit 초과 시 더 긴 대기 + jitter
                    wait_time = (backoff_base ** (attempt + 1)) * 5 + random.uniform(0, 3)
                    print(f"Waiting {wait_time:.0f} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Rate limit exceeded after {max_retries + 1} attempts")

            # 400 Bad Request (재시도 불필요)
            elif error_code == 400:
                print(f"400 Bad Request: {error_reason or 'Invalid request'}")
                raise

            # 404 Not Found (재시도 불필요)
            elif error_code == 404:
                print(f"404 Not Found: Resource not found")
                return None

            # 기타 오류: 재시도
            else:
                print(f"YouTube API error {error_code}: {e}")
                if attempt < max_retries:
                    continue
                else:
                    raise

        except Exception as e:
            last_exception = e
            api_stats[api_name]['errors'] += 1
            print(f"Unexpected error in {api_name}: {e}")
            if attempt < max_retries:
                continue
            else:
                raise

    # 모든 재시도 실패
    if last_exception:
        raise last_exception
    raise Exception(f"{api_name} API call failed after all retries")

def get_videos_batch(youtube, video_ids, max_batch_size=50):
    """
    배치로 여러 비디오 정보 가져오기 (quota 효율적)

    Args:
        youtube: YouTube API 클라이언트
        video_ids: 비디오 ID 리스트
        max_batch_size: 배치 크기 (최대 50)

    Returns:
        비디오 정보 리스트
    """
    all_videos = []

    # 비디오 ID를 배치로 나누기
    for i in range(0, len(video_ids), max_batch_size):
        batch = video_ids[i:i + max_batch_size]
        batch_ids = ','.join(batch)

        params = {
            'id': batch_ids,
            'part': 'snippet,statistics,contentDetails'
        }

        def api_call():
            return youtube.videos().list(**params).execute()

        try:
            response = execute_with_retry_and_cache(api_call, 'videos', params)
            if response:
                all_videos.extend(response.get('items', []))
        except Exception as e:
            print(f"Error fetching video batch: {e}")
            continue

    return all_videos

def search_videos_optimized(youtube, keyword, max_results=10, channel_id=None, published_after=None, order_by='relevance', top_n_by_views=None):
    """
    최적화된 비디오 검색

    1. 채널이 지정된 경우: PlaylistItems API 사용 (quota 1)
    2. 그 외: Search API 최소화 (필요한 만큼만 호출)

    Args:
        youtube: YouTube API 클라이언트
        keyword: 검색 키워드
        max_results: 최대 결과 수
        channel_id: 채널 ID (선택)
        published_after: 이 날짜 이후 게시된 영상만 검색 (ISO 8601 형식, 예: '2025-11-01T00:00:00Z')
        order_by: 정렬 기준 ('relevance', 'date', 'viewCount', 'rating')
        top_n_by_views: 조회수 기준 상위 N개 선택 (None이면 전체 반환)

    Returns:
        비디오 정보 리스트
    """
    # 채널이 지정된 경우: PlaylistItems API 사용 (더 효율적)
    if channel_id:
        print(f"🔍 Using PlaylistItems API for channel {channel_id} (quota: 1)")

        try:
            # 채널의 uploads 플레이리스트 ID 가져오기
            channel_params = {
                'id': channel_id,
                'part': 'contentDetails'
            }

            def get_channel_api_call():
                return youtube.channels().list(**channel_params).execute()

            channel_response = execute_with_retry_and_cache(
                get_channel_api_call,
                'channels',
                channel_params
            )

            if not channel_response or not channel_response.get('items'):
                print(f"Channel not found: {channel_id}")
                return []

            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            # PlaylistItems API로 비디오 ID 가져오기
            playlist_params = {
                'playlistId': uploads_playlist_id,
                'part': 'contentDetails',
                'maxResults': max_results
            }

            def get_playlist_api_call():
                return youtube.playlistItems().list(**playlist_params).execute()

            playlist_response = execute_with_retry_and_cache(
                get_playlist_api_call,
                'playlistItems',
                playlist_params
            )

            if not playlist_response:
                return []

            # 비디오 ID 추출
            video_ids = [
                item['contentDetails']['videoId']
                for item in playlist_response.get('items', [])
            ]

            # Videos API로 상세 정보 가져오기 (배치 처리)
            videos = get_videos_batch(youtube, video_ids)

            # 키워드 필터링 및 날짜 필터링
            filtered_videos = []
            keyword_lower = keyword.lower()

            for video in videos:
                snippet = video['snippet']
                title = snippet['title'].lower()
                description = snippet.get('description', '').lower()
                published_at = snippet['publishedAt']

                # 날짜 필터링
                if published_after:
                    from datetime import datetime
                    video_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    filter_date = datetime.fromisoformat(published_after.replace('Z', '+00:00'))
                    if video_date < filter_date:
                        continue

                if keyword_lower in title or keyword_lower in description:
                    view_count = int(video['statistics'].get('viewCount', 0))
                    filtered_videos.append({
                        'video_id': video['id'],
                        'title': snippet['title'],
                        'channel_title': snippet['channelTitle'],
                        'channel_id': snippet['channelId'],
                        'published_at': published_at,
                        'description': snippet.get('description', ''),
                        'view_count': view_count,
                        'like_count': int(video['statistics'].get('likeCount', 0)),
                        'comment_count': int(video['statistics'].get('commentCount', 0))
                    })

            # 정렬
            if order_by == 'viewCount':
                filtered_videos.sort(key=lambda x: x['view_count'], reverse=True)
            elif order_by == 'date':
                filtered_videos.sort(key=lambda x: x['published_at'], reverse=True)

            # 조회수 기준 상위 N개 선택
            if top_n_by_views:
                filtered_videos.sort(key=lambda x: x['view_count'], reverse=True)
                filtered_videos = filtered_videos[:top_n_by_views]

            print(f"Found {len(filtered_videos)} videos matching '{keyword}' (quota saved: ~{100 - 1 - 1})")
            return filtered_videos[:max_results]

        except Exception as e:
            print(f"Error using optimized channel search: {e}")
            print("Falling back to Search API...")

    # Search API 사용 (마지막 수단)
    print(f"⚠️  Using Search API for '{keyword}' (quota: 100)")

    search_params = {
        'q': f'"{keyword}"',
        'part': 'id',  # snippet 제외하여 quota 절약
        'type': 'video',
        'maxResults': min(max_results * 2, 20),  # 필터링을 위해 더 많이 가져옴
        'order': order_by  # 사용자가 지정한 정렬 기준 사용
    }

    if channel_id:
        search_params['channelId'] = channel_id

    # 최신 정보 필터링
    if published_after:
        search_params['publishedAfter'] = published_after

    def search_api_call():
        return youtube.search().list(**search_params).execute()

    try:
        search_response = execute_with_retry_and_cache(
            search_api_call,
            'search',
            search_params
        )

        if not search_response:
            return []

        # 비디오 ID 추출
        video_ids = [
            item['id']['videoId']
            for item in search_response.get('items', [])
        ]

        # Videos API로 상세 정보 가져오기 (배치 처리)
        videos = get_videos_batch(youtube, video_ids)

        result = []
        for video in videos:
            snippet = video['snippet']
            view_count = int(video['statistics'].get('viewCount', 0))
            result.append({
                'video_id': video['id'],
                'title': snippet['title'],
                'channel_title': snippet['channelTitle'],
                'channel_id': snippet['channelId'],
                'published_at': snippet['publishedAt'],
                'description': snippet.get('description', ''),
                'view_count': view_count,
                'like_count': int(video['statistics'].get('likeCount', 0)),
                'comment_count': int(video['statistics'].get('commentCount', 0))
            })

        # 조회수 기준 상위 N개 선택
        if top_n_by_views:
            result.sort(key=lambda x: x['view_count'], reverse=True)
            result = result[:top_n_by_views]

        return result[:max_results]

    except Exception as e:
        print(f"Error in search_videos_optimized: {e}")
        return []

def detect_comment_country(comment_text):
    """댓글 텍스트의 언어를 기반으로 국가 추정"""
    if not comment_text:
        return 'Unknown'

    # 한국어 문자 체크
    korean_chars = sum(1 for char in comment_text if ord(char) >= 0xAC00 and ord(char) <= 0xD7A3)
    # 일본어 문자 체크 (히라가나, 가타카나, 한자)
    japanese_chars = sum(1 for char in comment_text if (
        (ord(char) >= 0x3040 and ord(char) <= 0x309F) or  # 히라가나
        (ord(char) >= 0x30A0 and ord(char) <= 0x30FF) or  # 가타카나
        (ord(char) >= 0x4E00 and ord(char) <= 0x9FAF)     # 한자
    ))

    total_chars = len([c for c in comment_text if c.isalpha()])

    if total_chars == 0:
        return 'Unknown'

    korean_ratio = korean_chars / total_chars if total_chars > 0 else 0
    japanese_ratio = japanese_chars / total_chars if total_chars > 0 else 0

    if korean_ratio > 0.3:
        return 'KR'
    elif japanese_ratio > 0.3:
        return 'JP'
    else:
        # 영어 또는 기타 언어 (기본값은 미국)
        return 'US'

def is_vtuber_comment(author_name, author_channel_id=None):
    """댓글 작성자가 버튜버인지 판단 (간단한 휴리스틱)"""
    if not author_name:
        return False

    # 버튜버 관련 키워드 체크
    vtuber_keywords = ['버튜버', 'vtuber', '버츄얼', 'virtual', '아바타', 'avatar']
    author_lower = author_name.lower()

    # 채널명에 버튜버 관련 키워드가 있는지 확인
    for keyword in vtuber_keywords:
        if keyword in author_lower:
            return True

    return False

def get_video_comments_optimized(youtube, video_id, max_results=100):
    """
    최적화된 댓글 가져오기

    Args:
        youtube: YouTube API 클라이언트
        video_id: 비디오 ID
        max_results: 최대 댓글 수

    Returns:
        dict: {
            'comments': 댓글 리스트,
            'vtuber_stats': 버튜버 통계,
            'country_stats': 국가별 통계
        }
    """
    params = {
        'videoId': video_id,
        'part': 'snippet',  # replies 제외하여 quota 절약
        'maxResults': min(max_results, 100),
        'textFormat': 'plainText',
        'order': 'time'  # 최신 댓글 우선 (최근 작성된 댓글부터)
    }

    def api_call():
        return youtube.commentThreads().list(**params).execute()

    try:
        response = execute_with_retry_and_cache(
            api_call,
            'commentThreads',
            params
        )

        if not response:
            return {
                'comments': [],
                'vtuber_stats': None,
                'country_stats': {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}}
            }

        comments = []
        vtuber_comments = []
        vtuber_total_likes = 0
        country_stats = {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}}

        for item in response.get('items', []):
            top_comment = item['snippet']['topLevelComment']['snippet']
            author_name = top_comment['authorDisplayName']
            author_channel_id = top_comment.get('authorChannelId', {}).get('value')
            comment_text = top_comment['textDisplay']

            # 국가 추정
            detected_country = detect_comment_country(comment_text)
            if detected_country not in ['KR', 'US', 'JP']:
                detected_country = 'Other'

            # 버튜버 여부 확인
            is_vtuber = is_vtuber_comment(author_name, author_channel_id)

            comment_data = {
                'comment_id': item['id'],
                'author': author_name,
                'author_channel_id': author_channel_id,
                'text': comment_text,
                'like_count': top_comment['likeCount'],
                'published_at': top_comment['publishedAt'],
                'reply_count': item['snippet']['totalReplyCount'],
                'is_vtuber': is_vtuber,
                'country': detected_country,
                'replies': []  # replies는 quota 절약을 위해 빈 배열로
            }

            comments.append(comment_data)

            # 국가별 통계 업데이트
            country_stats[detected_country]['comments'] += 1
            country_stats[detected_country]['likes'] += top_comment['likeCount']

            # 버튜버 통계 업데이트
            if is_vtuber:
                vtuber_comments.append(comment_data)
                vtuber_total_likes += top_comment['likeCount']

        return {
            'comments': comments,
            'vtuber_stats': {
                'total_vtuber_comments': len(vtuber_comments),
                'vtuber_total_likes': vtuber_total_likes,
                'vtuber_comments': vtuber_comments
            },
            'country_stats': country_stats
        }

    except Exception as e:
        print(f"Error fetching comments for {video_id}: {e}")
        return {
            'comments': [],
            'vtuber_stats': None,
            'country_stats': {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}}
        }

def print_api_stats():
    """API 호출 통계 출력"""
    print("\n" + "="*60)
    print("📊 YouTube API Usage Statistics")
    print("="*60)

    total_calls = 0
    total_quota = 0
    total_errors = 0
    total_cache_hits = 0

    for api_name, stats in api_stats.items():
        if stats['calls'] > 0 or stats['cache_hits'] > 0:
            print(f"\n{api_name}:")
            print(f"  API Calls: {stats['calls']}")
            print(f"  Cache Hits: {stats['cache_hits']}")
            print(f"  Quota Used: {stats['quota']}")
            print(f"  Errors: {stats['errors']}")
            if stats['calls'] > 0:
                error_rate = (stats['errors'] / stats['calls']) * 100
                print(f"  Error Rate: {error_rate:.2f}%")

            total_calls += stats['calls']
            total_quota += stats['quota']
            total_errors += stats['errors']
            total_cache_hits += stats['cache_hits']

    print(f"\n{'-'*60}")
    print(f"Total API Calls: {total_calls}")
    print(f"Total Cache Hits: {total_cache_hits}")
    print(f"Total Quota Used: {total_quota}")
    print(f"Total Errors: {total_errors}")

    if total_calls > 0:
        overall_error_rate = (total_errors / total_calls) * 100
        cache_hit_rate = (total_cache_hits / (total_calls + total_cache_hits)) * 100 if (total_calls + total_cache_hits) > 0 else 0
        print(f"Overall Error Rate: {overall_error_rate:.2f}%")
        print(f"Cache Hit Rate: {cache_hit_rate:.2f}%")

    print("="*60 + "\n")

def reset_api_stats():
    """API 통계 초기화"""
    global api_stats
    api_stats = {
        'search': {'calls': 0, 'quota': 0, 'errors': 0, 'cache_hits': 0},
        'videos': {'calls': 0, 'quota': 0, 'errors': 0, 'cache_hits': 0},
        'channels': {'calls': 0, 'quota': 0, 'errors': 0, 'cache_hits': 0},
        'commentThreads': {'calls': 0, 'quota': 0, 'errors': 0, 'cache_hits': 0},
        'playlistItems': {'calls': 0, 'quota': 0, 'errors': 0, 'cache_hits': 0}
    }
