#!/usr/bin/env python3
"""
YouTube API를 사용하여 video_links의 published_at 날짜를 업데이트하는 스크립트
"""
import json
import os
import re
import requests
from datetime import datetime

# YouTube API 설정
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')

# 파일 경로
_BASE_DIR = os.environ.get('LOCAL_DATA_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'local-data'))
VUDDY_FILE = os.path.join(_BASE_DIR, 'vuddy/comprehensive_analysis/vuddy-creators.json')
AKAIV_FILE = os.path.join(_BASE_DIR, 'vuddy/comprehensive_analysis/akaiv-studio-members.json')

def extract_video_id(url):
    """YouTube URL에서 video ID 추출"""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_video_details(video_ids):
    """YouTube API로 비디오 상세 정보 가져오기"""
    if not YOUTUBE_API_KEY:
        print("⚠️  YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.")
        return {}

    if not video_ids:
        return {}

    # API는 최대 50개까지 한 번에 요청 가능
    video_details = {}

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        ids_str = ','.join(batch)

        url = f"https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'snippet',
            'id': ids_str,
            'key': YOUTUBE_API_KEY
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                for item in data.get('items', []):
                    video_id = item['id']
                    snippet = item.get('snippet', {})
                    video_details[video_id] = {
                        'published_at': snippet.get('publishedAt', ''),
                        'title': snippet.get('title', ''),
                        'channel_title': snippet.get('channelTitle', '')
                    }
            else:
                print(f"⚠️  API 오류: {response.status_code} - {response.text[:200]}")
        except Exception as e:
            print(f"⚠️  요청 오류: {e}")

    return video_details

def update_video_links_dates(creators, video_details):
    """크리에이터의 video_links에 published_at 업데이트"""
    updated_count = 0

    for creator in creators:
        name = creator.get('name', '')
        video_links = creator.get('video_links', [])

        for video in video_links:
            url = video.get('url', '')
            video_id = extract_video_id(url)

            if video_id and video_id in video_details:
                details = video_details[video_id]
                if details.get('published_at'):
                    video['published_at'] = details['published_at']
                    updated_count += 1

    return updated_count

def main():
    print("=" * 70)
    print("📅 YouTube 비디오 업로드 날짜 업데이트 스크립트")
    print("=" * 70)

    if not YOUTUBE_API_KEY:
        print("\n⚠️  YOUTUBE_API_KEY 환경 변수를 설정해주세요.")
        print("   export YOUTUBE_API_KEY='your-api-key'")
        return

    # 1. Vuddy 데이터 로드
    print("\n📂 vuddy-creators.json 로드 중...")
    with open(VUDDY_FILE, 'r', encoding='utf-8') as f:
        vuddy_data = json.load(f)

    # 2. 모든 비디오 ID 수집
    print("\n🔍 비디오 ID 수집 중...")
    all_video_ids = set()

    for creator in vuddy_data.get('creators', []):
        for video in creator.get('video_links', []):
            video_id = extract_video_id(video.get('url', ''))
            if video_id:
                all_video_ids.add(video_id)

    print(f"   총 {len(all_video_ids)}개의 고유 비디오 ID 발견")

    # 3. YouTube API로 비디오 정보 가져오기
    print("\n📡 YouTube API로 비디오 정보 조회 중...")
    video_details = get_video_details(list(all_video_ids))
    print(f"   {len(video_details)}개의 비디오 정보 조회 완료")

    # 4. vuddy-creators.json 업데이트
    print("\n✏️  vuddy-creators.json 업데이트 중...")
    updated = update_video_links_dates(vuddy_data.get('creators', []), video_details)
    print(f"   {updated}개의 비디오 날짜 업데이트됨")

    # 백업 생성
    backup_file = VUDDY_FILE + '.backup_dates'
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(vuddy_data, f, ensure_ascii=False, indent=2)
    print(f"   백업 파일: {backup_file}")

    # 저장
    with open(VUDDY_FILE, 'w', encoding='utf-8') as f:
        json.dump(vuddy_data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ vuddy-creators.json 저장 완료")

    # 5. akaiv-studio-members.json 업데이트
    print("\n✏️  akaiv-studio-members.json 업데이트 중...")
    with open(AKAIV_FILE, 'r', encoding='utf-8') as f:
        akaiv_data = json.load(f)

    updated = update_video_links_dates(akaiv_data.get('creators', []), video_details)
    print(f"   {updated}개의 비디오 날짜 업데이트됨")

    # 타임스탬프 업데이트
    akaiv_data['timestamp'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S+09:00')

    # 백업 생성
    backup_file = AKAIV_FILE + '.backup_dates'
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(akaiv_data, f, ensure_ascii=False, indent=2)
    print(f"   백업 파일: {backup_file}")

    # 저장
    with open(AKAIV_FILE, 'w', encoding='utf-8') as f:
        json.dump(akaiv_data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ akaiv-studio-members.json 저장 완료")

    # 결과 출력
    print("\n" + "=" * 70)
    print("✅ 업데이트 완료!")
    print("=" * 70)

    # 샘플 출력
    print("\n📋 샘플 데이터 확인:")
    for creator in akaiv_data.get('creators', [])[:2]:
        name = creator.get('name', '')
        videos = creator.get('video_links', [])
        print(f"\n{name}:")
        for video in videos[:2]:
            print(f"  - {video.get('title', '')[:40]}...")
            print(f"    📅 {video.get('published_at', 'N/A')}")

if __name__ == '__main__':
    main()
