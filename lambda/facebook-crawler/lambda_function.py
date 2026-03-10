"""
Facebook 크롤러
Facebook Graph API를 사용하여 특정 키워드의 게시물 및 댓글 수집
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
FACEBOOK_ACCESS_TOKEN = os.environ.get('FACEBOOK_ACCESS_TOKEN')
FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID')
SEARCH_KEYWORDS = os.environ.get('SEARCH_KEYWORDS', '').split(',')

def search_facebook_posts(keyword, max_results=10):
    """키워드로 Facebook 게시물 검색"""
    if not FACEBOOK_ACCESS_TOKEN:
        print("Facebook Access Token not configured")
        return []
    
    try:
        # Facebook Graph API 사용
        # 페이지 검색 또는 공개 게시물 검색
        url = "https://graph.facebook.com/v18.0/search"
        params = {
            'q': keyword,
            'type': 'page',
            'access_token': FACEBOOK_ACCESS_TOKEN,
            'limit': min(max_results, 25)
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            pages = data.get('data', [])
            
            posts = []
            for page in pages[:5]:  # 최대 5개 페이지
                page_id = page.get('id')
                
                # 페이지의 최근 게시물 가져오기
                posts_url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
                posts_params = {
                    'fields': 'id,message,created_time,likes.summary(true),comments.summary(true),shares',
                    'access_token': FACEBOOK_ACCESS_TOKEN,
                    'limit': 5
                }
                
                posts_response = requests.get(posts_url, params=posts_params, timeout=30)
                
                if posts_response.status_code == 200:
                    posts_data = posts_response.json()
                    for post in posts_data.get('data', []):
                        posts.append({
                            'post_id': post.get('id'),
                            'message': post.get('message', ''),
                            'created_at': post.get('created_time', ''),
                            'like_count': post.get('likes', {}).get('summary', {}).get('total_count', 0),
                            'comment_count': post.get('comments', {}).get('summary', {}).get('total_count', 0),
                            'share_count': post.get('shares', {}).get('count', 0) if post.get('shares') else 0
                        })
            
            print(f"Found {len(posts)} Facebook posts for keyword '{keyword}'")
            return posts
        else:
            print(f"Facebook API error: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"Error searching Facebook: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_post_comments(post_id, max_results=20):
    """게시물의 댓글 가져오기"""
    if not FACEBOOK_ACCESS_TOKEN:
        return []
    
    try:
        url = f"https://graph.facebook.com/v18.0/{post_id}/comments"
        params = {
            'fields': 'id,message,created_time,from,like_count',
            'access_token': FACEBOOK_ACCESS_TOKEN,
            'limit': min(max_results, 100)
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            comments = []
            
            for comment in data.get('data', []):
                author = comment.get('from', {})
                comments.append({
                    'comment_id': comment.get('id'),
                    'text': comment.get('message', ''),
                    'author': author.get('name', 'unknown'),
                    'author_id': author.get('id', ''),
                    'created_at': comment.get('created_time', ''),
                    'like_count': comment.get('like_count', 0)
                })
            
            return comments
        else:
            return []
            
    except Exception as e:
        print(f"Error getting post comments: {e}")
        return []

def save_to_s3(data, keyword):
    """수집된 데이터를 S3에 저장"""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    key = f"raw-data/facebook/{keyword}/{timestamp}.json"

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

def save_to_dynamodb(keyword, s3_key, total_posts, total_comments, total_likes):
    """DynamoDB에 결과 저장"""
    try:
        dynamodb_endpoint = os.environ.get('DYNAMODB_ENDPOINT')
        if dynamodb_endpoint:
            dynamodb = boto3.resource('dynamodb', endpoint_url=dynamodb_endpoint)
        else:
            dynamodb = boto3.resource('dynamodb')
        
        table = dynamodb.Table(os.environ.get('DYNAMODB_TABLE', 'sns-monitor-results'))
        
        item = {
            'id': f"facebook-{keyword}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            'platform': 'facebook',
            'keyword': keyword,
            'timestamp': datetime.utcnow().isoformat(),
            's3_key': s3_key,
            'total_posts': total_posts,
            'total_comments': total_comments,
            'total_likes': total_likes
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
                'platform': 'facebook',
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
        
        print(f"Searching Facebook for keyword: {keyword}")
        
        try:
            # 게시물 검색
            posts = search_facebook_posts(keyword, max_results=10)
            
            total_comments = 0
            total_likes = 0
            post_data = []
            
            # 각 게시물의 댓글 수집
            for post in posts[:5]:  # 최대 5개 게시물
                print(f"Fetching comments for post: {post['post_id']}")
                
                comments = get_post_comments(post['post_id'], max_results=20)
                total_comments += len(comments)
                total_likes += post.get('like_count', 0)
                
                post_data.append({
                    'post': post,
                    'comments': comments,
                    'comment_count': len(comments)
                })
            
            # S3에 저장
            crawl_result = {
                'keyword': keyword,
                'platform': 'facebook',
                'crawled_at': datetime.utcnow().isoformat(),
                'total_posts': len(posts),
                'total_comments': total_comments,
                'total_likes': total_likes,
                'data': post_data
            }
            
            s3_key = save_to_s3(crawl_result, keyword)
            
            # DynamoDB에 저장
            if s3_key:
                save_to_dynamodb(keyword, s3_key, len(posts), total_comments, total_likes)
            
            # LLM 분석 트리거
            trigger_llm_analysis(s3_key, keyword, total_comments)
            
            results.append({
                'keyword': keyword,
                'status': 'success',
                'posts_found': len(posts),
                'total_comments': total_comments,
                'total_likes': total_likes,
                's3_key': s3_key
            })
            
        except Exception as e:
            print(f"Error crawling Facebook for keyword '{keyword}': {e}")
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

