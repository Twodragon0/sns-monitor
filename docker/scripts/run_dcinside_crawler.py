#!/usr/bin/env python3
"""DCInside Crawler CLI Script for CronJob"""
import os
import json
import requests
import lambda_function


def main():
    # 환경 변수에서 설정 읽기
    api_endpoint = os.environ.get("API_ENDPOINT", "")
    galleries_str = os.environ.get("GALLERIES", "vtuber,virtualyoutuber")
    galleries = galleries_str.split(",") if galleries_str else []
    max_pages = int(os.environ.get("MAX_PAGES", "3"))

    event = {
        "galleries": galleries,
        "max_pages": max_pages
    }

    print(f"Starting DCInside crawler with galleries: {galleries}")
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
