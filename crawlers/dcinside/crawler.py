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

logger = logging.getLogger(__name__)

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

# 로컬 모드 설정
LOCAL_MODE = os.environ.get('LOCAL_MODE', '').lower() == 'true'
LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', './local-data')

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
    'example-gallery-3': {
        'url': 'https://gall.dcinside.com/mini/board/lists?id=example-gallery-3',
        'name': 'Example Gallery 3',
        'type': 'mini',
        'keywords': COMMON_KEYWORDS + ['examplegallery3', 'gallery3', 'vtuber', 'virtual']
    },
    'example-gallery-4': {
        'url': 'https://gall.dcinside.com/mini/board/lists/?id=example-gallery-4',
        'name': 'Example Gallery 4',
        'type': 'mini',
        'keywords': COMMON_KEYWORDS + ['examplegallery4', 'gallery4', 'streaming']
    },
    'example-gallery-5': {
        'url': 'https://gall.dcinside.com/mgallery/board/lists/?id=example-gallery-5',
        'name': 'Example Gallery 5',
        'type': 'mgallery',
        'keywords': COMMON_KEYWORDS + [
            'examplegallery5', 'gallery5',
            'creatorbrandshop', 'creatorbrand shop', 'creatorbrand.io',
            'creatorbrand popup'
        ]
    }
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

def get_e_s_n_o_token(gallery_id, post_id, gallery_type='mini'):
    """게시글 페이지에서 e_s_n_o 토큰 추출"""
    try:
        url = f"https://gall.dcinside.com/{gallery_type}/board/view/?id={gallery_id}&no={post_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        response = requests.get(url, headers=headers, timeout=15, verify=True)
        if response.status_code != 200:
            return ''

        # 스크립트에서 e_s_n_o 찾기
        match = re.search(r'e_s_n_o\s*[=:]\s*["\']([^"\']+)["\']', response.text)
        if match:
            return match.group(1)

        # hidden input에서 찾기
        soup = BeautifulSoup(response.text, 'lxml')
        e_s_n_o_input = soup.find('input', {'name': 'e_s_n_o'})
        if e_s_n_o_input:
            return e_s_n_o_input.get('value', '')

        return ''
    except Exception as e:
        logger.error("Error getting e_s_n_o token: %s", e)
        return ''


def _extract_comments_from_json(data):
    """JSON 응답에서 댓글 추출"""
    comments = data.get('comments', [])
    
    # 응답 구조 확인 (다양한 형식 지원)
    if not comments:
        comments = data.get('data', {}).get('comments', [])
    if not comments and isinstance(data, list):
        comments = data
    if not comments and isinstance(data, dict):
        comments = data.get('result', {}).get('comments', [])
    if not comments and isinstance(data, dict):
        # 직접 comments 필드가 없는 경우 모든 키 확인
        for key in data.keys():
            if 'comment' in key.lower():
                potential_comments = data.get(key, [])
                if isinstance(potential_comments, list) and len(potential_comments) > 0:
                    comments = potential_comments
                    logger.debug("Found comments in field: %s", key)
                    break
    
    return comments

def _parse_json_comments(comments):
    """JSON 댓글 리스트를 파싱하여 표준 형식으로 변환"""
    parsed_comments = []
    for cmt in comments:
        text = cmt.get('memo', '') or cmt.get('text', '') or cmt.get('comment', '')
        text = text.strip() if text else ''
        
        if text and not text.startswith('<') and len(text) > 0:
            parsed_comments.append({
                'author': cmt.get('name', cmt.get('author', '익명')),
                'text': text,
                'date': cmt.get('reg_date', cmt.get('date', '')),
                'comment_id': cmt.get('no', cmt.get('id', ''))
            })
    return parsed_comments

def _parse_html_comments(soup):
    """HTML에서 댓글 추출"""
    parsed_comments = []
    comment_items = soup.select('.cmt_info, .comment_info, .reply_info')
    
    if not comment_items:
        return parsed_comments
    
    for item in comment_items:
        try:
            nick_elem = item.select_one('.gall_writer, .nick, .writer')
            author = '익명'
            if nick_elem:
                author = nick_elem.get('data-nick', '') or nick_elem.get_text(strip=True) or '익명'

            text_elem = item.select_one('.usertxt, .comment_text, .reply_text')
            text = text_elem.get_text(strip=True) if text_elem else ''

            date_elem = item.select_one('.date_time, .date')
            date_str = date_elem.get_text(strip=True) if date_elem else ''

            if text and len(text) > 0:
                parsed_comments.append({
                    'author': author,
                    'text': text,
                    'date': date_str
                })
        except Exception as e:
            logger.error("Error parsing comment item: %s", e)
            continue

    return parsed_comments

def get_post_comments_ajax(gallery_id, post_id, gallery_type='mini'):
    """AJAX 엔드포인트를 통한 댓글 수집"""
    try:
        # 먼저 e_s_n_o 토큰 획득
        e_s_n_o = get_e_s_n_o_token(gallery_id, post_id, gallery_type)
        if not e_s_n_o:
            logger.warning("Failed to get e_s_n_o token, trying without token")
            e_s_n_o = ''

        # 데스크톱 버전 댓글 API 사용
        url = "https://gall.dcinside.com/board/comment/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Referer': f'https://gall.dcinside.com/{gallery_type}/board/view/?id={gallery_id}&no={post_id}'
        }

        all_comments = []
        page = 1
        max_pages = 5  # 최대 5페이지까지만 수집

        while page <= max_pages:
            params = {
                'id': gallery_id,
                'no': post_id,
                'cmt_id': gallery_id,
                'cmt_no': post_id,
                'e_s_n_o': e_s_n_o,
                'comment_page': str(page),
                'sort': ''
            }

            try:
                response = requests.get(url, headers=headers, params=params, timeout=15, verify=True)

                if response.status_code != 200:
                    logger.warning("AJAX request failed with status %d, response: %s", response.status_code, response.text[:200])
                    break

                # JSON 응답 시도
                try:
                    data = response.json()
                    logger.debug("AJAX response keys: %s", list(data.keys()) if isinstance(data, dict) else 'list')

                    comments = _extract_comments_from_json(data)
                    if not comments:
                        logger.debug("No comments found in JSON response (page %d), response sample: %s", page, str(data)[:200])
                        # 첫 페이지에서 댓글이 없으면 종료, 그 외에는 다음 페이지 시도
                        if page == 1:
                            break
                        else:
                            page += 1
                            continue

                    parsed_comments = _parse_json_comments(comments)
                    if parsed_comments:
                        all_comments.extend(parsed_comments)
                    else:
                        # 파싱된 댓글이 없으면 다음 페이지로
                        if page == 1:
                            break
                            
                except (ValueError, json.JSONDecodeError) as json_error:
                    # HTML 응답인 경우
                    logger.debug("JSON decode failed, trying HTML parsing: %s", json_error)
                    logger.debug("Response content type: %s", response.headers.get('Content-Type', 'unknown'))
                    logger.debug("Response text preview: %s", response.text[:500])

                    soup = BeautifulSoup(response.text, 'html.parser')
                    parsed_comments = _parse_html_comments(soup)

                    if not parsed_comments:
                        logger.debug("No comment items found in HTML (page %d)", page)
                        # 응답이 HTML이지만 댓글이 없는 경우, 실제 HTML 구조 확인
                        comment_containers = soup.select('.comment_box, .comment_wrap, .cmt_list, ul.cmt_list')
                        if comment_containers:
                            logger.debug("Found %d comment containers but no parsed comments", len(comment_containers))
                            # 더 넓은 범위의 셀렉터 시도
                            all_li_items = soup.select('li[data-no], li.cmt_info, li.reply_info')
                            logger.debug("Found %d potential comment items", len(all_li_items))
                        
                        # 첫 페이지에서 댓글이 없으면 종료, 그 외에는 다음 페이지 시도
                        if page == 1:
                            break
                        else:
                            page += 1
                            continue
                    
                    all_comments.extend(parsed_comments)

                # 다음 페이지로 이동
                page += 1
                time.sleep(0.5)  # Rate limiting 증가

            except Exception as e:
                logger.error("Error fetching comments page %d: %s", page, e)
                import traceback
                traceback.print_exc()
                # 에러가 발생해도 다음 페이지 시도
                if page < max_pages:
                    page += 1
                    continue
                break

        logger.info("Total comments collected via AJAX: %d", len(all_comments))
        return all_comments

    except Exception as e:
        logger.error("Error getting comments via AJAX: %s", e)
        import traceback
        traceback.print_exc()
        return []

def _extract_comment_author(item):
    """댓글 아이템에서 작성자 추출"""
    author = '익명'
    for nick_sel in ['.gall_writer', '.nickname', '.nick', 'em', '.nick_box', '[data-nick]']:
        nick_elem = item.select_one(nick_sel)
        if nick_elem:
            author = nick_elem.get('data-nick', '') or nick_elem.get_text(strip=True) or '익명'
            if author and author != '익명':
                return author
    
    # data-nick 속성 직접 확인
    if item.get('data-nick'):
        return item.get('data-nick')
    
    return author

def _extract_comment_text(item):
    """댓글 아이템에서 텍스트 추출"""
    for text_sel in ['.usertxt', '.cmt_txtbox', '.txt', 'p', '.comment_text', '.reply_text']:
        text_elem = item.select_one(text_sel)
        if text_elem:
            text = text_elem.get_text(strip=True)
            if text:
                return text
    
    # 텍스트가 없으면 item 자체의 텍스트 확인
    text = item.get_text(strip=True)
    # 너무 긴 텍스트는 제외 (게시글 본문일 수 있음)
    if len(text) > 500:
        return ''
    return text

def _extract_comment_date(item):
    """댓글 아이템에서 날짜 추출"""
    for date_sel in ['.date_time', '.date', '.time', '[data-date]']:
        date_elem = item.select_one(date_sel)
        if date_elem:
            date_str = date_elem.get_text(strip=True) or date_elem.get('data-date', '')
            if date_str:
                return date_str
    return ''

def _parse_comment_item(item):
    """댓글 아이템 파싱"""
    try:
        author = _extract_comment_author(item)
        text = _extract_comment_text(item)
        date_str = _extract_comment_date(item)

        # 텍스트 정제
        if text:
            text = text.strip()
            # dccon 이모티콘 제외
            if text.startswith('dccon'):
                return None
            # HTML 태그로 시작하는 경우 제외
            if text.startswith('<'):
                return None
            # 너무 짧은 텍스트 제외 (1자 이하)
            if len(text) <= 1:
                return None

        if text and len(text) > 0:
            return {
                'author': author,
                'text': text[:500],  # 최대 500자로 제한
                'date': date_str,
                'comment_id': item.get('data-no', '') or item.get('data-id', '')
            }
    except Exception as e:
        logger.error("Error parsing comment item: %s", e)
        import traceback
        traceback.print_exc()
    return None

def get_post_comments_direct(gallery_id, post_id, gallery_type='mini'):
    """게시글 페이지에서 직접 댓글 파싱"""
    try:
        url = f"https://gall.dcinside.com/{gallery_type}/board/view/?id={gallery_id}&no={post_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        response = requests.get(url, headers=headers, timeout=15, verify=True)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        comments = []

        # 댓글 영역 파싱 (여러 셀렉터 시도)
        comment_selectors = [
            '.comment_box .cmt_info',
            '.comment_wrap .cmt_nickbox',
            'ul.cmt_list li',
            '.reply_box .reply_info',
            '.comment_list li',
            '.cmt_list li',
            'li[data-no]',  # 댓글 번호가 있는 li 태그
        ]

        for selector in comment_selectors:
            comment_items = soup.select(selector)
            if not comment_items:
                continue
                
            logger.debug("Found %d items with selector: %s", len(comment_items), selector)
            for item in comment_items:
                comment = _parse_comment_item(item)
                if comment:
                    comments.append(comment)

            if comments:
                logger.info("Successfully parsed %d comments with selector: %s", len(comments), selector)
                break

        return comments

    except Exception as e:
        logger.error("Error getting comments directly: %s", e)
        return []

def get_comments_with_playwright(gallery_id, post_id, gallery_type='mini'):
    """Playwright를 사용하여 댓글 데이터 수집"""
    try:
        with sync_playwright() as p:
            # Chromium 브라우저 실행 (headless)
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 페이지 이동
            url = f"https://gall.dcinside.com/{gallery_type}/board/view/?id={gallery_id}&no={post_id}"
            page.goto(url, wait_until='networkidle', timeout=30000)

            # 댓글이 로드될 때까지 대기
            try:
                page.wait_for_selector('.comment_box, .cmt_list, ul.cmt_list', timeout=10000)
            except PlaywrightTimeoutError as e:
                logger.warning("Comment elements not found, trying anyway... (Error: %s)", e)

            # 추가 대기 (동적 로딩 완료)
            time.sleep(3)

            # 페이지 HTML 가져오기
            html = page.content()
            browser.close()

            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(html, 'html.parser')
            comments = []

            # 댓글 영역 파싱 (여러 셀렉터 시도)
            comment_selectors = [
                '.comment_box .cmt_info',
                '.comment_wrap .cmt_nickbox',
                'ul.cmt_list li',
                '.reply_box .reply_info',
                '.comment_list li',
                '.cmt_list li',
                'li[data-no]',
            ]

            for selector in comment_selectors:
                comment_items = soup.select(selector)
                if not comment_items:
                    continue
                    
                logger.debug("Found %d items with selector: %s (Playwright)", len(comment_items), selector)
                for item in comment_items:
                    comment = _parse_comment_item(item)
                    if comment:
                        comments.append(comment)

                if comments:
                    logger.info("Successfully parsed %d comments with Playwright (selector: %s)", len(comments), selector)
                    break

            # 댓글 수 확인
            comment_count = len(comments)
            comment_total_elem = soup.select_one('span[id^="comment_total_"]')
            if comment_total_elem:
                try:
                    comment_count_from_page = int(comment_total_elem.get_text(strip=True))
                    if comment_count_from_page > comment_count:
                        comment_count = comment_count_from_page
                except (ValueError, AttributeError) as e:
                    logger.warning("Could not parse comment count: %s", e)

            return {
                'comments': comments,
                'comment_count': comment_count
            }

    except Exception as e:
        logger.error("Error getting comments with Playwright: %s", e)
        import traceback
        traceback.print_exc()
        return {'comments': [], 'comment_count': 0}

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

    galleries_to_crawl = event.get('galleries', list(GALLERIES.keys()))
    results = []

    for gallery_id in galleries_to_crawl:
        if gallery_id not in GALLERIES:
            logger.warning("Unknown gallery: %s", gallery_id)
            continue

        logger.info("Crawling gallery: %s (%s)", gallery_id, GALLERIES[gallery_id]['name'])

        try:
            # 게시글 수집 (더 많이 가져오기)
            posts = get_gallery_posts(gallery_id, max_posts=50)

            # 키워드로 필터링
            keywords = GALLERIES[gallery_id]['keywords']
            filtered_posts = filter_posts_by_keywords(posts, keywords)

            # 최소 10개 게시글 보장
            min_posts = 10
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

            for post in filtered_posts[:30]:  # 최대 30개 게시글
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
            results.append({
                'gallery_id': gallery_id,
                'status': 'error',
                'error': str(e)
            })

    return {
        'statusCode': 200,
        'body': json.dumps({
            'results': results
        })
    }
