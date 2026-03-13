"""
API Backend
REST API 엔드포인트
"""

import json
import os
import sys
import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import glob
from urllib.parse import quote

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 로컬 모드 확인 (임포트 전에 확인)
LOCAL_MODE = os.environ.get('LOCAL_MODE', 'false').lower() == 'true'

# requests는 항상 임포트 (내부 서비스 호출에 필요)
# 보안: CVE-2024-35195 대응 - requests>=2.32.0 사용 (Session verify=False 이슈 수정)
try:
    import requests
    # requests 버전 확인 (2.32.0 이상 필요)
    requests_version = requests.__version__.split('.')
    if int(requests_version[0]) < 2 or (int(requests_version[0]) == 2 and int(requests_version[1]) < 32):
        logger.warning(f"requests version {requests.__version__} may be vulnerable to CVE-2024-35195. Upgrade to 2.32.0+")
except ImportError:
    requests = None
    logger.warning("requests not available")

# boto3는 로컬 모드가 아닐 때만 임포트
if not LOCAL_MODE:
    try:
        import boto3
    except ImportError as e:
        logger.warning(f"boto3 not available: {e}")
        boto3 = None
else:
    boto3 = None

def decimal_default(obj):
    """Decimal을 JSON 직렬화 가능한 타입으로 변환"""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def convert_decimal(obj):
    """딕셔너리나 리스트 내의 모든 Decimal을 변환"""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal(item) for item in obj]
    return obj

def is_timestamp_comment(text):
    """타임스탬프 형식의 댓글인지 확인 (노래 목록, 챕터 등)

    예: "00:16:46 怪獣の花唄 / Vaundy" 형태의 댓글 제외
    """
    if not text:
        return False

    # 타임스탬프 패턴 (00:00:00 또는 00:00 형식)
    timestamp_pattern = r'\d{1,2}:\d{2}(?::\d{2})?'

    # 댓글에서 타임스탬프 개수 확인
    timestamps = re.findall(timestamp_pattern, text)

    # 3개 이상의 타임스탬프가 있으면 노래 목록/챕터로 판단
    if len(timestamps) >= 3:
        return True

    # 첫 줄이 타임스탬프로 시작하고 여러 줄로 구성된 경우
    lines = text.strip().split('\n')
    if len(lines) < 3:
        return False
    
    # 여러 줄이 타임스탬프로 시작하는지 확인
    timestamp_lines = sum(1 for line in lines if re.match(r'^\s*\d{1,2}:\d{2}', line.strip()))
    return timestamp_lines >= 3


def calculate_sentiment_from_comments(comment_samples, total_comments):
    """댓글 샘플에서 감성 분석 결과 계산"""
    if not comment_samples:
        return None
    
    total = len(comment_samples)
    if total == 0:
        return None
    
    positive_count = sum(1 for c in comment_samples if c.get('sentiment') == 'positive')
    negative_count = sum(1 for c in comment_samples if c.get('sentiment') == 'negative')
    neutral_count = total - positive_count - negative_count
    
    # 감성 결정
    if positive_count > negative_count and positive_count > neutral_count:
        sentiment = 'positive'
    elif negative_count > positive_count and negative_count > neutral_count:
        sentiment = 'negative'
    else:
        sentiment = 'neutral'
    
    return {
        'sentiment': sentiment,
        'sentiment_distribution': {
            'positive': round(positive_count / total, 2),
            'negative': round(negative_count / total, 2),
            'neutral': round(neutral_count / total, 2)
        },
        'summary': f"총 {total_comments}개의 댓글이 수집되었습니다. 감성 분석 결과: 긍정 {int((positive_count / total) * 100)}%, 중립 {int((neutral_count / total) * 100)}%, 부정 {int((negative_count / total) * 100)}%",
        'keywords': [],
        'trends': [],
        'insights': [],
        'overall_score': int((positive_count / total) * 100)
    }


def is_archive_studio_channel(channel_id, channel_title, channel_handle, channel_filter_from_data, channel_handle_from_data):
    """Example Studio 채널인지 확인"""
    # 채널 필터가 있고, 현재 비디오의 채널 ID와 일치하면 Example Studio 채널
    if channel_filter_from_data and channel_id and str(channel_id) == str(channel_filter_from_data):
        return True

    # 채널 핸들 정보 확인
    if channel_handle_from_data:
        if '@example-studio-official' in channel_handle_from_data or 'ExampleStudioOfficial' in channel_handle_from_data:
            if channel_id and channel_filter_from_data and str(channel_id) == str(channel_filter_from_data):
                return True

    # 채널 제목 확인
    if channel_title:
        channel_title_lower = channel_title.lower()
        if 'example studio' in channel_title_lower or 'examplestyle' in channel_title_lower:
            return True

    # 채널 ID 확인
    if channel_id:
        channel_id_str = str(channel_id)
        if 'ExampleStudioOfficial' in channel_id_str or 'example-studio-official' in channel_id_str.lower():
            return True

    return False


def get_local_filepath(s3_key, local_data_dir):
    """로컬 모드에서 S3 키를 로컬 파일 경로로 변환"""
    if s3_key.startswith('local-data/'):
        return s3_key.replace('local-data/', local_data_dir + '/')
    if s3_key.startswith('./local-data/'):
        return s3_key.replace('./local-data/', local_data_dir + '/')
    # raw-data/youtube/keyword/timestamp.json 형식
    return os.path.join(local_data_dir, s3_key.replace('raw-data/', ''))


def detect_comment_sentiment(comment_text):
    """댓글 텍스트에서 감성 분석"""
    if not comment_text:
        return 'neutral'
    
    text_lower = comment_text.lower()
    positive_words = ['좋', '최고', '사랑', '감사', '고마', '훌륭', '멋', '대박', '완벽', '👍', '❤', '💕', '😊', '😍']
    negative_words = ['안좋', '최악', '싫', '별로', '실망', '나쁘', '문제', '불만', '😢', '😡', '👎']
    
    if any(word in text_lower for word in positive_words):
        return 'positive'
    if any(word in text_lower for word in negative_words):
        return 'negative'
    return 'neutral'


def find_channel_files_local(youtube_dir, requested_handle):
    """로컬 모드에서 채널 파일 찾기"""
    if not os.path.exists(youtube_dir):
        return []
    
    matching_files = []
    for root, dirs, files in os.walk(youtube_dir):
        for filename in files:
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(root, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    channel_handle = data.get('channel_handle', '')
                    if channel_handle.lower() == requested_handle.lower():
                        file_mtime = os.path.getmtime(filepath)
                        matching_files.append((filepath, file_mtime, data))
            except Exception as e:
                logger.error(f"Error loading channel data from {filepath}: {e}", exc_info=True)
    
    return matching_files


def find_channel_files_s3(s3_client, bucket, prefix, requested_handle):
    """S3에서 채널 파일 찾기"""
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if 'Contents' not in response:
            return []
        
        matching_files = []
        for obj in response['Contents']:
            try:
                obj_response = s3_client.get_object(Bucket=bucket, Key=obj['Key'])
                data = json.loads(obj_response['Body'].read().decode('utf-8'))
                if data.get('channel_handle', '') == requested_handle:
                    matching_files.append((obj, data))
            except Exception as e:
                logger.error(f"Error reading S3 object {obj['Key']}: {e}", exc_info=True)
        
        return matching_files
    except Exception as e:
        logger.error(f"Error listing S3 objects: {e}", exc_info=True)
        return []


def _load_metadata_files_local(metadata_dir):
    """로컬 모드에서 메타데이터 파일들을 로드"""
    items = []
    if not os.path.exists(metadata_dir):
        return items
    
    for platform_dir in os.listdir(metadata_dir):
        platform_path = os.path.join(metadata_dir, platform_dir)
        if not os.path.isdir(platform_path):
            continue
        
        for filename in os.listdir(platform_path):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(platform_path, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    item = json.load(f)
                    items.append(item)
            except Exception as e:
                logger.error(f"Error loading metadata file {filepath}: {e}", exc_info=True)
    
    return items

def _parse_timestamp_for_today(timestamp_str, today_start):
    """타임스탬프를 파싱하여 오늘 날짜인지 확인"""
    if not timestamp_str:
        return False
    
    try:
        if 'T' in timestamp_str:
            item_date = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if item_date.tzinfo:
                item_date = item_date.replace(tzinfo=None)
            return item_date >= today_start
    except Exception as e:
        logger.error(f"Error parsing timestamp {timestamp_str}: {e}", exc_info=True)
    
    return False

def calculate_sentiment_distribution(sentiment_dist):
    """감성 분포 계산"""
    if not sentiment_dist:
        return {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}
    
    total_sentiment = sum(sentiment_dist.values())
    if total_sentiment == 0:
        return {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}
    
    return {
        'positive': round(sentiment_dist.get('positive', 0) / total_sentiment, 2),
        'negative': round(sentiment_dist.get('negative', 0) / total_sentiment, 2),
        'neutral': round(sentiment_dist.get('neutral', 0) / total_sentiment, 2)
    }


def get_overall_sentiment(sentiment_dist):
    """전체 감성 결정"""
    if not sentiment_dist:
        return 'neutral'
    return max(sentiment_dist, key=sentiment_dist.get)


def safe_decimal_to_int(value, default=0):
    """Decimal을 안전하게 int로 변환"""
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return default


def safe_decimal_to_str(value, default='unknown'):
    """Decimal을 안전하게 str로 변환"""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str):
        return value
    return str(value) if value else default


def extract_sentiment_analysis_from_item(item, scan):
    """아이템에서 감성 분석 정보를 추출하여 scan에 추가"""
    sentiment_analysis = item.get('sentiment_analysis', {})
    if not sentiment_analysis:
        return
    
    sentiment_dist = sentiment_analysis.get('sentiment_distribution', {})
    if not sentiment_dist:
        return
    
    total_sentiment = sum(sentiment_dist.values()) if sentiment_dist else 0
    if total_sentiment > 0:
        sentiment_distribution = {
            'positive': round(sentiment_dist.get('positive', 0) / total_sentiment, 2),
            'negative': round(sentiment_dist.get('negative', 0) / total_sentiment, 2),
            'neutral': round(sentiment_dist.get('neutral', 0) / total_sentiment, 2)
        }
    else:
        sentiment_distribution = {
            'positive': float(sentiment_dist.get('positive', 0)),
            'negative': float(sentiment_dist.get('negative', 0)),
            'neutral': float(sentiment_dist.get('neutral', 0))
        }
    
    scan['analysis'] = {
        'sentiment': sentiment_analysis.get('overall_sentiment', 'neutral'),
        'sentiment_distribution': sentiment_distribution,
        'summary': sentiment_analysis.get('summary', '')
    }


def add_keyword_analysis_to_scan(item, scan):
    """키워드 분석 정보를 scan에 추가"""
    keyword_analysis = item.get('keyword_analysis', {})
    if not keyword_analysis:
        return
    
    if 'analysis' not in scan:
        scan['analysis'] = {}
    scan['analysis']['keywords'] = keyword_analysis.get('keywords', [])
    scan['analysis']['trends'] = keyword_analysis.get('trends', [])


def add_insights_to_scan(item, scan):
    """인사이트 정보를 scan에 추가"""
    insights = item.get('insights', {})
    if not insights:
        return
    
    if 'analysis' not in scan:
        scan['analysis'] = {}
    scan['analysis']['insights'] = insights.get('key_insights', [])
    overall_score = insights.get('overall_score', 50)
    scan['analysis']['overall_score'] = safe_decimal_to_int(overall_score, 50)


def extract_country_stats_from_item(item, scan):
    """국가별 통계를 추출하여 scan에 추가"""
    metadata_country_stats = item.get('country_stats', {})
    if not metadata_country_stats:
        return
    
    country_stats = {}
    for country_code, stats in metadata_country_stats.items():
        country_stats[country_code] = {
            'comments': safe_decimal_to_int(stats.get('comments', 0)),
            'likes': safe_decimal_to_int(stats.get('likes', 0))
        }
    
    if 'Other' not in country_stats:
        country_stats['Other'] = {'comments': 0, 'likes': 0}
    
    scan['country_stats'] = country_stats


def load_s3_data(s3_key, s3_client, s3_bucket, local_data_dir, local_mode):
    """S3 또는 로컬 파일에서 데이터 로드"""
    if not s3_key:
        return None
    
    try:
        if local_mode:
            filepath = get_local_filepath(s3_key, local_data_dir)
            if not os.path.exists(filepath):
                logger.warning(f"Local file not found: {filepath}")
                return None
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            obj = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
            return json.loads(obj['Body'].read().decode('utf-8'))
    except Exception as e:
        logger.error(f"Error loading S3 data for {s3_key}: {e}", exc_info=True)
        return None


def process_youtube_videos(s3_data):
    """YouTube 데이터에서 영상 정보 추출"""
    video_list = []
    for result in s3_data.get('data', []):
        video = result.get('video', {})
        if not video.get('video_id'):
            continue
        
        video_list.append({
            'title': video.get('title', ''),
            'url': f"https://www.youtube.com/watch?v={video.get('video_id')}",
            'channel': video.get('channel_title', ''),
            'comment_count': result.get('comment_count', 0)
        })
    return video_list[:5]  # 최대 5개


def is_recent_comment(comment, cutoff_date):
    """댓글이 최근 14일 이내인지 확인"""
    comment_published_at = comment.get('published_at') or comment.get('publishedAt', '')
    if not comment_published_at:
        return True  # 날짜 정보가 없으면 포함
    
    try:
        comment_date_str = comment_published_at.replace('Z', '+00:00')
        comment_date = datetime.fromisoformat(comment_date_str.replace('Z', '+00:00'))
        comment_date_naive = comment_date.replace(tzinfo=None)
        return comment_date_naive >= cutoff_date
    except (ValueError, AttributeError) as date_error:
        logger.warning(f"Failed to parse comment date '{comment_published_at}': {date_error}")
        return True  # 파싱 실패 시 포함


def load_data_from_s3_or_local(s3_key, s3_client, bucket, local_mode, local_data_dir):
    """S3 또는 로컬 파일에서 데이터 로드 (중첩 if 제거)"""
    if not s3_key:
        return None
    
    try:
        if local_mode:
            return _load_data_from_local(s3_key, local_data_dir)
        return _load_data_from_s3(s3_key, s3_client, bucket)
    except Exception as e:
        logger.error(f"Error loading data from {s3_key}: {e}", exc_info=True)
        return None


def _load_data_from_local(s3_key, local_data_dir):
    """로컬 파일에서 데이터 로드"""
    filepath = get_local_filepath(s3_key, local_data_dir)
    if not os.path.exists(filepath):
        logger.warning(f"Local file not found: {filepath}")
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def _load_data_from_s3(s3_key, s3_client, bucket):
    """S3에서 데이터 로드"""
    obj = s3_client.get_object(Bucket=bucket, Key=s3_key)
    return json.loads(obj['Body'].read().decode('utf-8'))


def should_skip_archive_studio_channel(channel_title, channel_id, is_archive_studio):
    """Example Studio 채널 필터링 (중첩 if 제거)"""
    if not is_archive_studio:
        return False

    # 채널 제목 확인
    if channel_title:
        channel_title_lower = channel_title.lower()
        if 'example studio' in channel_title_lower or 'examplestyle' in channel_title_lower:
            return False  # Example Studio 채널이므로 스킵하지 않음

    # 채널 ID 확인
    if channel_id and 'ExampleStudioOfficial' in str(channel_id):
        return False  # Example Studio 채널이므로 스킵하지 않음

    return True  # Example Studio 채널이 아니므로 스킵


def extract_comment_sentiment(comment, comment_text):
    """댓글에서 감성 분석 추출 (중첩 if 제거)"""
    # 기존 감성 분석 결과 확인
    sentiment = comment.get('sentiment') or comment.get('is_vtuber')
    if sentiment:
        return sentiment
    
    # 감성 분석이 없으면 키워드 기반 분석
    return detect_comment_sentiment(comment_text)


def create_comment_sample(comment, video, video_id):
    """댓글 샘플 객체 생성 (중첩 if 제거)"""
    comment_text = comment.get('text') or comment.get('textDisplay', '')
    if not comment_text or is_timestamp_comment(comment_text):
        return None
    
    sentiment = extract_comment_sentiment(comment, comment_text)
    
    return {
        'text': comment_text[:200],
        'author': comment.get('author', '') or comment.get('authorDisplayName', '익명'),
        'like_count': int(comment.get('like_count', 0) or comment.get('likeCount', 0)),
        'video_title': video.get('title', ''),
        'video_id': video_id,
        'video_url': f"https://www.youtube.com/watch?v={video_id}" if video_id else '',
        'sentiment': sentiment
    }


def extract_comments_from_video_data(video_data, comment_cutoff_date, is_archive_studio, max_comments=10):
    """비디오 데이터에서 댓글 샘플 추출 (중첩 if 제거)"""
    video = video_data.get('video', {})
    channel_title = video.get('channel_title', '')
    channel_id = video.get('channel_id', '')
    
    # ExampleStudio channel filtering
    if should_skip_archive_studio_channel(channel_title, channel_id, is_archive_studio):
        return []
    
    comments = video_data.get('comments', [])
    if not comments:
        return []
    
    comment_samples = []
    for comment in comments[:5]:
        if len(comment_samples) >= max_comments:
            break
        
        # 댓글 날짜 확인
        if not is_recent_comment(comment, comment_cutoff_date):
            continue
        
        # 댓글 샘플 생성
        comment_sample = create_comment_sample(comment, video, video.get('video_id'))
        if comment_sample:
            comment_samples.append(comment_sample)
    
    return comment_samples


def _distribute_comments_to_posts(posts_in_file, file_total_comments):
    """게시글에 댓글 수 분배 (중첩 if 제거)"""
    # comment_count가 있는 게시글과 없는 게시글 분리
    posts_with_count = [p for p in posts_in_file if (p.get('post', {}).get('comment_count', 0) > 0 or p.get('comment_count', 0) > 0)]
    posts_without_count = [p for p in posts_in_file if not (p.get('post', {}).get('comment_count', 0) > 0 or p.get('comment_count', 0) > 0)]
    
    # comment_count가 있는 게시글들의 총 댓글 수 계산
    counted_comments = sum([p.get('post', {}).get('comment_count', 0) or p.get('comment_count', 0) for p in posts_with_count])
    
    # 남은 댓글 수를 comment_count가 없는 게시글에 분배
    if posts_without_count:
        remaining_comments = max(0, file_total_comments - counted_comments)
        if remaining_comments > 0:
            avg_comments = max(1, remaining_comments // len(posts_without_count))
            _set_comment_count_for_posts(posts_without_count, avg_comments)
    elif not posts_with_count:
        # 모든 게시글에 comment_count가 없으면 평균 분배
        avg_comments = max(1, file_total_comments // len(posts_in_file))
        _set_comment_count_for_posts(posts_in_file, avg_comments)


def _set_comment_count_for_posts(posts, comment_count):
    """게시글에 댓글 수 설정 (중첩 if 제거)"""
    for post_data in posts:
        if 'post' in post_data:
            post_data['post']['comment_count'] = comment_count
        post_data['comment_count'] = comment_count


def process_youtube_comments(s3_data, scan, is_archive_studio, channel_handle):
    """YouTube 댓글 샘플 처리"""
    comment_samples = []
    comment_cutoff_date = datetime.now() - timedelta(days=14)
    
    country_stats = scan.get('country_stats', {
        'KR': {'comments': 0, 'likes': 0},
        'US': {'comments': 0, 'likes': 0},
        'JP': {'comments': 0, 'likes': 0},
        'Other': {'comments': 0, 'likes': 0}
    })
    
    for result in s3_data.get('data', []):
        video = result.get('video', {})
        channel_title = video.get('channel_title', '')
        channel_id = video.get('channel_id', '')
        
        # Example Studio 채널 필터링
        if is_archive_studio:
            channel_filter_from_data = s3_data.get('channel_filter')
            channel_handle_from_data = s3_data.get('channel_handle')
            is_archive_channel = is_archive_studio_channel(
                channel_id, channel_title, channel_handle,
                channel_filter_from_data, channel_handle_from_data
            )
            if not is_archive_channel:
                continue
        
        # 국가별 통계 집계
        result_country_stats = result.get('country_stats', {})
        for country_code, stats in result_country_stats.items():
            if country_code not in country_stats:
                continue
            
            comments_val = safe_decimal_to_int(stats.get('comments', 0))
            likes_val = safe_decimal_to_int(stats.get('likes', 0))
            country_stats[country_code]['comments'] += comments_val
            country_stats[country_code]['likes'] += likes_val
        
        # 댓글 샘플 추출
        for comment in result.get('comments', [])[:3]:
            if not is_recent_comment(comment, comment_cutoff_date):
                continue
            
            comment_text = comment.get('text') or comment.get('textDisplay', '')
            if not comment_text or is_timestamp_comment(comment_text):
                continue
            
            sentiment = comment.get('sentiment') or detect_comment_sentiment(comment_text)
            comment_samples.append({
                'text': comment_text[:150],
                'author': comment.get('author', '') or comment.get('authorDisplayName', '익명'),
                'like_count': int(comment.get('like_count', 0) or comment.get('likeCount', 0)),
                'video_title': result.get('video', {}).get('title', ''),
                'video_url': f"https://www.youtube.com/watch?v={video.get('video_id')}" if video.get('video_id') else '',
                'sentiment': sentiment
            })
    
    scan['comment_samples'] = comment_samples[:10]
    scan['country_stats'] = country_stats
    return scan


def process_youtube_platform_data(s3_data, scan, keyword, table, local_mode):
    """YouTube 플랫폼 데이터 처리"""
    # 영상 정보 추출
    scan['videos'] = process_youtube_videos(s3_data)
    
    # ExampleStudio related keyword check
    keyword_lower = scan.get('keyword', '').lower()
    is_archive_studio = any(kw in keyword_lower for kw in ['example studio', 'examplestyle', 'examplestudio'])
    
    # 댓글 샘플 및 국가별 통계 처리
    channel_handle = scan.get('channel', '')
    process_youtube_comments(s3_data, scan, is_archive_studio, channel_handle)
    
    # DynamoDB 또는 로컬 파일에서 분석 결과 가져오기
    try:
        if local_mode or table is None:
            analysis_item = load_latest_metadata('youtube', keyword)
        else:
            analysis_response = table.query(
                IndexName='platform-keyword-index',
                KeyConditionExpression='platform = :platform AND keyword = :keyword',
                ExpressionAttributeValues={
                    ':platform': 'youtube',
                    ':keyword': keyword
                },
                ScanIndexForward=False,
                Limit=1
            )
            analysis_item = analysis_response.get('Items', [None])[0] if analysis_response.get('Items') else None
        
        if analysis_item:
            # 감성 분석 결과 추출
            sentiment_analysis = analysis_item.get('sentiment_analysis', {})
            if sentiment_analysis:
                sentiment_dist = sentiment_analysis.get('sentiment_distribution', {})
                sentiment_distribution = {}
                for key in ['positive', 'negative', 'neutral']:
                    value = sentiment_dist.get(key, 0)
                    sentiment_distribution[key] = float(value) if isinstance(value, Decimal) else float(value) if value else 0.0
                
                scan['analysis'] = {
                    'sentiment': sentiment_analysis.get('overall_sentiment', 'neutral'),
                    'sentiment_distribution': sentiment_distribution
                }
            
            # 키워드 분석 결과 추출
            keyword_analysis = analysis_item.get('keyword_analysis', {})
            if keyword_analysis:
                if 'analysis' not in scan:
                    scan['analysis'] = {}
                scan['analysis']['summary'] = keyword_analysis.get('summary', '')
                scan['analysis']['keywords'] = keyword_analysis.get('keywords', [])
                scan['analysis']['trends'] = keyword_analysis.get('trends', [])
            
            # 인사이트 추출
            insights = analysis_item.get('insights', {})
            if insights:
                if 'analysis' not in scan:
                    scan['analysis'] = {}
                scan['analysis']['insights'] = insights.get('key_insights', [])
                overall_score = insights.get('overall_score', 50)
                scan['analysis']['overall_score'] = safe_decimal_to_int(overall_score, 50)
    except Exception as e:
        logger.error(f"Error loading analysis for YouTube scan: {e}", exc_info=True)
        # 분석 결과가 없으면 댓글 샘플에서 기본 감성 분포 계산
        comment_samples = scan.get('comment_samples', [])
        total_comments = scan.get('total_comments', 0)
        analysis = calculate_sentiment_from_comments(comment_samples, total_comments)
        if analysis:
            scan['analysis'] = analysis


def process_rss_platform_data(s3_data, scan):
    """RSS 플랫폼 데이터 처리"""
    entries = []
    for entry in s3_data.get('entries', [])[:5]:
        entries.append({
            'title': entry.get('title', ''),
            'link': entry.get('link', ''),
            'published': entry.get('published', ''),
            'summary': entry.get('summary', '')[:200]
        })
    scan['entries'] = entries


def _detect_reply_sentiment(reply_text):
    """댓글 텍스트에서 감성 분석 (중첩 if 제거)"""
    text_lower = reply_text.lower()
    positive_words = ['좋', '최고', '사랑', '감사', '고마', '훌륭', '멋', '대박', '완벽', '👍', '❤', '💕', '😊', '😍']
    negative_words = ['안좋', '최악', '싫', '별로', '실망', '나쁘', '문제', '불만', '😢', '😡', '👎']
    
    if any(word in text_lower for word in positive_words):
        return 'positive'
    if any(word in text_lower for word in negative_words):
        return 'negative'
    return 'neutral'


def _extract_twitter_replies(replies):
    """트위터 댓글 샘플 추출 (중첩 if 제거)"""
    comment_samples = []
    for reply in replies[:3]:
        reply_text = reply.get('text', '')
        if not reply_text:
            continue
        
        sentiment = reply.get('sentiment') or _detect_reply_sentiment(reply_text)
        
        comment_samples.append({
            'text': reply_text[:150],
            'author': reply.get('author', '익명'),
            'like_count': reply.get('like_count', 0),
            'sentiment': sentiment
        })
    return comment_samples


def process_twitter_platform_data(s3_data, scan):
    """Twitter 플랫폼 데이터 처리"""
    tweet_list = []
    comment_samples = []
    
    for result in s3_data.get('data', []):
        tweet = result.get('tweet', {})
        if tweet.get('tweet_id'):
            tweet_list.append({
                'title': tweet.get('text', '')[:100],
                'url': f"https://twitter.com/{tweet.get('author', '')}/status/{tweet.get('tweet_id', '')}",
                'author': tweet.get('author', ''),
                'like_count': tweet.get('like_count', 0)
            })
        
        # 댓글 샘플 추출
        replies = result.get('replies', [])
        comment_samples.extend(_extract_twitter_replies(replies))
    
    scan['tweets'] = tweet_list[:5]
    scan['comment_samples'] = comment_samples[:10]


def process_social_platform_data(s3_data, scan, platform):
    """Instagram, Facebook, Threads 등 소셜 플랫폼 데이터 처리"""
    post_list = []
    comment_samples = []
    
    for result in s3_data.get('data', []):
        post = result.get('post', {})
        if not post.get('post_id'):
            continue
        
        # 플랫폼별 URL 생성
        if platform == 'instagram':
            url = post.get('permalink', '')
            title = post.get('caption', '')[:100] or 'Instagram Post'
        elif platform == 'facebook':
            url = f"https://facebook.com/{post.get('post_id', '')}"
            title = post.get('message', '')[:100] or 'Facebook Post'
        elif platform == 'threads':
            url = f"https://threads.net/@{post.get('author', '')}/post/{post.get('post_id', '')}"
            title = post.get('text', '')[:100] or 'Threads Post'
        else:
            url = ''
            title = post.get('text', '')[:100] or f'{platform} Post'
        
        post_list.append({
            'title': title,
            'url': url,
            'author': post.get('author', platform),
            'like_count': post.get('like_count', 0)
        })
        
        # 댓글 샘플 추출
        comments = result.get('comments', []) if platform != 'threads' else result.get('replies', [])
        for comment in comments[:3]:
            comment_text = comment.get('text', '')
            if not comment_text:
                continue
            
            sentiment = comment.get('sentiment') or detect_comment_sentiment(comment_text)
            comment_samples.append({
                'text': comment_text[:150],
                'author': comment.get('author', '익명'),
                'like_count': comment.get('like_count', 0),
                'sentiment': sentiment
            })
    
    scan['posts'] = post_list[:5]
    scan['comment_samples'] = comment_samples[:10]


def convert_item_to_scan(item):
    """DynamoDB 아이템을 스캔 객체로 변환"""
    # Decimal 타입 변환
    total_comments = safe_decimal_to_int(item.get('total_comments', 0))
    videos_found = safe_decimal_to_int(item.get('videos_found', 0) or item.get('videos_analyzed', 0))
    entries_found = safe_decimal_to_int(item.get('entries_found', 0))
    tweets_found = safe_decimal_to_int(item.get('total_tweets', 0) or item.get('tweets_found', 0))
    posts_found = safe_decimal_to_int(item.get('total_posts', 0) or item.get('posts_found', 0))
    platform_value = safe_decimal_to_str(item.get('platform', 'unknown'))
    total_likes = safe_decimal_to_int(item.get('total_likes', 0))
    
    scan = {
        'id': item.get('id', ''),
        'platform': platform_value,
        'keyword': item.get('keyword', ''),
        'timestamp': item.get('timestamp', ''),
        's3_key': item.get('s3_key', ''),
        'total_comments': total_comments,
        'total_likes': total_likes,
        'videos_found': videos_found,
        'entries_found': entries_found,
        'tweets_found': tweets_found,
        'posts_found': posts_found,
        'channel': item.get('channel', ''),
        'channel_title': item.get('channel_title', '')
    }
    
    # 메타데이터에서 분석 정보 추출
    extract_sentiment_analysis_from_item(item, scan)
    add_keyword_analysis_to_scan(item, scan)
    add_insights_to_scan(item, scan)
    extract_country_stats_from_item(item, scan)
    
    return scan


def enrich_scan_with_s3_data(scan, s3_client, s3_bucket, local_data_dir, local_mode, table):
    """S3 데이터로 스캔 객체를 보강"""
    s3_key = scan.get('s3_key', '')
    s3_data = load_s3_data(s3_key, s3_client, s3_bucket, local_data_dir, local_mode)
    
    if not s3_data:
        return scan
    
    platform = scan.get('platform', '')
    keyword = scan.get('keyword', '')
    
    if platform == 'youtube':
        process_youtube_platform_data(s3_data, scan, keyword, table, local_mode)
    elif platform == 'rss':
        process_rss_platform_data(s3_data, scan)
    elif platform == 'twitter':
        process_twitter_platform_data(s3_data, scan)
    elif platform in ['instagram', 'facebook', 'threads']:
        process_social_platform_data(s3_data, scan, platform)
    # vuddy는 이미 처리됨
    
    return scan


def load_dcinside_gallery_data_local(gallery_dir, max_files=5, days_back=14):
    """로컬 모드에서 DC인사이드 갤러리 데이터 로드 (성능 최적화: 최신 파일만 읽기)
    
    Args:
        gallery_dir: 갤러리 디렉토리 경로
        max_files: 읽을 최대 파일 수 (0이면 제한 없음)
        days_back: 과거 며칠치 데이터를 읽을지 (기본 14일)
    """
    if not os.path.exists(gallery_dir):
        return [], '', [], 0, 0, 0
    
    all_posts_data = []
    seen_post_ids = set()
    latest_data = None
    total_comments = 0
    positive_count = 0
    negative_count = 0
    crawled_at = ''
    keywords = []
    
    # 날짜 기반 필터링을 위한 임계값 계산
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=days_back)
    
    # 최신 파일만 읽기 (성능 최적화)
    files = sorted(glob.glob(os.path.join(gallery_dir, '*.json')), reverse=True)
    
    # 날짜 기반 필터링: 파일명에서 날짜 추출 (형식: YYYY-MM-DD-HH-MM-SS.json)
    files_to_read = []
    for file_path in files:
        filename = os.path.basename(file_path)
        # 파일명에서 날짜 부분 추출 (YYYY-MM-DD)
        try:
            date_str = filename[:10]  # '2026-01-13'
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
            if file_date >= cutoff_date:
                files_to_read.append(file_path)
            else:
                # 날짜가 오래된 파일은 건너뛰기
                break
        except (ValueError, IndexError):
            # 날짜 파싱 실패 시 파일명에 날짜가 없는 경우이므로 포함
            files_to_read.append(file_path)
    
    # max_files 제한 적용 (0이면 제한 없음)
    if max_files > 0:
        files_to_read = files_to_read[:max_files]
    
    for i, file_path in enumerate(files_to_read):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
                if i == 0:  # 최신 파일에서 메타데이터 가져오기
                    latest_data = file_data
                    crawled_at = file_data.get('crawled_at', '')
                    keywords = file_data.get('keywords', [])
                file_total_comments = file_data.get('total_comments', 0)
                total_comments += file_total_comments
                positive_count += file_data.get('positive_count', 0)
                negative_count += file_data.get('negative_count', 0)
                posts_in_file = file_data.get('data', [])
                # 파일의 total_comments를 게시글에 분배 (각 게시글의 comment_count가 없을 때)
                if file_total_comments > 0 and posts_in_file:
                    _distribute_comments_to_posts(posts_in_file, file_total_comments)
                
                for post_data in posts_in_file:
                    post_id = post_data.get('post', {}).get('post_id', '')
                    if post_id and post_id not in seen_post_ids:
                        seen_post_ids.add(post_id)
                        all_posts_data.append(post_data)
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}", exc_info=True)
            continue
    
    return all_posts_data, crawled_at, keywords, total_comments, positive_count, negative_count

LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', './local-data')

def validate_environment_variables():
    """
    필수 환경 변수 검증
    
    보안 규칙 준수: 앱 시작 시점에 필수 환경 변수 존재 여부 확인
    """
    missing_vars = []
    
    # 로컬 모드가 아닐 때는 AWS 관련 환경 변수 필수
    if not LOCAL_MODE:
        required_vars = ['DYNAMODB_TABLE', 'S3_BUCKET']
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
    
    # 항상 필요한 환경 변수
    if not os.environ.get('AUTH_SERVICE_ENDPOINT'):
        logger.warning("AUTH_SERVICE_ENDPOINT not set, using default")
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info("Environment variables validated successfully")

# 환경 변수 검증 실행
try:
    validate_environment_variables()
except ValueError as e:
    logger.error(f"Environment validation failed: {e}")
    # Lambda에서는 계속 실행하되 경고만 남김 (운영 환경에서는 실패해야 함)

# 로컬 모드가 아닐 때만 AWS 클라이언트 초기화
if not LOCAL_MODE and boto3:
    # AWS 클라이언트
    dynamodb = boto3.resource('dynamodb')
    s3_client = boto3.client('s3')

# 환경 변수
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'sns-monitor-results')
DYNAMODB_ENDPOINT = os.environ.get('DYNAMODB_ENDPOINT')
S3_BUCKET = os.environ.get('S3_BUCKET', 'sns-monitor-data')
S3_ENDPOINT = os.environ.get('S3_ENDPOINT')

if boto3 and DYNAMODB_ENDPOINT:
    dynamodb = boto3.resource('dynamodb', endpoint_url=DYNAMODB_ENDPOINT)

if boto3 and S3_ENDPOINT:
    s3_client = boto3.client('s3', endpoint_url=S3_ENDPOINT)
elif not boto3 or not S3_ENDPOINT:
    # 로컬 모드: 공통 유틸리티 임포트
    common_path = os.path.join(os.path.dirname(__file__), '..', 'common')
    if os.path.exists(common_path):
        sys.path.insert(0, common_path)
    else:
        # 절대 경로로 시도
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        common_path = os.path.join(project_root, 'lambda', 'common')
        sys.path.insert(0, common_path)
    
    try:
        from local_storage import (
            load_from_local_file,
            list_local_files,
            load_latest_metadata
        )
    except ImportError as e:
        logger.warning(f"Could not import local_storage: {e}")
        # 기본 함수 정의
        def load_from_local_file(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        def list_local_files(platform, keyword=None, subdir=None):
            return []
        def load_latest_metadata(platform, keyword=None):
            return None
    
    dynamodb = None
    s3_client = None

# 환경 변수
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'sns-monitor-results')
AUTH_SERVICE_ENDPOINT = os.environ.get('AUTH_SERVICE_ENDPOINT', 'http://auth-service:8080')

def _handle_auth_proxy(event, path, query_params, http_method):
    """Auth 서비스 프록시 처리"""
    if not requests:
        return {
            'statusCode': 503,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Service unavailable: requests module not available'})
        }
    
    # 경로 검증 (보안: 경로 인젝션 방지)
    auth_path = path.replace('/api', '')
    # 허용된 경로 패턴만 허용 (화이트리스트 방식)
    if not re.match(r'^/auth(/[a-zA-Z0-9_-]+)*$', auth_path):
        logger.warning(f"Invalid auth path: {auth_path}")
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Invalid path'})
        }
    
    auth_url = f"{AUTH_SERVICE_ENDPOINT}{auth_path}"

    if http_method == 'GET':
        if query_params:
            # URL 인젝션 방지: 쿼리 파라미터를 안전하게 인코딩
            safe_params = []
            for k, v in query_params.items():
                # 키와 값 검증 (알파벳, 숫자, 하이픈, 언더스코어만 허용)
                if not re.match(r'^[a-zA-Z0-9_-]+$', str(k)):
                    logger.warning(f"Invalid query parameter key: {k}")
                    continue
                safe_params.append(f"{quote(str(k))}={quote(str(v))}")
            if safe_params:
                auth_url += '?' + '&'.join(safe_params)
        response = requests.get(auth_url, timeout=30, verify=True)
    elif http_method == 'POST':
        response = requests.post(auth_url, json=event.get('body'), timeout=30, verify=True)
    elif http_method == 'DELETE':
        response = requests.delete(auth_url, json=event.get('body'), timeout=30, verify=True)
    else:
        return {
            'statusCode': 405,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Method not allowed'})
        }

    return {
        'statusCode': response.status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': response.text
    }


def _handle_health_check():
    """헬스 체크 엔드포인트"""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat()
        })
    }


def _handle_dashboard_stats():
    """대시보드 통계 엔드포인트"""
    stats = {
        'total_items': 0,
        'today_items': 0,
        'analyzed_items': 0,
        'total_comments': 0,
        'avg_sentiment': 'neutral'
    }
    
    try:
        if LOCAL_MODE:
            metadata_dir = os.path.join(LOCAL_DATA_DIR, 'metadata')
            items = _load_metadata_files_local(metadata_dir)
        else:
            table = dynamodb.Table(DYNAMODB_TABLE)
            response = table.scan()
            items = response.get('Items', [])
        
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=None)
        
        total_items = len(items)
        today_items = 0
        analyzed_items = 0
        total_comments = 0
        
        for item in items:
            timestamp_str = item.get('timestamp', '')
            if _parse_timestamp_for_today(timestamp_str, today_start):
                today_items += 1
            
            if (item.get('synthesized_result') or 
                item.get('sentiment') or 
                item.get('sentiment_analysis') or
                item.get('insights')):
                analyzed_items += 1
            
            comments_value = item.get('total_comments', 0)
            if comments_value:
                # Decimal과 int 모두 int로 변환 (중복 블록 제거)
                total_comments += int(comments_value)
        
        stats = {
            'total_items': total_items,
            'today_items': today_items,
            'analyzed_items': analyzed_items,
            'total_comments': total_comments,
            'avg_sentiment': 'neutral'
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(stats, default=decimal_default)
    }


def _handle_scans():
    """스캔 목록 엔드포인트"""
    try:
        if LOCAL_MODE:
            metadata_dir = os.path.join(LOCAL_DATA_DIR, 'metadata')
            items = _load_metadata_files_local(metadata_dir)
            items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            items = items[:100]
        else:
            table = dynamodb.Table(DYNAMODB_TABLE)
            response = table.scan(Limit=100)
            items = response.get('Items', [])
        
        scans = []
        table_obj = table if not LOCAL_MODE else None
        for item in items:
            scan = convert_item_to_scan(item)
            scan = enrich_scan_with_s3_data(
                scan, s3_client, S3_BUCKET, LOCAL_DATA_DIR, LOCAL_MODE, table_obj
            )
            scans.append(scan)
        
        scans.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
    except Exception as e:
        logger.error(f"Error getting scans: {e}", exc_info=True)
        scans = []

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'scans': scans}, default=decimal_default)
    }


def _handle_channels():
    """채널 목록 엔드포인트"""
    channels = []
    
    try:
        if LOCAL_MODE:
            youtube_dir = os.path.join(LOCAL_DATA_DIR, 'youtube')
            channels = _load_channels_from_local(youtube_dir)
        else:
            if dynamodb:
                table = dynamodb.Table(DYNAMODB_TABLE)
                response = table.scan()
                items = response.get('Items', [])

                channels_dict = {}
                for item in items:
                    channel = item.get('channel', '')
                    if not channel:
                        continue

                    if channel not in channels_dict:
                        channels_dict[channel] = {
                            'channel': channel,
                            'channel_title': item.get('channel_title', channel),
                            'videos_analyzed': 0,
                            'total_comments': 0,
                            'vtuber_comments': 0,
                            'vtuber_likes': 0,
                            's3_key': item.get('s3_key', ''),
                            'last_updated': item.get('timestamp', '')
                        }

                    channels_dict[channel]['videos_analyzed'] += item.get('videos_analyzed', 0)
                    channels_dict[channel]['total_comments'] += item.get('total_comments', 0)
                    channels_dict[channel]['vtuber_comments'] += item.get('vtuber_comments', 0)
                    channels_dict[channel]['vtuber_likes'] += item.get('vtuber_likes', 0)

                    if item.get('timestamp', '') > channels_dict[channel].get('last_updated', ''):
                        channels_dict[channel]['s3_key'] = item.get('s3_key', '')
                        channels_dict[channel]['last_updated'] = item.get('timestamp', '')

                channels = list(channels_dict.values())
                channels.sort(key=lambda x: x.get('last_updated', ''), reverse=True)
            else:
                logger.warning("DynamoDB not available in production mode")
                channels = []
        
    except Exception as e:
        logger.error(f"Error getting channels: {e}", exc_info=True)
        channels = []

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'channels': channels}, default=decimal_default)
    }


def _convert_decimal_to_int(value):
    """Decimal 타입을 int로 변환하는 헬퍼 함수"""
    if isinstance(value, Decimal):
        return int(value)
    elif not isinstance(value, int):
        return int(value) if value else 0
    return value


def _process_country_stats(raw_country_stats):
    """국가별 통계 필드명 변환 및 처리"""
    country_stats = {}
    for country_code, stats in raw_country_stats.items():
        country_stats[country_code] = {
            'comments': stats.get('comment_count', stats.get('comments', 0)),
            'likes': stats.get('total_likes', stats.get('likes', 0))
        }
    return country_stats


def _process_creators_from_data(creators_data):
    """creators 배열에서 직접 정보 추출"""
    creators = []
    for creator_data in creators_data:
        raw_country_stats = creator_data.get('country_stats', {})
        country_stats = _process_country_stats(raw_country_stats)

        creator_info = {
            'name': creator_data.get('name', ''),
            'youtube_channel': creator_data.get('youtube_channel', ''),
            'vuddy_channel': creator_data.get('vuddy_channel', ''),
            'total_comments': creator_data.get('total_comments', 0),
            'total_likes': creator_data.get('total_likes', 0),
            'total_blog_posts': creator_data.get('total_blog_posts', 0),
            'total_google_results': creator_data.get('total_google_results', len(creator_data.get('google_links', []))),
            'youtube_search_status': 'success',
            'blog_search_status': 'success',
            'google_search_status': 'success',
            'comment_samples': [],
            'video_links': [],
            'social_media': creator_data.get('social_media', []),
            'google_links': creator_data.get('google_links', []),
            'platform_links': creator_data.get('platform_links', []),
            'soop_analysis': creator_data.get('soop_analysis'),
            'statistics': creator_data.get('statistics', {}),
            'country_stats': country_stats
        }

        # 댓글 샘플 변환
        for comment in creator_data.get('comment_samples', [])[:10]:
            comment_text = comment.get('text', '')
            if is_timestamp_comment(comment_text):
                continue

            video_id = comment.get('video_id', '')
            video_url = comment.get('video_url', '')
            if video_id and not video_url:
                video_url = f"https://www.youtube.com/watch?v={video_id}"

            creator_info['comment_samples'].append({
                'text': comment.get('text', ''),
                'author': comment.get('author', '익명'),
                'like_count': comment.get('like_count', 0),
                'published_at': comment.get('published_at', ''),
                'country': comment.get('country', 'Unknown'),
                'video_title': comment.get('video_title', ''),
                'video_id': video_id,
                'video_url': video_url,
                'sentiment': comment.get('sentiment', 'neutral')
            })

        # 비디오 링크 변환
        for video in creator_data.get('video_links', [])[:10]:
            creator_info['video_links'].append({
                'title': video.get('title', ''),
                'url': video.get('url', ''),
                'channel': video.get('channel', creator_data.get('name', '')),
                'published_at': video.get('published_at', '')
            })

        # 분석 결과 추가
        analysis_data = creator_data.get('analysis', {})
        sentiment_dist = creator_data.get('sentiment_distribution', {})
        sentiment_distribution = calculate_sentiment_distribution(sentiment_dist)
        overall_sentiment = get_overall_sentiment(sentiment_dist)

        creator_info['analysis'] = {
            'sentiment': overall_sentiment,
            'sentiment_distribution': sentiment_distribution,
            'summary': analysis_data.get('summary', f"총 {creator_info['total_comments']}개의 댓글이 수집되었습니다."),
            'keywords': analysis_data.get('keywords', []),
            'trends': analysis_data.get('trends', []),
            'insights': analysis_data.get('insights', []),
            'overall_score': creator_data.get('overall_score', 50),
            'analyzed_at': ''
        }

        creators.append(creator_info)
    
    return creators


def _aggregate_country_stats_from_s3(s3_key, s3_client, country_stats):
    """S3에서 데이터를 로드하여 국가별 통계 집계"""
    try:
        yt_data = load_data_from_s3_or_local(
            s3_key, s3_client, S3_BUCKET, LOCAL_MODE, LOCAL_DATA_DIR
        )
        if not yt_data:
            return
        
        video_country_stats = yt_data.get('country_stats', {})
        for country_code, stats in video_country_stats.items():
            if country_code not in country_stats:
                continue
            
            comments_val = _convert_decimal_to_int(stats.get('comments', 0))
            likes_val = _convert_decimal_to_int(stats.get('likes', 0))
            
            country_stats[country_code]['comments'] += comments_val
            country_stats[country_code]['likes'] += likes_val
    except Exception as e:
        logger.error(f"Error loading country stats from S3 {s3_key}: {e}", exc_info=True)


def _process_comprehensive_analysis(comprehensive_analysis):
    """종합 분석 결과에서 크리에이터 정보 추출"""
    creators = []
    
    for analysis in comprehensive_analysis:
        creator_name = analysis.get('creator_name', '')
        comment_samples = []
        video_links = []
        
        # Example Studio 채널 확인 (두 섹션에서 공통 사용)
        creator_name_lower = creator_name.lower()
        is_archive_studio = any(kw in creator_name_lower for kw in ['example studio', 'examplestyle', 'examplestudio'])
        comment_cutoff_date = datetime.now() - timedelta(days=14)
        
        # YouTube 검색 결과 처리
        youtube_search = analysis.get('youtube_search', {})
        if youtube_search.get('status') == 'success':
            
            for result in youtube_search.get('data', []):
                s3_key = result.get('s3_key')
                if not s3_key:
                    continue
                
                try:
                    yt_data = load_data_from_s3_or_local(
                        s3_key, s3_client, S3_BUCKET, LOCAL_MODE, LOCAL_DATA_DIR
                    )
                    if not yt_data:
                        continue
                    
                    for video_data in yt_data.get('data', []):
                        video = video_data.get('video', {})
                        video_id = video.get('video_id')
                        
                        if video_id and len(video_links) < 10:
                            video_links.append({
                                'title': video.get('title', ''),
                                'url': f"https://www.youtube.com/watch?v={video_id}",
                                'channel': video.get('channel_title', ''),
                                'published_at': video.get('published_at', '')
                            })
                        
                        if len(comment_samples) < 10:
                            extracted_comments = extract_comments_from_video_data(
                                video_data, comment_cutoff_date, is_archive_studio, max_comments=10
                            )
                            comment_samples.extend(extracted_comments)
                except Exception as e:
                    logger.error(f"Error loading YouTube search data from S3 {s3_key}: {e}", exc_info=True)
        
        # YouTube 채널 분석 결과 처리
        youtube_channel = analysis.get('youtube_channel_analysis', {})
        if youtube_channel.get('status') == 'success':
            for channel_result in youtube_channel.get('data', []):
                s3_key = channel_result.get('s3_key')
                if not s3_key:
                    continue
                
                try:
                    ch_data = load_data_from_s3_or_local(
                        s3_key, s3_client, S3_BUCKET, LOCAL_MODE, LOCAL_DATA_DIR
                    )
                    if not ch_data:
                        continue
                    
                    for video_info in ch_data.get('videos', []):
                        video = video_info.get('video', {})
                        video_id = video.get('video_id')
                        
                        if video_id and len(video_links) < 10:
                            video_links.append({
                                'title': video.get('title', ''),
                                'url': f"https://www.youtube.com/watch?v={video_id}",
                                'channel': ch_data.get('channel_title', ''),
                                'published_at': video.get('published_at', '')
                            })
                        
                        if len(comment_samples) < 10:
                            extracted_comments = extract_comments_from_video_data(
                                video_info, comment_cutoff_date, is_archive_studio, max_comments=10
                            )
                            comment_samples.extend(extracted_comments)
                except Exception as e:
                    logger.error(f"Error loading YouTube channel data from S3 {s3_key}: {e}", exc_info=True)
        
        # 분석 결과 가져오기
        analysis_result = _get_analysis_result(creator_name)
        
        # Google 검색 결과 링크 수집
        google_links = []
        google_search = analysis.get('google_search', {})
        if google_search.get('status') == 'success':
            for result in google_search.get('data', [])[:10]:
                google_links.append({
                    'title': result.get('title', ''),
                    'url': result.get('link', ''),
                    'snippet': result.get('snippet', '')[:200],
                    'source': result.get('source', 'google_search')
                })
        
        # 국가별 통계 집계
        country_stats = {'KR': {'comments': 0, 'likes': 0}, 'US': {'comments': 0, 'likes': 0}, 
                        'JP': {'comments': 0, 'likes': 0}, 'Other': {'comments': 0, 'likes': 0}}
        
        if youtube_search.get('status') == 'success':
            for result in youtube_search.get('data', []):
                s3_key = result.get('s3_key')
                if s3_key:
                    _aggregate_country_stats_from_s3(s3_key, s3_client, country_stats)
        
        youtube_channel = analysis.get('youtube_channel_analysis', {})
        if youtube_channel.get('status') == 'success':
            for channel_result in youtube_channel.get('data', []):
                s3_key = channel_result.get('s3_key')
                if s3_key:
                    _aggregate_country_stats_from_s3(s3_key, s3_client, country_stats)
        
        # 국가별 통계 직렬화
        country_stats_serialized = {}
        for country_code, stats in country_stats.items():
            country_stats_serialized[country_code] = {
                'comments': _convert_decimal_to_int(stats.get('comments', 0)),
                'likes': _convert_decimal_to_int(stats.get('likes', 0))
            }
        
        # 요약 및 키워드 생성
        summary_text, top_keywords = _generate_summary_and_keywords(comment_samples, video_links)
        google_summary_text = _generate_google_summary(google_links)
        
        creator_info = {
            'name': creator_name,
            'youtube_channel': analysis.get('youtube_channel', ''),
            'total_comments': analysis.get('total_comments', 0),
            'total_likes': analysis.get('total_likes', 0),
            'total_blog_posts': analysis.get('total_blog_posts', 0),
            'total_google_results': analysis.get('total_google_results', 0),
            'youtube_search_status': analysis.get('youtube_search', {}).get('status'),
            'blog_search_status': analysis.get('blog_search', {}).get('status'),
            'google_search_status': analysis.get('google_search', {}).get('status'),
            'comment_samples': comment_samples[:10],
            'video_links': video_links[:10],
            'google_links': google_links[:10],
            'country_stats': country_stats_serialized
        }
        
        # 분석 결과 추가
        creator_info['analysis'] = _build_analysis_info(
            analysis_result, comment_samples, summary_text, top_keywords, google_summary_text
        )
        
        creators.append(creator_info)
    
    return creators


def _get_analysis_result(creator_name):
    """DynamoDB 또는 로컬 파일에서 분석 결과 가져오기"""
    analysis_result = None
    try:
        if LOCAL_MODE:
            analysis_result = load_latest_metadata('vuddy', creator_name)
        else:
            table = dynamodb.Table(DYNAMODB_TABLE)
            try:
                response_db = table.query(
                    IndexName='platform-keyword-index',
                    KeyConditionExpression='platform = :platform AND keyword = :keyword',
                    ExpressionAttributeValues={
                        ':platform': 'vuddy',
                        ':keyword': creator_name
                    },
                    ScanIndexForward=False,
                    Limit=1
                )
                if response_db.get('Items'):
                    analysis_result = response_db['Items'][0]
            except Exception as query_error:
                logger.warning(f"Error querying with index, falling back to scan: {query_error}")
                response_scan = table.scan(
                    FilterExpression='platform = :platform AND keyword = :keyword',
                    ExpressionAttributeValues={
                        ':platform': 'vuddy',
                        ':keyword': creator_name
                    }
                )
                if response_scan.get('Items'):
                    analysis_result = sorted(
                        response_scan['Items'],
                        key=lambda x: x.get('timestamp', ''),
                        reverse=True
                    )[0]
    except Exception as e:
        logger.error(f"Error querying metadata for {creator_name}: {e}", exc_info=True)
    
    return analysis_result


def _generate_summary_and_keywords(comment_samples, video_links):
    """댓글 샘플 기반 요약 및 키워드 생성"""
    summary_text = ''
    top_keywords = []
    
    if not comment_samples:
        return summary_text, top_keywords
    
    from collections import Counter
    
    comment_texts = [c.get('text', '') for c in comment_samples[:10]]
    positive_count = sum(1 for c in comment_samples if c.get('sentiment') == 'positive')
    negative_count = sum(1 for c in comment_samples if c.get('sentiment') == 'negative')
    neutral_count = sum(1 for c in comment_samples if c.get('sentiment') == 'neutral')
    
    all_words = []
    for text in comment_texts:
        words = text.split()
        all_words.extend([w for w in words if len(w) > 1])
    
    word_freq = Counter(all_words)
    top_keywords = [word for word, count in word_freq.most_common(5) if count > 1]
    
    summary_parts = [f"총 {len(comment_samples)}개의 댓글 샘플이 수집되었습니다."]
    
    if positive_count > 0 or negative_count > 0 or neutral_count > 0:
        total_sentiment = positive_count + negative_count + neutral_count
        if total_sentiment > 0:
            pos_pct = int((positive_count / total_sentiment) * 100)
            neg_pct = int((negative_count / total_sentiment) * 100)
            neu_pct = int((neutral_count / total_sentiment) * 100)
            summary_parts.append(f"감성 분석 결과: 긍정 {pos_pct}%, 중립 {neu_pct}%, 부정 {neg_pct}%")
    
    if len(video_links) > 0:
        summary_parts.append(f"YouTube에서 {len(video_links)}개의 관련 영상을 찾았습니다.")
    
    if top_keywords:
        summary_parts.append(f"주요 키워드: {', '.join(top_keywords[:5])}")
    
    summary_text = ' '.join(summary_parts) if summary_parts else ''
    return summary_text, top_keywords


def _generate_google_summary(google_links):
    """Google 검색 결과 요약 생성"""
    if not google_links:
        return ''
    
    from collections import Counter
    
    google_summary_parts = [f"Google 검색에서 {len(google_links)}개의 관련 결과를 찾았습니다."]
    
    google_snippets = [link.get('snippet', '') for link in google_links[:5] if link.get('snippet')]
    if google_snippets:
        google_words = []
        for snippet in google_snippets:
            words = snippet.split()
            google_words.extend([w for w in words if len(w) > 2])
        
        google_word_freq = Counter(google_words)
        google_top_keywords = [word for word, count in google_word_freq.most_common(3) if count > 1]
        
        if google_top_keywords:
            google_summary_parts.append(f"Google 검색 주요 키워드: {', '.join(google_top_keywords)}")
        
        main_topics = []
        for snippet in google_snippets[:3]:
            if len(snippet) > 50:
                main_topics.append(snippet[:100] + '...')
            else:
                main_topics.append(snippet)
        
        if main_topics:
            google_summary_parts.append(f"주요 검색 내용: {' | '.join(main_topics[:2])}")
    
    return ' '.join(google_summary_parts) if google_summary_parts else ''


def _build_analysis_info(analysis_result, comment_samples, summary_text, top_keywords, google_summary_text):
    """분석 정보 빌드"""
    if analysis_result:
        sentiment_dist = analysis_result.get('sentiment_analysis', {}).get('sentiment_distribution', {})
        if sentiment_dist:
            sentiment_distribution = {}
            for key in ['positive', 'negative', 'neutral']:
                value = sentiment_dist.get(key, 0)
                if isinstance(value, Decimal):
                    sentiment_distribution[key] = float(value)
                else:
                    sentiment_distribution[key] = float(value) if value else 0.0
        else:
            sentiment_distribution = _calculate_sentiment_from_samples(comment_samples)
        
        overall_score = analysis_result.get('insights', {}).get('overall_score', 50)
        if isinstance(overall_score, Decimal):
            overall_score = int(overall_score)
        
        llm_summary = analysis_result.get('keyword_analysis', {}).get('summary', '')
        final_summary = llm_summary if llm_summary else summary_text
        if google_summary_text:
            final_summary += f" {google_summary_text}"
        
        llm_keywords = analysis_result.get('keyword_analysis', {}).get('keywords', [])
        final_keywords = llm_keywords if llm_keywords else top_keywords[:5]
        
        return {
            'sentiment': analysis_result.get('sentiment_analysis', {}).get('overall_sentiment', 'neutral'),
            'sentiment_distribution': sentiment_distribution,
            'summary': final_summary,
            'keywords': final_keywords,
            'trends': analysis_result.get('keyword_analysis', {}).get('trends', []),
            'insights': analysis_result.get('insights', {}).get('key_insights', []),
            'overall_score': overall_score,
            'analyzed_at': analysis_result.get('analyzed_at', '')
        }
    
    if comment_samples:
        sentiment_distribution, overall_sentiment, calculated_score = _calculate_sentiment_from_samples(comment_samples)
        final_summary = summary_text if summary_text else '댓글 분석 중입니다. 곧 요약이 제공됩니다.'
        if google_summary_text:
            final_summary += f" {google_summary_text}"
        
        return {
            'sentiment': overall_sentiment,
            'sentiment_distribution': sentiment_distribution,
            'summary': final_summary,
            'keywords': top_keywords[:5] if 'top_keywords' in locals() else [],
            'trends': [],
            'insights': [],
            'overall_score': calculated_score,
            'analyzed_at': ''
        }
    
    return {
        'sentiment': 'neutral',
        'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0},
        'summary': '',
        'keywords': [],
        'trends': [],
        'insights': [],
        'overall_score': 50,
        'analyzed_at': ''
    }


def _calculate_sentiment_from_samples(comment_samples):
    """댓글 샘플에서 감성 분포 계산"""
    if not comment_samples:
        return {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'neutral', 50
    
    total = len(comment_samples)
    positive_count = sum(1 for c in comment_samples if c.get('sentiment') == 'positive')
    negative_count = sum(1 for c in comment_samples if c.get('sentiment') == 'negative')
    neutral_count = total - positive_count - negative_count
    
    if total == 0:
        return {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'neutral', 50
    
    sentiment_distribution = {
        'positive': round(positive_count / total, 2),
        'negative': round(negative_count / total, 2),
        'neutral': round(neutral_count / total, 2)
    }
    
    if positive_count > negative_count and positive_count > neutral_count:
        overall_sentiment = 'positive'
    elif negative_count > positive_count and negative_count > neutral_count:
        overall_sentiment = 'negative'
    else:
        overall_sentiment = 'neutral'
    
    positive_ratio = positive_count / total if total > 0 else 0
    calculated_score = int(positive_ratio * 100)
    
    return sentiment_distribution, overall_sentiment, calculated_score


def _handle_vuddy_creators():
    """Vuddy 크리에이터 목록 엔드포인트"""
    try:
        creators = []
        data = None
        
        if LOCAL_MODE:
            vuddy_file = os.path.join(LOCAL_DATA_DIR, 'vuddy', 'comprehensive_analysis', 'vuddy-creators.json')
            if os.path.exists(vuddy_file):
                try:
                    with open(vuddy_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        logger.info(f"Loaded vuddy-creators.json with {len(data.get('creators', []))} creators")
                except Exception as e:
                    logger.error(f"Error loading vuddy-creators.json: {e}", exc_info=True)
            else:
                logger.debug(f"vuddy-creators.json not found at {vuddy_file}")
        else:
            vuddy_key = 'raw-data/vuddy/comprehensive_analysis/vuddy-creators.json'
            try:
                obj = s3_client.get_object(Bucket=S3_BUCKET, Key=vuddy_key)
                data = json.loads(obj['Body'].read().decode('utf-8'))
                logger.info(f"Loaded vuddy-creators.json from S3 with {len(data.get('creators', []))} creators")
            except Exception as e:
                logger.error(f"Error loading vuddy-creators.json from S3: {e}", exc_info=True)
        
        if not data:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'creators': []}, default=decimal_default, ensure_ascii=False)
            }
        
        # creators 배열에서 직접 정보 추출
        if 'creators' in data:
            creators = _process_creators_from_data(data.get('creators', []))
        
        # 종합 분석 결과에서 크리에이터 정보 추출 (기존 방식)
        elif 'comprehensive_analysis' in data:
            creators = _process_comprehensive_analysis(data.get('comprehensive_analysis', []))
        
    except Exception as e:
        logger.error(f"Error getting vuddy creators: {e}", exc_info=True)
        creators = []

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'creators': creators}, default=decimal_default, ensure_ascii=False)
    }


def _normalize_video_id_and_url(video_id, video_url):
    """
    video_id와 video_url을 정규화하는 헬퍼 함수
    video_id가 있으면 video_url을 생성하고, video_url이 있으면 video_id를 추출합니다.
    
    Args:
        video_id: YouTube video ID (optional)
        video_url: YouTube video URL (optional)
    
    Returns:
        tuple: (normalized_video_id, normalized_video_url)
    """
    normalized_id = video_id or ''
    normalized_url = video_url or ''
    
    # video_id가 있지만 video_url이 없으면 생성
    if normalized_id and not normalized_url:
        normalized_url = f"https://www.youtube.com/watch?v={normalized_id}"
    # video_url이 있지만 video_id가 없으면 추출 시도
    elif normalized_url and not normalized_id:
        match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', normalized_url)
        if match:
            normalized_id = match.group(1)
    
    return normalized_id, normalized_url


def _handle_group_a_members():
    """GroupA 멤버 목록 엔드포인트"""
    try:
        creators = []
        last_crawled = ''

        if LOCAL_MODE:
            # 먼저 group-a-members.json 파일에서 읽기 (빠름)
            group_a_json_path = os.path.join(LOCAL_DATA_DIR, 'vuddy', 'comprehensive_analysis', 'group-a-members.json')
            if os.path.exists(group_a_json_path):
                with open(group_a_json_path, 'r', encoding='utf-8') as f:
                    group_a_data = json.load(f)

                last_crawled = group_a_data.get('updated_at', '')

                for creator in group_a_data.get('creators', []):
                    # 댓글 샘플 변환
                    comment_samples = []
                    for sample in creator.get('comment_samples', [])[:50]:
                        video_id, video_url = _normalize_video_id_and_url(
                            sample.get('video_id', '') or '',
                            sample.get('video_url', '')
                        )

                        comment_samples.append({
                            'text': sample.get('text', ''),
                            'author': sample.get('author', '익명'),
                            'like_count': sample.get('likes', 0) or sample.get('like_count', 0),
                            'video_title': sample.get('video_title', ''),
                            'video_id': video_id,
                            'video_url': video_url,
                            'sentiment': sample.get('sentiment', 'neutral'),
                            'published_at': sample.get('published_at', '')
                        })

                    creator_info = {
                        'name': creator.get('name', ''),
                        'youtube_channel': creator.get('channel_handle', ''),
                        'channel_title': creator.get('channel_title', ''),
                        'total_comments': creator.get('total_comments', 0),
                        'statistics': {'subscriberCount': creator.get('subscriber_count', 0)},
                        'country_stats': {},
                        'comment_samples': comment_samples,
                        'video_links': [],
                        'last_crawled': last_crawled,
                        'analysis': {
                            'sentiment': 'neutral',
                            'sentiment_distribution': creator.get('sentiment_summary', {'positive': 0.6, 'neutral': 0.3, 'negative': 0.1}),
                            'summary': f"총 {creator.get('total_comments', 0)}개의 댓글이 수집되었습니다.",
                            'keywords': [],
                            'overall_score': 50
                        }
                    }
                    creators.append(creator_info)

                logger.info(f"Loaded {len(creators)} GroupA members from JSON file")

    except Exception as e:
        logger.error(f"Error getting GroupA members: {e}", exc_info=True)
        creators = []

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'creators': creators,
            'last_crawled': last_crawled
        }, default=decimal_default, ensure_ascii=False)
    }


def _handle_group_b_members():
    """GroupB 멤버 목록 엔드포인트"""
    try:
        creators = []
        data = None

        if LOCAL_MODE:
            # 로컬 모드: group-b-members.json 파일 로드
            filepath = os.path.join(LOCAL_DATA_DIR, 'vuddy', 'comprehensive_analysis', 'group-b-members.json')
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading GroupB members data: {e}", exc_info=True)
        else:
            # 프로덕션 모드: S3에서 group-b-members.json 가져오기
            try:
                obj = s3_client.get_object(
                    Bucket=S3_BUCKET,
                    Key='raw-data/vuddy/comprehensive_analysis/group-b-members.json'
                )
                data = json.loads(obj['Body'].read().decode('utf-8'))
            except Exception as e:
                logger.error(f"Error loading S3 data for GroupB members: {e}", exc_info=True)

        # 전체 수집 날짜
        last_crawled = data.get('timestamp', '') if data else ''

        if data and 'creators' in data:
            for creator_data in data.get('creators', []):
                # country_stats 필드명 변환
                raw_country_stats = creator_data.get('country_stats', {})
                country_stats = _process_country_stats(raw_country_stats)

                creator_info = {
                    'name': creator_data.get('name', ''),
                    'youtube_channel': creator_data.get('youtube_channel', ''),
                    'vuddy_channel': creator_data.get('vuddy_channel', ''),
                    'total_comments': creator_data.get('total_comments', 0),
                    'total_likes': creator_data.get('total_likes', 0),
                    'total_blog_posts': creator_data.get('total_blog_posts', 0),
                    'total_google_results': creator_data.get('total_google_results', len(creator_data.get('google_links', []))),
                    'youtube_search_status': 'success',
                    'blog_search_status': 'success',
                    'google_search_status': 'success',
                    'comment_samples': [],
                    'video_links': [],
                    'social_media': creator_data.get('social_media', []),
                    'google_links': creator_data.get('google_links', []),
                    'platform_links': creator_data.get('platform_links', []),
                    'statistics': creator_data.get('statistics', {}),
                    'country_stats': country_stats,
                    'last_crawled': last_crawled
                }

                # 댓글 샘플 변환 (최근 14일 이내 댓글만)
                comment_cutoff_date = datetime.now() - timedelta(days=14)
                creator_info['comment_samples'] = _process_group_b_comments(creator_data, comment_cutoff_date)

                # 비디오 링크 변환
                for video in creator_data.get('video_links', [])[:10]:
                    creator_info['video_links'].append({
                        'title': video.get('title', ''),
                        'url': video.get('url', ''),
                        'channel': video.get('channel', creator_data.get('name', '')),
                        'published_at': video.get('published_at', '')
                    })

                # 분석 결과 추가
                analysis_data = creator_data.get('analysis', {})
                sentiment_dist = creator_data.get('sentiment_distribution', {})
                sentiment_distribution = _calculate_sentiment_distribution_from_dict(sentiment_dist)
                overall_sentiment = _get_overall_sentiment_from_dist(sentiment_dist)

                creator_info['analysis'] = {
                    'sentiment': overall_sentiment,
                    'sentiment_distribution': sentiment_distribution,
                    'summary': analysis_data.get('summary', f"총 {creator_info['total_comments']}개의 댓글이 수집되었습니다."),
                    'keywords': analysis_data.get('keywords', []),
                    'trends': analysis_data.get('trends', []),
                    'insights': analysis_data.get('insights', []),
                    'overall_score': creator_data.get('overall_score', 50),
                    'analyzed_at': ''
                }

                creators.append(creator_info)

    except Exception as e:
        logger.error(f"Error getting GroupB members: {e}", exc_info=True)
        creators = []
        last_crawled = ''

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'creators': creators,
            'last_crawled': last_crawled
        }, default=decimal_default, ensure_ascii=False)
    }


def _handle_group_c_members():
    """GroupC 멤버 목록 엔드포인트"""
    try:
        creators = []
        data = None

        if LOCAL_MODE:
            # 로컬 모드: group-c-members.json 파일 로드
            filepath = os.path.join(LOCAL_DATA_DIR, 'vuddy', 'comprehensive_analysis', 'group-c-members.json')
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading GroupC members data: {e}", exc_info=True)
        else:
            # 프로덕션 모드: S3에서 group-c-members.json 가져오기
            try:
                obj = s3_client.get_object(
                    Bucket=S3_BUCKET,
                    Key='raw-data/vuddy/comprehensive_analysis/group-c-members.json'
                )
                data = json.loads(obj['Body'].read().decode('utf-8'))
            except Exception as e:
                logger.error(f"Error loading S3 data for GroupC members: {e}", exc_info=True)

        # 전체 수집 날짜
        last_crawled = data.get('timestamp', '') if data else ''

        if data and 'creators' in data:
            for creator_data in data.get('creators', []):
                # country_stats 필드명 변환
                raw_country_stats = creator_data.get('country_stats', {})
                country_stats = _process_country_stats(raw_country_stats)

                creator_info = {
                    'name': creator_data.get('name', ''),
                    'youtube_channel': creator_data.get('youtube_channel', ''),
                    'vuddy_channel': creator_data.get('vuddy_channel', ''),
                    'total_comments': creator_data.get('total_comments', 0),
                    'total_likes': creator_data.get('total_likes', 0),
                    'total_blog_posts': creator_data.get('total_blog_posts', 0),
                    'total_google_results': creator_data.get('total_google_results', len(creator_data.get('google_links', []))),
                    'youtube_search_status': 'success',
                    'blog_search_status': 'success',
                    'google_search_status': 'success',
                    'comment_samples': [],
                    'video_links': [],
                    'social_media': creator_data.get('social_media', []),
                    'google_links': creator_data.get('google_links', []),
                    'platform_links': creator_data.get('platform_links', []),
                    'statistics': creator_data.get('statistics', {}),
                    'country_stats': country_stats,
                    'last_crawled': last_crawled
                }

                # 댓글 샘플 변환 (최근 14일 이내 댓글만)
                comment_cutoff_date = datetime.now() - timedelta(days=14)
                creator_info['comment_samples'] = _process_group_b_comments(creator_data, comment_cutoff_date)

                # 비디오 링크 변환
                for video in creator_data.get('video_links', [])[:10]:
                    creator_info['video_links'].append({
                        'title': video.get('title', ''),
                        'url': video.get('url', ''),
                        'channel': video.get('channel', creator_data.get('name', '')),
                        'published_at': video.get('published_at', '')
                    })

                # 분석 결과 추가
                analysis_data = creator_data.get('analysis', {})
                sentiment_dist = creator_data.get('sentiment_distribution', {})
                sentiment_distribution = _calculate_sentiment_distribution_from_dict(sentiment_dist)
                overall_sentiment = _get_overall_sentiment_from_dist(sentiment_dist)

                creator_info['analysis'] = {
                    'sentiment': overall_sentiment,
                    'sentiment_distribution': sentiment_distribution,
                    'summary': analysis_data.get('summary', f"총 {creator_info['total_comments']}개의 댓글이 수집되었습니다."),
                    'keywords': analysis_data.get('keywords', []),
                    'trends': analysis_data.get('trends', []),
                    'insights': analysis_data.get('insights', []),
                    'overall_score': creator_data.get('overall_score', 50),
                    'analyzed_at': ''
                }

                creators.append(creator_info)

    except Exception as e:
        logger.error(f"Error getting GroupC members: {e}", exc_info=True)
        creators = []
        last_crawled = ''

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'creators': creators,
            'last_crawled': last_crawled
        }, default=decimal_default, ensure_ascii=False)
    }


def _load_group_c_members_data():
    """GroupC 멤버 데이터 로드"""
    data = None
    if LOCAL_MODE:
        filepath = os.path.join(LOCAL_DATA_DIR, 'vuddy', 'comprehensive_analysis', 'group-c-members.json')
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading GroupC members data: {e}", exc_info=True)
    else:
        try:
            obj = s3_client.get_object(
                Bucket=S3_BUCKET,
                Key='raw-data/vuddy/comprehensive_analysis/group-c-members.json'
            )
            data = json.loads(obj['Body'].read().decode('utf-8'))
        except Exception as e:
            logger.error(f"Error loading S3 data for GroupC members: {e}", exc_info=True)
    return data


def _handle_group_c_channel(event):
    """GroupC 채널 정보 엔드포인트"""
    try:
        # 쿼리 파라미터에서 channel_handle 가져오기
        query_params = event.get('queryStringParameters') or {}
        requested_handle = query_params.get('channel_handle') or query_params.get('channel', '')

        # 특정 채널 요청이 없으면 모든 GroupC 멤버 데이터 집계
        if not requested_handle:
            channels_data = []
            last_crawled = ''
            group_c_data = _load_group_c_members_data()

            if group_c_data:
                last_crawled = group_c_data.get('updated_at', '') or group_c_data.get('timestamp', '')

                for creator in group_c_data.get('creators', []):
                    # channel_handle이 없으면 youtube_channel 사용
                    channel_handle = creator.get('channel_handle', '') or creator.get('youtube_channel', '')
                    # channel_title 추출
                    channel_title = _extract_channel_title_from_name(creator)

                    # 채널 데이터 형식으로 변환
                    channel_info = {
                        'channel_handle': channel_handle,
                        'channel_title': channel_title,
                        'channel_thumbnail': creator.get('profile_image', ''),
                        'subscriber_count': creator.get('subscriber_count', 0),
                        'total_comments': creator.get('total_comments', 0),
                        'total_videos': creator.get('total_videos', 0),
                        'analysis_date': last_crawled,
                        'videos': [],
                        'comment_samples': creator.get('comment_samples', [])
                    }
                    channels_data.append(channel_info)

                logger.info(f"Loaded {len(channels_data)} GroupC channels from JSON file")

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'channels': channels_data,
                    'last_crawled': last_crawled
                }, default=decimal_default, ensure_ascii=False)
            }

        # @ 기호가 없으면 추가
        if not requested_handle.startswith('@'):
            requested_handle = '@' + requested_handle

        logger.debug(f"GroupC - Requested channel handle: {requested_handle}")

        channel_data = None

        if LOCAL_MODE:
            # 로컬 모드: YouTube 크롤러 데이터에서 해당 채널 찾기
            youtube_dir = os.path.join(LOCAL_DATA_DIR, 'youtube', 'channels')
            matching_files = find_channel_files_local(youtube_dir, requested_handle)
            if matching_files:
                matching_files.sort(key=lambda x: x[1], reverse=True)
                latest_filepath, _, channel_data = matching_files[0]
                logger.info(f"Found latest channel data for {requested_handle} in {latest_filepath}")
        else:
            # 프로덕션 모드: S3에서 채널 데이터 찾기
            s3_prefix = 'raw-data/youtube/channels/'
            matching_files = find_channel_files_s3(s3_client, S3_BUCKET, s3_prefix, requested_handle)
            if matching_files:
                latest_file, latest_data = max(matching_files, key=lambda x: x[0]['LastModified'])
                channel_data = latest_data
                logger.info(f"Found GroupC channel data for {requested_handle} in S3: {latest_file['Key']}")

        if channel_data:
            # 댓글 데이터 변환
            videos_list = channel_data.get('videos', [])
            videos, total_comments, total_vtuber_comments, total_vtuber_likes = _process_channel_videos(videos_list)

            logger.info(f"GroupC: Processed {len(videos)} videos, total_comments: {total_comments}")

            last_crawled_date = channel_data.get('timestamp', '') or channel_data.get('analysis_date', '')

            result = {
                'channel_title': channel_data.get('channel_title', requested_handle),
                'channel_id': channel_data.get('channel_id', ''),
                'channel_handle': channel_data.get('channel_handle', requested_handle),
                'videos': videos,
                'total_comments': total_comments,
                'total_vtuber_comments': total_vtuber_comments,
                'total_vtuber_likes': total_vtuber_likes,
                'statistics': channel_data.get('statistics', {}),
                'last_crawled': last_crawled_date
            }
        else:
            result = {
                'channel_title': requested_handle.replace('@', ''),
                'channel_id': '',
                'channel_handle': requested_handle,
                'videos': [],
                'total_comments': 0,
                'total_vtuber_comments': 0,
                'total_vtuber_likes': 0,
                'statistics': {},
                'last_crawled': ''
            }

    except Exception as e:
        logger.error(f"Error getting GroupC channel data: {e}", exc_info=True)
        result = {
            'channel_title': 'GroupC',
            'channel_id': '',
            'channel_handle': '@example-group-c',
            'videos': [],
            'total_comments': 0,
            'total_vtuber_comments': 0,
            'total_vtuber_likes': 0,
            'statistics': {},
            'last_crawled': ''
        }

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(result, default=decimal_default, ensure_ascii=False)
    }


def _process_channel_videos(videos_list):
    """채널 비디오 데이터를 처리하여 videos 리스트와 통계를 반환"""
    videos = []
    total_comments = 0
    total_vtuber_comments = 0
    total_vtuber_likes = 0

    if not videos_list:
        return videos, total_comments, total_vtuber_comments, total_vtuber_likes

    for video_info in videos_list:
        if not isinstance(video_info, dict):
            continue

        video_data = video_info.get('video', {})
        video_comments = video_info.get('comments', [])
        vtuber_stats = video_info.get('vtuber_stats', {})

        video_id = video_data.get('video_id', '') or video_data.get('id', '')
        video_title = video_data.get('title', '')
        published_at = video_data.get('published_at', '') or video_data.get('publishedAt', '')
        view_count = video_data.get('view_count', 0) or video_data.get('viewCount', 0)

        videos.append({
            'video_id': video_id,
            'title': video_title,
            'published_at': published_at,
            'view_count': view_count,
            'comments': video_comments,
            'vtuber_stats': vtuber_stats
        })

        total_comments += len(video_comments)
        if vtuber_stats:
            total_vtuber_comments += vtuber_stats.get('total_vtuber_comments', 0)
            total_vtuber_likes += vtuber_stats.get('vtuber_total_likes', 0)

    return videos, total_comments, total_vtuber_comments, total_vtuber_likes


def _is_comment_within_cutoff(comment_published_at, comment_cutoff_date):
    """댓글이 최근 14일 이내인지 확인 (중첩 if 제거)"""
    if not comment_published_at:
        return True  # 날짜가 없으면 포함
    
    try:
        comment_date_str = comment_published_at.replace('Z', '+00:00')
        comment_date = datetime.fromisoformat(comment_date_str.replace('Z', '+00:00'))
        comment_date_naive = comment_date.replace(tzinfo=None)
        return comment_date_naive >= comment_cutoff_date
    except (ValueError, AttributeError) as date_error:
        logger.warning(f"Failed to parse comment date '{comment_published_at}': {date_error}")
        return True  # 파싱 실패 시 포함


def _create_comment_sample_from_data(comment):
    """댓글 데이터에서 샘플 생성 (중첩 if 제거)"""
    video_id = comment.get('video_id', '')
    video_url = comment.get('video_url', '')
    
    if video_id and not video_url:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    return {
        'text': comment.get('text', ''),
        'author': comment.get('author', '익명'),
        'like_count': comment.get('like_count', 0),
        'video_title': comment.get('video_title', ''),
        'video_id': video_id,
        'video_url': video_url,
        'sentiment': comment.get('sentiment', 'neutral'),
        'published_at': comment.get('published_at', comment.get('publishedAt', ''))
    }


def _process_group_b_comments(creator_data, comment_cutoff_date):
    """GroupB/C 멤버의 댓글 샘플 처리 (중첩 if 제거)"""
    comment_samples = []
    
    for comment in creator_data.get('comment_samples', [])[:50]:
        comment_published_at = comment.get('published_at') or comment.get('publishedAt', '')
        if not _is_comment_within_cutoff(comment_published_at, comment_cutoff_date):
            continue
        
        comment_text = comment.get('text', '')
        if is_timestamp_comment(comment_text):
            continue
        
        comment_samples.append(_create_comment_sample_from_data(comment))
    
    return comment_samples


def _calculate_sentiment_distribution_from_dict(sentiment_dist):
    """감성 분포 딕셔너리에서 분포 계산 (중첩 if 제거)"""
    total_sentiment = sum(sentiment_dist.values()) if sentiment_dist else 0
    if total_sentiment > 0:
        return {
            'positive': round(sentiment_dist.get('positive', 0) / total_sentiment, 2),
            'negative': round(sentiment_dist.get('negative', 0) / total_sentiment, 2),
            'neutral': round(sentiment_dist.get('neutral', 0) / total_sentiment, 2)
        }
    return {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}


def _get_overall_sentiment_from_dist(sentiment_dist):
    """감성 분포에서 전체 감성 결정 (중첩 if 제거)"""
    if sentiment_dist:
        return max(sentiment_dist, key=sentiment_dist.get)
    return 'neutral'


def _extract_channel_title_from_name(creator):
    """
    creator 데이터에서 channel_title을 추출하는 헬퍼 함수
    channel_title이 없으면 name에서 괄호 앞부분만 추출합니다.
    
    Args:
        creator: creator 딕셔너리
    
    Returns:
        str: 추출된 channel_title
    """
    channel_title = creator.get('channel_title', '')
    if not channel_title:
        name = creator.get('name', '')
        # 이름에서 괄호 앞부분만 추출
        if '(' in name:
            channel_title = name.split('(')[0].strip()
        else:
            channel_title = name
    return channel_title


def _load_group_b_members_data():
    """
    GroupB 멤버 데이터를 로드하는 헬퍼 함수
    로컬 모드면 파일에서, 프로덕션 모드면 S3에서 로드합니다.

    Returns:
        dict: group_b_data 또는 None
    """
    group_b_data = None

    if LOCAL_MODE:
        # 먼저 group-b-members.json 파일에서 읽기 (빠름)
        group_b_json_path = os.path.join(LOCAL_DATA_DIR, 'vuddy', 'comprehensive_analysis', 'group-b-members.json')
        if os.path.exists(group_b_json_path):
            try:
                with open(group_b_json_path, 'r', encoding='utf-8') as f:
                    group_b_data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading GroupB members data: {e}", exc_info=True)
    else:
        # 프로덕션 모드: S3에서 group-b-members.json 가져오기
        try:
            obj = s3_client.get_object(
                Bucket=S3_BUCKET,
                Key='raw-data/vuddy/comprehensive_analysis/group-b-members.json'
            )
            group_b_data = json.loads(obj['Body'].read().decode('utf-8'))
        except Exception as e:
            logger.error(f"Error loading S3 data for GroupB members: {e}", exc_info=True)

    return group_b_data


def _handle_group_b_channel(event):
    """GroupB 채널 정보 엔드포인트"""
    try:
        # 쿼리 파라미터에서 channel_handle 가져오기
        query_params = event.get('queryStringParameters') or {}
        requested_handle = query_params.get('channel_handle') or query_params.get('channel', '')

        # 특정 채널 요청이 없으면 모든 GroupB 멤버 데이터 집계
        if not requested_handle:
            channels_data = []
            last_crawled = ''
            group_b_data = _load_group_b_members_data()

            if group_b_data:
                last_crawled = group_b_data.get('updated_at', '') or group_b_data.get('timestamp', '')

                for creator in group_b_data.get('creators', []):
                    # channel_handle이 없으면 youtube_channel 사용
                    channel_handle = creator.get('channel_handle', '') or creator.get('youtube_channel', '')
                    # channel_title 추출
                    channel_title = _extract_channel_title_from_name(creator)

                    # 채널 데이터 형식으로 변환
                    channel_info = {
                        'channel_handle': channel_handle,
                        'channel_title': channel_title,
                        'channel_thumbnail': creator.get('profile_image', ''),
                        'subscriber_count': creator.get('subscriber_count', 0),
                        'total_comments': creator.get('total_comments', 0),
                        'total_videos': creator.get('total_videos', 0),
                        'analysis_date': last_crawled,
                        'videos': [],
                        'comment_samples': creator.get('comment_samples', [])
                    }
                    channels_data.append(channel_info)

                logger.info(f"Loaded {len(channels_data)} GroupB channels from JSON file")

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'channels': channels_data,
                    'last_crawled': last_crawled
                }, default=decimal_default, ensure_ascii=False)
            }

        # @ 기호가 없으면 추가
        if not requested_handle.startswith('@'):
            requested_handle = '@' + requested_handle

        logger.debug(f"GroupB - Requested channel handle: {requested_handle}")

        channel_data = None

        if LOCAL_MODE:
            # 로컬 모드: YouTube 크롤러 데이터에서 해당 채널 찾기
            youtube_dir = os.path.join(LOCAL_DATA_DIR, 'youtube', 'channels')
            matching_files = find_channel_files_local(youtube_dir, requested_handle)
            if matching_files:
                matching_files.sort(key=lambda x: x[1], reverse=True)
                latest_filepath, _, channel_data = matching_files[0]
                logger.info(f"Found latest channel data for {requested_handle} in {latest_filepath}")
        else:
            # 프로덕션 모드: S3에서 채널 데이터 찾기
            s3_prefix = 'raw-data/youtube/channels/'
            matching_files = find_channel_files_s3(s3_client, S3_BUCKET, s3_prefix, requested_handle)
            if matching_files:
                latest_file, latest_data = max(matching_files, key=lambda x: x[0]['LastModified'])
                channel_data = latest_data
                logger.info(f"Found GroupB channel data for {requested_handle} in S3: {latest_file['Key']}")

        if channel_data:
            # 댓글 데이터 변환
            videos_list = channel_data.get('videos', [])
            videos, total_comments, total_vtuber_comments, total_vtuber_likes = _process_channel_videos(videos_list)

            logger.info(f"GroupB: Processed {len(videos)} videos, total_comments: {total_comments}")

            last_crawled_date = channel_data.get('timestamp', '') or channel_data.get('analysis_date', '')

            result = {
                'channel_title': channel_data.get('channel_title', requested_handle),
                'channel_id': channel_data.get('channel_id', ''),
                'channel_handle': channel_data.get('channel_handle', requested_handle),
                'videos': videos,
                'total_comments': total_comments,
                'total_vtuber_comments': total_vtuber_comments,
                'total_vtuber_likes': total_vtuber_likes,
                'statistics': channel_data.get('statistics', {}),
                'last_crawled': last_crawled_date
            }
        else:
            result = {
                'channel_title': requested_handle.replace('@', ''),
                'channel_id': '',
                'channel_handle': requested_handle,
                'videos': [],
                'total_comments': 0,
                'total_vtuber_comments': 0,
                'total_vtuber_likes': 0,
                'statistics': {},
                'last_crawled': ''
            }

    except Exception as e:
        logger.error(f"Error getting GroupB channel data: {e}", exc_info=True)
        result = {
            'channel_title': 'GroupB',
            'channel_id': '',
            'channel_handle': '@example-group-b',
            'videos': [],
            'total_comments': 0,
            'total_vtuber_comments': 0,
            'total_vtuber_likes': 0,
            'statistics': {},
            'last_crawled': ''
        }

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(result, default=decimal_default, ensure_ascii=False)
    }


def _trigger_youtube_crawler(requested_handle):
    """YouTube 크롤러 트리거 (중첩 if 제거)"""
    logger.info(f"No data found for {requested_handle}, triggering YouTube crawler...")
    
    if not requests:
        logger.warning("requests module not available, cannot trigger crawler")
        return
    
    try:
        youtube_crawler_url = os.environ.get('YOUTUBE_CRAWLER_ENDPOINT', 'http://youtube-crawler:5000/invoke')
        # 보안 강화: verify=False 제거, 기본값(verify=True) 사용
        # HTTP URL의 경우 SSL 검증이 적용되지 않지만, HTTPS URL의 경우 반드시 검증됨
        # 내부 서비스도 HTTPS를 사용하도록 권장 (프로덕션 환경)
        # 참고: verify=False를 사용하면 Session 객체가 생성될 때 보안 문제가 발생할 수 있음
        requests.post(youtube_crawler_url, json={
            'type': 'channel',
            'channels': [requested_handle],
            'max_videos': 10,
            'max_comments_per_video': 100
        }, timeout=5)  # verify 파라미터 제거 (기본값 True 사용)
        logger.info(f"Triggered YouTube crawler for {requested_handle}")
    except Exception as e:
        logger.error(f"Error triggering YouTube crawler for {requested_handle}: {e}", exc_info=True)


def _load_group_a_channel_members_from_local():
    """로컬에서 GroupA channel 멤버 데이터 로드 (중첩 if 제거)"""
    channels_data = []
    last_crawled = ''

    group_a_channel_json_path = os.path.join(LOCAL_DATA_DIR, 'vuddy', 'comprehensive_analysis', 'group-a-channel-members.json')
    if not os.path.exists(group_a_channel_json_path):
        return channels_data, last_crawled

    try:
        with open(group_a_channel_json_path, 'r', encoding='utf-8') as f:
            group_a_channel_data = json.load(f)

        last_crawled = group_a_channel_data.get('updated_at', '')

        for creator in group_a_channel_data.get('creators', []):
            channel_info = {
                'channel_handle': creator.get('channel_handle', ''),
                'channel_title': creator.get('channel_title', creator.get('name', '')),
                'channel_thumbnail': creator.get('profile_image', ''),
                'subscriber_count': creator.get('subscriber_count', 0),
                'total_comments': creator.get('total_comments', 0),
                'total_videos': creator.get('total_videos', 0),
                'analysis_date': last_crawled or group_a_channel_data.get('timestamp', ''),
                'videos': [],
                'comment_samples': creator.get('comment_samples', [])
            }
            channels_data.append(channel_info)

        logger.info(f"Loaded {len(channels_data)} GroupA channel members from JSON file")
    except Exception as e:
        logger.error(f"Error loading GroupA channel members from local: {e}", exc_info=True)

    return channels_data, last_crawled


def _handle_group_a_channel_all_channels():
    """모든 GroupA channel 데이터 반환 (중첩 if 제거)"""
    channels_data = []
    last_crawled = ''

    if LOCAL_MODE:
        channels_data, last_crawled = _load_group_a_channel_members_from_local()

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'channels': channels_data,
            'last_crawled': last_crawled
        }, default=decimal_default, ensure_ascii=False)
    }


def _handle_group_a_channel(event):
    """GroupA channel 정보 엔드포인트"""
    try:
        # 쿼리 파라미터에서 channel_handle 가져오기
        query_params = event.get('queryStringParameters') or {}
        requested_handle = query_params.get('channel_handle') or query_params.get('channel', '')

        # 특정 채널 요청이 없으면 모든 GroupA channel 멤버 데이터 집계
        if not requested_handle:
            return _handle_group_a_channel_all_channels()

        # @ 기호가 없으면 추가
        if not requested_handle.startswith('@'):
            requested_handle = '@' + requested_handle

        logger.debug(f"Requested channel handle: {requested_handle}")

        channel_data = None

        if LOCAL_MODE:
            # 로컬 모드: YouTube 크롤러 데이터에서 해당 채널 찾기
            youtube_dir = os.path.join(LOCAL_DATA_DIR, 'youtube', 'channels')
            matching_files = find_channel_files_local(youtube_dir, requested_handle)
            if matching_files:
                matching_files.sort(key=lambda x: x[1], reverse=True)
                latest_filepath, _, channel_data = matching_files[0]
                logger.info(f"Found latest channel data for {requested_handle} in {latest_filepath}")
        else:
            # 프로덕션 모드: S3에서 채널 데이터 찾기
            s3_prefix = 'raw-data/youtube/channels/'
            matching_files = find_channel_files_s3(s3_client, S3_BUCKET, s3_prefix, requested_handle)
            if matching_files:
                latest_file, latest_data = max(matching_files, key=lambda x: x[0]['LastModified'])
                channel_data = latest_data
                logger.info(f"Found channel data for {requested_handle} in S3: {latest_file['Key']}")
                logger.debug(f"Channel data keys: {list(channel_data.keys())}")
                logger.debug(f"Videos count: {len(channel_data.get('videos', []))}")
                if channel_data.get('videos'):
                    logger.debug(f"First video structure: {list(channel_data['videos'][0].keys()) if channel_data['videos'] else 'N/A'}")

        # 데이터가 없으면 YouTube 크롤러를 트리거하여 수집
        if not channel_data:
            _trigger_youtube_crawler(requested_handle)

        if channel_data:
            # 댓글 데이터 변환
            videos_list = channel_data.get('videos', [])
            videos, total_comments, total_vtuber_comments, total_vtuber_likes = _process_channel_videos(videos_list)

            logger.info(f"Processed {len(videos)} videos, total_comments: {total_comments}")

            # timestamp 또는 analysis_date에서 날짜 가져오기
            last_crawled_date = channel_data.get('timestamp', '') or channel_data.get('analysis_date', '')
            
            result = {
                'channel_title': channel_data.get('channel_title', requested_handle),
                'channel_id': channel_data.get('channel_id', ''),
                'channel_handle': channel_data.get('channel_handle', requested_handle),
                'videos': videos,
                'total_comments': total_comments,
                'total_vtuber_comments': total_vtuber_comments,
                'total_vtuber_likes': total_vtuber_likes,
                'statistics': channel_data.get('statistics', {}),
                'last_crawled': last_crawled_date
            }
        else:
            result = {
                'channel_title': requested_handle.replace('@', ''),
                'channel_id': '',
                'channel_handle': requested_handle,
                'videos': [],
                'total_comments': 0,
                'total_vtuber_comments': 0,
                'total_vtuber_likes': 0,
                'statistics': {},
                'last_crawled': ''
            }

    except Exception as e:
        logger.error(f"Error getting GroupA channel data: {e}", exc_info=True)
        result = {
            'channel_title': 'GroupA Channel',
            'channel_id': '',
            'channel_handle': '@example-group-a-channel',
            'videos': [],
            'total_comments': 0,
            'total_vtuber_comments': 0,
            'total_vtuber_likes': 0,
            'statistics': {},
            'last_crawled': ''
        }

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(result, default=decimal_default, ensure_ascii=False)
    }


def _process_dcinside_s3_files(s3_client, bucket, gallery_id):
    """S3에서 DC인사이드 갤러리 파일들을 처리하여 게시글 데이터와 통계를 반환"""
    all_posts_data = []
    seen_post_ids = set()
    latest_data = None
    total_comments = 0
    positive_count = 0
    negative_count = 0
    crawled_at = ''
    keywords = []

    prefix = f'raw-data/dcinside/{gallery_id}/'
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    
    if 'Contents' not in response:
        return all_posts_data, latest_data, total_comments, positive_count, negative_count, crawled_at, keywords

    files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
    
    for i, file_info in enumerate(files):
        try:
            obj = s3_client.get_object(Bucket=bucket, Key=file_info['Key'])
            file_data = json.loads(obj['Body'].read().decode('utf-8'))
            
            if i == 0:  # 최신 파일에서 메타데이터 가져오기
                latest_data = file_data
                crawled_at = file_data.get('crawled_at', '')
                keywords = file_data.get('keywords', [])
            
            total_comments += file_data.get('total_comments', 0)
            positive_count += file_data.get('positive_count', 0)
            negative_count += file_data.get('negative_count', 0)
            
            # 게시글 데이터 수집 및 중복 제거
            for post_data in file_data.get('data', []):
                post_id = post_data.get('post', {}).get('post_id', '')
                if post_id and post_id not in seen_post_ids:
                    seen_post_ids.add(post_id)
                    all_posts_data.append(post_data)
        except Exception as e:
            logger.error(f"Error reading S3 object: {e}", exc_info=True)
            continue

    return all_posts_data, latest_data, total_comments, positive_count, negative_count, crawled_at, keywords


def _distribute_comment_counts(all_posts_data, total_comments):
    """total_comments가 있지만 각 게시글의 comment_count가 없는 경우 평균 분배"""
    if total_comments <= 0 or len(all_posts_data) == 0:
        return
    
    posts_with_count = [
        p for p in all_posts_data 
        if (p.get('post', {}).get('comment_count', 0) > 0 or p.get('comment_count', 0) > 0)
    ]
    
    if len(posts_with_count) > 0:
        return
    
    # total_comments를 게시글 수로 나눠서 각 게시글에 분배
    avg_comments_per_post = max(1, total_comments // len(all_posts_data))
    
    for post_data in all_posts_data:
        post = post_data.get('post', {})
        if not post.get('comment_count', 0):
            post['comment_count'] = avg_comments_per_post
        if not post_data.get('comment_count', 0):
            post_data['comment_count'] = avg_comments_per_post


def _handle_dcinside_galleries():
    """DC인사이드 갤러리 목록 엔드포인트"""
    try:
        galleries_data = []

        # DC인사이드 갤러리 목록
        gallery_ids = ['example-gallery-1', 'example-gallery-2', 'example-gallery-3', 'example-gallery-4', 'example-gallery-5']
        gallery_names = {
            'example-gallery-1': 'Example Gallery 1',
            'example-gallery-2': 'Example Gallery 2',
            'example-gallery-3': 'Example Gallery 3',
            'example-gallery-4': 'Example Gallery 4',
            'example-gallery-5': 'Example Gallery 5',
        }

        for gallery_id in gallery_ids:
            try:
                all_posts_data = []
                seen_post_ids = set()
                latest_data = None
                total_comments = 0
                positive_count = 0
                negative_count = 0
                crawled_at = ''
                keywords = []

                if LOCAL_MODE:
                    # 로컬 모드: 과거 14일치 데이터 읽기
                    gallery_dir = os.path.join(LOCAL_DATA_DIR, 'dcinside', gallery_id)
                    # 과거 14일치 데이터 읽기 (max_files=0이면 날짜 필터만 적용)
                    posts_data, crawled_at_val, keywords_val, comments_val, pos_val, neg_val = \
                        load_dcinside_gallery_data_local(gallery_dir, max_files=0, days_back=14)
                    all_posts_data.extend(posts_data)
                    crawled_at = crawled_at_val
                    keywords = keywords_val
                    total_comments += comments_val
                    positive_count += pos_val
                    negative_count += neg_val
                    
                    # total_comments가 있지만 각 게시글의 comment_count가 없는 경우 미리 분배
                    _distribute_comment_counts(all_posts_data, total_comments)
                else:
                    # 프로덕션 모드: S3에서 모든 파일 수집
                    all_posts_data, latest_data, total_comments, positive_count, negative_count, crawled_at, keywords = \
                        _process_dcinside_s3_files(s3_client, S3_BUCKET, gallery_id)

                if all_posts_data:
                    # 게시글 데이터 포맷팅 (최대 20개, 성능 최적화)
                    posts = []
                    # 댓글이 있는 게시글 우선 표시
                    posts_with_comments = [p for p in all_posts_data if p.get('comments') and len(p.get('comments', [])) > 0]
                    posts_without_comments = [p for p in all_posts_data if not p.get('comments') or len(p.get('comments', [])) == 0]
                    
                    # 댓글이 있는 게시글 먼저, 그 다음 댓글 없는 게시글
                    sorted_posts = posts_with_comments + posts_without_comments
                    
                    # total_comments가 있지만 각 게시글의 comment_count가 0인 경우 분배
                    posts_with_actual_comments = [p for p in sorted_posts if (p.get('post', {}).get('comment_count', 0) > 0 or p.get('comment_count', 0) > 0 or (p.get('comments') and len(p.get('comments', [])) > 0))]
                    if total_comments > 0 and len(posts_with_actual_comments) == 0 and len(sorted_posts) > 0:
                        # total_comments를 게시글 수로 나눠서 각 게시글에 분배
                        avg_comments_per_post = max(1, total_comments // len(sorted_posts))
                        for post_data in sorted_posts:
                            post = post_data.get('post', {})
                            if not post.get('comment_count', 0):
                                post['comment_count'] = avg_comments_per_post
                            if not post_data.get('comment_count', 0):
                                post_data['comment_count'] = avg_comments_per_post
                    
                    for post_data in sorted_posts[:20]:
                        post = post_data.get('post', {})
                        comments = post_data.get('comments', [])
                        # comment_count 우선순위: post의 comment_count > post_data의 comment_count > comments 길이
                        comment_count = post.get('comment_count', 0) or post_data.get('comment_count', 0) or len(comments) if comments else 0
                        
                        posts.append({
                            'post_id': post.get('post_id', ''),
                            'title': post.get('title', ''),
                            'author': post.get('author', '익명'),
                            'date': post.get('date', ''),
                            'view_count': post.get('view_count', 0),
                            'recommend_count': post.get('recommend_count', 0),
                            'url': post.get('url', ''),
                            'content': post_data.get('content', ''),
                            'comment_count': comment_count,
                            'comments': comments[:10] if comments else [],  # 최대 10개 댓글만 전송 (성능 최적화)
                            'matched_keyword': post.get('matched_keyword', '')
                        })

                    galleries_data.append({
                        'gallery_id': gallery_id,
                        'gallery_name': gallery_names.get(gallery_id, gallery_id),
                        'total_posts': len(all_posts_data),  # 모든 파일의 고유 게시글 수
                        'total_comments': total_comments,
                        'positive_count': positive_count,
                        'negative_count': negative_count,
                        'crawled_at': crawled_at,
                        'keywords': keywords,
                        'posts': posts
                    })
            except Exception as e:
                logger.error(f"Error loading gallery {gallery_id}: {e}", exc_info=True)
                continue

    except Exception as e:
        logger.error(f"Error getting DC인사이드 galleries: {e}", exc_info=True)
        galleries_data = []

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'galleries': galleries_data}, default=decimal_default, ensure_ascii=False)
    }


def _handle_dcinside_gallery_posts(event, path):
    """DC인사이드 특정 갤러리의 게시글 페이지네이션 엔드포인트"""
    try:
        # URL에서 gallery_id 추출
        parts = path.split('/')
        gallery_id_idx = parts.index('gallery') + 1
        gallery_id = parts[gallery_id_idx] if gallery_id_idx < len(parts) else None

        if not gallery_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Gallery ID is required'})
            }

        # 쿼리 파라미터에서 페이지네이션 정보 추출
        query_params = event.get('queryStringParameters', {}) or {}
        page = int(query_params.get('page', 1))
        limit = min(int(query_params.get('limit', 20)), 100)  # 최대 100개
        offset = (page - 1) * limit

        all_posts_data = []
        seen_post_ids = set()

        if LOCAL_MODE:
            gallery_dir = os.path.join(LOCAL_DATA_DIR, 'dcinside', gallery_id)
            # 페이지네이션을 위해 과거 14일치 데이터 읽기
            posts_data, _, _, _, _, _ = load_dcinside_gallery_data_local(gallery_dir, max_files=0, days_back=14)
            for post_data in posts_data:
                post_id = post_data.get('post', {}).get('post_id', '')
                if post_id and post_id not in seen_post_ids:
                    seen_post_ids.add(post_id)
                    all_posts_data.append(post_data)
        else:
            prefix = f'raw-data/dcinside/{gallery_id}/'
            response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
            if 'Contents' in response:
                files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
                for file_info in files:
                    try:
                        obj = s3_client.get_object(Bucket=S3_BUCKET, Key=file_info['Key'])
                        file_data = json.loads(obj['Body'].read().decode('utf-8'))
                        for post_data in file_data.get('data', []):
                            post_id = post_data.get('post', {}).get('post_id', '')
                            if post_id and post_id not in seen_post_ids:
                                seen_post_ids.add(post_id)
                                all_posts_data.append(post_data)
                    except Exception as e:
                        logger.error(f"Error reading S3 object: {e}", exc_info=True)
                        continue

        if all_posts_data:
            total_posts = len(all_posts_data)

            # 페이지네이션 적용
            paginated_data = all_posts_data[offset:offset + limit]

            posts = []
            for post_data in paginated_data:
                post = post_data.get('post', {})
                posts.append({
                    'post_id': post.get('post_id', ''),
                    'title': post.get('title', ''),
                    'author': post.get('author', '익명'),
                    'date': post.get('date', ''),
                    'view_count': post.get('view_count', 0),
                    'recommend_count': post.get('recommend_count', 0),
                    'url': post.get('url', ''),
                    'content': post_data.get('content', ''),
                    'comment_count': post_data.get('comment_count', 0),
                    'comments': post_data.get('comments', []),
                    'matched_keyword': post.get('matched_keyword', '')
                })

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'gallery_id': gallery_id,
                    'posts': posts,
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total_posts': total_posts,
                        'total_pages': (total_posts + limit - 1) // limit,
                        'has_more': offset + limit < total_posts
                    }
                }, default=decimal_default, ensure_ascii=False)
            }
        
        # Gallery not found
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Gallery not found'})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }


def _handle_data_s3_key(path):
    """S3 키로 데이터 조회 엔드포인트"""
    s3_key = path.replace('/api/data/', '')
    
    try:
        if LOCAL_MODE:
            # 로컬 모드: 파일 시스템에서 읽기
            if s3_key.startswith('local-data/'):
                filepath = s3_key.replace('local-data/', LOCAL_DATA_DIR + '/')
            elif s3_key.startswith('./local-data/'):
                filepath = s3_key.replace('./local-data/', LOCAL_DATA_DIR + '/')
            else:
                filepath = os.path.join(LOCAL_DATA_DIR, s3_key.replace('raw-data/', ''))
            
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Data not found'})
                }
        else:
            # 프로덕션 모드: S3에서 읽기
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            data = json.loads(response['Body'].read().decode('utf-8'))
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(data, default=decimal_default, ensure_ascii=False)
        }
    except Exception as e:
        logger.error(f"Error getting data: {e}", exc_info=True)
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Data not found'})
        }


def _fetch_tweets_from_crawler(twitter_crawler_endpoint, keyword):
    """Twitter 크롤러 API를 호출하여 트윗 데이터를 가져옴"""
    tweets = []
    replies = []
    
    if not requests:
        return tweets, replies
    
    try:
        response = requests.post(
            f"{twitter_crawler_endpoint}/crawl",
            json={'keywords': [keyword]},
            timeout=30,
            verify=True
        )
        
        if response.status_code != 200:
            return tweets, replies
        
        data = response.json()
        results = data.get('results', [])
        
        if not results:
            return tweets, replies
        
        keyword_result = results[0]
        tweets = keyword_result.get('tweets', [])
        replies = keyword_result.get('replies', [])
    except Exception as e:
        logger.error(f"Error calling Twitter crawler: {e}", exc_info=True)
    
    return tweets, replies


def _load_tweets_from_local_files(keyword):
    """로컬 파일 시스템에서 키워드와 관련된 트위터 데이터를 로드"""
    tweets = []
    replies = []
    
    if not LOCAL_MODE:
        return tweets, replies
    
    twitter_data_dir = os.path.join(LOCAL_DATA_DIR, 'twitter')
    if not os.path.exists(twitter_data_dir):
        return tweets, replies
    
    for file_path in glob.glob(os.path.join(twitter_data_dir, '**/*.json'), recursive=True):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 키워드가 데이터에 포함되어 있는지 확인
            if keyword.lower() not in json.dumps(data, ensure_ascii=False).lower():
                continue
            
            # tweets 데이터 추출
            if 'tweets' in data:
                tweets.extend(data['tweets'])
            
            # data 배열에서 추가 트윗 및 댓글 추출
            if 'data' in data:
                for item in data['data']:
                    if 'tweet' in item:
                        tweets.append(item['tweet'])
                    if 'replies' in item:
                        replies.extend(item['replies'])
        except Exception as e:
            logger.error(f"Error reading twitter data file {file_path}: {e}", exc_info=True)
    
    return tweets, replies


def _handle_twitter_search(event):
    """트위터 키워드 검색 엔드포인트"""
    try:
        # 입력 검증: JSON 파싱 및 예외 처리
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in request body: {e}")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Invalid JSON format'})
            }
        
        action = body.get('action', 'search')
        # 입력 검증: action 값 화이트리스트
        if action not in ['search', 'bulk_search']:
            logger.warning(f"Invalid action: {action}")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Invalid action'})
            }

        # Twitter 크롤러 엔드포인트
        twitter_crawler_endpoint = os.environ.get('TWITTER_CRAWLER_ENDPOINT', 'http://twitter-crawler:5000')

        if action == 'bulk_search':
            # 여러 키워드 동시 검색
            keywords = body.get('keywords', [])
            results = {}

            for keyword in keywords[:10]:  # 최대 10개
                try:
                    tweets, replies = _fetch_tweets_from_crawler(twitter_crawler_endpoint, keyword)
                    results[keyword] = {
                        'tweets': tweets,
                        'replies': replies,
                        'total_tweets': len(tweets)
                    }
                except Exception as e:
                    logger.error(f"Error searching keyword '{keyword}': {e}", exc_info=True)
                    results[keyword] = {'tweets': [], 'replies': [], 'error': str(e)}

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'results': results}, default=decimal_default, ensure_ascii=False)
            }
        
        # 단일 키워드 검색
        keyword = body.get('keyword', '')

        if not keyword:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Keyword is required'})
            }

        tweets, replies = _fetch_tweets_from_crawler(twitter_crawler_endpoint, keyword)

        # 로컬 데이터에서 추가 트위터 데이터 검색
        local_tweets, local_replies = _load_tweets_from_local_files(keyword)
        tweets.extend(local_tweets)
        replies.extend(local_replies)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'tweets': tweets,
                'replies': replies,
                'keyword': keyword,
                'total_tweets': len(tweets),
                'total_replies': len(replies)
            }, default=decimal_default, ensure_ascii=False)
        }
    except Exception as e:
        logger.error(f"Error in Twitter search: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }


def _save_youtube_result(result, timestamp):
    """YouTube 크롤러 결과 저장 (중첩 if 제거)"""
    channel_handle = result.get('channel')
    if not channel_handle:
        return False, None
    
    channel_clean = channel_handle.lstrip('@').lower()
    
    if LOCAL_MODE:
        save_dir = os.path.join(LOCAL_DATA_DIR, 'youtube', channel_clean)
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, f"{timestamp}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved YouTube crawler result to {filepath}")
    else:
        s3_key = f"raw-data/youtube/{channel_clean}/{timestamp}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(result, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        logger.info(f"Saved YouTube crawler result to s3://{S3_BUCKET}/{s3_key}")
    
    return True, channel_handle


def _save_dcinside_result(result, timestamp):
    """DCInside 크롤러 결과 저장 (중첩 if 제거)"""
    gallery_id = result.get('gallery_id')
    if not gallery_id:
        return False
    
    if LOCAL_MODE:
        save_dir = os.path.join(LOCAL_DATA_DIR, 'dcinside', gallery_id)
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, f"{timestamp}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved DCInside crawler result to {filepath}")
    else:
        s3_key = f"raw-data/dcinside/{gallery_id}/{timestamp}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(result, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        logger.info(f"Saved DCInside crawler result to s3://{S3_BUCKET}/{s3_key}")
    
    return True


def _handle_crawler_results(event):
    """크롤러 결과 저장 엔드포인트 (DCInside + YouTube)"""
    try:
        # 입력 검증: JSON 파싱 및 예외 처리
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in crawler results: {e}")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Invalid JSON format'})
            }
        
        results = body.get('results', [])
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        
        saved_count = 0
        youtube_channels_saved = []
        
        for result in results:
            # YouTube 결과 처리
            saved, channel_handle = _save_youtube_result(result, timestamp)
            if saved:
                saved_count += 1
                youtube_channels_saved.append(channel_handle)
                continue
            
            # DCInside 결과 처리
            if _save_dcinside_result(result, timestamp):
                saved_count += 1
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': f'Saved {saved_count} results',
                'saved_count': saved_count,
                'youtube_channels': youtube_channels_saved
            })
        }
    except Exception as e:
        logger.error(f"Error saving crawler results: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }


def _handle_analyze_url(event):
    """URL 분석 엔드포인트 - YouTube, DCInside 등 SNS URL을 분석"""
    try:
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Invalid JSON format'})
            }

        url = body.get('url', '').strip()
        if not url:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'URL is required'})
            }

        # URL validation (allowlist approach)
        import re as re_mod
        url_pattern = re_mod.compile(
            r'^https?://(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com|'
            r'gall\.dcinside\.com|dcinside\.com|'
            r'reddit\.com|old\.reddit\.com|'
            r't\.me|twitter\.com|x\.com)'
        )
        if not url_pattern.match(url):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Unsupported URL. Supported: YouTube, DCInside, Reddit, Twitter/X, Telegram'})
            }

        lower_url = url.lower()
        result = {'url': url, 'analyzed_at': datetime.now().isoformat()}

        if 'youtube.com' in lower_url or 'youtu.be' in lower_url:
            result.update(_analyze_youtube_url(url))
        elif 'dcinside.com' in lower_url:
            result.update(_analyze_dcinside_url(url))
        elif 'twitter.com' in lower_url or 'x.com' in lower_url:
            result.update(_analyze_twitter_url(url))
        elif 'reddit.com' in lower_url:
            result.update(_analyze_reddit_url(url))
        elif 't.me' in lower_url:
            result.update({'platform': 'telegram', 'title': 'Telegram', 'description': 'Telegram URL analysis is not yet supported'})

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(result, ensure_ascii=False, default=decimal_default)
        }
    except Exception as e:
        logger.error(f"Error in _handle_analyze_url: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }


def _analyze_youtube_url(url):
    """YouTube URL 분석 - YouTube Data API 또는 로컬 데이터 활용"""
    import re as re_mod

    result = {'platform': 'youtube'}

    # Extract video ID
    video_id = None
    video_match = re_mod.search(r'(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})', url)
    if video_match:
        video_id = video_match.group(1)

    # Extract channel handle
    channel_handle = None
    handle_match = re_mod.search(r'youtube\.com/(@[\w.-]+)', url)
    if handle_match:
        channel_handle = handle_match.group(1)

    # Try YouTube Data API
    youtube_api_key = os.environ.get('YOUTUBE_API_KEY', '')
    if youtube_api_key and requests:
        try:
            if video_id:
                api_url = (
                    f'https://www.googleapis.com/youtube/v3/videos'
                    f'?part=snippet,statistics&id={video_id}&key={youtube_api_key}'
                )
                resp = requests.get(api_url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('items'):
                        item = data['items'][0]
                        snippet = item['snippet']
                        stats = item.get('statistics', {})
                        result.update({
                            'title': snippet.get('title', ''),
                            'description': snippet.get('description', '')[:500],
                            'channel_name': snippet.get('channelTitle', ''),
                            'published_at': snippet.get('publishedAt', ''),
                            'view_count': int(stats.get('viewCount', 0)),
                            'like_count': int(stats.get('likeCount', 0)),
                            'comment_count': int(stats.get('commentCount', 0)),
                            'video_id': video_id,
                        })

                        # Fetch comments
                        comments = _fetch_youtube_comments(video_id, youtube_api_key)
                        if comments:
                            result['comments'] = comments[:20]
                            result['analysis'] = _simple_sentiment_analysis(comments)
                        result['url'] = f'https://www.youtube.com/watch?v={video_id}'
                        return result

            elif channel_handle:
                handle_clean = channel_handle.lstrip('@')
                api_url = (
                    f'https://www.googleapis.com/youtube/v3/search'
                    f'?part=snippet&q={quote(handle_clean)}&type=channel&key={youtube_api_key}'
                )
                resp = requests.get(api_url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('items'):
                        channel_id = data['items'][0]['snippet']['channelId']
                        ch_url = (
                            f'https://www.googleapis.com/youtube/v3/channels'
                            f'?part=snippet,statistics&id={channel_id}&key={youtube_api_key}'
                        )
                        ch_resp = requests.get(ch_url, timeout=10)
                        if ch_resp.status_code == 200:
                            ch_data = ch_resp.json()
                            if ch_data.get('items'):
                                ch_item = ch_data['items'][0]
                                ch_snippet = ch_item['snippet']
                                ch_stats = ch_item.get('statistics', {})
                                result.update({
                                    'title': ch_snippet.get('title', ''),
                                    'description': ch_snippet.get('description', '')[:500],
                                    'channel_name': ch_snippet.get('title', ''),
                                    'subscriber_count': int(ch_stats.get('subscriberCount', 0)),
                                    'video_count': int(ch_stats.get('videoCount', 0)),
                                    'view_count': int(ch_stats.get('viewCount', 0)),
                                })

                                # Fetch recent videos
                                videos = _fetch_channel_recent_videos(channel_id, youtube_api_key)
                                if videos:
                                    result['recent_videos'] = videos[:10]
                                return result
        except Exception as e:
            logger.warning(f"YouTube API error: {e}")

    # Fallback: search local data
    result.update(_search_local_youtube_data(video_id, channel_handle))
    return result


def _fetch_youtube_comments(video_id, api_key):
    """YouTube 동영상 댓글 가져오기"""
    try:
        api_url = (
            f'https://www.googleapis.com/youtube/v3/commentThreads'
            f'?part=snippet&videoId={video_id}&maxResults=50&order=relevance&key={api_key}'
        )
        resp = requests.get(api_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            comments = []
            for item in data.get('items', []):
                snippet = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'text': snippet.get('textDisplay', ''),
                    'author': snippet.get('authorDisplayName', ''),
                    'like_count': snippet.get('likeCount', 0),
                    'published_at': snippet.get('publishedAt', ''),
                })
            return comments
    except Exception as e:
        logger.warning(f"Error fetching comments: {e}")
    return []


def _fetch_channel_recent_videos(channel_id, api_key):
    """채널 최근 동영상 목록"""
    try:
        api_url = (
            f'https://www.googleapis.com/youtube/v3/search'
            f'?part=snippet&channelId={channel_id}&maxResults=10&order=date&type=video&key={api_key}'
        )
        resp = requests.get(api_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            videos = []
            for item in data.get('items', []):
                vid = item['id'].get('videoId', '')
                videos.append({
                    'title': item['snippet'].get('title', ''),
                    'video_id': vid,
                    'published_at': item['snippet'].get('publishedAt', ''),
                    'description': item['snippet'].get('description', '')[:200],
                    'url': f'https://www.youtube.com/watch?v={vid}' if vid else '',
                })
            return videos
    except Exception as e:
        logger.warning(f"Error fetching channel videos: {e}")
    return []


def _search_local_youtube_data(video_id, channel_handle):
    """로컬 데이터에서 YouTube 정보 검색"""
    result = {}
    local_data_dir = os.environ.get('LOCAL_DATA_DIR', '/app/local-data')
    youtube_dir = os.path.join(local_data_dir, 'youtube', 'channels')

    if not os.path.exists(youtube_dir):
        result['title'] = 'YouTube'
        result['description'] = 'No local data available. Set YOUTUBE_API_KEY for live analysis.'
        return result

    # Search through channel files
    for file_path in glob.glob(os.path.join(youtube_dir, '**', '*.json'), recursive=True):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if video_id:
                # Search for matching video
                for video in data.get('videos', []):
                    if video.get('video_id') == video_id:
                        result.update({
                            'title': video.get('title', ''),
                            'view_count': video.get('views', 0),
                            'like_count': video.get('likes', 0),
                            'comment_count': video.get('comments', 0),
                            'video_id': video_id,
                        })
                        comments = video.get('comment_samples', [])
                        if comments:
                            result['comments'] = comments[:20]
                            result['analysis'] = _simple_sentiment_analysis(comments)
                        return result

            if channel_handle:
                handle_clean = channel_handle.lstrip('@').lower()
                ch_handle = (data.get('channel_handle', '') or '').lstrip('@').lower()
                if handle_clean == ch_handle:
                    result.update({
                        'title': data.get('channel_title', ''),
                        'channel_name': data.get('channel_title', ''),
                        'description': data.get('description', '')[:500],
                        'subscriber_count': data.get('subscriber_count', 0),
                        'video_count': data.get('video_count', 0),
                    })
                    if data.get('videos'):
                        result['recent_videos'] = data['videos'][:10]
                    return result
        except Exception:
            continue

    result['title'] = channel_handle or video_id or 'YouTube'
    result['description'] = 'No matching data found in local storage.'
    return result


def _analyze_dcinside_url(url):
    """DCInside URL 분석 - 로컬 데이터에서 검색"""
    import re as re_mod
    result = {'platform': 'dcinside'}

    # Extract gallery ID from URL
    gallery_match = re_mod.search(r'[?&]id=([^&]+)', url)
    gallery_id = gallery_match.group(1) if gallery_match else None

    if not gallery_id:
        # Try path-based: /board/lists/?id=xxx or /mini/board/lists/?id=xxx
        path_match = re_mod.search(r'/(?:mini|mgallery)/board/lists/?\?id=([^&]+)', url)
        if path_match:
            gallery_id = path_match.group(1)

    if not gallery_id:
        result['title'] = 'DCInside'
        result['description'] = 'Could not extract gallery ID from URL.'
        return result

    result['gallery_id'] = gallery_id

    # Search local data
    local_data_dir = os.environ.get('LOCAL_DATA_DIR', '/app/local-data')
    dcinside_dir = os.path.join(local_data_dir, 'dcinside')

    for file_path in glob.glob(os.path.join(dcinside_dir, f'{gallery_id}', '*.json')) + \
                      glob.glob(os.path.join(dcinside_dir, f'{gallery_id}.json')):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            result.update({
                'title': data.get('gallery_name', gallery_id),
                'total_posts': data.get('total_posts', len(data.get('posts', []))),
                'total_comments': data.get('total_comments', 0),
            })

            posts = data.get('posts', [])
            if posts:
                # Include comments for each post and add URL
                enriched_posts = []
                for p in posts[:20]:
                    post_data = dict(p)
                    # Add direct URL if not present
                    if not post_data.get('url') and gallery_id and post_data.get('post_id'):
                        post_data['url'] = f'https://gall.dcinside.com/mgallery/board/view/?id={gallery_id}&no={post_data["post_id"]}'
                    enriched_posts.append(post_data)
                result['posts'] = enriched_posts
                # Build analysis from posts and comments
                all_texts = []
                for p in posts:
                    all_texts.append({'text': p.get('title', '') + ' ' + p.get('content', '')})
                    for c in p.get('comments', []):
                        all_texts.append({'text': c.get('text', '') or c.get('content', '')})
                result['analysis'] = _simple_sentiment_analysis(all_texts)
            return result
        except Exception:
            continue

    result['title'] = gallery_id
    result['description'] = f'Gallery "{gallery_id}" not found in local data. Run crawler first.'
    return result


def _analyze_twitter_url(url):
    """Twitter/X URL 분석"""
    import re as re_mod
    result = {'platform': 'twitter'}

    # Extract username
    user_match = re_mod.search(r'(?:twitter\.com|x\.com)/(@?[\w]+)', url)
    username = user_match.group(1) if user_match else None

    if username:
        result['title'] = f'@{username.lstrip("@")}'

    # Search local twitter data
    local_data_dir = os.environ.get('LOCAL_DATA_DIR', '/app/local-data')
    twitter_dir = os.path.join(local_data_dir, 'twitter')

    if os.path.exists(twitter_dir):
        for file_path in glob.glob(os.path.join(twitter_dir, '**', '*.json'), recursive=True):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                tweets = data.get('tweets', [])
                if tweets:
                    result['posts'] = tweets[:20]
                    result['total_posts'] = len(tweets)
                    result['analysis'] = _simple_sentiment_analysis(
                        [{'text': t.get('text', '')} for t in tweets]
                    )
                    return result
            except Exception:
                continue

    result['description'] = 'Twitter data analysis requires crawler data. Run the Twitter crawler first.'
    return result


def _analyze_reddit_url(url):
    """Reddit URL 분석"""
    import re as re_mod
    result = {'platform': 'reddit'}

    sub_match = re_mod.search(r'reddit\.com/r/([\w]+)', url)
    if sub_match:
        result['subreddit'] = sub_match.group(1)
        result['title'] = f'r/{sub_match.group(1)}'
    else:
        result['title'] = 'Reddit'

    result['description'] = 'Reddit analysis requires crawler data.'
    return result


def _simple_sentiment_analysis(items):
    """간단한 감성 분석 (키워드 기반)"""
    positive_words = ['좋아', '최고', '감사', '사랑', '대박', '멋지', '예쁘', '귀엽',
                      '응원', '화이팅', 'love', 'great', 'amazing', 'awesome', 'best',
                      '좋다', '재밌', '웃기', '감동', '완벽', '훌륭', '행복']
    negative_words = ['싫어', '나쁘', '최악', '실망', '별로', '짜증', '혐오',
                      'hate', 'worst', 'bad', 'terrible', 'awful',
                      '쓰레기', '망했', '노잼']

    total = len(items)
    if total == 0:
        return None

    pos = 0
    neg = 0
    top_keywords = {}

    for item in items:
        text = (item.get('text', '') or '').lower()
        is_pos = any(w in text for w in positive_words)
        is_neg = any(w in text for w in negative_words)
        if is_pos and not is_neg:
            pos += 1
        elif is_neg and not is_pos:
            neg += 1

        # Extract keywords
        for word in text.split():
            word = word.strip('.,!?()[]{}"\':;')
            if len(word) >= 2 and word not in ('the', 'and', 'for', 'that', 'this', 'with', 'are', 'was', 'has'):
                top_keywords[word] = top_keywords.get(word, 0) + 1

    neu = total - pos - neg
    overall = 'positive' if pos > neg else ('negative' if neg > pos else 'neutral')

    sorted_keywords = sorted(top_keywords.items(), key=lambda x: x[1], reverse=True)[:15]

    return {
        'total': total,
        'sentiment': {
            'positive': pos,
            'neutral': neu,
            'negative': neg,
        },
        'overall': overall,
        'top_keywords': [{'word': w, 'count': c} for w, c in sorted_keywords],
    }


def lambda_handler(event, context):
    """
    Lambda 핸들러

    API Gateway 프록시 통합
    """
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '')
    query_params = event.get('queryStringParameters') or {}

    logger.info(f"Received request: {http_method} {path}")

    try:
        # Auth 엔드포인트 프록시
        if path.startswith('/api/auth'):
            return _handle_auth_proxy(event, path, query_params, http_method)

        # GET /health
        if path.endswith('/health'):
            return _handle_health_check()

        # GET /api/dashboard/stats
        elif path.endswith('/dashboard/stats'):
            return _handle_dashboard_stats()

        # GET /api/scans
        elif path.endswith('/scans'):
            return _handle_scans()

        # GET /api/channels
        elif path.endswith('/channels'):
            return _handle_channels()

        # GET /api/vuddy/creators
        elif path.endswith('/vuddy/creators'):
            return _handle_vuddy_creators()

        # GET /api/group-a/members (GroupA members)
        elif path.endswith('/group-a/members'):
            return _handle_group_a_members()

        # GET /api/group-b/members (GroupB members)
        elif path.endswith('/group-b/members'):
            return _handle_group_b_members()

        # GET /api/group-b/channel (GroupB channel)
        elif path.endswith('/group-b/channel'):
            return _handle_group_b_channel(event)

        # GET /api/group-c/members (GroupC members)
        elif path.endswith('/group-c/members'):
            return _handle_group_c_members()

        # GET /api/group-c/channel (GroupC channel)
        elif path.endswith('/group-c/channel'):
            return _handle_group_c_channel(event)

        # GET /api/group-a/channel (GroupA channel)
        elif path.endswith('/group-a/channel'):
            return _handle_group_a_channel(event)

        # GET /api/dcinside/galleries
        elif path.endswith('/dcinside/galleries'):
            return _handle_dcinside_galleries()

        # GET /api/dcinside/gallery/{gallery_id}/posts - 특정 갤러리의 게시글 페이지네이션
        elif '/dcinside/gallery/' in path and path.endswith('/posts'):
            return _handle_dcinside_gallery_posts(event, path)

        # POST /api/twitter/search - 트위터 키워드 검색
        elif path.endswith('/twitter/search') and http_method == 'POST':
            return _handle_twitter_search(event)

        # GET /api/data/{s3_key}
        elif path.startswith('/api/data/'):
            return _handle_data_s3_key(path)

        # POST /api/analyze/url - URL 분석
        elif path.endswith('/analyze/url') and http_method == 'POST':
            return _handle_analyze_url(event)

        # POST /api/crawler/results - 크롤러 결과 저장 (DCInside + YouTube)
        elif path.endswith('/crawler/results') and http_method == 'POST':
            return _handle_crawler_results(event)

        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Not found'})
            }

    except Exception as e:
        logger.error(f"Unhandled error in lambda_handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
