"""
RSS 피드 크롤러
블로그, 뉴스 사이트 등의 RSS 피드를 수집하고 키워드 필터링
"""

import json
import os
import boto3
from datetime import datetime, timedelta
import feedparser
import requests
from urllib.parse import urlparse

# AWS 클라이언트
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')

# 환경 변수
S3_BUCKET = os.environ.get('S3_BUCKET')
LLM_ANALYZER_FUNCTION = os.environ.get('LLM_ANALYZER_FUNCTION')
SEARCH_KEYWORDS = os.environ.get('SEARCH_KEYWORDS', '').split(',')
RSS_FEEDS = os.environ.get('RSS_FEEDS', '').split(',')  # RSS 피드 URL 목록
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')

def fetch_rss_feed(feed_url):
    """RSS 피드 가져오기"""
    try:
        # User-Agent 설정 (일부 사이트에서 필요)
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; SNS-Monitor-Bot/1.0)'
        }

        response = requests.get(feed_url, headers=headers, timeout=30)
        response.raise_for_status()

        # feedparser로 파싱
        feed = feedparser.parse(response.content)

        if feed.bozo:  # 파싱 오류
            print(f"Feed parsing error: {feed.bozo_exception}")
            return None

        return feed

    except Exception as e:
        print(f"Error fetching RSS feed {feed_url}: {e}")
        return None

def filter_by_keywords(entry, keywords):
    """키워드로 필터링"""
    title = entry.get('title', '').lower()
    summary = entry.get('summary', '').lower()
    content = entry.get('content', [{}])[0].get('value', '').lower() if 'content' in entry else ''

    text = f"{title} {summary} {content}"

    # 키워드 중 하나라도 포함되면 True
    return any(keyword.lower() in text for keyword in keywords)

def filter_by_date(entry, hours=24):
    """최근 N시간 이내 게시물만 필터링"""
    try:
        if 'published_parsed' in entry:
            published = datetime(*entry.published_parsed[:6])
        elif 'updated_parsed' in entry:
            published = datetime(*entry.updated_parsed[:6])
        else:
            return True  # 날짜 정보 없으면 포함

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return published >= cutoff

    except Exception as e:
        print(f"Date parsing error: {e}")
        return True  # 오류 시 포함

def extract_entry_data(entry, feed_info):
    """RSS 엔트리에서 데이터 추출"""

    # 기본 정보
    data = {
        'title': entry.get('title', ''),
        'link': entry.get('link', ''),
        'summary': entry.get('summary', ''),
        'author': entry.get('author', 'Unknown'),
        'published': entry.get('published', ''),
        'updated': entry.get('updated', ''),
        'feed_title': feed_info.get('title', ''),
        'feed_link': feed_info.get('link', ''),
        'source': urlparse(entry.get('link', '')).netloc
    }

    # 전체 콘텐츠 (있는 경우)
    if 'content' in entry and entry.content:
        data['content'] = entry.content[0].get('value', '')

    # 태그/카테고리
    if 'tags' in entry:
        data['tags'] = [tag.term for tag in entry.tags]

    return data

def crawl_rss_feeds(keywords):
    """RSS 피드 크롤링"""
    results = []

    feeds = [f.strip() for f in RSS_FEEDS if f.strip()]

    if not feeds:
        print("No RSS feeds configured")
        return results

    for feed_url in feeds:
        print(f"Crawling RSS feed: {feed_url}")

        feed = fetch_rss_feed(feed_url)
        if not feed:
            continue

        feed_info = {
            'title': feed.feed.get('title', ''),
            'link': feed.feed.get('link', ''),
            'description': feed.feed.get('description', '')
        }

        matched_entries = []

        for entry in feed.entries:
            # 날짜 필터링 (최근 24시간)
            if not filter_by_date(entry, hours=24):
                continue

            # 키워드 필터링
            if keywords and not filter_by_keywords(entry, keywords):
                continue

            # 데이터 추출
            entry_data = extract_entry_data(entry, feed_info)
            matched_entries.append(entry_data)

        if matched_entries:
            results.append({
                'feed_url': feed_url,
                'feed_info': feed_info,
                'entries': matched_entries,
                'entry_count': len(matched_entries)
            })

            print(f"Found {len(matched_entries)} matching entries in {feed_url}")

    return results

def save_to_s3(data, keyword):
    """수집된 데이터를 S3에 저장"""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    key = f"raw-data/rss/{keyword}/{timestamp}.json"

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

def trigger_llm_analysis(s3_key, keyword, total_entries):
    """LLM 분석기 호출"""
    try:
        payload = {
            'source': 'rss',
            's3_key': s3_key,
            'keyword': keyword,
            'total_items': total_entries,
            'timestamp': datetime.utcnow().isoformat()
        }

        lambda_client.invoke(
            FunctionName=LLM_ANALYZER_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        print(f"LLM analysis triggered for {s3_key}")
    except Exception as e:
        print(f"Error triggering LLM analysis: {e}")

def lambda_handler(event, context):
    """
    Lambda 핸들러

    EventBridge에서 주기적으로 호출
    """

    print(f"Event: {json.dumps(event)}")

    # 키워드 준비 (event에서 받거나 환경 변수에서 가져오기)
    event_keywords = event.get('keywords', [])
    if event_keywords:
        keywords = [k.strip() for k in event_keywords if k.strip()]
    else:
        keywords = [k.strip() for k in SEARCH_KEYWORDS if k.strip()]

    if not keywords:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'No search keywords provided'})
        }

    results = []

    try:
        # RSS 피드 크롤링
        crawl_results = crawl_rss_feeds(keywords)

        if not crawl_results:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No RSS entries found'})
            }

        # 키워드별로 그룹화하여 저장
        for keyword in keywords:
            keyword_entries = []

            for feed_result in crawl_results:
                for entry in feed_result['entries']:
                    # 이 엔트리가 해당 키워드를 포함하는지 확인
                    text = f"{entry['title']} {entry['summary']}".lower()
                    if keyword.lower() in text:
                        keyword_entries.append({
                            'feed_url': feed_result['feed_url'],
                            'feed_title': feed_result['feed_info']['title'],
                            **entry
                        })

            if keyword_entries:
                # S3에 저장
                crawl_data = {
                    'platform': 'rss',
                    'keyword': keyword,
                    'crawled_at': datetime.utcnow().isoformat(),
                    'total_entries': len(keyword_entries),
                    'entries': keyword_entries
                }

                s3_key = save_to_s3(crawl_data, keyword)

                # LLM 분석 트리거
                trigger_llm_analysis(s3_key, keyword, len(keyword_entries))

                results.append({
                    'keyword': keyword,
                    'entries_found': len(keyword_entries),
                    's3_key': s3_key
                })

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'RSS crawling completed',
                'results': results
            }, ensure_ascii=False)
        }

    except Exception as e:
        print(f"Error in RSS crawling: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
