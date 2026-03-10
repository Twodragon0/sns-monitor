#!/usr/bin/env python3
"""
YouTube 크롤러 실행 스크립트
"""
import json
import sys
import os
from lambda_function import lambda_handler, YOUTUBE_CHANNELS

if __name__ == "__main__":
    # 이벤트 설정
    if len(sys.argv) > 1:
        event = json.loads(sys.argv[1])
    else:
        # 환경 변수에 채널 목록이 있으면 채널 모드로 실행
        if YOUTUBE_CHANNELS:
            event = {
                "type": "channel",
                "channels": YOUTUBE_CHANNELS
            }
            print(f"Running in channel mode with {len(YOUTUBE_CHANNELS)} channels")
        else:
            # 기본 이벤트: IVNIT 키워드 검색
            event = {
                "type": "keyword",
                "keywords": ["IVNIT"]
            }
            print("Running in keyword mode (no channels found in environment)")

    # Lambda 핸들러 실행
    result = lambda_handler(event, None)

    # 결과 출력
    print(json.dumps(result, ensure_ascii=False, indent=2))
