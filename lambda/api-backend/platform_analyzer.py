"""
Multi-platform SNS content analyzer.
Detects platform from URL, fetches content, and provides analysis.
Supported: YouTube, DCInside, Reddit, Telegram, Kakao
"""
import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
from collections import Counter

import requests

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class PlatformAnalyzer:
    """Analyze content from various SNS platforms given a URL."""

    PLATFORM_PATTERNS = {
        'youtube': [
            r'(?:youtube\.com|youtu\.be)',
        ],
        'dcinside': [
            r'gall\.dcinside\.com',
        ],
        'reddit': [
            r'(?:www\.)?reddit\.com',
            r'old\.reddit\.com',
        ],
        'telegram': [
            r't\.me/',
        ],
        'kakao': [
            r'open\.kakao\.com',
            r'story\.kakao\.com',
            r'pf\.kakao\.com',
        ],
    }

    def __init__(self, data_dir='/app/local-data'):
        self.data_dir = data_dir
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        })

    def detect_platform(self, url):
        """Detect which platform a URL belongs to."""
        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return platform
        return None

    def analyze(self, url):
        """Main entry point: detect platform and analyze content."""
        platform = self.detect_platform(url)
        if not platform:
            raise ValueError(
                f'Unsupported platform. Supported: {", ".join(self.PLATFORM_PATTERNS.keys())}'
            )

        handler = getattr(self, f'_analyze_{platform}', None)
        if not handler:
            raise ValueError(f'Analyzer not implemented for: {platform}')

        result = handler(url)
        result['platform'] = platform
        result['source_url'] = url
        result['analyzed_at'] = datetime.now(KST).isoformat()

        # Add sentiment analysis
        if 'comments' in result or 'posts' in result:
            items = result.get('comments', result.get('posts', []))
            result['analysis'] = self._analyze_sentiment(items)

        # Save result
        self._save_result(platform, url, result)
        return result

    def list_platforms(self):
        """List all supported platforms with example URLs."""
        return [
            {
                'name': 'YouTube',
                'id': 'youtube',
                'examples': [
                    'https://www.youtube.com/watch?v=VIDEO_ID',
                    'https://www.youtube.com/@CHANNEL_HANDLE',
                    'https://youtu.be/VIDEO_ID',
                ],
                'description': 'Video comments and channel analysis',
            },
            {
                'name': 'DCInside',
                'id': 'dcinside',
                'examples': [
                    'https://gall.dcinside.com/mini/board/lists?id=GALLERY_ID',
                    'https://gall.dcinside.com/mgallery/board/lists/?id=GALLERY_ID',
                ],
                'description': 'Gallery posts and sentiment analysis',
            },
            {
                'name': 'Reddit',
                'id': 'reddit',
                'examples': [
                    'https://www.reddit.com/r/SUBREDDIT/',
                    'https://www.reddit.com/r/SUBREDDIT/comments/POST_ID/title/',
                ],
                'description': 'Subreddit posts and comment analysis',
            },
            {
                'name': 'Telegram',
                'id': 'telegram',
                'examples': [
                    'https://t.me/CHANNEL_NAME',
                    'https://t.me/s/CHANNEL_NAME',
                ],
                'description': 'Public channel messages',
            },
            {
                'name': 'Kakao',
                'id': 'kakao',
                'examples': [
                    'https://pf.kakao.com/PROFILE_ID',
                    'https://story.kakao.com/PROFILE_ID',
                ],
                'description': 'Kakao profile and story analysis',
            },
        ]

    # ==========================================
    # YouTube Analyzer
    # ==========================================
    def _analyze_youtube(self, url):
        """Analyze YouTube video or channel."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Extract video ID
        video_id = None
        if 'v' in params:
            video_id = params['v'][0]
        elif parsed.hostname and 'youtu.be' in parsed.hostname:
            video_id = parsed.path.strip('/')

        # Extract channel handle
        channel_handle = None
        if '/@' in url or '/@' in parsed.path:
            match = re.search(r'/@([^/?]+)', url)
            if match:
                channel_handle = f'@{match.group(1)}'

        api_key = os.environ.get('YOUTUBE_API_KEY')
        if not api_key:
            raise ValueError('YOUTUBE_API_KEY environment variable is required')

        if video_id:
            return self._analyze_youtube_video(video_id, api_key)
        elif channel_handle:
            return self._analyze_youtube_channel(channel_handle, api_key)
        else:
            raise ValueError('Could not extract video ID or channel handle from URL')

    def _analyze_youtube_video(self, video_id, api_key):
        """Fetch video info and comments."""
        base = 'https://www.googleapis.com/youtube/v3'

        # Get video details
        resp = self._session.get(f'{base}/videos', params={
            'part': 'snippet,statistics',
            'id': video_id,
            'key': api_key,
        }, timeout=10)
        resp.raise_for_status()
        items = resp.json().get('items', [])
        if not items:
            raise ValueError(f'Video not found: {video_id}')

        video = items[0]
        snippet = video['snippet']
        stats = video.get('statistics', {})

        # Get comments
        comments = []
        try:
            resp = self._session.get(f'{base}/commentThreads', params={
                'part': 'snippet',
                'videoId': video_id,
                'maxResults': 100,
                'order': 'relevance',
                'textFormat': 'plainText',
                'key': api_key,
            }, timeout=10)
            resp.raise_for_status()
            for item in resp.json().get('items', []):
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'text': comment.get('textDisplay', ''),
                    'author': comment.get('authorDisplayName', ''),
                    'like_count': comment.get('likeCount', 0),
                    'published_at': comment.get('publishedAt', ''),
                })
        except Exception as e:
            logger.warning(f'Failed to fetch comments for {video_id}: {e}')

        return {
            'type': 'video',
            'title': snippet.get('title', ''),
            'channel': snippet.get('channelTitle', ''),
            'published_at': snippet.get('publishedAt', ''),
            'view_count': int(stats.get('viewCount', 0)),
            'like_count': int(stats.get('likeCount', 0)),
            'comment_count': int(stats.get('commentCount', 0)),
            'description': snippet.get('description', '')[:500],
            'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
            'comments': comments,
        }

    def _analyze_youtube_channel(self, channel_handle, api_key):
        """Fetch channel info and recent videos."""
        base = 'https://www.googleapis.com/youtube/v3'
        handle = channel_handle.lstrip('@')

        # Get channel by handle
        resp = self._session.get(f'{base}/channels', params={
            'part': 'snippet,statistics',
            'forHandle': handle,
            'key': api_key,
        }, timeout=10)
        resp.raise_for_status()
        items = resp.json().get('items', [])
        if not items:
            raise ValueError(f'Channel not found: {channel_handle}')

        channel = items[0]
        stats = channel.get('statistics', {})

        # Get recent videos
        videos = []
        try:
            resp = self._session.get(f'{base}/search', params={
                'part': 'snippet',
                'channelId': channel['id'],
                'order': 'date',
                'maxResults': 10,
                'type': 'video',
                'key': api_key,
            }, timeout=10)
            resp.raise_for_status()
            for item in resp.json().get('items', []):
                videos.append({
                    'video_id': item['id'].get('videoId', ''),
                    'title': item['snippet'].get('title', ''),
                    'published_at': item['snippet'].get('publishedAt', ''),
                    'thumbnail': item['snippet'].get('thumbnails', {}).get('medium', {}).get('url', ''),
                })
        except Exception as e:
            logger.warning(f'Failed to fetch videos for {channel_handle}: {e}')

        return {
            'type': 'channel',
            'title': channel['snippet'].get('title', ''),
            'description': channel['snippet'].get('description', '')[:500],
            'subscriber_count': int(stats.get('subscriberCount', 0)),
            'video_count': int(stats.get('videoCount', 0)),
            'view_count': int(stats.get('viewCount', 0)),
            'thumbnail': channel['snippet'].get('thumbnails', {}).get('high', {}).get('url', ''),
            'recent_videos': videos,
        }

    # ==========================================
    # DCInside Analyzer
    # ==========================================
    def _analyze_dcinside(self, url):
        """Analyze DCInside gallery."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        gallery_id = params.get('id', [None])[0]
        if not gallery_id:
            match = re.search(r'/board/lists/?\?.*id=([^&]+)', url)
            if match:
                gallery_id = match.group(1)

        if not gallery_id:
            raise ValueError('Could not extract gallery ID from URL')

        # Determine gallery type from URL
        is_mini = '/mini/' in url
        is_mgallery = '/mgallery/' in url

        if is_mini:
            list_url = f'https://gall.dcinside.com/mini/board/lists?id={gallery_id}'
        elif is_mgallery:
            list_url = f'https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}'
        else:
            list_url = f'https://gall.dcinside.com/board/lists/?id={gallery_id}'

        posts = []
        try:
            headers = {
                'User-Agent': self._session.headers['User-Agent'],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9',
                'Referer': 'https://gall.dcinside.com/',
            }
            resp = self._session.get(list_url, headers=headers, timeout=15)
            resp.raise_for_status()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')

            rows = soup.select('tr.ub-content')
            for row in rows[:50]:
                title_el = row.select_one('.gall_tit a')
                if not title_el:
                    continue

                num_el = row.select_one('.gall_num')
                writer_el = row.select_one('.gall_writer')
                date_el = row.select_one('.gall_date')
                count_el = row.select_one('.gall_count')
                recommend_el = row.select_one('.gall_recommend')

                post_num = num_el.get_text(strip=True) if num_el else ''
                if not post_num.isdigit():
                    continue

                posts.append({
                    'text': title_el.get_text(strip=True),
                    'number': int(post_num),
                    'author': writer_el.get_text(strip=True) if writer_el else '',
                    'date': date_el.get('title', date_el.get_text(strip=True)) if date_el else '',
                    'view_count': int(count_el.get_text(strip=True)) if count_el and count_el.get_text(strip=True).isdigit() else 0,
                    'recommend': int(recommend_el.get_text(strip=True)) if recommend_el and recommend_el.get_text(strip=True).lstrip('-').isdigit() else 0,
                })
        except ImportError:
            logger.warning('beautifulsoup4 not installed, using basic scraping')
        except Exception as e:
            logger.warning(f'DCInside scraping failed: {e}')

        return {
            'type': 'gallery',
            'gallery_id': gallery_id,
            'gallery_type': 'mini' if is_mini else ('mgallery' if is_mgallery else 'major'),
            'total_posts': len(posts),
            'posts': posts,
        }

    # ==========================================
    # Reddit Analyzer
    # ==========================================
    def _analyze_reddit(self, url):
        """Analyze Reddit subreddit or post."""
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')

        # Check if it's a specific post
        post_match = re.search(r'/r/([^/]+)/comments/([^/]+)', path)
        subreddit_match = re.search(r'/r/([^/]+)/?$', path)

        headers = {
            'User-Agent': 'SNSMonitor/1.0 (content analysis tool)',
        }

        if post_match:
            subreddit = post_match.group(1)
            post_id = post_match.group(2)
            return self._analyze_reddit_post(subreddit, post_id, headers)
        elif subreddit_match:
            subreddit = subreddit_match.group(1)
            return self._analyze_reddit_subreddit(subreddit, headers)
        else:
            raise ValueError('Could not extract subreddit or post from URL')

    def _analyze_reddit_subreddit(self, subreddit, headers):
        """Fetch subreddit posts."""
        resp = self._session.get(
            f'https://www.reddit.com/r/{subreddit}/hot.json',
            params={'limit': 50},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get('data', {})

        posts = []
        for child in data.get('children', []):
            post = child.get('data', {})
            if post.get('stickied'):
                continue
            posts.append({
                'text': post.get('title', ''),
                'author': post.get('author', '[deleted]'),
                'score': post.get('score', 0),
                'num_comments': post.get('num_comments', 0),
                'created_utc': post.get('created_utc', 0),
                'url': post.get('url', ''),
                'selftext': (post.get('selftext', '') or '')[:300],
                'permalink': f"https://reddit.com{post.get('permalink', '')}",
            })

        # Get subreddit info
        about_resp = self._session.get(
            f'https://www.reddit.com/r/{subreddit}/about.json',
            headers=headers,
            timeout=10,
        )
        about = {}
        if about_resp.ok:
            about = about_resp.json().get('data', {})

        return {
            'type': 'subreddit',
            'subreddit': subreddit,
            'subscribers': about.get('subscribers', 0),
            'active_users': about.get('accounts_active', 0),
            'description': (about.get('public_description', '') or '')[:500],
            'total_posts': len(posts),
            'posts': posts,
        }

    def _analyze_reddit_post(self, subreddit, post_id, headers):
        """Fetch a specific Reddit post with comments."""
        resp = self._session.get(
            f'https://www.reddit.com/r/{subreddit}/comments/{post_id}.json',
            params={'limit': 100},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data or len(data) < 2:
            raise ValueError('Reddit post not found')

        post_data = data[0]['data']['children'][0]['data']
        comments_data = data[1]['data']['children']

        comments = []
        for child in comments_data:
            if child.get('kind') != 't1':
                continue
            comment = child.get('data', {})
            comments.append({
                'text': comment.get('body', ''),
                'author': comment.get('author', '[deleted]'),
                'score': comment.get('score', 0),
                'created_utc': comment.get('created_utc', 0),
            })

        return {
            'type': 'post',
            'subreddit': subreddit,
            'title': post_data.get('title', ''),
            'author': post_data.get('author', '[deleted]'),
            'score': post_data.get('score', 0),
            'upvote_ratio': post_data.get('upvote_ratio', 0),
            'num_comments': post_data.get('num_comments', 0),
            'selftext': (post_data.get('selftext', '') or '')[:1000],
            'created_utc': post_data.get('created_utc', 0),
            'comments': comments,
        }

    # ==========================================
    # Telegram Analyzer
    # ==========================================
    def _analyze_telegram(self, url):
        """Analyze public Telegram channel."""
        match = re.search(r't\.me/(?:s/)?([^/?]+)', url)
        if not match:
            raise ValueError('Could not extract Telegram channel name from URL')

        channel_name = match.group(1)
        preview_url = f'https://t.me/s/{channel_name}'

        resp = self._session.get(preview_url, timeout=15)
        resp.raise_for_status()

        messages = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Channel info
            title_el = soup.select_one('.tgme_channel_info_header_title')
            desc_el = soup.select_one('.tgme_channel_info_description')
            counter_el = soup.select_one('.tgme_channel_info_counter .counter_value')

            channel_title = title_el.get_text(strip=True) if title_el else channel_name
            channel_desc = desc_el.get_text(strip=True) if desc_el else ''
            subscriber_count = counter_el.get_text(strip=True) if counter_el else '0'

            # Messages
            for msg_el in soup.select('.tgme_widget_message_wrap'):
                text_el = msg_el.select_one('.tgme_widget_message_text')
                date_el = msg_el.select_one('.tgme_widget_message_date time')
                views_el = msg_el.select_one('.tgme_widget_message_views')

                if text_el:
                    messages.append({
                        'text': text_el.get_text(strip=True)[:500],
                        'date': date_el.get('datetime', '') if date_el else '',
                        'views': views_el.get_text(strip=True) if views_el else '0',
                    })
        except ImportError:
            logger.warning('beautifulsoup4 not installed')
            channel_title = channel_name
            channel_desc = ''
            subscriber_count = '0'

        return {
            'type': 'channel',
            'channel_name': channel_name,
            'title': channel_title,
            'description': channel_desc,
            'subscriber_count': subscriber_count,
            'total_messages': len(messages),
            'posts': messages,
        }

    # ==========================================
    # Kakao Analyzer
    # ==========================================
    def _analyze_kakao(self, url):
        """Analyze Kakao profile or story."""
        parsed = urlparse(url)

        if 'pf.kakao.com' in parsed.hostname:
            return self._analyze_kakao_profile(url, parsed)
        elif 'story.kakao.com' in parsed.hostname:
            return self._analyze_kakao_story(url, parsed)
        elif 'open.kakao.com' in parsed.hostname:
            return self._analyze_kakao_openchat(url, parsed)
        else:
            raise ValueError('Unsupported Kakao URL type')

    def _analyze_kakao_profile(self, url, parsed):
        """Analyze Kakao PlusFriend profile page."""
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()

        profile_info = {'type': 'kakao_profile', 'url': url}
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')

            title_el = soup.select_one('title')
            meta_desc = soup.select_one('meta[name="description"]') or soup.select_one('meta[property="og:description"]')

            profile_info['title'] = title_el.get_text(strip=True) if title_el else ''
            profile_info['description'] = meta_desc.get('content', '') if meta_desc else ''
        except ImportError:
            pass

        return profile_info

    def _analyze_kakao_story(self, url, parsed):
        """Analyze Kakao Story profile."""
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()

        story_info = {'type': 'kakao_story', 'url': url}
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')

            title_el = soup.select_one('title')
            meta_desc = soup.select_one('meta[property="og:description"]')

            story_info['title'] = title_el.get_text(strip=True) if title_el else ''
            story_info['description'] = meta_desc.get('content', '') if meta_desc else ''
        except ImportError:
            pass

        return story_info

    def _analyze_kakao_openchat(self, url, parsed):
        """Analyze Kakao OpenChat room info."""
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()

        chat_info = {'type': 'kakao_openchat', 'url': url}
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')

            title_el = soup.select_one('title')
            meta_desc = soup.select_one('meta[property="og:description"]')
            meta_image = soup.select_one('meta[property="og:image"]')

            chat_info['title'] = title_el.get_text(strip=True) if title_el else ''
            chat_info['description'] = meta_desc.get('content', '') if meta_desc else ''
            chat_info['thumbnail'] = meta_image.get('content', '') if meta_image else ''
        except ImportError:
            pass

        return chat_info

    # ==========================================
    # Sentiment Analysis
    # ==========================================
    def _analyze_sentiment(self, items):
        """Analyze sentiment distribution from text items."""
        if not items:
            return {'total': 0, 'sentiment': {'positive': 0, 'neutral': 0, 'negative': 0}}

        positive_kw = [
            '좋아', '굿', '최고', '감사', '사랑', '축하', '대박', '멋지', '예쁘', '귀엽',
            '화이팅', '응원', '레전드', '갓', 'good', 'great', 'love', 'amazing', 'awesome',
            'best', 'nice', 'cool', 'beautiful', 'wonderful', 'excellent', 'perfect',
        ]
        negative_kw = [
            '싫어', '나쁘', '최악', '짜증', '실망', '별로', '노잼', '재미없',
            '쓰레기', '망했', 'bad', 'worst', 'hate', 'terrible', 'awful', 'boring',
            'ugly', 'trash', 'waste', 'stupid', 'sucks',
        ]

        sentiment_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
        keywords = Counter()

        for item in items:
            text = (item.get('text', '') or '').lower()
            if not text:
                continue

            has_pos = any(kw in text for kw in positive_kw)
            has_neg = any(kw in text for kw in negative_kw)

            if has_pos and not has_neg:
                sentiment_counts['positive'] += 1
            elif has_neg and not has_pos:
                sentiment_counts['negative'] += 1
            else:
                sentiment_counts['neutral'] += 1

            # Extract keywords (simple word frequency)
            words = re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', text)
            keywords.update(words)

        total = sum(sentiment_counts.values())
        distribution = {k: round(v / total, 3) if total > 0 else 0 for k, v in sentiment_counts.items()}

        return {
            'total': total,
            'sentiment': sentiment_counts,
            'distribution': distribution,
            'top_keywords': [{'word': w, 'count': c} for w, c in keywords.most_common(20)],
            'overall': max(sentiment_counts, key=sentiment_counts.get) if total > 0 else 'neutral',
        }

    # ==========================================
    # Save Results
    # ==========================================
    def _save_result(self, platform, url, result):
        """Save analysis result to local data directory."""
        try:
            save_dir = os.path.join(self.data_dir, 'analysis', platform)
            os.makedirs(save_dir, exist_ok=True)

            timestamp = datetime.now(KST).strftime('%Y-%m-%d-%H-%M-%S')
            # Create safe filename from URL
            safe_name = re.sub(r'[^\w\-.]', '_', urlparse(url).path.strip('/'))[:50]
            filename = f'{safe_name}_{timestamp}.json'

            filepath = os.path.join(save_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f'Saved analysis result: {filepath}')
        except Exception as e:
            logger.warning(f'Failed to save result: {e}')
