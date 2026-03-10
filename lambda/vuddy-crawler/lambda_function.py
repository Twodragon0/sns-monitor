"""
Vuddy.io 크리에이터 종합 크롤러
vuddy.io 크리에이터 이름을 기준으로 YouTube, 블로그, 구글 검색을 통합하여 댓글 및 좋아요 분석
"""

import json
import os
import sys
import boto3
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# KST 타임존 (UTC+9)
KST = timezone(timedelta(hours=9))

def get_kst_now():
    """현재 KST 시간 반환"""
    return datetime.now(KST)

import re
from urllib.parse import urljoin, urlparse, quote_plus
import time

# 로컬 모드 확인
LOCAL_MODE = os.environ.get('LOCAL_MODE', 'false').lower() == 'true'
LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', './local-data')

# 로컬 모드가 아닐 때만 AWS 클라이언트 초기화
if not LOCAL_MODE:
    # AWS 클라이언트 (LocalStack 지원)
    s3_endpoint = os.environ.get('S3_ENDPOINT')
    dynamodb_endpoint = os.environ.get('DYNAMODB_ENDPOINT')
    s3_client = boto3.client('s3', endpoint_url=s3_endpoint) if s3_endpoint else boto3.client('s3')
    dynamodb = boto3.resource('dynamodb', endpoint_url=dynamodb_endpoint) if dynamodb_endpoint else boto3.resource('dynamodb')
    lambda_client = boto3.client('lambda')
else:
    # 로컬 모드: 공통 유틸리티 임포트
    # 컨테이너에서는 /app/lambda/common/, 로컬에서는 ../common
    common_path = os.path.join(os.path.dirname(__file__), 'lambda', 'common')
    if not os.path.exists(common_path):
        common_path = os.path.join(os.path.dirname(__file__), '..', 'common')
    sys.path.insert(0, common_path)
    from local_storage import (
        save_to_local_file, 
        save_metadata_to_local, 
        is_local_mode
    )
    s3_client = None
    dynamodb = None
    lambda_client = None

# 환경 변수
S3_BUCKET = os.environ.get('S3_BUCKET', 'sns-monitor-data')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'sns-monitor-results')
LLM_ANALYZER_ENDPOINT = os.environ.get('LLM_ANALYZER_ENDPOINT', 'http://llm-analyzer:5000')
VUDDY_URL = os.environ.get('VUDDY_URL', 'https://vuddy.io')
YOUTUBE_CRAWLER_ENDPOINT = os.environ.get('YOUTUBE_CRAWLER_ENDPOINT', 'http://youtube-crawler:5000')
RSS_CRAWLER_ENDPOINT = os.environ.get('RSS_CRAWLER_ENDPOINT', 'http://rss-crawler:5000')
GOOGLE_SEARCH_API_KEY = os.environ.get('GOOGLE_SEARCH_API_KEY', '')
GOOGLE_SEARCH_ENGINE_ID = os.environ.get('GOOGLE_SEARCH_ENGINE_ID', '')

def get_creators_from_vuddy():
    """vuddy.io에서 크리에이터 목록 가져오기"""
    creators = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # vuddy.io 메인 페이지 또는 크리에이터 목록 페이지 크롤링
        response = requests.get(VUDDY_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 크리에이터 카드/링크 찾기
        creator_links = soup.find_all('a', href=re.compile(r'/creator|/channel|/artist'))
        
        for link in creator_links:
            creator_url = urljoin(VUDDY_URL, link.get('href', ''))
            creator_name = link.get_text(strip=True) or link.get('title', '')
            
            if creator_url and creator_name:
                creators.append({
                    'name': creator_name,
                    'vuddy_url': creator_url,
                    'youtube_channel': None
                })
        
        # 크리에이터 상세 페이지에서 YouTube 채널 추출
        for creator in creators[:50]:  # 최대 50개로 제한
            try:
                creator_page = requests.get(creator['vuddy_url'], headers=headers, timeout=30)
                creator_soup = BeautifulSoup(creator_page.content, 'html.parser')
                
                # YouTube 채널 링크 찾기
                youtube_links = creator_soup.find_all('a', href=re.compile(r'youtube\.com|youtu\.be'))
                
                for yt_link in youtube_links:
                    yt_url = yt_link.get('href', '')
                    if 'youtube.com' in yt_url or 'youtu.be' in yt_url:
                        if '/channel/' in yt_url:
                            channel_id = yt_url.split('/channel/')[-1].split('?')[0]
                            creator['youtube_channel'] = channel_id
                        elif '/@' in yt_url:
                            channel_handle = yt_url.split('/@')[-1].split('/')[0].split('?')[0]
                            creator['youtube_channel'] = f"@{channel_handle}"
                        elif '/c/' in yt_url:
                            channel_custom = yt_url.split('/c/')[-1].split('/')[0].split('?')[0]
                            creator['youtube_channel'] = f"@{channel_custom}"
                        break
            except Exception as e:
                print(f"Error fetching creator page {creator['vuddy_url']}: {e}")
                continue
        
        print(f"Found {len(creators)} creators from vuddy.io")
        return creators
        
    except Exception as e:
        print(f"Error crawling vuddy.io: {e}")
        # API 엔드포인트 시도
        try:
            api_url = f"{VUDDY_URL}/api/creators"
            api_response = requests.get(api_url, headers=headers, timeout=30)
            if api_response.status_code == 200:
                api_data = api_response.json()
                return api_data.get('creators', [])
        except:
            pass
        
        return []

def get_acquired_companies_channels():
    """인수한 회사들의 YouTube 채널 목록"""
    return [
        {
            'name': 'BARABARA',
            'youtube_channel': '@BARABARA_KR',
            'company': '바라바라',
            'acquired': True
        },
        {
            'name': 'IVNIT',
            'youtube_channel': '@IVNITOFFICIAL',
            'company': '이브닛',
            'acquired': True
        },
        {
            'name': 'AkaiV Studio',
            'youtube_channel': '@AkaivStudioOfficial',
            'company': 'AkaiV Studio',
            'acquired': True
        },
        {
            'name': 'u32',
            'youtube_channel': '@u32S2',
            'company': 'AkaiV Studio',
            'acquired': True
        },
        {
            'name': '여르미',
            'youtube_channel': '@Yeorumi',
            'company': 'AkaiV Studio',
            'acquired': True
        },
        {
            'name': '한결',
            'youtube_channel': '@hangyeol8008',
            'company': 'AkaiV Studio',
            'acquired': True
        },
        {
            'name': '비몽',
            'youtube_channel': '@beemong_',
            'company': 'AkaiV Studio',
            'acquired': True
        },
        {
            'name': '샤르망',
            'youtube_channel': '@owo_zzzz',
            'company': 'AkaiV Studio',
            'acquired': True
        }
    ]

def clean_creator_name_for_search(creator_name):
    """AkaiV Studio 멤버의 경우 "AkaiV" 제거하고 순수한 이름만 반환"""
    if not creator_name:
        return creator_name
    
    # 먼저 AkaiV 관련 키워드 모두 제거
    cleaned_name = creator_name.replace('AkaiV', '').replace('akaiv', '').replace('AKAIV', '')
    cleaned_name = cleaned_name.replace('Studio', '').replace('studio', '').replace('STUDIO', '')
    cleaned_name = cleaned_name.replace('  ', ' ').strip()
    
    # 멤버 이름 매핑 (모든 가능한 변형 포함)
    member_mapping = {
        '여르미': ['여르미', 'Yeorumi', 'yeorumi', 'Yeorumi030'],
        '한결': ['한결', 'Hangyeol', 'hangyeol', 'hangyeol8008'],
        '비몽': ['비몽', 'Beemong', 'beemong', 'beemong_'],
        '샤르망': ['샤르망', 'Charmant', 'charmant', 'owo_zzzz'],
        'u32': ['u32', '우사미', 'U32', 'u32S2', 'u32 (우사미)', '우사미 (u32)']
    }
    
    # 멤버 이름 찾기 (더 강력한 매칭)
    creator_name_lower = creator_name.lower()
    cleaned_name_lower = cleaned_name.lower()
    
    for member_name, variants in member_mapping.items():
        for variant in variants:
            variant_lower = variant.lower()
            # 원본 이름이나 정제된 이름에 멤버 이름이 포함되어 있는지 확인
            if (variant_lower in creator_name_lower or 
                variant_lower in cleaned_name_lower or
                creator_name_lower in variant_lower or
                cleaned_name_lower in variant_lower):
                print(f"Cleaned creator name: '{creator_name}' -> '{member_name}'")
                return member_name
    
    # 멤버 이름을 찾지 못한 경우, 정제된 이름 반환
    if cleaned_name:
        print(f"Cleaned creator name: '{creator_name}' -> '{cleaned_name}'")
        return cleaned_name
    
    # 모두 실패하면 원본 반환
    print(f"Using original creator name: '{creator_name}'")
    return creator_name

def search_youtube_by_creator_name(creator_name):
    """크리에이터 이름으로 YouTube 검색"""
    try:
        # AkaiV Studio 멤버의 경우 "AkaiV" 제거하고 순수한 이름만 사용
        search_keyword = clean_creator_name_for_search(creator_name)
        
        payload = {
            'type': 'keyword',
            'keywords': [search_keyword],
            'max_videos': 10,
            'max_comments_per_video': 100
        }
        
        response = requests.post(
            f"{YOUTUBE_CRAWLER_ENDPOINT}/invoke",
            json=payload,
            timeout=300
        )
        
        if response.status_code == 200:
            result = response.json()
            body = json.loads(result.get('body', '{}'))
            return {
                'status': 'success',
                'data': body.get('results', [])
            }
        else:
            return {
                'status': 'error',
                'error': f"HTTP {response.status_code}"
            }
    except Exception as e:
        print(f"Error searching YouTube for {creator_name}: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

def search_blogs_by_creator_name(creator_name):
    """크리에이터 이름으로 블로그 검색 (RSS 크롤러 활용)"""
    try:
        # AkaiV Studio 멤버의 경우 "AkaiV" 제거하고 순수한 이름만 사용
        search_keyword = clean_creator_name_for_search(creator_name)
        
        payload = {
            'keywords': [search_keyword],
            'max_results': 20
        }
        
        response = requests.post(
            f"{RSS_CRAWLER_ENDPOINT}/invoke",
            json=payload,
            timeout=180
        )
        
        if response.status_code == 200:
            result = response.json()
            body = json.loads(result.get('body', '{}'))
            return {
                'status': 'success',
                'data': body.get('results', [])
            }
        else:
            return {
                'status': 'error',
                'error': f"HTTP {response.status_code}"
            }
    except Exception as e:
        print(f"Error searching blogs for {creator_name}: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

def search_google_by_creator_name(creator_name):
    """크리에이터 이름으로 구글 검색"""
    results = {
        'status': 'success',
        'data': [],
        'total_results': 0
    }

    # AkaiV Studio 멤버의 경우 "AkaiV" 제거하고 순수한 이름만 사용
    search_query = clean_creator_name_for_search(creator_name)
    
    # AkaiV Studio / 아카이브 스튜디오 검색어 변환 (메인 채널인 경우만)
    if creator_name in ['AkaiV Studio', 'Archive Studio']:
        search_query = 'AkaiV Studio OR 아카이브스튜디오 OR 아카이브 스튜디오'

    # Google Custom Search API 사용 (API 키가 있는 경우)
    if GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
        try:
            search_url = 'https://www.googleapis.com/customsearch/v1'

            # 국가별 우선 검색: 한국, 미국, 일본
            all_results = []
            priority_countries = [
                {'gl': 'kr', 'hl': 'ko', 'name': '한국'},
                {'gl': 'us', 'hl': 'en', 'name': '미국'},
                {'gl': 'jp', 'hl': 'ja', 'name': '일본'}
            ]

            for country in priority_countries:
                try:
                    params = {
                        'key': GOOGLE_SEARCH_API_KEY,
                        'cx': GOOGLE_SEARCH_ENGINE_ID,
                        'q': search_query if ' OR ' in search_query else f'"{search_query}"',
                        'num': 10,
                        'gl': country['gl'],  # 국가 코드
                        'hl': country['hl']   # 언어 코드
                    }
                    
                    response = requests.get(search_url, params=params, timeout=30, verify=True)
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get('items', [])
                        
                        for item in items:
                            # 중복 제거를 위해 URL 체크
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
                        
                        print(f"Found {len(items)} Google results from {country['name']} ({country['gl']})")
                except Exception as e:
                    print(f"Error searching Google for {country['name']}: {e}")
                    continue
            
            # 결과 정리 (우선 국가 결과를 먼저 포함)
            results['data'] = all_results[:10]  # 최대 10개
            results['total_results'] = len(all_results)
            print(f"Found {len(all_results)} total Google results for {creator_name} (prioritized by country)")
        except Exception as e:
            print(f"Error using Google Custom Search API: {e}")
            # 웹 크롤링으로 대체
            results = search_google_web_scraping(creator_name)
    else:
        # Google Custom Search API가 없으면 웹 크롤링 사용
        print("Google Custom Search API not configured, using web scraping")
        results = search_google_web_scraping(creator_name)
    
    return results

def search_google_web_scraping(creator_name):
    """웹 크롤링으로 구글 검색 (API 없이)"""
    results = {
        'status': 'success',
        'data': [],
        'total_results': 0
    }

    try:
        # AkaiV Studio 멤버의 경우 "AkaiV" 제거하고 순수한 이름만 사용
        search_term = clean_creator_name_for_search(creator_name)
        
        # AkaiV Studio / 아카이브 스튜디오 검색어 변환 (메인 채널인 경우만)
        if creator_name in ['AkaiV Studio', 'Archive Studio']:
            search_term = 'AkaiV Studio OR 아카이브스튜디오 OR 아카이브 스튜디오'

        # DuckDuckGo HTML 검색 사용 (더 많은 결과 제공)
        search_query = quote_plus(search_term if ' OR ' in search_term else f'"{search_term}"')
        
        # DuckDuckGo HTML 검색
        ddg_html_url = f"https://html.duckduckgo.com/html/?q={search_query}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(ddg_html_url, headers=headers, timeout=30, verify=True)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 검색 결과 추출
            result_links = soup.find_all('a', class_='result__a')
            result_snippets = soup.find_all('a', class_='result__snippet')
            
            for idx, link in enumerate(result_links[:10]):
                title = link.get_text(strip=True)
                url = link.get('href', '')
                
                # URL이 상대 경로인 경우 절대 경로로 변환
                if url.startswith('/'):
                    url = f"https://duckduckgo.com{url}"
                
                snippet = ''
                if idx < len(result_snippets):
                    snippet = result_snippets[idx].get_text(strip=True)
                
                if title and url:
                    results['data'].append({
                        'title': title[:200],
                        'link': url,
                        'snippet': snippet[:300] if snippet else '',
                        'source': 'duckduckgo',
                        'display_link': urlparse(url).netloc if url else ''
                    })
        
        # DuckDuckGo Instant Answer API도 시도 (추가 정보)
        try:
            ddg_api_url = f"https://api.duckduckgo.com/?q={search_query}&format=json&no_html=1&skip_disambig=1"
            api_response = requests.get(ddg_api_url, timeout=30, verify=True)
            if api_response.status_code == 200:
                data = api_response.json()
                
                # Abstract 추가 (중복 체크)
                if data.get('Abstract') and data.get('AbstractURL'):
                    abstract_url = data.get('AbstractURL', '')
                    if not any(r['link'] == abstract_url for r in results['data']):
                        results['data'].insert(0, {
                            'title': data.get('Heading', creator_name),
                            'link': abstract_url,
                            'snippet': data.get('Abstract', ''),
                            'source': 'duckduckgo',
                            'display_link': urlparse(abstract_url).netloc if abstract_url else ''
                        })
                
                # 관련 주제 추가
                if data.get('RelatedTopics'):
                    for topic in data.get('RelatedTopics', [])[:5]:
                        if isinstance(topic, dict) and topic.get('Text') and topic.get('FirstURL'):
                            topic_url = topic.get('FirstURL', '')
                            if not any(r['link'] == topic_url for r in results['data']):
                                results['data'].append({
                                    'title': topic.get('Text', '')[:200],
                                    'link': topic_url,
                                    'snippet': topic.get('Text', '')[:300],
                                    'source': 'duckduckgo',
                                    'display_link': urlparse(topic_url).netloc if topic_url else ''
                                })
        except Exception as e:
            print(f"Error fetching DuckDuckGo API: {e}")
        
        results['total_results'] = len(results['data'])
        print(f"Found {len(results['data'])} Google/DuckDuckGo results for {creator_name}")
        
    except Exception as e:
        print(f"Error in web scraping Google search: {e}")
        import traceback
        traceback.print_exc()
        results['status'] = 'error'
        results['error'] = str(e)
    
    return results

def analyze_channel_by_name(creator_name, youtube_channel):
    """크리에이터 이름과 YouTube 채널로 종합 분석"""
    analysis = {
        'creator_name': creator_name,
        'youtube_channel': youtube_channel,
        'youtube_search': None,
        'youtube_channel_analysis': None,
        'blog_search': None,
        'google_search': None,
        'total_comments': 0,
        'total_likes': 0,
        'total_blog_posts': 0,
        'total_google_results': 0
    }
    
    # 1. YouTube 키워드 검색 (크리에이터 이름으로)
    print(f"Searching YouTube for creator: {creator_name}")
    youtube_search = search_youtube_by_creator_name(creator_name)
    analysis['youtube_search'] = youtube_search
    
    if youtube_search.get('status') == 'success':
        for result in youtube_search.get('data', []):
            analysis['total_comments'] += result.get('comments_collected', 0)
    
    # 2. YouTube 채널 분석 (채널이 있는 경우)
    if youtube_channel:
        print(f"Analyzing YouTube channel: {youtube_channel}")
        try:
            payload = {
                'type': 'channel',
                'channels': [youtube_channel],
                'max_videos': 10,
                'max_comments_per_video': 100
            }
            
            response = requests.post(
                f"{YOUTUBE_CRAWLER_ENDPOINT}/invoke",
                json=payload,
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                body = json.loads(result.get('body', '{}'))
                analysis['youtube_channel_analysis'] = {
                    'status': 'success',
                    'data': body.get('results', [])
                }
                
                for channel_result in body.get('results', []):
                    analysis['total_comments'] += channel_result.get('total_comments', 0)
                    # 버튜버 좋아요도 포함
                    analysis['total_likes'] += channel_result.get('vtuber_likes', 0)
        except Exception as e:
            print(f"Error analyzing YouTube channel: {e}")
            analysis['youtube_channel_analysis'] = {
                'status': 'error',
                'error': str(e)
            }
    
    # 3. 블로그 검색
    print(f"Searching blogs for creator: {creator_name}")
    blog_search = search_blogs_by_creator_name(creator_name)
    analysis['blog_search'] = blog_search
    
    if blog_search.get('status') == 'success':
        blog_data = blog_search.get('data', [])
        if isinstance(blog_data, list):
            for result in blog_data:
                if isinstance(result, dict):
                    analysis['total_blog_posts'] += result.get('entries_found', 0)
                elif isinstance(result, list):
                    # 결과가 리스트인 경우 (직접 엔트리 리스트)
                    analysis['total_blog_posts'] += len(result)
        elif isinstance(blog_data, dict):
            # 결과가 딕셔너리인 경우
            analysis['total_blog_posts'] += blog_data.get('entries_found', 0)
    
    # 4. 구글 검색
    print(f"Searching Google for creator: {creator_name}")
    google_search = search_google_by_creator_name(creator_name)
    analysis['google_search'] = google_search
    
    if google_search.get('status') == 'success':
        analysis['total_google_results'] = len(google_search.get('data', []))
    
    return analysis

def save_to_s3(data, source):
    """수집된 데이터를 S3 또는 로컬 파일 시스템에 저장"""
    if LOCAL_MODE:
        # 로컬 모드: 파일 시스템에 저장
        timestamp = get_kst_now().strftime('%Y-%m-%d-%H-%M-%S')
        file_dir = os.path.join(LOCAL_DATA_DIR, 'vuddy', source)
        ensure_local_dir(file_dir)
        filename = f"{timestamp}.json"
        filepath = os.path.join(file_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"Data saved to local file: {filepath}")
        # S3 키 형식으로 반환 (호환성 유지)
        return filepath.replace(os.path.sep, '/').replace(LOCAL_DATA_DIR.replace(os.path.sep, '/'), 'local-data')
    else:
        # 프로덕션 모드: S3에 저장
        timestamp = get_kst_now().strftime('%Y-%m-%d-%H-%M-%S')
        key = f"raw-data/vuddy/{source}/{timestamp}.json"
        
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=json.dumps(data, ensure_ascii=False, indent=2),
                ContentType='application/json'
            )
            print(f"Data saved to s3://{S3_BUCKET}/{key}")
            return key
        except Exception as e:
            print(f"Error saving to S3: {e}")
            raise

def save_to_dynamodb(analysis_data, s3_key):
    """DynamoDB 또는 로컬 파일에 분석 결과 저장"""
    try:
        # 각 크리에이터별로 저장
        for analysis in analysis_data.get('comprehensive_analysis', []):
            creator_name = analysis.get('creator_name', '')
            if not creator_name:
                continue
            
            item = {
                'id': f"vuddy-{creator_name}-{get_kst_now().strftime('%Y%m%d%H%M%S')}",
                'platform': 'vuddy',
                'keyword': creator_name,
                'channel': analysis.get('youtube_channel', ''),
                'channel_title': creator_name,
                'timestamp': get_kst_now().isoformat(),
                's3_key': s3_key,
                'total_comments': analysis.get('total_comments', 0),
                'total_likes': analysis.get('total_likes', 0),
                'videos_analyzed': 0,  # YouTube 검색 결과에서 계산
                'vtuber_comments': 0,
                'vtuber_likes': analysis.get('total_likes', 0),
                'blog_posts': analysis.get('total_blog_posts', 0),
                'google_results': analysis.get('total_google_results', 0),
                'youtube_search_status': analysis.get('youtube_search', {}).get('status', ''),
                'blog_search_status': analysis.get('blog_search', {}).get('status', ''),
                'google_search_status': analysis.get('google_search', {}).get('status', '')
            }
            
            # YouTube 검색 결과에서 영상 수 계산
            youtube_search = analysis.get('youtube_search', {})
            if youtube_search.get('status') == 'success':
                for result in youtube_search.get('data', []):
                    item['videos_analyzed'] += result.get('videos_found', 0)
                    item['total_comments'] += result.get('comments_collected', 0)
            
            # YouTube 채널 분석 결과 추가
            youtube_channel = analysis.get('youtube_channel_analysis', {})
            if youtube_channel.get('status') == 'success':
                for channel_result in youtube_channel.get('data', []):
                    item['videos_analyzed'] += channel_result.get('videos_analyzed', 0)
                    item['total_comments'] += channel_result.get('total_comments', 0)
                    item['vtuber_comments'] += channel_result.get('vtuber_comments', 0)
                    item['vtuber_likes'] += channel_result.get('vtuber_likes', 0)
            
            if LOCAL_MODE:
                save_metadata_to_local(item, 'vuddy')
                print(f"Saved metadata to local file: {creator_name}")
            else:
                table = dynamodb.Table(DYNAMODB_TABLE)
            table.put_item(Item=item)
            print(f"Saved to DynamoDB: {creator_name}")
        
    except Exception as e:
        print(f"Error saving metadata: {e}")
        import traceback
        traceback.print_exc()

def trigger_llm_analysis(s3_key, source, total_items):
    """LLM 분석기 호출"""
    if LOCAL_MODE:
        print(f"⚠️  로컬 모드: LLM 분석은 건너뜁니다. (s3_key: {s3_key})")
        return
    
    try:
        payload = {
            'source': 'vuddy',
            's3_key': s3_key,
            'keyword': source,
            'total_items': total_items,
            'timestamp': get_kst_now().isoformat()
        }
        
        requests.post(
            f"{LLM_ANALYZER_ENDPOINT}/invoke",
            json=payload,
            timeout=60
        )
        print(f"LLM analysis triggered for {s3_key}")
    except Exception as e:
        print(f"Error triggering LLM analysis: {e}")

def lambda_handler(event, context):
    """
    Lambda 핸들러
    
    vuddy.io 크리에이터 이름을 기준으로 YouTube, 블로그, 구글 검색 통합 분석
    """
    
    print(f"Event: {json.dumps(event)}")
    
    results = {
        'vuddy_creators': [],
        'acquired_companies': [],
        'comprehensive_analysis': []
    }
    
    try:
        # 1. vuddy.io에서 크리에이터 목록 가져오기
        print("Fetching creators from vuddy.io...")
        vuddy_creators = get_creators_from_vuddy()
        results['vuddy_creators'] = vuddy_creators
        
        # 2. 인수한 회사 채널 목록 가져오기
        print("Getting acquired companies channels...")
        acquired_channels = get_acquired_companies_channels()
        results['acquired_companies'] = acquired_channels
        
        # 3. 모든 크리에이터에 대해 종합 분석 수행
        all_creators = []
        
        # 인수한 회사 먼저 추가 (우선순위)
        for company in acquired_channels:
            all_creators.append({
                'name': company.get('name'),
                'youtube_channel': company.get('youtube_channel'),
                'source': 'acquired_company',
                'company': company.get('company'),
                'priority': True  # 우선순위 표시
            })
        
        # vuddy 크리에이터 추가
        for creator in vuddy_creators:
            all_creators.append({
                'name': creator.get('name'),
                'youtube_channel': creator.get('youtube_channel'),
                'source': 'vuddy',
                'priority': False
            })
        
        # 우선순위가 있는 크리에이터를 먼저 정렬
        all_creators.sort(key=lambda x: (not x.get('priority', False), x.get('name', '')))
        
        # 각 크리에이터에 대해 종합 분석
        # 우선순위 크리에이터는 항상 포함, 나머지는 최대 20개로 제한
        priority_creators = [c for c in all_creators if c.get('priority', False)]
        other_creators = [c for c in all_creators if not c.get('priority', False)]
        
        creators_to_analyze = priority_creators + other_creators[:max(0, 20 - len(priority_creators))]
        
        print(f"Starting comprehensive analysis for {len(creators_to_analyze)} creators...")
        print(f"Priority creators (always included): {[c['name'] for c in priority_creators]}")
        
        for creator_info in creators_to_analyze:
            creator_name = creator_info.get('name')
            if not creator_name:
                continue
            
            print(f"\n{'='*60}")
            print(f"Analyzing creator: {creator_name}")
            print(f"{'='*60}")
            
            try:
                analysis = analyze_channel_by_name(
                    creator_name,
                    creator_info.get('youtube_channel')
                )
                
                results['comprehensive_analysis'].append(analysis)
                
                # API 할당량 고려하여 딜레이
                time.sleep(2)
                
            except Exception as e:
                print(f"Error analyzing creator {creator_name}: {e}")
                results['comprehensive_analysis'].append({
                    'creator_name': creator_name,
                    'status': 'error',
                    'error': str(e)
                })
        
        # 4. 종합 통계 계산
        total_stats = {
            'total_creators_analyzed': len(results['comprehensive_analysis']),
            'total_comments': sum(a.get('total_comments', 0) for a in results['comprehensive_analysis']),
            'total_likes': sum(a.get('total_likes', 0) for a in results['comprehensive_analysis']),
            'total_blog_posts': sum(a.get('total_blog_posts', 0) for a in results['comprehensive_analysis']),
            'total_google_results': sum(a.get('total_google_results', 0) for a in results['comprehensive_analysis'])
        }
        
        # 5. S3에 저장
        crawl_data = {
            'platform': 'vuddy',
            'crawled_at': get_kst_now().isoformat(),
            'total_creators': len(vuddy_creators),
            'total_acquired_companies': len(acquired_channels),
            'comprehensive_analysis': results['comprehensive_analysis'],
            'statistics': total_stats,
            'creators': vuddy_creators,
            'acquired_companies': acquired_channels
        }
        
        s3_key = save_to_s3(crawl_data, 'comprehensive_analysis')
        
        # 6. DynamoDB에 저장
        save_to_dynamodb(crawl_data, s3_key)
        
        # 7. LLM 분석 트리거
        trigger_llm_analysis(s3_key, 'vuddy_comprehensive', total_stats['total_creators_analyzed'])
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Vuddy comprehensive analysis completed',
                'results': results,
                'statistics': total_stats,
                's3_key': s3_key
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        print(f"Error in Vuddy comprehensive analysis: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
