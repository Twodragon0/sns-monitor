"""
Threads 크롤러
Meta Threads API 또는 웹 스크래핑을 사용하여 특정 키워드의 게시물 및 댓글 수집
"""

import json
import os
import boto3
from datetime import datetime
import requests
from urllib.parse import quote

# AWS 클라이언트 (LocalStack 지원)
s3_endpoint = os.environ.get('S3_ENDPOINT')
s3_client = boto3.client('s3', endpoint_url=s3_endpoint) if s3_endpoint else boto3.client('s3')

# 환경 변수
S3_BUCKET = os.environ.get('S3_BUCKET')
LLM_ANALYZER_ENDPOINT = os.environ.get('LLM_ANALYZER_ENDPOINT', 'http://llm-analyzer:5000')
THREADS_ACCESS_TOKEN = os.environ.get('THREADS_ACCESS_TOKEN')
THREADS_APP_ID = os.environ.get('THREADS_APP_ID')
SEARCH_KEYWORDS = os.environ.get('SEARCH_KEYWORDS', '').split(',')

def search_threads_posts(keyword, max_results=10):
    """키워드로 Threads 게시물 검색"""
    if not THREADS_ACCESS_TOKEN:
        print("Threads Access Token not configured")
        return []
    
    try:
        # Threads API 사용 (Meta Graph API 기반)
        # 사용자 검색 또는 해시태그 검색
        url = "https://graph.threads.net/v1.0/search"
        params = {
            'q': keyword,
            'access_token': THREADS_ACCESS_TOKEN,
            'limit': min(max_results, 25)
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            posts = []
            
            for post in data.get('data', []):
                posts.append({
                    'post_id': post.get('id'),
                    'text': post.get('text', ''),
                    'author': post.get('user', {}).get('username', 'unknown'),
                    'created_at': post.get('created_at', ''),
                    'like_count': post.get('like_count', 0),
                    'reply_count': post.get('reply_count', 0)
                })
            
            print(f"Found {len(posts)} Threads posts for keyword '{keyword}'")
            return posts
        else:
            print(f"Threads API error: {response.status_code} - {response.text}")
            # API가 없으면 빈 리스트 반환
            return []
            
    except Exception as e:
        print(f"Error searching Threads: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_post_replies(post_id, max_results=20):
    """게시물의 댓글 가져오기"""
    if not THREADS_ACCESS_TOKEN:
        return []
    
    try:
        url = f"https://graph.threads.net/v1.0/{post_id}/replies"
        params = {
            'fields': 'id,text,created_at,from,like_count',
            'access_token': THREADS_ACCESS_TOKEN,
            'limit': min(max_results, 100)
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            replies = []
            
            for reply in data.get('data', []):
                author = reply.get('from', {})
                replies.append({
                    'reply_id': reply.get('id'),
                    'text': reply.get('text', ''),
                    'author': author.get('username', 'unknown'),
                    'created_at': reply.get('created_at', ''),
                    'like_count': reply.get('like_count', 0)
                })
            
            return replies
        else:
            return []
            
    except Exception as e:
        print(f"Error getting post replies: {e}")
        return []

def save_to_s3(data, keyword):
    """수집된 데이터를 S3에 저장"""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    key = f"raw-data/threads/{keyword}/{timestamp}.json"

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        print(f"Saved to s3://{S3_BUCKET}/{key}")
        return key
    except Exception as e:
        print(f"Error saving to S3: {e}")
        return None

def save_to_dynamodb(keyword, s3_key, total_posts, total_replies, total_likes):
    """DynamoDB에 결과 저장"""
    try:
        dynamodb_endpoint = os.environ.get('DYNAMODB_ENDPOINT')
        if dynamodb_endpoint:
            dynamodb = boto3.resource('dynamodb', endpoint_url=dynamodb_endpoint)
        else:
            dynamodb = boto3.resource('dynamodb')
        
        table = dynamodb.Table(os.environ.get('DYNAMODB_TABLE', 'sns-monitor-results'))
        
        item = {
            'id': f"threads-{keyword}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            'platform': 'threads',
            'keyword': keyword,
            'timestamp': datetime.utcnow().isoformat(),
            's3_key': s3_key,
            'total_posts': total_posts,
            'total_replies': total_replies,
            'total_likes': total_likes,
            'total_comments': total_replies  # 댓글 수
        }
        
        table.put_item(Item=item)
        print(f"Saved to DynamoDB: {keyword}")
    except Exception as e:
        print(f"Error saving to DynamoDB: {e}")

def trigger_llm_analysis(s3_key, keyword, total_comments):
    """LLM 분석 트리거"""
    try:
        requests.post(
            f"{LLM_ANALYZER_ENDPOINT}/analyze",
            json={
                's3_key': s3_key,
                'keyword': keyword,
                'platform': 'threads',
                'total_comments': total_comments
            },
            timeout=30
        )
    except Exception as e:
        print(f"Error triggering LLM analysis: {e}")

def lambda_handler(event, context):
    """
    Lambda 핸들러
    
    EventBridge에서 주기적으로 호출
    또는 API Gateway를 통한 수동 호출
    """
    
    print(f"Event: {json.dumps(event)}")
    
    keywords_to_search = event.get('keywords', []) or SEARCH_KEYWORDS
    results = []
    
    for keyword in keywords_to_search:
        keyword = keyword.strip()
        if not keyword:
            continue
        
        print(f"Searching Threads for keyword: {keyword}")
        
        try:
            # 게시물 검색
            posts = search_threads_posts(keyword, max_results=10)
            
            total_replies = 0
            total_likes = 0
            post_data = []
            
            # 각 게시물의 댓글 수집
            for post in posts[:5]:  # 최대 5개 게시물
                print(f"Fetching replies for post: {post['post_id']}")
                
                replies = get_post_replies(post['post_id'], max_results=20)
                total_replies += len(replies)
                total_likes += post.get('like_count', 0)
                
                post_data.append({
                    'post': post,
                    'replies': replies,
                    'reply_count': len(replies)
                })
            
            # S3에 저장
            crawl_result = {
                'keyword': keyword,
                'platform': 'threads',
                'crawled_at': datetime.utcnow().isoformat(),
                'total_posts': len(posts),
                'total_replies': total_replies,
                'total_likes': total_likes,
                'data': post_data
            }
            
            s3_key = save_to_s3(crawl_result, keyword)
            
            # DynamoDB에 저장
            if s3_key:
                save_to_dynamodb(keyword, s3_key, len(posts), total_replies, total_likes)
            
            # LLM 분석 트리거
            trigger_llm_analysis(s3_key, keyword, total_replies)
            
            results.append({
                'keyword': keyword,
                'status': 'success',
                'posts_found': len(posts),
                'total_replies': total_replies,
                'total_likes': total_likes,
                's3_key': s3_key
            })
            
        except Exception as e:
            print(f"Error crawling Threads for keyword '{keyword}': {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'keyword': keyword,
                'status': 'error',
                'error': str(e)
            })
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'results': results
        })
    }

