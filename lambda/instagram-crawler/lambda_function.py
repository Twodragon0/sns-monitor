"""
Instagram 크롤러
Instagram Basic Display API 또는 Graph API를 사용하여 특정 키워드의 게시물 및 댓글 수집
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
INSTAGRAM_ACCESS_TOKEN = os.environ.get('INSTAGRAM_ACCESS_TOKEN')
INSTAGRAM_APP_ID = os.environ.get('INSTAGRAM_APP_ID')
SEARCH_KEYWORDS = os.environ.get('SEARCH_KEYWORDS', '').split(',')

def search_instagram_posts(keyword, max_results=10):
    """키워드로 Instagram 게시물 검색"""
    if not INSTAGRAM_ACCESS_TOKEN:
        print("Instagram Access Token not configured")
        return []
    
    try:
        # Instagram Graph API 사용
        # 해시태그 검색
        url = f"https://graph.instagram.com/v18.0/ig_hashtag_search"
        params = {
            'q': keyword,
            'access_token': INSTAGRAM_ACCESS_TOKEN
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            hashtag_id = data.get('data', [{}])[0].get('id') if data.get('data') else None
            
            if not hashtag_id:
                print(f"No hashtag found for '{keyword}'")
                return []
            
            # 해시태그의 최근 미디어 가져오기
            media_url = f"https://graph.instagram.com/v18.0/{hashtag_id}/recent_media"
            media_params = {
                'fields': 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count',
                'access_token': INSTAGRAM_ACCESS_TOKEN,
                'limit': min(max_results, 25)
            }
            
            media_response = requests.get(media_url, params=media_params, timeout=30)
            
            if media_response.status_code == 200:
                media_data = media_response.json()
                posts = []
                
                for post in media_data.get('data', []):
                    posts.append({
                        'post_id': post.get('id'),
                        'caption': post.get('caption', ''),
                        'media_type': post.get('media_type', ''),
                        'media_url': post.get('media_url', ''),
                        'permalink': post.get('permalink', ''),
                        'created_at': post.get('timestamp', ''),
                        'like_count': post.get('like_count', 0),
                        'comments_count': post.get('comments_count', 0)
                    })
                
                print(f"Found {len(posts)} Instagram posts for keyword '{keyword}'")
                return posts
            else:
                print(f"Instagram API error: {media_response.status_code} - {media_response.text}")
                return []
        else:
            print(f"Instagram API error: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"Error searching Instagram: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_post_comments(post_id, max_results=20):
    """게시물의 댓글 가져오기"""
    if not INSTAGRAM_ACCESS_TOKEN:
        return []
    
    try:
        url = f"https://graph.instagram.com/v18.0/{post_id}/comments"
        params = {
            'fields': 'id,text,timestamp,username,like_count',
            'access_token': INSTAGRAM_ACCESS_TOKEN,
            'limit': min(max_results, 100)
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            comments = []
            
            for comment in data.get('data', []):
                comments.append({
                    'comment_id': comment.get('id'),
                    'text': comment.get('text', ''),
                    'author': comment.get('username', 'unknown'),
                    'created_at': comment.get('timestamp', ''),
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
    key = f"raw-data/instagram/{keyword}/{timestamp}.json"

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
            'id': f"instagram-{keyword}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            'platform': 'instagram',
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
                'platform': 'instagram',
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
        
        print(f"Searching Instagram for keyword: {keyword}")
        
        try:
            # 게시물 검색
            posts = search_instagram_posts(keyword, max_results=10)
            
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
                'platform': 'instagram',
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
            print(f"Error crawling Instagram for keyword '{keyword}': {e}")
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

