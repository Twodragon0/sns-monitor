"""
DC인사이드 갤러리 크롤러
특정 갤러리에서 게시글 및 댓글 수집
"""

import json
import logging
import os
import sys
import boto3
from datetime import datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup
import time
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from comment_collector import (
    get_e_s_n_o_token,
    get_post_comments_ajax,
    get_post_comments_direct,
    get_comments_with_playwright,
    _parse_comment_item,
    _extract_comments_from_json,
    _parse_json_comments,
    _parse_html_comments,
    _extract_comment_author,
    _extract_comment_text,
    _extract_comment_date,
)

logger = logging.getLogger(__name__)

# Playwright timeout constant (milliseconds)
PAGE_TIMEOUT_MS = 30000
SELECTOR_TIMEOUT_MS = 10000

# KST 시간대 설정
KST = timezone(timedelta(hours=9))

def now_kst():
    """현재 KST 시간 반환"""
    return datetime.now(KST)

def isoformat_kst():
    """KST ISO 8601 형식"""
    return now_kst().isoformat()

# 환경 변수
S3_BUCKET = os.environ.get('S3_BUCKET')
LLM_ANALYZER_ENDPOINT = os.environ.get('LLM_ANALYZER_ENDPOINT', 'http://llm-analyzer:5000')

# 로컬 모드 설정
LOCAL_MODE = os.environ.get('LOCAL_MODE', 'false').lower() == 'true'
LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', './local-data')

logger.info("LOCAL_MODE=%s LOCAL_DATA_DIR=%s", LOCAL_MODE, LOCAL_DATA_DIR)

# AWS 클라이언트 — only initialised when not in LOCAL_MODE
s3_client = None
if not LOCAL_MODE:
    s3_endpoint = os.environ.get('S3_ENDPOINT')
    s3_client = boto3.client('s3', endpoint_url=s3_endpoint) if s3_endpoint else boto3.client('s3')

# Playwright는 드라이버 생성 함수가 필요 없음 - 컨텍스트 매니저 사용

# DC인사이드 갤러리 설정
# 공통 키워드 (모든 갤러리에서 사용)
COMMON_KEYWORDS = [
    # ExampleCorp / CreatorBrand (platform)
    'examplecorp', 'ExampleCorp', 'EXAMPLECORP',
    'creatorbrand', 'CreatorBrand', 'CREATORBRAND',
    # Creator group keywords
    'Creator1', 'creator1',
    'Creator2', 'creator2',
    'Creator3', 'creator3',
    'ExampleStudio', 'examplestyle',
    # Merchandise related
    'goods', 'photocard', 'keyring', 'sticker', 'poster', 'album', 'limited',
    'digitalgoods', 'officialgoods',
    # Fan activity
    'event', 'giveaway', 'fanmeet',
]

GALLERIES = {
    # === Active galleries ===
    'ivnit': {
        'url': 'https://gall.dcinside.com/mini/board/lists/?id=ivnit',
        'name': '이브닛 갤러리',
        'type': 'mini',
        'keywords': COMMON_KEYWORDS + ['이브닛', '쿠우', '사미', '퍼지데이', 'ivnit']
    },
    'akaiv': {
        'url': 'https://gall.dcinside.com/mini/board/lists/?id=akaiv',
        'name': '아카이브 갤러리',
        'type': 'mini',
        'keywords': COMMON_KEYWORDS + ['아카이브', '여르미', '결이', '몽이', 'akaiv']
    },
    'soopvirtualstreamer': {
        'url': 'https://gall.dcinside.com/mini/board/lists/?id=soopvirtualstreamer',
        'name': 'SOOP 버추얼 스트리머 갤러리',
        'type': 'mini',
        'keywords': COMMON_KEYWORDS + ['버추얼', '챠니', '챱츄', '기원', 'vtuber', 'soop']
    },
    'spv': {
        'url': 'https://gall.dcinside.com/mini/board/lists/?id=spv',
        'name': 'SPV 갤러리',
        'type': 'mini',
        'keywords': COMMON_KEYWORDS + ['버시', '버추얼', 'spv', 'soop']
    },
    'soopstreaming': {
        'url': 'https://gall.dcinside.com/mini/board/lists/?id=soopstreaming',
        'name': 'SOOP 스트리밍 갤러리',
        'type': 'mini',
        'keywords': COMMON_KEYWORDS + ['세구', '와우', '제우스', 'soop', '스트리밍']
    },
    'skoshism': {
        'url': 'https://gall.dcinside.com/mgallery/board/lists/?id=skoshism',
        'name': '스코시즘 갤러리',
        'type': 'mgallery',
        'keywords': COMMON_KEYWORDS + ['스코시즘', '방송', 'skoshism']
    },
    # === Example galleries (kept for testing) ===
    'example-gallery-1': {
        'url': 'https://gall.dcinside.com/mini/board/lists/?id=example-gallery-1',
        'name': 'Example Gallery 1',
        'type': 'mini',
        'keywords': COMMON_KEYWORDS + ['examplegallery1', 'gallery1']
    },
    'example-gallery-2': {
        'url': 'https://gall.dcinside.com/mini/board/lists?id=example-gallery-2',
        'name': 'Example Gallery 2',
        'type': 'mini',
        'keywords': COMMON_KEYWORDS + ['examplegallery2', 'gallery2']
    },
}

def get_gallery_posts(gallery_id, max_posts=20):
    """갤러리 게시글 목록 가져오기"""
    try:
        gallery_info = GALLERIES.get(gallery_id)
        if not gallery_info:
            logger.warning("Unknown gallery: %s", gallery_id)
            return []

        url = gallery_info['url']
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []

        # 게시글 목록 파싱
        post_list = soup.select('.gall_list tbody tr.ub-content')

        for post in post_list[:max_posts]:
            try:
                # 게시글 번호
                post_num = post.select_one('.gall_num')
                if not post_num or post_num.text.strip() in ['공지', '설문']:
                    continue

                post_id = post_num.text.strip()

                # 숫자가 아닌 게시글 ID 건너뛰기 (예: '-', 'AD' 등)
                if not post_id.isdigit():
                    continue

                # 제목과 댓글 수
                title_elem = post.select_one('.gall_tit a')
                title = title_elem.text.strip() if title_elem else ''

                # 댓글 수 (게시글 목록에서 직접 가져오기)
                reply_num_elem = post.select_one('.gall_tit .reply_num')
                comment_count = 0
                if reply_num_elem:
                    reply_text = reply_num_elem.text.strip()
                    # [15] 형식에서 숫자 추출
                    match = re.search(r'\[(\d+)\]', reply_text)
                    if match:
                        comment_count = int(match.group(1))

                # 공지/규정/가이드라인 게시글 제외
                notice_keywords = [
                    '공지', '규정', '말모이', '신문고', '질문 및 끌올', '차단 해제 문의',
                    '규칙', '가이드라인', '가이드 라인', '창작 가이드', '2차 창작'
                ]
                if any(keyword in title for keyword in notice_keywords):
                    continue

                # 유튜브 타임스탬프 형식 게시글 제외 (예: "32:15 초딩말티즈 32:46 오타니")
                # 타임스탬프 패턴이 3개 이상 포함된 경우 제외
                timestamp_pattern = r'\d{1,2}:\d{2}'
                timestamp_matches = re.findall(timestamp_pattern, title)
                if len(timestamp_matches) >= 3:
                    continue

                # 작성자
                author_elem = post.select_one('.gall_writer')
                author = author_elem.get('data-nick', '익명') if author_elem else '익명'

                # 날짜
                date_elem = post.select_one('.gall_date')
                date_str = date_elem.get('title', '') if date_elem else ''

                # 조회수
                view_elem = post.select_one('.gall_count')
                view_count = int(view_elem.text.strip()) if view_elem else 0

                # 추천수
                recommend_elem = post.select_one('.gall_recommend')
                recommend_count = int(recommend_elem.text.strip()) if recommend_elem else 0

                # URL (갤러리 타입에 따라 경로 다름)
                gallery_type = gallery_info.get('type', 'mini')
                post_url = f"https://gall.dcinside.com/{gallery_type}/board/view/?id={gallery_id}&no={post_id}"

                posts.append({
                    'post_id': post_id,
                    'title': title,
                    'author': author,
                    'date': date_str,
                    'view_count': view_count,
                    'recommend_count': recommend_count,
                    'comment_count': comment_count,
                    'url': post_url,
                    'gallery_id': gallery_id,
                    'gallery_name': gallery_info['name'],
                    'gallery_type': gallery_type
                })

            except Exception as e:
                logger.error("Error parsing post: %s", e)
                continue

        logger.info("Found %d posts in gallery '%s'", len(posts), gallery_id)
        return posts

    except Exception as e:
        logger.error("Error getting gallery posts: %s", e)
        import traceback
        traceback.print_exc()
        return []


def get_post_content(gallery_id, post_id, gallery_type='mini'):
    """게시글 내용 및 댓글 가져오기"""
    try:
        # AJAX를 사용하여 실제 댓글 데이터 수집
        comments = get_post_comments_ajax(gallery_id, post_id, gallery_type)
        
        # 댓글이 없으면 Playwright로 댓글 수만 확인
        if not comments:
            comment_data = get_comments_with_playwright(gallery_id, post_id, gallery_type)
            comment_count = comment_data.get('comment_count', 0)
        else:
            comment_count = len(comments)

        # 게시글 내용은 간단히 requests로 가져오기
        url = f"https://gall.dcinside.com/{gallery_type}/board/view/?id={gallery_id}&no={post_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30, verify=True)
        soup = BeautifulSoup(response.text, 'html.parser')

        content_elem = soup.select_one('.write_div')
        content = content_elem.get_text(strip=True) if content_elem else ''

        return {
            'content': content,
            'comments': comments,
            'comment_count': comment_count
        }

    except Exception as e:
        logger.error("Error getting post content: %s", e)
        import traceback
        traceback.print_exc()
        return {
            'content': '',
            'comments': [],
            'comment_count': 0
        }

def filter_posts_by_keywords(posts, keywords):
    """키워드로 게시글 필터링"""
    filtered_posts = []

    for post in posts:
        title = post.get('title', '').lower()

        # 키워드 매칭
        for keyword in keywords:
            if keyword.lower() in title:
                post['matched_keyword'] = keyword
                filtered_posts.append(post)
                break

    return filtered_posts

def save_to_s3(data, gallery_id):
    """수집된 데이터를 S3 또는 로컬 파일 시스템에 저장"""
    timestamp = now_kst().strftime('%Y-%m-%d-%H-%M-%S')
    key = f"raw-data/dcinside/{gallery_id}/{timestamp}.json"

    try:
        if LOCAL_MODE:
            # 로컬 모드: 파일 시스템에 저장
            filepath = os.path.join(LOCAL_DATA_DIR, 'dcinside', gallery_id, f"{timestamp}.json")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info("Saved locally: %s", filepath)
            return key
        else:
            # 프로덕션 모드: S3에 저장
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=json.dumps(data, ensure_ascii=False, indent=2),
                ContentType='application/json'
            )
            logger.info("Saved to s3://%s/%s", S3_BUCKET, key)
            return key
    except Exception as e:
        logger.error("Error saving data: %s", e)
        return None

def save_to_dynamodb(gallery_id, s3_key, total_posts, total_comments, positive_count, negative_count):
    """DynamoDB에 결과 저장"""
    try:
        dynamodb_endpoint = os.environ.get('DYNAMODB_ENDPOINT')
        if dynamodb_endpoint:
            dynamodb = boto3.resource('dynamodb', endpoint_url=dynamodb_endpoint)
        else:
            dynamodb = boto3.resource('dynamodb')

        table = dynamodb.Table(os.environ.get('DYNAMODB_TABLE', 'sns-monitor-results'))

        item = {
            'id': f"dcinside-{gallery_id}-{now_kst().strftime('%Y%m%d%H%M%S')}",
            'platform': 'dcinside',
            'gallery_id': gallery_id,
            'gallery_name': GALLERIES[gallery_id]['name'],
            'timestamp': isoformat_kst(),
            's3_key': s3_key,
            'total_posts': total_posts,
            'total_comments': total_comments,
            'positive_count': positive_count,
            'negative_count': negative_count
        }

        table.put_item(Item=item)
        logger.info("Saved to DynamoDB: %s", gallery_id)
    except Exception as e:
        logger.error("Error saving to DynamoDB: %s", e)

def trigger_llm_analysis(s3_key, gallery_id, total_comments):
    """LLM 분석 트리거"""
    try:
        requests.post(
            f"{LLM_ANALYZER_ENDPOINT}/analyze",
            json={
                's3_key': s3_key,
                'gallery_id': gallery_id,
                'platform': 'dcinside',
                'total_comments': total_comments
            },
            timeout=30,
            verify=True
        )
    except Exception as e:
        logger.error("Error triggering LLM analysis: %s", e)

def lambda_handler(event, context):
    """
    Lambda 핸들러

    EventBridge에서 주기적으로 호출
    또는 API Gateway를 통한 수동 호출
    """

    logger.info("Event: %s", json.dumps(event))

    crawl_start = time.monotonic()
    galleries_to_crawl = event.get('galleries', list(GALLERIES.keys()))
    results = []
    failed_count = 0

    for gallery_id in galleries_to_crawl:
        if gallery_id not in GALLERIES:
            logger.warning("Unknown gallery: %s", gallery_id)
            continue

        logger.info("Crawling gallery: %s (%s)", gallery_id, GALLERIES[gallery_id]['name'])

        try:
            # 게시글 수집 (더 많이 가져오기)
            posts = get_gallery_posts(gallery_id, max_posts=200)

            # 키워드로 필터링
            keywords = GALLERIES[gallery_id]['keywords']
            filtered_posts = filter_posts_by_keywords(posts, keywords)

            # 최소 30개 게시글 보장
            min_posts = 30
            if len(filtered_posts) < min_posts and len(posts) >= min_posts:
                logger.info("Filtered posts (%d) < minimum (%d), adding more posts", len(filtered_posts), min_posts)
                # 필터링된 게시글이 부족하면 필터링되지 않은 게시글도 추가
                filtered_post_ids = {p['post_id'] for p in filtered_posts}
                for post in posts:
                    if post['post_id'] not in filtered_post_ids:
                        filtered_posts.append(post)
                        if len(filtered_posts) >= min_posts:
                            break

            logger.info("Filtered %d posts with keywords (minimum %d guaranteed)", len(filtered_posts), min_posts)

            # 각 게시글의 내용 및 댓글 수집
            total_comments = 0
            positive_count = 0
            negative_count = 0
            post_data = []

            # 감성 분석 키워드 정의
            positive_keywords = ['좋아', '굿', '최고', '감사', '사랑', '축하', '대박', '멋지', '예쁘', '귀엽',
                                '화이팅', '응원', '존경', '멋있', '훌륭', '완벽', '최고야', 'ㄱㅇㄷ', 'ㅊㅊ',
                                '개좋', '레전드', '갓', '천재', '실화', '미쳤', '개꿀', '개이득']
            negative_keywords = ['싫어', '나쁘', '최악', '욕', '비난', '혐오', '짜증', '실망', '별로',
                               '쓰레기', '망했', '노잼', '재미없', '허접', '구리', '병신', '개같', '개별로',
                               '개망', '답없', '노답', 'ㅅㅂ', 'ㅂㅅ', '꺼져', '죽어']

            # 갤러리 타입 가져오기
            gallery_type = GALLERIES[gallery_id].get('type', 'mini')

            for post in filtered_posts[:100]:  # 최대 100개 게시글
                logger.info("Processing post: %s - %s", post['post_id'], post.get('title', '')[:30])

                # 게시글 목록에서 이미 가져온 댓글 수
                post_comment_count = post.get('comment_count', 0)

                # 댓글이 있는 게시글만 댓글 수집 (효율성)
                post_comments = []
                if post_comment_count > 0:
                    logger.info("Collecting %d comments...", post_comment_count)

                    # 1순위: 직접 파싱 (가장 빠름)
                    post_comments = get_post_comments_direct(gallery_id, post['post_id'], gallery_type)

                    # 2순위: AJAX로 댓글 수집 시도 (안정적)
                    if not post_comments:
                        logger.info("Direct parsing failed, trying AJAX...")
                        post_comments = get_post_comments_ajax(gallery_id, post['post_id'], gallery_type)

                    # 3순위: Playwright를 사용하여 댓글 수집 (가장 안정적이지만 느림)
                    if not post_comments:
                        logger.info("AJAX failed, trying Playwright...")
                        comment_data = get_comments_with_playwright(gallery_id, post['post_id'], gallery_type)
                        post_comments = comment_data.get('comments', [])

                    logger.info("Collected %d comments", len(post_comments))

                    # 댓글에 대한 키워드 필터링 및 감성 분석
                    for comment in post_comments:
                        comment_text = comment.get('text', '').lower()
                        
                        # 키워드 매칭
                        matched_keywords = [kw for kw in keywords if kw.lower() in comment_text]
                        if matched_keywords:
                            comment['matched_keywords'] = matched_keywords

                        # 감성 분석
                        if any(kw in comment_text for kw in positive_keywords):
                            comment['sentiment'] = 'positive'
                            positive_count += 1
                        elif any(kw in comment_text for kw in negative_keywords):
                            comment['sentiment'] = 'negative'
                            negative_count += 1
                        else:
                            comment['sentiment'] = 'neutral'

                    time.sleep(0.5)  # Rate limiting

                total_comments += len(post_comments) if post_comments else post_comment_count

                # 게시글 제목에 대한 감성 분석
                post_title = post.get('title', '').lower()

                # 게시글 감성 분석 (제목 기준)
                if any(keyword in post_title for keyword in positive_keywords):
                    positive_count += 1
                elif any(keyword in post_title for keyword in negative_keywords):
                    negative_count += 1

                post_data.append({
                    'post': post,
                    'content': '',
                    'comments': post_comments,
                    'comment_count': len(post_comments) if post_comments else post_comment_count
                })

            # S3에 저장
            crawl_result = {
                'gallery_id': gallery_id,
                'gallery_name': GALLERIES[gallery_id]['name'],
                'platform': 'dcinside',
                'crawled_at': isoformat_kst(),
                'total_posts': len(filtered_posts),
                'total_comments': total_comments,
                'positive_count': positive_count,
                'negative_count': negative_count,
                'keywords': keywords,
                'data': post_data
            }

            s3_key = save_to_s3(crawl_result, gallery_id)

            # DynamoDB에 저장
            if s3_key:
                save_to_dynamodb(gallery_id, s3_key, len(filtered_posts), total_comments, positive_count, negative_count)

            # LLM 분석 트리거
            trigger_llm_analysis(s3_key, gallery_id, total_comments)

            logger.info(
                "Gallery summary | gallery=%s posts=%d comments=%d positive=%d negative=%d s3_key=%s",
                gallery_id, len(filtered_posts), total_comments,
                positive_count, negative_count, s3_key,
            )

            results.append({
                'gallery_id': gallery_id,
                'status': 'success',
                'posts_found': len(filtered_posts),
                'total_comments': total_comments,
                'positive_count': positive_count,
                'negative_count': negative_count,
                's3_key': s3_key
            })

        except Exception as e:
            logger.error("Error crawling gallery '%s': %s", gallery_id, e)
            import traceback
            traceback.print_exc()
            failed_count += 1
            results.append({
                'gallery_id': gallery_id,
                'status': 'error',
                'error': str(e)
            })

    crawl_duration_s = time.monotonic() - crawl_start
    total_posts_all = sum(r.get('posts_found', 0) for r in results)
    total_comments_all = sum(r.get('total_comments', 0) for r in results)
    logger.info(
        "Crawl complete | galleries_processed=%d galleries_failed=%d "
        "total_posts=%d total_comments=%d duration_s=%.1f",
        len(galleries_to_crawl), failed_count,
        total_posts_all, total_comments_all, crawl_duration_s,
    )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'results': results
        })
    }


if __name__ == '__main__':
    """Docker entrypoint: run crawler once, then repeat every CRAWL_INTERVAL seconds."""
    import signal

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    interval = int(os.environ.get('CRAWL_INTERVAL', 7200))  # default 2 hours
    galleries = os.environ.get('DCINSIDE_GALLERIES', '').strip()
    event = {}
    if galleries:
        event['galleries'] = [g.strip() for g in galleries.split(',') if g.strip()]

    stop = [False]
    def _sig(sig, frame):
        stop[0] = True
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    while not stop[0]:
        logger.info("=== DCInside crawler run starting (galleries=%s) ===",
                     event.get('galleries', 'all'))
        try:
            result = lambda_handler(event, None)
            body = json.loads(result.get('body', '{}'))
            for r in body.get('results', []):
                logger.info("  %s: %s (posts=%s)", r.get('gallery_id'), r.get('status'), r.get('posts_found', '?'))

            # Trigger daily report generation after crawl
            try:
                api_base = os.environ.get('API_BASE_URL', 'http://api-backend:8080')
                resp = requests.post(f'{api_base}/api/analysis/report/generate-daily', timeout=60)
                if resp.ok:
                    rdata = resp.json()
                    logger.info("Daily report generated: %s items, %s galleries",
                                rdata.get('summary', {}).get('total_items', '?'),
                                rdata.get('summary', {}).get('total_galleries', '?'))
                else:
                    logger.warning("Report generation failed: %s", resp.status_code)
            except Exception as re:
                logger.warning("Report trigger failed: %s", re)

        except Exception as e:
            logger.error("Crawler run failed: %s", e, exc_info=True)

        if interval <= 0:
            break
        logger.info("Sleeping %d seconds until next run...", interval)
        for _ in range(interval):
            if stop[0]:
                break
            time.sleep(1)

    logger.info("Crawler stopped.")
