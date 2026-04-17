"""
DCInside comment collection functions.
Extracted from crawler.py to keep file size manageable.
"""

import json
import logging
import re
import time

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Playwright timeout constants
PAGE_TIMEOUT_MS = 30000
SELECTOR_TIMEOUT_MS = 10000


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
            html = ''
            try:
                page = browser.new_page()

                # 페이지 이동
                url = f"https://gall.dcinside.com/{gallery_type}/board/view/?id={gallery_id}&no={post_id}"
                page.goto(url, wait_until='networkidle', timeout=PAGE_TIMEOUT_MS)

                # 댓글이 로드될 때까지 대기
                try:
                    page.wait_for_selector('.comment_box, .cmt_list, ul.cmt_list', timeout=SELECTOR_TIMEOUT_MS)
                except PlaywrightTimeoutError as e:
                    logger.warning(
                        "Selector timeout gallery=%s post=%s: %s — continuing with available HTML",
                        gallery_id, post_id, e,
                    )

                # 추가 대기 (동적 로딩 완료)
                time.sleep(3)

                # 페이지 HTML 가져오기
                html = page.content()
            finally:
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
