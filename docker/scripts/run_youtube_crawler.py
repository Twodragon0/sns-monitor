#!/usr/bin/env python3
"""YouTube Crawler CLI Script for CronJob"""
import os
import json
import requests
import lambda_function


def main():
    # 환경 변수에서 설정 읽기
    api_endpoint = os.environ.get("API_ENDPOINT", "")
    channels_str = os.environ.get("CHANNELS", "")
    channels = channels_str.split(",") if channels_str else []
    max_videos = int(os.environ.get("MAX_VIDEOS", "10"))
    max_comments = int(os.environ.get("MAX_COMMENTS", "100"))

    event = {
        "type": "channel",
        "channels": channels,
        "max_videos": max_videos,
        "max_comments_per_video": max_comments
    }

    print(f"Starting YouTube crawler with channels: {channels}")
    result = lambda_function.lambda_handler(event, {})
    status_code = result.get("statusCode")
    print(f"Crawler completed: {status_code}")

    # API로 결과 전송 (옵션)
    if api_endpoint:
        try:
            body = json.loads(result.get("body", "{}"))
            response = requests.post(
                f"{api_endpoint}/api/crawler/results",
                json=body,
                timeout=30
            )
            print(f"Sent results to API: {response.status_code}")
        except Exception as e:
            print(f"Failed to send results to API: {e}")


if __name__ == "__main__":
    main()
