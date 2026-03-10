#!/usr/bin/env python3
"""
로컬 테스트 스크립트
로컬 모드로 크롤러를 실행하여 테스트합니다.
"""

import os
import sys
import json
import requests
from pathlib import Path

# 프로젝트 루트 디렉토리 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 로컬 모드 활성화
os.environ['LOCAL_MODE'] = 'true'
os.environ['LOCAL_DATA_DIR'] = './local-data'

def test_youtube_crawler():
    """YouTube 크롤러 로컬 테스트"""
    print("=" * 60)
    print("YouTube 크롤러 로컬 테스트")
    print("=" * 60)
    
    # YouTube API 키 확인
    youtube_api_key = os.environ.get('YOUTUBE_API_KEY')
    if not youtube_api_key:
        print("⚠️  YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일에 YOUTUBE_API_KEY를 설정하거나 환경 변수로 설정하세요.")
        return False
    
    # 크롤러 직접 실행
    try:
        sys.path.insert(0, str(project_root / 'lambda' / 'youtube-crawler'))
        from lambda_function import lambda_handler
        
        event = {
            'type': 'keyword',
            'keywords': ['AkaiV Studio', '아카이브스튜디오']
        }
        
        result = lambda_handler(event, None)
        print("\n✅ 크롤러 실행 완료!")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return True
    except Exception as e:
        print(f"\n❌ 크롤러 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_vuddy_crawler():
    """Vuddy 크롤러 로컬 테스트"""
    print("=" * 60)
    print("Vuddy 크롤러 로컬 테스트")
    print("=" * 60)
    
    try:
        sys.path.insert(0, str(project_root / 'lambda' / 'vuddy-crawler'))
        from lambda_function import lambda_handler
        
        event = {}
        result = lambda_handler(event, None)
        print("\n✅ 크롤러 실행 완료!")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return True
    except Exception as e:
        print(f"\n❌ 크롤러 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def list_local_data():
    """로컬에 저장된 데이터 목록 조회"""
    print("=" * 60)
    print("로컬 데이터 목록")
    print("=" * 60)
    
    local_data_dir = Path('./local-data')
    if not local_data_dir.exists():
        print("로컬 데이터 디렉토리가 없습니다.")
        return
    
    for platform_dir in local_data_dir.iterdir():
        if not platform_dir.is_dir() or platform_dir.name == 'metadata':
            continue
        
        print(f"\n📁 {platform_dir.name}/")
        for keyword_dir in platform_dir.iterdir():
            if not keyword_dir.is_dir():
                continue
            
            files = list(keyword_dir.glob('*.json'))
            if not files:
                continue
            
            print(f"  └─ {keyword_dir.name}/ ({len(files)}개 파일)")
            for file in sorted(files, reverse=True)[:3]:  # 최신 3개만 표시
                print(f"     • {file.name}")

def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='로컬 테스트 스크립트')
    parser.add_argument('--youtube', action='store_true', help='YouTube 크롤러 테스트')
    parser.add_argument('--vuddy', action='store_true', help='Vuddy 크롤러 테스트')
    parser.add_argument('--list', action='store_true', help='로컬 데이터 목록 조회')
    parser.add_argument('--all', action='store_true', help='모든 크롤러 테스트')
    
    args = parser.parse_args()
    
    if args.list:
        list_local_data()
    elif args.youtube:
        test_youtube_crawler()
    elif args.vuddy:
        test_vuddy_crawler()
    elif args.all:
        test_youtube_crawler()
        print("\n")
        test_vuddy_crawler()
        print("\n")
        list_local_data()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()

