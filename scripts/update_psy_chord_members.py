#!/usr/bin/env python3
"""
Update psy-chord-members.json with new YouTube channel data
"""
import json
import os
import glob
from datetime import datetime

LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', '/app/local-data')

# Mapping of member names to their YouTube channel handles
CHANNEL_MAPPING = {
    '루이쨘': ['@louiszzan'],
    '감제이': ['@9jayaj9'],
    '연이': ['@yeon2vt'],
    '하루토': ['@psy_haruto'],
    '늦잠': ['@oversleepZzz']
}

def find_latest_channel_data(channel_handles):
    """Find the latest data file for given channel handles"""
    youtube_dir = os.path.join(LOCAL_DATA_DIR, 'youtube', 'channels')
    latest_data = None
    latest_mtime = 0

    if not os.path.exists(youtube_dir):
        print(f"YouTube directory not found: {youtube_dir}")
        return None

    for root, dirs, files in os.walk(youtube_dir):
        for filename in files:
            if filename.endswith('.json'):
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        data_handle = data.get('channel_handle', '')
                        if data_handle in channel_handles:
                            file_mtime = os.path.getmtime(filepath)
                            if file_mtime > latest_mtime:
                                latest_mtime = file_mtime
                                latest_data = data
                                print(f"Found channel data for {data_handle} in {filepath}")
                except Exception as e:
                    print(f"Error loading {filepath}: {e}")

    return latest_data

def extract_comment_samples(channel_data, max_comments=10):
    """Extract comment samples from YouTube channel data"""
    comments = []
    videos = channel_data.get('videos', [])

    for video_info in videos:
        video_data = video_info.get('video', {})
        video_comments = video_info.get('comments', [])

        video_id = video_data.get('video_id', '') or video_data.get('id', '')
        video_title = video_data.get('title', '')

        for comment in video_comments[:5]:  # Limit comments per video
            comments.append({
                'text': comment.get('text', ''),
                'author': comment.get('author', ''),
                'like_count': comment.get('like_count', 0),
                'video_title': video_title,
                'video_id': video_id,
                'video_url': f"https://www.youtube.com/watch?v={video_id}" if video_id else '',
                'sentiment': comment.get('sentiment', 'neutral'),
                'published_at': comment.get('published_at', '')
            })

            if len(comments) >= max_comments:
                break

        if len(comments) >= max_comments:
            break

    return comments

def extract_video_links(channel_data, max_videos=10):
    """Extract video links from YouTube channel data"""
    videos = []
    channel_title = channel_data.get('channel_title', '')

    for video_info in channel_data.get('videos', [])[:max_videos]:
        video_data = video_info.get('video', {})
        video_id = video_data.get('video_id', '') or video_data.get('id', '')

        videos.append({
            'title': video_data.get('title', ''),
            'url': f"https://www.youtube.com/watch?v={video_id}" if video_id else '',
            'channel': channel_title,
            'published_at': video_data.get('published_at', '')
        })

    return videos

def update_psy_chord_members():
    """Update psy-chord-members.json with new YouTube data"""
    members_file = os.path.join(LOCAL_DATA_DIR, 'vuddy', 'comprehensive_analysis', 'psy-chord-members.json')

    # 디렉토리가 없으면 생성
    os.makedirs(os.path.dirname(members_file), exist_ok=True)

    # 기존 데이터 로드 또는 초기화
    if os.path.exists(members_file):
        with open(members_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        # 초기 데이터 구조 생성
        data = {
            'group_name': 'PSY_CHORD',
            'description': 'PSY_CHORD 소속 VTuber 크리에이터',
            'official_channel': '@psy_chord',
            'timestamp': datetime.now().isoformat(),
            'creators': [
                {
                    'name': '루이쨘',
                    'youtube_channel': '@louiszzan',
                    'total_comments': 0,
                    'total_likes': 0,
                    'comment_samples': [],
                    'video_links': [],
                    'statistics': {},
                    'country_stats': {}
                },
                {
                    'name': '감제이',
                    'youtube_channel': '@9jayaj9',
                    'total_comments': 0,
                    'total_likes': 0,
                    'comment_samples': [],
                    'video_links': [],
                    'statistics': {},
                    'country_stats': {}
                },
                {
                    'name': '연이',
                    'youtube_channel': '@yeon2vt',
                    'total_comments': 0,
                    'total_likes': 0,
                    'comment_samples': [],
                    'video_links': [],
                    'statistics': {},
                    'country_stats': {}
                },
                {
                    'name': '하루토',
                    'youtube_channel': '@psy_haruto',
                    'total_comments': 0,
                    'total_likes': 0,
                    'comment_samples': [],
                    'video_links': [],
                    'statistics': {},
                    'country_stats': {}
                },
                {
                    'name': '늦잠',
                    'youtube_channel': '@oversleepZzz',
                    'total_comments': 0,
                    'total_likes': 0,
                    'comment_samples': [],
                    'video_links': [],
                    'statistics': {},
                    'country_stats': {}
                }
            ]
        }

    # Update each creator
    updated_count = 0
    for creator in data.get('creators', []):
        name = creator.get('name', '')
        youtube_channel = creator.get('youtube_channel', '')

        # Find matching channel handles
        channel_handles = CHANNEL_MAPPING.get(name, [])
        if youtube_channel and youtube_channel not in channel_handles:
            channel_handles.append(youtube_channel)

        if not channel_handles:
            print(f"No channel mapping for {name}")
            continue

        # Find latest channel data
        channel_data = find_latest_channel_data(channel_handles)

        if channel_data:
            # Update comment samples
            new_comments = extract_comment_samples(channel_data)
            if new_comments:
                creator['comment_samples'] = new_comments
                creator['total_comments'] = channel_data.get('total_comments', len(new_comments))
                print(f"Updated {name}: {len(new_comments)} comment samples")

            # Update video links
            new_videos = extract_video_links(channel_data)
            if new_videos:
                creator['video_links'] = new_videos

            # Update country stats if available
            if 'country_stats' in channel_data:
                creator['country_stats'] = channel_data['country_stats']

            # Update statistics
            if 'channel_stats' in channel_data:
                creator['statistics'] = channel_data['channel_stats']

            updated_count += 1
        else:
            print(f"No channel data found for {name}")

    # Update timestamp
    data['timestamp'] = datetime.now().isoformat()

    # Save updated data
    with open(members_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nUpdated {updated_count} creators")
    print(f"Saved to {members_file}")
    print(f"New timestamp: {data['timestamp']}")

    return True

if __name__ == '__main__':
    update_psy_chord_members()
