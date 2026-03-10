#!/usr/bin/env python3
"""
Update all members JSON files (AkaiV Studio, SKOSHISM, BARABARA, PSY_CHORD) with latest YouTube channel data.
This script is designed to run after the YouTube crawler cronjob completes.
"""
import json
import os
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', '/app/local-data')

# AkaiV Studio members mapping
AKAIV_MEMBERS = {
    'u32 (우사미)': {
        'handles': ['@u32S2', '@yell_u32'],
        'youtube_channel': '@u32S2'
    },
    '여르미 (Yeorumi)': {
        'handles': ['@Yeorumi', '@yeorumi'],
        'youtube_channel': '@Yeorumi'
    },
    '한결 (Hangyeol)': {
        'handles': ['@hangyeol8008', '@hangyeol'],
        'youtube_channel': '@hangyeol8008',
        'channel_id': 'UCluZa5CRH783-eU22_N7f7w'  # 한결 채널 ID
    },
    '비몽 (Beemong)': {
        'handles': ['@beemong_', '@bee_mong', '@beemong'],
        'youtube_channel': '@beemong_',
        'channel_id': 'UCO11lxcm_-212ciYIGXZRgw'  # 비몽 채널 ID
    },
    '샤르망 (Charmante)': {
        'handles': ['@owo_zzzz'],
        'youtube_channel': '@owo_zzzz',
        'channel_id': 'UC3JYpe9DEFydDKtLpsHGbxA',  # 샤르망 채널 ID
        'channel_name': '샤르망'  # 샤르망 디렉토리로 매칭
    }
}

# SKOSHISM members mapping
SKOSHISM_MEMBERS = {
    '이로 클라우드': {
        'handles': ['@irocloud_', '@IroCloud'],
        'youtube_channel': '@irocloud_'
    },
    '니노 선데이': {
        'handles': ['@NIN0SUNDAY'],
        'youtube_channel': '@NIN0SUNDAY'
    },
    '코요 템페스트': {
        'handles': ['@KoyoTempest'],
        'youtube_channel': '@KoyoTempest'
    },
    '오토 레이니': {
        'handles': ['@otorainy'],
        'youtube_channel': '@otorainy'
    },
    '로보 프로스터': {
        'handles': ['@RoboFroster'],
        'youtube_channel': '@RoboFroster'
    }
}

# BARABARA members mapping
BARABARA_MEMBERS = {
    'BARABARA': {
        'handles': ['@BARABARA_KR'],
        'youtube_channel': '@BARABARA_KR'
    },
    '아오세이 준': {
        'handles': ['@aoseijun'],
        'youtube_channel': '@aoseijun'
    },
    '아카즈네 카츠키': {
        'handles': ['@AkazuneKatsuki'],
        'youtube_channel': '@AkazuneKatsuki'
    },
    '시로네 하루': {
        'handles': ['@Shironeharu'],
        'youtube_channel': '@Shironeharu'
    },
    '네루 쿠로밍': {
        'handles': ['@NeruKuroming'],
        'youtube_channel': '@NeruKuroming'
    },
    '시니초코 레이토': {
        'handles': ['@sinichocoreito'],
        'youtube_channel': '@sinichocoreito'
    },
    '미즈히로 슈우': {
        'handles': ['@mizuiroSyu'],
        'youtube_channel': '@mizuiroSyu'
    }
}

# PSY_CHORD members mapping
PSY_CHORD_MEMBERS = {
    '루이쨘': {
        'handles': ['@louiszzan'],
        'youtube_channel': '@louiszzan'
    },
    '감제이': {
        'handles': ['@9jayaj9'],
        'youtube_channel': '@9jayaj9'
    },
    '연이': {
        'handles': ['@yeon2vt'],
        'youtube_channel': '@yeon2vt'
    },
    '하루토': {
        'handles': ['@psy_haruto'],
        'youtube_channel': '@psy_haruto'
    },
    '늦잠': {
        'handles': ['@oversleepZzz'],
        'youtube_channel': '@oversleepZzz'
    }
}


def find_channel_data(channel_handles, channel_name=None, channel_id=None):
    """Find the latest data file for given channel handles - optimized version"""
    youtube_dir = os.path.join(LOCAL_DATA_DIR, 'youtube', 'channels')
    latest_data = None
    latest_mtime = 0

    if not os.path.exists(youtube_dir):
        print(f"YouTube directory not found: {youtube_dir}")
        return None

    # Strategy 1: Look directly in channel name directories (fast path)
    search_dirs = []
    if channel_name:
        search_dirs.append(os.path.join(youtube_dir, channel_name))
    # Special handling: 샤르망은 샤르망 디렉토리에서 찾기
    if channel_id == 'UC3JYpe9DEFydDKtLpsHGbxA':  # 샤르망 채널 ID
        search_dirs.append(os.path.join(youtube_dir, '샤르망'))
    # Also search by common variations
    for handle in channel_handles:
        clean_handle = handle.lstrip('@')
        search_dirs.append(os.path.join(youtube_dir, clean_handle))

    # Strategy 2: List directories and find matching channel titles
    try:
        for dirname in os.listdir(youtube_dir):
            dir_path = os.path.join(youtube_dir, dirname)
            if os.path.isdir(dir_path) and dirname != 'channels':
                # Check if any handle appears in directory name
                dirname_lower = dirname.lower()
                for handle in channel_handles:
                    clean_handle = handle.lstrip('@').lower()
                    if clean_handle in dirname_lower or dirname_lower in dirname_lower:
                        search_dirs.append(dir_path)
                        break
                # Also check exact channel name match
                if channel_name and channel_name.lower() in dirname_lower:
                    search_dirs.append(dir_path)
                # Special handling for @owo_zzzz -> 샤르망 (샤르망 디렉토리)
                if '@owo_zzzz' in channel_handles and ('샤르망' in dirname or 'charmante' in dirname_lower):
                    search_dirs.append(dir_path)
                # 비몽 = 왕갈비몽: 비몽 디렉토리 사용
                if '@beemong_' in channel_handles and ('비몽' in dirname or 'beemong' in dirname_lower):
                    search_dirs.append(dir_path)
    except Exception as e:
        logger.warning(f"Error listing YouTube directory {youtube_dir}: {e}", exc_info=True)

    # Remove duplicates
    search_dirs = list(set(search_dirs))

    # Strategy 3: If channel_id is provided, search all directories for matching channel ID
    if channel_id:
        try:
            for dirname in os.listdir(youtube_dir):
                dir_path = os.path.join(youtube_dir, dirname)
                if os.path.isdir(dir_path) and dirname != 'channels':
                    search_dirs.append(dir_path)
        except Exception as e:
            logger.warning(f"Error listing YouTube directory for channel_id search: {e}", exc_info=True)
        search_dirs = list(set(search_dirs))

    # Search only in targeted directories
    for dir_path in search_dirs:
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            continue

        try:
            files = os.listdir(dir_path)
            json_files = [f for f in files if f.endswith('.json')]
            # Sort by modification time (newest first)
            json_files.sort(key=lambda f: os.path.getmtime(os.path.join(dir_path, f)), reverse=True)

            # Only check the newest file per directory
            for filename in json_files[:1]:
                filepath = os.path.join(dir_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        data_handle = data.get('channel_handle', '')
                        data_channel_id = data.get('channel_id', '')
                        # Check if this channel matches any of our handles or channel ID
                        handle_match = False
                        # Priority 1: Check handle match first (for 비몽, handle matching is more reliable)
                        if data_handle in channel_handles or data_handle.lower() in [h.lower() for h in channel_handles]:
                            # Also check if handle variations match (e.g., @beemong vs @beemong_)
                            handle_variations_match = False
                            for handle in channel_handles:
                                clean_data_handle = data_handle.lower().replace('_', '')
                                clean_handle = handle.lower().replace('_', '')
                                if clean_data_handle == clean_handle:
                                    handle_variations_match = True
                                    break
                            if handle_variations_match:
                                handle_match = True
                        # Priority 2: Check channel ID match (for 샤르망/왕갈비몽)
                        elif channel_id and data_channel_id == channel_id:
                            handle_match = True
                        # Also check if directory name matches channel name (for cases like "한결", "비몽 Beemong", "왕갈비몽")
                        elif channel_name:
                            dirname_lower = os.path.basename(dir_path).lower()
                            channel_name_lower = channel_name.lower()
                            # Check if channel name appears in directory name or vice versa
                            if channel_name_lower in dirname_lower or dirname_lower in channel_name_lower:
                                # Additional check: make sure the handle is related
                                for handle in channel_handles:
                                    clean_handle = handle.lstrip('@').lower()
                                    if clean_handle in dirname_lower:
                                        handle_match = True
                                        break
                                # Special cases: 한결, 비몽, 샤르망
                                if ('한결' in dirname_lower or 'hangyeol' in dirname_lower) and '@hangyeol8008' in channel_handles:
                                    handle_match = True
                                elif ('비몽' in dirname_lower or 'beemong' in dirname_lower) and '@beemong_' in channel_handles:
                                    handle_match = True
                                elif ('샤르망' in dirname_lower or 'charmante' in dirname_lower) and '@owo_zzzz' in channel_handles:
                                    handle_match = True
                        
                        if handle_match:
                            file_mtime = os.path.getmtime(filepath)
                            if file_mtime > latest_mtime:
                                latest_mtime = file_mtime
                                latest_data = data
                                print(f"Found channel data: {os.path.basename(dir_path)} -> {data_handle} (channel_id: {data_channel_id}, total_comments: {data.get('total_comments', 0)})")
                except Exception as e:
                    logger.warning(f"Error reading {filepath}: {e}", exc_info=True)
        except Exception as e:
            logger.warning(f"Error listing directory {dir_path}: {e}", exc_info=True)

    return latest_data


def extract_comments_from_channel(channel_data, max_comments=50):
    """Extract comment samples from YouTube channel data"""
    comments = []
    videos = channel_data.get('videos', [])

    for video_info in videos:
        # Handle both direct video data and nested video structure
        if isinstance(video_info, dict):
            video_data = video_info.get('video', video_info)
            video_comments = video_info.get('comments', [])
        else:
            continue

        video_id = video_data.get('video_id', '') or video_data.get('id', '')
        video_title = video_data.get('title', '')

        for comment in video_comments:
            if len(comments) >= max_comments:
                break

            comments.append({
                'text': comment.get('text', ''),
                'author': comment.get('author', ''),
                'likes': comment.get('like_count', 0),
                'video_title': video_title,
                'video_id': video_id,
                'video_url': f"https://www.youtube.com/watch?v={video_id}" if video_id else '',
                'published_at': comment.get('published_at', '')
            })

        if len(comments) >= max_comments:
            break

    return comments


def update_group_json(group_name, members_mapping, output_filename):
    """Update JSON file for a specific group"""
    output_path = os.path.join(LOCAL_DATA_DIR, 'vuddy', 'comprehensive_analysis', output_filename)

    creators = []
    total_updated = 0

    for name, config in members_mapping.items():
        handles = config['handles']
        youtube_channel = config['youtube_channel']
        channel_id = config.get('channel_id')  # Optional channel ID for precise matching

        # Find channel data (pass name and channel_id for optimized directory lookup)
        # For 샤르망, use '샤르망' as channel_name to search in 샤르망 directory
        config_channel_name = config.get('channel_name')
        search_name = config_channel_name if config_channel_name else name
        channel_data = find_channel_data(handles, search_name, channel_id)

        if channel_data:
            # Extract comments
            comments = extract_comments_from_channel(channel_data, max_comments=50)
            # Try both 'videos' and 'video_data' keys
            videos = channel_data.get('videos', []) or channel_data.get('video_data', [])
            total_comments = channel_data.get('total_comments', 0) or sum(len(v.get('comments', [])) for v in videos)
            total_videos_analyzed = channel_data.get('total_videos_analyzed', 0) or len(videos)

            creator_info = {
                'name': name,
                'channel_title': channel_data.get('channel_title', name),
                'channel_handle': youtube_channel,
                'total_comments': total_comments,
                'total_videos': total_videos_analyzed,
                'comment_samples': comments,
                'profile_image': channel_data.get('channel_thumbnail', ''),
                'subscriber_count': channel_data.get('channel_stats', {}).get('subscriber_count', 0) or channel_data.get('statistics', {}).get('subscriberCount', 0)
            }

            creators.append(creator_info)
            total_updated += 1
            print(f"  {name}: {len(comments)} comments from {len(channel_data.get('videos', []))} videos")
        else:
            # Create empty placeholder
            creator_info = {
                'name': name,
                'channel_title': name,
                'channel_handle': youtube_channel,
                'total_comments': 0,
                'total_videos': 0,
                'comment_samples': [],
                'profile_image': '',
                'subscriber_count': 0
            }
            creators.append(creator_info)
            print(f"  {name}: No data found")

    # Build output data
    output_data = {
        'group': group_name,
        'updated_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'creators': creators,
        'total_creators': len(creators)
    }

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"  Saved: {output_path}")
    print(f"  Total updated: {total_updated}/{len(members_mapping)}")

    return total_updated


def main():
    print(f"=" * 60)
    print(f"Members JSON Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"=" * 60)
    print(f"LOCAL_DATA_DIR: {LOCAL_DATA_DIR}")
    print()

    # Update AkaiV Studio
    print("Updating AkaiV Studio members...")
    akaiv_updated = update_group_json('AkaiV Studio', AKAIV_MEMBERS, 'akaiv-studio-members.json')
    print()

    # Update SKOSHISM
    print("Updating SKOSHISM members...")
    skoshism_updated = update_group_json('SKOSHISM', SKOSHISM_MEMBERS, 'skoshism-members.json')
    print()

    # Update BARABARA
    print("Updating BARABARA members...")
    barabara_updated = update_group_json('BARABARA', BARABARA_MEMBERS, 'barabara-members.json')
    print()

    # Update PSY_CHORD
    print("Updating PSY_CHORD members...")
    psy_chord_updated = update_group_json('PSY_CHORD', PSY_CHORD_MEMBERS, 'psy-chord-members.json')
    print()

    print(f"=" * 60)
    print(f"Summary:")
    print(f"  AkaiV Studio: {akaiv_updated}/{len(AKAIV_MEMBERS)} updated")
    print(f"  SKOSHISM: {skoshism_updated}/{len(SKOSHISM_MEMBERS)} updated")
    print(f"  BARABARA: {barabara_updated}/{len(BARABARA_MEMBERS)} updated")
    print(f"  PSY_CHORD: {psy_chord_updated}/{len(PSY_CHORD_MEMBERS)} updated")
    print(f"=" * 60)


if __name__ == '__main__':
    main()
