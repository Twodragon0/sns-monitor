"""
Twitter/X 크롤러
트위터/X 데이터 수집 (Twitter API v2 + 로컬 데이터)
"""

import json
import os
import sys
import boto3
from datetime import datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup
import time
import re
import random
import urllib3

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# KST 시간대 설정
KST = timezone(timedelta(hours=9))

def now_kst():
    """현재 KST 시간 반환"""
    return datetime.now(KST)

def isoformat_kst():
    """KST ISO 8601 형식"""
    return now_kst().isoformat()

# AWS 클라이언트 (LocalStack 지원)
s3_endpoint = os.environ.get('S3_ENDPOINT')
s3_client = boto3.client('s3', endpoint_url=s3_endpoint) if s3_endpoint else boto3.client('s3')

# 환경 변수
S3_BUCKET = os.environ.get('S3_BUCKET')
LLM_ANALYZER_ENDPOINT = os.environ.get('LLM_ANALYZER_ENDPOINT', 'http://llm-analyzer:5000')
TWITTER_BEARER_TOKEN = os.environ.get('TWITTER_BEARER_TOKEN', '')

# 로컬 모드 설정
LOCAL_MODE = os.environ.get('LOCAL_MODE', '').lower() == 'true'
LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', './local-data')

# Twitter Syndication/Embed API
TWITTER_EMBED_URL = 'https://publish.twitter.com/oembed'

# 모니터링 키워드 매핑
CREATOR_KEYWORDS = {
    '버디': ['버디', 'vuddy', 'VUDDY', 'Vuddy'],
    '레벨스': ['레벨스', 'levvels', 'LEVVELS', 'Levvels'],
    '스코시즘': ['스코시즘', 'skoshism', 'SKOSHISM', '스코'],
    '아카이브': ['아카이브', 'archive', 'AkaiV', 'akaiv', '아카이브스튜디오'],
    '바라바라': ['바라바라', 'barabara', 'BARABARA', '바라'],
    '이브닛': ['이브닛', 'ivnit', 'IVNIT', '이브'],
    'u32': ['u32', 'U32', '사미', '우사미'],
    '여르미': ['여르미', '엶', 'yeorumi'],
    '한결': ['한결', '결', 'hangyeol'],
    '비몽': ['비몽', '몽', 'beemong'],
    '샤르망': ['샤르망', '쭈쭈', 'charmant'],
    '나나문': ['나나문', '쿠우', 'nanamun'],
}

# 모니터링 키워드 (전체)
MONITORING_KEYWORDS = [
    '아카이브', 'archive', '바라바라', 'barabara', '이브닛', 'ivnit', '스코시즘', 'skoshism',
    'u32', '사미', '우사미', '여르미', '엶', '한결', '결', '비몽', '몽', '샤르망', '쭈쭈', '나나문', '쿠우',
    '버디', 'vuddy', '레벨스', 'levvels',
    '굿즈', '포토카드', '포카', '아크릴', '키링', '스티커',
    '팬싸', '영통팬싸', '응모', '당첨',
    '커버곡', '오리지널곡', '라이브', '방송',
]

# 감정 분석 함수
def analyze_sentiment(text):
    """텍스트의 감정 분석"""
    if not text:
        return 'neutral'

    lower_text = text.lower()

    positive_keywords = ['좋아', '굿', '최고', '감사', '사랑', '축하', '대박', '멋지', '예쁘', '귀엽',
                         '화이팅', '응원', '존경', '멋있', '훌륭', '완벽', 'ㄱㅇㄷ', 'ㅊㅊ',
                         '개좋', '레전드', '갓', '천재', '미쳤', '개꿀', '힐링', '감동']
    negative_keywords = ['싫어', '나쁘', '최악', '욕', '비난', '혐오', '짜증', '실망', '별로',
                         '쓰레기', '망했', '노잼', '재미없', '허접', '구리', '답없', '노답']

    has_positive = any(keyword in lower_text for keyword in positive_keywords)
    has_negative = any(keyword in lower_text for keyword in negative_keywords)

    if has_positive and not has_negative:
        return 'positive'
    if has_negative and not has_positive:
        return 'negative'
    return 'neutral'

def find_matching_keywords(text):
    """텍스트에서 모니터링 키워드 매칭"""
    if not text:
        return []
    lower_text = text.lower()
    return [keyword for keyword in MONITORING_KEYWORDS if keyword.lower() in lower_text]

def get_headers():
    """HTTP 요청 헤더"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    ]
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
    }

def search_twitter_api_v2(keyword, max_results=10):
    """Twitter API v2로 검색 (Bearer Token 필요)"""
    if not TWITTER_BEARER_TOKEN:
        print("Twitter Bearer Token not configured")
        return []

    try:
        url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {
            'Authorization': f'Bearer {TWITTER_BEARER_TOKEN}',
            'Content-Type': 'application/json',
        }
        params = {
            'query': keyword,
            'max_results': min(max_results, 100),
            'tweet.fields': 'created_at,public_metrics,author_id',
            'user.fields': 'username,name',
            'expansions': 'author_id',
        }

        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            tweets = []

            # 유저 정보 매핑
            users = {}
            if 'includes' in data and 'users' in data['includes']:
                for user in data['includes']['users']:
                    users[user['id']] = {
                        'username': user['username'],
                        'name': user['name']
                    }

            if 'data' in data:
                for tweet in data['data']:
                    author_info = users.get(tweet.get('author_id'), {})
                    metrics = tweet.get('public_metrics', {})

                    tweets.append({
                        'tweet_id': tweet['id'],
                        'text': tweet['text'],
                        'author': author_info.get('username', 'unknown'),
                        'author_name': author_info.get('name', 'Unknown'),
                        'created_at': tweet.get('created_at', isoformat_kst()),
                        'like_count': metrics.get('like_count', 0),
                        'retweet_count': metrics.get('retweet_count', 0),
                        'reply_count': metrics.get('reply_count', 0),
                        'sentiment': analyze_sentiment(tweet['text']),
                        'matched_keywords': find_matching_keywords(tweet['text']),
                        'source': 'twitter_api_v2'
                    })

            print(f"Twitter API v2: Found {len(tweets)} tweets for '{keyword}'")
            return tweets

        elif response.status_code == 401:
            print("Twitter API: Invalid Bearer Token")
        elif response.status_code == 403:
            print("Twitter API: Access forbidden (may need paid plan)")
        elif response.status_code == 429:
            print("Twitter API: Rate limit exceeded")
        else:
            print(f"Twitter API error: {response.status_code} - {response.text[:200]}")

    except Exception as e:
        print(f"Twitter API v2 error: {e}")

    return []

def load_local_twitter_data(keyword):
    """로컬 저장된 트위터 데이터 로드"""
    tweets = []
    replies = []

    twitter_dir = os.path.join(LOCAL_DATA_DIR, 'twitter')
    if not os.path.exists(twitter_dir):
        return tweets, replies

    try:
        import glob
        for file_path in glob.glob(os.path.join(twitter_dir, '**/*.json'), recursive=True):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    # 키워드가 데이터에 포함되어 있는지 확인
                    data_str = json.dumps(data, ensure_ascii=False).lower()
                    if keyword.lower() in data_str:
                        if 'tweets' in data:
                            # 샘플 데이터 제외
                            for t in data['tweets']:
                                if t.get('source') != 'sample_data' and not str(t.get('tweet_id', '')).startswith('sample_'):
                                    tweets.append(t)
                        if 'data' in data:
                            for item in data['data']:
                                if 'tweet' in item:
                                    t = item['tweet']
                                    if t.get('source') != 'sample_data' and not str(t.get('tweet_id', '')).startswith('sample_'):
                                        tweets.append(t)
                                if 'replies' in item:
                                    replies.extend(item['replies'])
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    except Exception as e:
        print(f"Error loading local data: {e}")

    return tweets, replies

def save_to_local(data, keyword):
    """로컬 파일 시스템에 저장"""
    try:
        twitter_dir = os.path.join(LOCAL_DATA_DIR, 'twitter')
        os.makedirs(twitter_dir, exist_ok=True)

        filename = f"{keyword}_{now_kst().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(twitter_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Saved to local: {filepath}")
        return filepath
    except Exception as e:
        print(f"Error saving to local: {e}")
        return None

def save_to_s3(data, keyword):
    """S3에 데이터 저장"""
    if LOCAL_MODE or not S3_BUCKET:
        return save_to_local(data, keyword)

    try:
        timestamp = now_kst().strftime('%Y%m%d_%H%M%S')
        s3_key = f"raw-data/twitter/{keyword}/{timestamp}.json"

        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(data, ensure_ascii=False),
            ContentType='application/json'
        )

        print(f"Saved to S3: s3://{S3_BUCKET}/{s3_key}")
        return s3_key
    except Exception as e:
        print(f"Error saving to S3: {e}")
        return save_to_local(data, keyword)

def trigger_llm_analysis(s3_key, keyword, comment_count):
    """LLM 분석 트리거"""
    if not s3_key or comment_count < 3:
        return

    try:
        response = requests.post(
            f"{LLM_ANALYZER_ENDPOINT}/analyze",
            json={
                's3_key': s3_key,
                'keyword': keyword,
                'platform': 'twitter'
            },
            timeout=5
        )
        print(f"LLM analysis triggered: {response.status_code}")
    except Exception as e:
        print(f"Failed to trigger LLM analysis: {e}")

def search_twitter(keyword, max_results=10):
    """트위터 검색 (API v2 -> 로컬 데이터)"""
    all_tweets = []
    all_replies = []
    data_source = None

    print(f"\n=== Searching Twitter for: {keyword} ===")

    # 1. Twitter API v2 시도 (Bearer Token이 있는 경우)
    if TWITTER_BEARER_TOKEN:
        print("Trying Twitter API v2...")
        api_tweets = search_twitter_api_v2(keyword, max_results)
        if api_tweets:
            all_tweets.extend(api_tweets)
            data_source = 'twitter_api_v2'
            print(f"Found {len(api_tweets)} tweets from Twitter API v2")

    # 2. 로컬 저장 데이터 로드 (실제 데이터만)
    local_tweets, local_replies = load_local_twitter_data(keyword)

    if local_tweets:
        # 중복 제거
        existing_ids = {t.get('tweet_id') for t in all_tweets}
        added_count = 0
        for tweet in local_tweets:
            tweet_id = tweet.get('tweet_id')
            if tweet_id and tweet_id not in existing_ids:
                all_tweets.append(tweet)
                existing_ids.add(tweet_id)
                added_count += 1

        if added_count > 0:
            print(f"Added {added_count} tweets from local data")
            if not data_source:
                data_source = 'local_data'

    all_replies.extend(local_replies)

    # 결과 상태 로그
    if not all_tweets:
        print(f"No tweets found for '{keyword}'")
        print("Note: Twitter/X requires API access. For reliable data:")
        print("  - Set TWITTER_BEARER_TOKEN env var (requires Twitter API subscription)")

    return all_tweets, all_replies, data_source

def lambda_handler(event, context):
    """
    Lambda 핸들러
    실제 트위터/X 데이터만 수집 (샘플 데이터 없음)
    """
    print(f"Event: {json.dumps(event)}")
    print(f"Twitter Bearer Token configured: {bool(TWITTER_BEARER_TOKEN)}")
    print(f"Local mode: {LOCAL_MODE}")

    keywords_to_search = event.get('keywords', [])

    # 기본 키워드 설정
    if not keywords_to_search:
        keywords_to_search = list(CREATOR_KEYWORDS.keys())

    results = []
    total_tweets_found = 0

    for keyword in keywords_to_search:
        keyword = keyword.strip()
        if not keyword:
            continue

        print(f"\n{'='*50}")
        print(f"Processing keyword: {keyword}")
        print(f"{'='*50}")

        try:
            # 크리에이터 키워드 확장
            search_keywords = CREATOR_KEYWORDS.get(keyword, [keyword])

            all_tweets = []
            all_replies = []
            data_source = None

            # 각 확장 키워드로 검색 (최대 2개)
            for search_kw in search_keywords[:2]:
                tweets, replies, source = search_twitter(search_kw, max_results=10)

                # 중복 제거하면서 추가
                existing_ids = {t.get('tweet_id') for t in all_tweets}
                for tweet in tweets:
                    tweet_id = tweet.get('tweet_id')
                    if tweet_id and tweet_id not in existing_ids:
                        all_tweets.append(tweet)
                        existing_ids.add(tweet_id)

                all_replies.extend(replies)

                if source and not data_source:
                    data_source = source

                time.sleep(1)  # Rate limiting between keywords

            # 통계 계산
            total_likes = sum(t.get('like_count', 0) for t in all_tweets)
            total_retweets = sum(t.get('retweet_count', 0) for t in all_tweets)

            # 데이터 저장 (실제 데이터가 있을 때만)
            s3_key = None
            if all_tweets:
                crawl_result = {
                    'keyword': keyword,
                    'platform': 'twitter',
                    'crawled_at': isoformat_kst(),
                    'data_source': data_source,
                    'total_tweets': len(all_tweets),
                    'total_replies': len(all_replies),
                    'total_likes': total_likes,
                    'total_retweets': total_retweets,
                    'tweets': all_tweets,
                    'data': [{'tweet': t, 'replies': []} for t in all_tweets[:5]]
                }

                s3_key = save_to_s3(crawl_result, keyword)

                # LLM 분석 트리거
                if len(all_tweets) >= 3:
                    trigger_llm_analysis(s3_key, keyword, len(all_tweets))

            total_tweets_found += len(all_tweets)

            results.append({
                'keyword': keyword,
                'status': 'success' if all_tweets else 'no_data',
                'data_source': data_source,
                'tweets_found': len(all_tweets),
                'total_replies': len(all_replies),
                'total_likes': total_likes,
                'total_retweets': total_retweets,
                's3_key': s3_key,
                'tweets': all_tweets,
                'replies': all_replies,
                'message': None if all_tweets else 'No tweets found - Twitter API subscription required'
            })

            print(f"Completed: {keyword} - {len(all_tweets)} tweets, {total_likes} likes")

        except Exception as e:
            print(f"Error processing keyword '{keyword}': {e}")
            import traceback
            traceback.print_exc()

            # 에러 발생시 로컬 데이터로 폴백
            local_tweets, local_replies = load_local_twitter_data(keyword)

            results.append({
                'keyword': keyword,
                'status': 'partial' if local_tweets else 'error',
                'data_source': 'local_data' if local_tweets else None,
                'tweets_found': len(local_tweets),
                'total_replies': len(local_replies),
                'total_likes': sum(t.get('like_count', 0) for t in local_tweets),
                'error': str(e),
                'tweets': local_tweets,
                'replies': local_replies
            })

    print(f"\n{'='*50}")
    print(f"Twitter crawl complete: {total_tweets_found} total tweets found")
    print(f"{'='*50}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'results': results,
            'crawled_at': isoformat_kst(),
            'total_tweets_found': total_tweets_found,
            'twitter_api_configured': bool(TWITTER_BEARER_TOKEN),
            'note': 'Real data only - no sample data' if total_tweets_found > 0 else 'No data collected - Twitter API required'
        }, ensure_ascii=False)
    }
