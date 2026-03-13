"""
YouTube 댓글 크롤러
YouTube Data API v3를 사용하여 특정 키워드의 영상 및 댓글 수집
"""

import json
import logging
import os
import sys
import boto3
import time
from datetime import datetime, timezone, timedelta
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# KST 타임존 (UTC+9)
KST = timezone(timedelta(hours=9))

def get_kst_now():
    """현재 KST 시간 반환"""
    return datetime.now(KST)

from googleapiclient.errors import HttpError

# Import optimized YouTube API functions
from optimized_youtube_api import (
    search_videos_optimized,
    get_video_comments_optimized,
    get_videos_batch,
    print_api_stats,
    reset_api_stats
)

# 로컬 모드 확인
LOCAL_MODE_ENV = os.environ.get('LOCAL_MODE', 'false').lower()
LOCAL_MODE = LOCAL_MODE_ENV == 'true'
LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', './local-data')

logger.info("LOCAL_MODE: %s (env: %s)", LOCAL_MODE, LOCAL_MODE_ENV)

# 로컬 모드가 아닐 때만 AWS 클라이언트 초기화
if not LOCAL_MODE:
    # AWS 클라이언트 (LocalStack 지원)
    s3_endpoint = os.environ.get('S3_ENDPOINT')
    s3_client = boto3.client('s3', endpoint_url=s3_endpoint) if s3_endpoint else boto3.client('s3')
    lambda_client = boto3.client('lambda')
    secrets_client = boto3.client('secretsmanager')

    # DynamoDB 리소스
    dynamodb_endpoint = os.environ.get('DYNAMODB_ENDPOINT')
    if dynamodb_endpoint:
        dynamodb = boto3.resource('dynamodb', endpoint_url=dynamodb_endpoint)
    else:
        dynamodb = boto3.resource('dynamodb')
    
    # 로컬 모드 함수들 None으로 설정
    save_to_local_file = None
    save_metadata_to_local = None
else:
    # 로컬 모드: 공통 유틸리티 임포트
    try:
        # 현재 디렉토리에서 먼저 시도 (복사된 파일)
        try:
            from local_storage import (
                save_to_local_file, 
                save_metadata_to_local, 
                is_local_mode
            )
            logger.info("Successfully imported local_storage from current directory")
        except ImportError:
            # 여러 경로 시도
            common_paths = [
                os.path.join(os.path.dirname(__file__), '..', 'common'),
                '/app/common',
                os.path.join(os.path.dirname(__file__), 'common')
            ]
            imported = False
            for common_path in common_paths:
                if os.path.exists(common_path):
                    sys.path.insert(0, common_path)
                    try:
                        from local_storage import (
                            save_to_local_file, 
                            save_metadata_to_local, 
                            is_local_mode
                        )
                        imported = True
                        logger.info("Successfully imported local_storage from %s", common_path)
                        break
                    except ImportError:
                        continue
            
            if not imported:
                raise ImportError("Could not find local_storage module in any path")
    except ImportError as e:
        logger.warning("Could not import local_storage: %s", e)
        save_to_local_file = None
        save_metadata_to_local = None
    
    s3_client = None
    lambda_client = None
    secrets_client = None
    dynamodb = None

# 환경 변수
S3_BUCKET = os.environ.get('S3_BUCKET')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'sns-monitor-results')
LLM_ANALYZER_FUNCTION = os.environ.get('LLM_ANALYZER_FUNCTION')
SEARCH_KEYWORDS = os.environ.get('SEARCH_KEYWORDS', '').split(',')
YOUTUBE_API_KEY_SECRET = os.environ.get('YOUTUBE_API_KEY_SECRET')
# CHANNELS 또는 YOUTUBE_CHANNELS 환경 변수에서 채널 목록 가져오기 (CronJob은 CHANNELS 사용)
YOUTUBE_CHANNELS_STR = os.environ.get('CHANNELS') or os.environ.get('YOUTUBE_CHANNELS', '')
YOUTUBE_CHANNELS = [ch.strip() for ch in YOUTUBE_CHANNELS_STR.split(',') if ch.strip()] if YOUTUBE_CHANNELS_STR else []  # 채널 URL 또는 핸들명

# MAX_VIDEOS와 MAX_COMMENTS 환경 변수 (CronJob에서 설정)
MAX_VIDEOS = int(os.environ.get('MAX_VIDEOS', '15'))
MAX_COMMENTS = int(os.environ.get('MAX_COMMENTS', '50'))

# 채널 핸들 -> 채널 ID 직접 매핑 (YouTube 검색이 잘못된 결과를 반환하는 경우 사용)
# GroupA channel members and GroupA Studio member channels
CHANNEL_ID_OVERRIDE = {
    # GroupA 공식 채널
    '@example-studio-official': 'UCExampleStudioOfficial1',  # Example Studio official
    '@ExampleStudioOfficial': 'UCExampleStudioOfficial1',    # Example Studio official (alt)

    # GroupA / Creator Group 1 멤버들
    '@example-creator-1': 'UCExampleCreator00000001',  # Creator1
    '@example-creator-2': 'UCExampleCreator00000002',  # Creator2
    '@example-creator-3': 'UCExampleCreator00000003',  # Creator3
    '@example-creator-4': 'UCExampleCreator00000004',  # Creator4
    '@example-creator-5': 'UCExampleCreator00000005',  # Creator5

    # GroupB 소속
    '@example-group-b': 'UCExampleGroupB000000001',  # GroupB official

    # GroupB 멤버들
    '@example-creator-6': 'UCExampleCreator00000006',  # Creator6
    '@example-creator-7': 'UCExampleCreator00000007',  # Creator7
    '@example-creator-8': 'UCExampleCreator00000008',  # Creator8
    '@example-creator-9': 'UCExampleCreator00000009',  # Creator9

    # GroupC 멤버들
    '@example-creator-10': 'UCExampleCreator0000010A',  # Creator10
    '@example-creator-11': 'UCExampleCreator0000011B',  # Creator11
    '@example-creator-12': 'UCExampleCreator0000012C',  # Creator12
    '@example-creator-13': 'UCExampleCreator0000013D',  # Creator13
    '@example-creator-14': 'UCExampleCreator0000014E',  # Creator14
}

# 채널 핸들에 대응하는 한국어 이름 (검색용)
CHANNEL_KOREAN_NAMES = {
    '@example-creator-1': 'Creator1',
    '@example-creator-2': 'Creator2',
    '@example-creator-3': 'Creator3',
    '@example-creator-4': 'Creator4',
    '@example-creator-5': 'Creator5',
    '@example-creator-6': 'Creator6',
    '@example-creator-7': 'Creator7',
    '@example-creator-8': 'Creator8',
    '@example-creator-9': 'Creator9',
    '@example-creator-10': 'Creator10',
    '@example-creator-11': 'Creator11',
    '@example-creator-12': 'Creator12',
    '@example-creator-13': 'Creator13',
    '@example-creator-14': 'Creator14',
}

# 추가 검색 키워드 (채널을 찾지 못할 경우 사용)
CHANNEL_SEARCH_KEYWORDS = {
    '@example-creator-1': ['Creator1 vtuber', 'ExampleCorp creator1'],
    '@example-creator-2': ['Creator2 vtuber', 'ExampleCorp creator2'],
    '@example-creator-3': ['Creator3 vtuber', 'GroupA creator3'],
    '@example-creator-4': ['Creator4 vtuber', 'GroupA creator4'],
    '@example-creator-5': ['Creator5 vtuber', 'GroupA creator5'],
    '@example-creator-6': ['Creator6 vtuber', 'GroupB creator6'],
    '@example-creator-7': ['Creator7 vtuber', 'GroupB creator7'],
    '@example-creator-8': ['Creator8 vtuber', 'GroupB creator8'],
    '@example-creator-9': ['Creator9 vtuber', 'GroupB creator9'],
    '@example-creator-10': ['Creator10 vtuber', 'GroupC creator10'],
    '@example-creator-11': ['Creator11 vtuber', 'GroupC creator11'],
    '@example-creator-12': ['Creator12 vtuber', 'GroupC creator12'],
    '@example-creator-13': ['Creator13 vtuber', 'GroupC creator13'],
    '@example-creator-14': ['Creator14 vtuber', 'GroupC creator14'],
}

# 잘못된 채널 ID 필터링 (이 채널 ID는 수집하지 않음)
BLOCKED_CHANNEL_IDS = {
    # Add channel IDs to block here (e.g., unrelated channels with similar names)
    # 'UCExampleBlockedChannel000',  # Example blocked channel
}

# API Rate Limiting 설정
API_REQUEST_DELAY = float(os.environ.get('API_REQUEST_DELAY', '0.5'))  # 기본 0.5초 딜레이
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))  # 최대 재시도 횟수
RETRY_BACKOFF_BASE = float(os.environ.get('RETRY_BACKOFF_BASE', '2.0'))  # 지수 백오프 베이스

def get_youtube_api_key():
    """Secrets Manager 또는 환경 변수에서 YouTube API 키 가져오기"""
    # 로컬 개발 환경: 환경 변수에서 직접 가져오기
    api_key_from_env = os.environ.get('YOUTUBE_API_KEY')
    if api_key_from_env:
        return api_key_from_env

    # AWS 환경: Secrets Manager에서 가져오기
    try:
        if not YOUTUBE_API_KEY_SECRET:
            raise ValueError("No YouTube API key found in environment or Secrets Manager")

        response = secrets_client.get_secret_value(SecretId=YOUTUBE_API_KEY_SECRET)
        secret = json.loads(response['SecretString'])
        return secret['youtube_api_key']
    except Exception as e:
        logger.error("Error getting YouTube API key: %s", e)
        raise

def execute_with_retry(api_call, max_retries=MAX_RETRIES, backoff_base=RETRY_BACKOFF_BASE):
    """
    YouTube API 호출을 재시도 로직과 함께 실행
    
    Args:
        api_call: 실행할 API 호출 함수 (callable)
        max_retries: 최대 재시도 횟수
        backoff_base: 지수 백오프 베이스
    
    Returns:
        API 응답 결과
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            # Rate limiting: 요청 간 딜레이
            if attempt > 0:
                delay = backoff_base ** attempt
                logger.debug("Retrying API call after %.2f seconds (attempt %d/%d)", delay, attempt + 1, max_retries + 1)
                time.sleep(delay)
            elif attempt == 0:
                # 첫 요청 전에도 기본 딜레이 적용
                time.sleep(API_REQUEST_DELAY)
            
            result = api_call()
            return result
            
        except HttpError as e:
            last_exception = e
            error_code = e.resp.status if hasattr(e, 'resp') else None
            error_reason = None
            
            try:
                error_data = json.loads(e.content.decode('utf-8'))
                error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', '')
            except:
                pass
            
            # 403 Forbidden: 할당량 초과 또는 권한 없음
            if error_code == 403:
                if error_reason in ['quotaExceeded', 'dailyLimitExceeded']:
                    logger.warning("YouTube API quota exceeded. Reason: %s", error_reason)
                    if attempt < max_retries:
                        # 할당량 초과 시 더 긴 대기 시간
                        wait_time = (backoff_base ** (attempt + 2)) * 10  # 최소 40초 대기
                        logger.debug("Waiting %.0f seconds before retry...", wait_time)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"YouTube API quota exceeded after {max_retries + 1} attempts")
                elif error_reason == 'commentsDisabled':
                    logger.info("Comments disabled for this video/channel")
                    return None  # 댓글이 비활성화된 경우는 오류가 아님
                else:
                    logger.error("403 Forbidden error: %s", error_reason or 'Unknown reason')
                    if attempt < max_retries:
                        continue
                    else:
                        raise

            # 429 Too Many Requests: Rate limit 초과
            elif error_code == 429:
                logger.warning("Rate limit exceeded (429). Attempt %d/%d", attempt + 1, max_retries + 1)
                if attempt < max_retries:
                    # Rate limit 초과 시 더 긴 대기 시간
                    wait_time = (backoff_base ** (attempt + 1)) * 5  # 최소 10초 대기
                    logger.debug("Waiting %.0f seconds before retry...", wait_time)
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Rate limit exceeded after {max_retries + 1} attempts")

            # 400 Bad Request: 잘못된 요청 (재시도 불필요)
            elif error_code == 400:
                logger.error("400 Bad Request: %s", error_reason or 'Invalid request')
                raise

            # 404 Not Found: 리소스 없음 (재시도 불필요)
            elif error_code == 404:
                logger.warning("404 Not Found: Resource not found")
                return None

            # 기타 오류: 재시도
            else:
                logger.error("YouTube API error %s: %s", error_code, e)
                if attempt < max_retries:
                    continue
                else:
                    raise

        except Exception as e:
            last_exception = e
            logger.error("Unexpected error: %s", e)
            if attempt < max_retries:
                continue
            else:
                raise
    
    # 모든 재시도 실패
    if last_exception:
        raise last_exception
    raise Exception("API call failed after all retries")

def search_videos(youtube, keyword, max_results=10, regions=None, channel_id_filter=None):
    """키워드로 영상 검색 (정확한 키워드 매칭 필터링 포함, 국가별 우선 검색, 채널 필터링 지원)"""
    # 기본 지역: 한국, 미국, 일본 우선
    if regions is None:
        regions = [
            {'code': 'KR', 'language': 'ko', 'name': '한국'},
            {'code': 'US', 'language': 'en', 'name': '미국'},
            {'code': 'JP', 'language': 'ja', 'name': '일본'}
        ]
    
    try:
        # 검색 쿼리 개선: 정확한 매칭을 위해 따옴표 추가
        search_query = f'"{keyword}"'
        
        # 채널 필터가 있으면 채널 ID로 검색
        if channel_id_filter:
            search_query = f'"{keyword}" channel:{channel_id_filter}'
        
        all_videos = []
        videos_by_region = {}
        
        # 각 지역별로 검색
        for region in regions:
            try:
                def search_api_call():
                    params = {
                        'q': search_query,
                        'part': 'id,snippet',
                        'type': 'video',
                        'maxResults': max_results * 2,  # 필터링을 위해 더 많이 가져옴
                        'order': 'relevance',
                        'relevanceLanguage': region['language'],
                        'regionCode': region['code']
                    }
                    # 채널 필터가 있으면 channelId 파라미터 추가
                    if channel_id_filter:
                        params['channelId'] = channel_id_filter
                    return youtube.search().list(**params).execute()
                
                search_response = execute_with_retry(search_api_call)
                if not search_response:
                    continue
                
                region_videos = []
                keyword_lower = keyword.lower()
                
                for item in search_response.get('items', []):
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    title = snippet['title']
                    description = snippet['description']
                    channel_id = snippet.get('channelId')
                    
                    # 채널 필터가 있으면 채널 ID 확인
                    if channel_id_filter and channel_id != channel_id_filter:
                        continue
                    
                    # 정확한 키워드 매칭 필터링
                    title_lower = title.lower()
                    description_lower = description.lower()
                    
                    # 정확한 키워드 매칭 확인
                    should_include = False
                    
                    if keyword == "ExampleCorp" or keyword == "examplecorp":
                        if "examplecorp" in title_lower or "examplecorp" in description_lower:
                            should_include = True
                        else:
                            continue
                    elif keyword.lower() == "groupb" or keyword == "GroupB":
                        # GroupB 키워드의 경우 채널 필터가 있으면 이미 필터링됨
                        if channel_id_filter:
                            should_include = True
                        else:
                            if "groupb" in title_lower or "groupb" in description_lower:
                                should_include = True
                    else:
                        if keyword_lower in title_lower or keyword_lower in description_lower:
                            should_include = True
                    
                    if should_include:
                        video_info = {
                            'video_id': video_id,
                            'title': title,
                            'channel_title': snippet['channelTitle'],
                            'channel_id': channel_id,  # 채널 ID 추가
                            'published_at': snippet['publishedAt'],
                            'description': description,
                            'region': region['code'],
                            'region_name': region['name']
                        }
                        region_videos.append(video_info)
                        
                        # 중복 제거를 위해 video_id로 체크
                        if not any(v['video_id'] == video_id for v in all_videos):
                            all_videos.append(video_info)
                
                videos_by_region[region['code']] = region_videos
                logger.info("Found %d videos from %s (%s)", len(region_videos), region['name'], region['code'])

            except Exception as e:
                logger.error("YouTube API error for region %s: %s", region['code'], e)
                continue
        
        # 우선 지역(한국, 미국, 일본)의 영상을 먼저 포함하고, 나머지는 추가
        prioritized_videos = []
        priority_regions = ['KR', 'US', 'JP']
        
        for region_code in priority_regions:
            if region_code in videos_by_region:
                for video in videos_by_region[region_code][:max_results]:
                    if not any(v['video_id'] == video['video_id'] for v in prioritized_videos):
                        prioritized_videos.append(video)
        
        # 우선 지역 영상이 부족하면 다른 지역 영상 추가
        for video in all_videos:
            if len(prioritized_videos) >= max_results:
                break
            if not any(v['video_id'] == video['video_id'] for v in prioritized_videos):
                prioritized_videos.append(video)
        
        logger.info("Found %d videos matching exact keyword '%s' (prioritized by region)", len(prioritized_videos), keyword)
        return prioritized_videos[:max_results]

    except HttpError as e:
        logger.error("YouTube API error in search_videos: %s", e)
        return []

def get_channel_id_from_handle(youtube, channel_handle):
    """채널 핸들명 또는 URL에서 채널 ID 가져오기"""
    try:
        # URL에서 핸들명 추출 (쿼리 파라미터 제거)
        original_handle = channel_handle
        if 'youtube.com' in channel_handle or 'youtu.be' in channel_handle:
            # URL에서 쿼리 파라미터 제거 (예: ?si=...)
            if '?' in channel_handle:
                channel_handle = channel_handle.split('?')[0]
            if '@' in channel_handle:
                handle = channel_handle.split('@')[-1].split('/')[0]
                original_handle = '@' + handle
            else:
                # URL에서 핸들명 추출 시도
                parts = channel_handle.split('/')
                handle = None
                for part in parts:
                    if part.startswith('@'):
                        handle = part[1:]
                        original_handle = '@' + handle
                        break
                if not handle:
                    return None
        elif channel_handle.startswith('@'):
            handle = channel_handle[1:]
            original_handle = channel_handle
        else:
            handle = channel_handle
            original_handle = '@' + channel_handle

        # 1. 먼저 CHANNEL_ID_OVERRIDE에서 직접 매핑 확인
        if original_handle in CHANNEL_ID_OVERRIDE and CHANNEL_ID_OVERRIDE[original_handle]:
            override_id = CHANNEL_ID_OVERRIDE[original_handle]
            logger.info("Using override channel ID for %s: %s", original_handle, override_id)
            return override_id

        # 2. forHandle API로 직접 검색 시도 (가장 정확함)
        def get_channel_by_handle_api_call():
            return youtube.channels().list(
            part='id',
            forHandle=handle
        ).execute()

        channels_response = execute_with_retry(get_channel_by_handle_api_call)
        if channels_response and channels_response.get('items'):
            channel_id = channels_response['items'][0]['id']
            logger.info("Found channel ID via forHandle for %s: %s", original_handle, channel_id)
            return channel_id

        # 3. 한국어 이름으로 검색 시도 (VTuber 채널용)
        korean_name = CHANNEL_KOREAN_NAMES.get(original_handle)
        if korean_name:
            def search_korean_name_api_call():
                return youtube.search().list(
                q=korean_name,
                part='snippet',
                type='channel',
                maxResults=5
            ).execute()

            search_response = execute_with_retry(search_korean_name_api_call)
            if search_response and search_response.get('items'):
                # 한국어 이름이 포함된 채널 찾기
                for item in search_response['items']:
                    title = item['snippet']['title']
                    if korean_name in title or handle.lower() in title.lower():
                        channel_id = item['snippet']['channelId']
                        logger.info("Found channel ID via Korean name search for %s: %s (%s)", original_handle, channel_id, title)
                        return channel_id

        # 4. 추가 검색 키워드로 검색 시도
        additional_keywords = CHANNEL_SEARCH_KEYWORDS.get(original_handle, [])
        for search_keyword in additional_keywords:
            def search_additional_api_call():
                return youtube.search().list(
                q=search_keyword,
                part='snippet',
                type='channel',
                maxResults=5
            ).execute()

            search_response = execute_with_retry(search_additional_api_call)
            if search_response and search_response.get('items'):
                for item in search_response['items']:
                    title = item['snippet']['title'].lower()
                    # 핸들명이나 한국어 이름이 포함된 채널 찾기
                    if handle.lower() in title or (korean_name and korean_name in item['snippet']['title']):
                        channel_id = item['snippet']['channelId']
                        logger.info("Found channel ID via additional keyword '%s' for %s: %s (%s)", search_keyword, original_handle, channel_id, item['snippet']['title'])
                        return channel_id

        # 5. 영문 핸들로 일반 검색
        def search_channel_api_call():
            return youtube.search().list(
            q=handle,
            part='snippet',
            type='channel',
            maxResults=1
        ).execute()

        search_response = execute_with_retry(search_channel_api_call)
        if search_response and search_response.get('items'):
            channel_id = search_response['items'][0]['snippet']['channelId']
            # 차단된 채널 ID 확인
            if channel_id in BLOCKED_CHANNEL_IDS:
                logger.warning("Blocked channel ID detected for %s: %s - skipping", original_handle, channel_id)
                return None
            logger.info("Found channel ID via general search for %s: %s", original_handle, channel_id)
            return channel_id

        return None
    except Exception as e:
        logger.error("Error getting channel ID for %s: %s", channel_handle, e)
        return None

def get_channel_videos(youtube, channel_id, max_results=10):
    """특정 채널의 최근 영상 가져오기"""
    try:
        # 채널의 업로드 플레이리스트 ID 가져오기
        def get_channel_details_api_call():
            return youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()

        channel_response = execute_with_retry(get_channel_details_api_call)
        if not channel_response or not channel_response.get('items'):
            logger.warning("Channel not found: %s", channel_id)
            return []
        
        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # 플레이리스트에서 영상 가져오기
        videos = []
        def get_playlist_items_api_call():
            return youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=max_results
            ).execute()
        
        request = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=max_results
        )
        
        while request:
            def execute_playlist_request():
                return request.execute()
            
            response = execute_with_retry(execute_playlist_request)
            if not response:
                break
            
            for item in response.get('items', []):
                snippet = item['snippet']
                video_id = snippet['resourceId']['videoId']
                
                videos.append({
                    'video_id': video_id,
                    'title': snippet['title'],
                    'channel_title': snippet['channelTitle'],
                    'published_at': snippet['publishedAt'],
                    'description': snippet.get('description', '')
                })

            if len(videos) >= max_results:
                break

            request = youtube.playlistItems().list_next(request, response)

        return videos[:max_results]
    except HttpError as e:
        logger.error("YouTube API error in get_channel_videos: %s", e)
        return []

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
    
    # 추가 판단 로직: 채널 정보를 확인할 수 있다면 더 정확하게 판단 가능
    # 여기서는 간단한 휴리스틱만 사용
    
    return False

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

def _process_replies(item, analyze_vtubers):
    """대댓글 처리 헬퍼 함수 (중첩 복잡도 감소)"""
    replies = []
    if 'replies' not in item:
        return replies
    
    for reply in item['replies']['comments']:
        reply_snippet = reply['snippet']
        reply_author = reply_snippet['authorDisplayName']
        reply_is_vtuber = False
        
        if analyze_vtubers:
            reply_is_vtuber = is_vtuber_comment(reply_author)
        
        replies.append({
            'author': reply_author,
            'text': reply_snippet['textDisplay'],
            'like_count': reply_snippet['likeCount'],
            'published_at': reply_snippet['publishedAt'],
            'is_vtuber': reply_is_vtuber
        })
    
    return replies

def _calculate_vtuber_likes_from_replies(replies, analyze_vtubers):
    """대댓글에서 버튜버 좋아요 합산 헬퍼 함수 (중첩 복잡도 감소)"""
    if not analyze_vtubers:
        return 0
    
    total_likes = 0
    for reply in replies:
        if reply.get('is_vtuber', False):
            total_likes += reply.get('like_count', 0)
    
    return total_likes

def _process_comment_item(item, analyze_vtubers, video_region, vtuber_comments, vtuber_total_likes, country_stats):
    """단일 댓글 아이템 처리 헬퍼 함수 (중첩 복잡도 감소)"""
    top_comment = item['snippet']['topLevelComment']['snippet']
    author_name = top_comment['authorDisplayName']
    author_channel_id = top_comment.get('authorChannelId', {}).get('value')
    comment_text = top_comment['textDisplay']
    
    # 국가 추정 (영상 지역 정보 우선, 없으면 댓글 텍스트 분석)
    detected_country = video_region if video_region else detect_comment_country(comment_text)
    if detected_country not in ['KR', 'US', 'JP']:
        detected_country = 'Other'

    comment_data = {
        'comment_id': item['id'],
        'author': author_name,
        'author_channel_id': author_channel_id,
        'text': comment_text,
        'like_count': top_comment['likeCount'],
        'published_at': top_comment['publishedAt'],
        'reply_count': item['snippet']['totalReplyCount'],
        'is_vtuber': False,
        'country': detected_country
    }
    
    # 국가별 통계 업데이트
    country_stats[detected_country]['comments'] += 1
    country_stats[detected_country]['likes'] += top_comment['likeCount']

    # 버튜버 여부 확인
    if analyze_vtubers:
        is_vtuber = is_vtuber_comment(author_name, author_channel_id)
        comment_data['is_vtuber'] = is_vtuber
        
        if is_vtuber:
            vtuber_comments.append(comment_data)
            vtuber_total_likes += top_comment['likeCount']
    
    # 대댓글 수집
    replies = _process_replies(item, analyze_vtubers)
    
    # 대댓글의 버튜버 좋아요 합산
    vtuber_total_likes += _calculate_vtuber_likes_from_replies(replies, analyze_vtubers)
    
    comment_data['replies'] = replies
    return comment_data, vtuber_total_likes

def get_video_comments(youtube, video_id, max_results=100, analyze_vtubers=False, video_region=None):
    """영상의 댓글 가져오기 (버튜버 분석 포함, 국가별 분류)"""
    try:
        comments = []
        vtuber_comments = []
        vtuber_total_likes = 0
        country_stats = {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}}
        
        request = youtube.commentThreads().list(
            part='snippet,replies',
            videoId=video_id,
            maxResults=max_results,
            textFormat='plainText',
            order='time'  # 최신 댓글 우선 (최근 작성된 댓글부터)
        )

        while request:
            def execute_comment_request():
                return request.execute()
            
            response = execute_with_retry(execute_comment_request)
            if not response:
                break

            for item in response.get('items', []):
                comment_data, updated_vtuber_likes = _process_comment_item(
                    item, analyze_vtubers, video_region, 
                    vtuber_comments, vtuber_total_likes, country_stats
                )
                vtuber_total_likes = updated_vtuber_likes
                comments.append(comment_data)

            # 다음 페이지 (할당량 고려하여 제한)
            if len(comments) >= max_results:
                break

            request = youtube.commentThreads().list_next(request, response)

        result = {
            'comments': comments,
            'vtuber_stats': {
                'total_vtuber_comments': len(vtuber_comments),
                'vtuber_total_likes': vtuber_total_likes,
                'vtuber_comments': vtuber_comments
            } if analyze_vtubers else None,
            'country_stats': country_stats
        }
        
        return result

    except Exception as e:
        logger.error("YouTube API error in get_video_comments: %s", e)
        return {'comments': [], 'vtuber_stats': None, 'country_stats': {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}}}

def save_to_s3(data, keyword):
    """수집된 데이터를 S3 또는 로컬 파일 시스템에 저장"""
    if LOCAL_MODE:
        # 로컬 모드: 파일 시스템에 저장
        filepath = save_to_local_file(data, 'youtube', keyword)
        # S3 키 형식으로 반환 (호환성 유지)
        return filepath.replace(os.path.sep, '/').replace(LOCAL_DATA_DIR.replace(os.path.sep, '/'), 'local-data')
    else:
        # 프로덕션 모드: S3에 저장
        timestamp = get_kst_now().strftime('%Y-%m-%d-%H-%M-%S')
        key = f"raw-data/youtube/{keyword}/{timestamp}.json"

        try:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=json.dumps(data, ensure_ascii=False, indent=2),
                ContentType='application/json'
            )
            logger.info("Data saved to s3://%s/%s", S3_BUCKET, key)
            return key
        except Exception as e:
            logger.error("Error saving to S3: %s", e)
            raise

def trigger_llm_analysis(s3_key, keyword, total_comments):
    """LLM 분석기 호출"""
    if LOCAL_MODE:
        logger.warning("로컬 모드: LLM 분석은 건너뜁니다. (s3_key: %s)", s3_key)
        return

    try:
        payload = {
            'source': 'youtube',
            's3_key': s3_key,
            'keyword': keyword,
            'total_items': total_comments,
            'timestamp': get_kst_now().isoformat()
        }

        lambda_client.invoke(
            FunctionName=LLM_ANALYZER_FUNCTION,
            InvocationType='Event',  # 비동기 호출
            Payload=json.dumps(payload)
        )
        logger.info("LLM analysis triggered for %s", s3_key)
    except Exception as e:
        logger.error("Error triggering LLM analysis: %s", e)

def analyze_channel(youtube, channel_handle, max_videos=10, max_comments_per_video=100):
    """특정 채널의 영상과 댓글 분석 (버튜버 분석 포함)"""
    logger.info("Analyzing channel: %s", channel_handle)
    
    # 채널 ID 가져오기
    channel_id = get_channel_id_from_handle(youtube, channel_handle)
    if not channel_id:
        return {
            'error': f'Could not find channel: {channel_handle}',
            'channel_handle': channel_handle
        }
    
    # 채널 정보 가져오기
    try:
        def get_channel_info_api_call():
            return youtube.channels().list(
            part='snippet,statistics',
            id=channel_id
        ).execute()
        
        channel_info = execute_with_retry(get_channel_info_api_call)
        if not channel_info or not channel_info.get('items'):
            return {'error': 'Channel not found', 'channel_id': channel_id}
        
        channel_data = channel_info['items'][0]
        channel_title = channel_data['snippet']['title']
        channel_stats = channel_data.get('statistics', {})
    except Exception as e:
        logger.error("Error getting channel info: %s", e)
        channel_title = "Unknown"
        channel_stats = {}
    
    # 채널의 영상 가져오기
    videos = get_channel_videos(youtube, channel_id, max_results=max_videos)
    
    if not videos:
        return {
            'error': 'No videos found',
            'channel_id': channel_id,
            'channel_title': channel_title
        }
    
    total_comments = 0
    total_country_stats = {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}}
    total_vtuber_comments = 0
    total_vtuber_likes = 0
    video_data = []
    all_vtuber_comments = []
    
    # 각 영상의 댓글 수집 및 분석 - 최적화된 함수 사용
    for video in videos:
        logger.info("Fetching comments for video: %s (ID: %s)", video['title'], video['video_id'])

        try:
            comment_result = get_video_comments_optimized(
                youtube,
                video['video_id'],
                max_results=max_comments_per_video
            )
            
            comments = comment_result.get('comments', [])
            vtuber_stats = comment_result.get('vtuber_stats')
            
            country_stats = comment_result.get('country_stats', {})
            
            # 국가별 통계 집계
            for country_code, stats in country_stats.items():
                if country_code in total_country_stats:
                    total_country_stats[country_code]['comments'] += stats.get('comments', 0)
                    total_country_stats[country_code]['likes'] += stats.get('likes', 0)
            total_comments += len(comments)
            
            if vtuber_stats:
                total_vtuber_comments += vtuber_stats['total_vtuber_comments']
                total_vtuber_likes += vtuber_stats['vtuber_total_likes']
                all_vtuber_comments.extend(vtuber_stats['vtuber_comments'])
            
            logger.info("Collected %d comments for video: %s", len(comments), video['title'])
            
            video_data.append({
                'video': video,
                'comments': comments,
                'comment_count': len(comments),
                'vtuber_stats': vtuber_stats,
                'country_stats': country_stats
            })
        except Exception as e:
            logger.error("Error fetching comments for video %s: %s", video['video_id'], e)
            # 댓글 수집 실패해도 영상 정보는 저장
            video_data.append({
                'video': video,
                'comments': [],
                'comment_count': 0,
                'vtuber_stats': None,
                'country_stats': {},
                'error': str(e)
            })
    
    # 분석 결과 요약
    analysis_summary = {
        'channel_id': channel_id,
        'channel_title': channel_title,
        'channel_handle': channel_handle,
        'channel_stats': {
            'subscriber_count': channel_stats.get('subscriberCount', '0'),
            'video_count': channel_stats.get('videoCount', '0'),
            'view_count': channel_stats.get('viewCount', '0')
        },
        'analysis_date': get_kst_now().isoformat(),
        'total_videos_analyzed': len(videos),
        'total_comments': total_comments,
        'vtuber_analysis': {
            'total_vtuber_comments': total_vtuber_comments,
            'total_vtuber_likes': total_vtuber_likes,
            'vtuber_comment_ratio': round((total_vtuber_comments / total_comments * 100), 2) if total_comments > 0 else 0,
            'top_vtuber_comments': sorted(
                all_vtuber_comments, 
                key=lambda x: x['like_count'], 
                reverse=True
            )[:10]  # 좋아요가 많은 버튜버 댓글 Top 10
        },
        'country_stats': total_country_stats,
        'videos': video_data
    }
    
    return analysis_summary

def clean_creator_name_for_search(creator_name):
    """Example Studio 멤버의 경우 그룹 이름을 제거하고 순수한 이름만 반환"""
    if not creator_name:
        return creator_name

    # 그룹 이름 관련 키워드 제거
    cleaned_name = creator_name.replace('ExampleStudio', '').replace('examplestudio', '')
    cleaned_name = cleaned_name.replace('Studio', '').replace('studio', '').replace('STUDIO', '')
    cleaned_name = cleaned_name.replace('  ', ' ').strip()

    # 멤버 이름 매핑
    member_mapping = {
        'Creator1': ['Creator1', 'creator1'],
        'Creator2': ['Creator2', 'creator2'],
        'Creator3': ['Creator3', 'creator3'],
        'Creator4': ['Creator4', 'creator4'],
        'Creator5': ['Creator5', 'creator5'],
    }

    # 멤버 이름 찾기
    for member_name, variants in member_mapping.items():
        for variant in variants:
            if variant.lower() in cleaned_name.lower() or variant.lower() in creator_name.lower():
                logger.debug("Cleaned creator name: '%s' -> '%s'", creator_name, member_name)
                return member_name

    # 멤버 이름을 찾지 못한 경우, 정제된 이름 반환
    if cleaned_name:
        logger.debug("Cleaned creator name: '%s' -> '%s'", creator_name, cleaned_name)
        return cleaned_name

    # 모두 실패하면 원본 반환
    logger.debug("Using original creator name: '%s'", creator_name)
    return creator_name

def _get_keyword_channel_map():
    """키워드와 채널 매핑 반환"""
    return {
        'GroupB': '@example-group-b',
        'groupb': '@example-group-b',
        'ExampleStudio': '@example-studio-official',
        'example studio': '@example-studio-official',
        'EXAMPLE STUDIO': '@example-studio-official',
        'ExampleStudioOfficial': '@example-studio-official',
    }

def _find_channel_by_partial_match(keyword, keyword_normalized, keyword_channel_map):
    """부분 매칭으로 채널 핸들 찾기 (중첩 복잡도 감소)"""
    for map_keyword, map_channel in keyword_channel_map.items():
        if map_keyword.lower() not in keyword_normalized and keyword_normalized not in map_keyword.lower():
            continue
        
        # Example Studio 관련 키워드인지 확인
        is_studio_keyword = 'example studio' in keyword_normalized or 'examplestudio' in keyword_normalized
        if is_studio_keyword and '@example-studio-official' in map_channel:
            return map_channel

        # GroupB 관련 키워드인지 확인
        is_groupb_keyword = 'groupb' in keyword_normalized or 'group b' in keyword_normalized
        if is_groupb_keyword and '@example-group-b' in map_channel:
            return map_channel
    
    return None

def _resolve_channel_filter(youtube, keyword, search_keyword):
    """키워드에 해당하는 채널 필터 해석 (중첩 복잡도 감소)"""
    keyword_channel_map = _get_keyword_channel_map()
    keyword_normalized = search_keyword.lower().strip()
    
    # 정확한 매칭 먼저 시도
    channel_handle = keyword_channel_map.get(keyword)
    if not channel_handle:
        # 대소문자 무시 매칭
        channel_handle = keyword_channel_map.get(keyword_normalized)
    
    if not channel_handle:
        # 부분 매칭 (키워드에 포함된 경우)
        channel_handle = _find_channel_by_partial_match(keyword, keyword_normalized, keyword_channel_map)
    
    channel_filter = None
    if channel_handle:
        channel_id = get_channel_id_from_handle(youtube, channel_handle)
        if channel_id:
            channel_filter = channel_id
            logger.info("Filtering by channel: %s (ID: %s) for keyword: %s", channel_handle, channel_id, keyword)
            # Example Studio 채널인 경우 채널 정보 저장
            if '@example-studio-official' in channel_handle or 'examplestudio' in channel_handle.lower():
                logger.info("Example Studio channel detected: %s -> %s", channel_handle, channel_id)
        else:
            logger.warning("Could not get channel ID for %s", channel_handle)
    
    return channel_filter, channel_handle

def _save_channel_analysis_result(analysis_result, channel_handle):
    """채널 분석 결과 저장 헬퍼 함수"""
    timestamp = get_kst_now().strftime('%Y-%m-%d-%H-%M-%S')
    channel_name = analysis_result.get('channel_title', channel_handle).replace('/', '_')
    
    # channel_handle과 timestamp를 analysis_result에 추가 (백엔드 API에서 찾기 위해)
    analysis_result['channel_handle'] = channel_handle
    analysis_result['timestamp'] = get_kst_now().isoformat()
    
    if LOCAL_MODE and save_to_local_file:
        s3_key = save_to_local_file(analysis_result, 'youtube', channel_name, 'channels')
        logger.info("Channel analysis saved to local file: %s", s3_key)
        return s3_key
    else:
        s3_key = f"raw-data/youtube/channels/{channel_name}/{timestamp}.json"
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=json.dumps(analysis_result, ensure_ascii=False, indent=2),
                ContentType='application/json'
            )
            logger.info("Channel analysis saved to s3://%s/%s", S3_BUCKET, s3_key)
            return s3_key
        except Exception as e:
            logger.error("Error saving to S3: %s", e)
            raise

def _process_channel_analysis(youtube, event, results):
    """채널 분석 모드 처리 헬퍼 함수"""
    channels_to_analyze = event.get('channels', []) or YOUTUBE_CHANNELS
    
    for channel_handle in channels_to_analyze:
        channel_handle = channel_handle.strip()
        if not channel_handle:
            continue
        
        logger.info("Analyzing channel: %s", channel_handle)

        try:
            max_videos = event.get('max_videos') or MAX_VIDEOS
            max_comments_per_video = event.get('max_comments_per_video') or MAX_COMMENTS
            
            analysis_result = analyze_channel(
                youtube, 
                channel_handle,
                max_videos=max_videos,
                max_comments_per_video=max_comments_per_video
            )
            
            if 'error' in analysis_result:
                results.append({
                    'channel': channel_handle,
                    'error': analysis_result['error']
                })
                continue
            
            s3_key = _save_channel_analysis_result(analysis_result, channel_handle)
            
            # LLM 분석 트리거
            trigger_llm_analysis(s3_key, f"channel:{channel_handle}", analysis_result['total_comments'])
            
            results.append({
                'channel': channel_handle,
                'channel_title': analysis_result.get('channel_title'),
                'videos_analyzed': analysis_result.get('total_videos_analyzed', 0),
                'total_comments': analysis_result.get('total_comments', 0),
                'vtuber_comments': analysis_result.get('vtuber_analysis', {}).get('total_vtuber_comments', 0),
                'vtuber_likes': analysis_result.get('vtuber_analysis', {}).get('total_vtuber_likes', 0),
                's3_key': s3_key
            })
            
        except Exception as e:
            logger.error("Error analyzing channel '%s': %s", channel_handle, e)
            results.append({
                'channel': channel_handle,
                'error': str(e)
            })

def _process_keyword_search(youtube, event, results):
    """키워드 검색 모드 처리 헬퍼 함수"""
    keywords_to_search = event.get('keywords', []) or SEARCH_KEYWORDS
    
    for keyword in keywords_to_search:
        keyword = keyword.strip()
        if not keyword:
            continue

        # For ExampleStudio members, remove the studio prefix and use the creator name only
        search_keyword = clean_creator_name_for_search(keyword)

        logger.info("Searching YouTube for keyword: %s (original: %s)", search_keyword, keyword)
        
        # 키워드에 해당하는 채널 필터 확인
        channel_filter, channel_handle = _resolve_channel_filter(youtube, keyword, search_keyword)

        try:
            # 영상 검색 (채널 필터 적용) - 최적화된 함수 사용
            videos = search_videos_optimized(youtube, search_keyword, max_results=5, channel_id=channel_filter)

            total_comments = 0
            video_data = []
            total_country_stats = {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}}

            # 각 영상의 댓글 수집 - 최적화된 함수 사용
            for video in videos:
                logger.info("Fetching comments for video: %s", video['title'])

                comment_result = get_video_comments_optimized(
                    youtube,
                    video['video_id'],
                    max_results=50
                )
                comments = comment_result['comments']
                country_stats = comment_result.get('country_stats', {})
                
                # 국가별 통계 집계
                for country_code, stats in country_stats.items():
                    if country_code in total_country_stats:
                        total_country_stats[country_code]['comments'] += stats.get('comments', 0)
                        total_country_stats[country_code]['likes'] += stats.get('likes', 0)
                
                total_comments += len(comments)

                video_data.append({
                    'video': video,
                    'comments': comments,
                    'comment_count': len(comments),
                    'vtuber_stats': comment_result.get('vtuber_stats'),
                    'country_stats': country_stats
                })
            
            # S3에 저장
            crawl_result = {
                'keyword': keyword,
                'platform': 'youtube',
                'crawled_at': get_kst_now().isoformat(),
                'total_videos': len(videos),
                'total_comments': total_comments,
                'country_stats': total_country_stats,
                'channel_filter': channel_filter if channel_filter else None,
                'channel_handle': channel_handle if channel_handle else None,
                'data': video_data
            }

            s3_key = save_to_s3(crawl_result, keyword)

            # DynamoDB 또는 로컬 파일에 저장
            try:
                item_id = f"youtube-{keyword}-{get_kst_now().strftime('%Y%m%d%H%M%S')}"
                metadata = {
                    'id': item_id,
                    'platform': 'youtube',
                    'keyword': keyword,
                    'timestamp': get_kst_now().isoformat(),
                    's3_key': s3_key,
                    'total_comments': total_comments,
                    'videos_found': len(videos),
                    'videos_analyzed': len(videos),
                    'country_stats': total_country_stats
                }
                
                if LOCAL_MODE:
                    save_metadata_to_local(metadata, 'youtube')
                    logger.info("Saved metadata to local file: %s", item_id)
                else:
                    table = dynamodb.Table(DYNAMODB_TABLE)
                    table.put_item(Item=metadata)
                    logger.info("Saved to DynamoDB: %s", item_id)
            except Exception as e:
                logger.error("Error saving metadata: %s", e)

            # LLM 분석 트리거
            trigger_llm_analysis(s3_key, keyword, total_comments)

            results.append({
                'keyword': keyword,
                'videos_found': len(videos),
                'comments_collected': total_comments,
                's3_key': s3_key
            })

        except Exception as e:
            logger.error("Error processing keyword '%s': %s", keyword, e)
            results.append({
                'keyword': keyword,
                'error': str(e)
            })

def lambda_handler(event, context):
    """
    Lambda 핸들러

    EventBridge에서 주기적으로 호출
    또는 API Gateway를 통한 수동 호출

    이벤트 형식:
    - 키워드 검색: {"type": "keyword", "keywords": ["keyword1", "keyword2"]}
    - 채널 분석: {"type": "channel", "channels": ["@channel1", "https://youtube.com/@channel2"]}
    """
    logger.info("Event: %s", json.dumps(event))

    # Reset API statistics at the start of each lambda invocation
    reset_api_stats()

    # API 키 가져오기
    try:
        api_key = get_youtube_api_key()
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to get YouTube API key'})
        }

    # YouTube API 클라이언트 초기화
    youtube = build('youtube', 'v3', developerKey=api_key)

    results = []

    # 이벤트 타입 확인
    # 환경 변수에 채널 목록이 있으면 자동으로 채널 모드로 실행
    event_type = event.get('type')
    if not event_type and YOUTUBE_CHANNELS:
        event_type = 'channel'
    elif not event_type:
        event_type = 'keyword'
    
    # 채널 분석 모드
    if event_type == 'channel' or YOUTUBE_CHANNELS:
        _process_channel_analysis(youtube, event, results)
    
    # 키워드 검색 모드
    if event_type == 'keyword' or (not event_type == 'channel' and SEARCH_KEYWORDS):
        _process_keyword_search(youtube, event, results)

    # Print API usage statistics at the end
    logger.info("=== YouTube API Usage Statistics ===")
    print_api_stats()
    logger.info("====================================\n")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'YouTube crawling completed',
            'results': results
        }, ensure_ascii=False)
    }
