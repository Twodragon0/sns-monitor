#!/bin/bash

# DC인사이드 정기 크롤링 스크립트
# 사용법: ./schedule-dcinside-crawl.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "========================================="
echo "DC인사이드 크롤링 시작: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="

# 5개 갤러리 크롤링
docker exec sns-monitor-dcinside-crawler python3 -c "
import lambda_function
import json

galleries = ['ivnit', 'akaiv', 'soopvirtualstreamer', 'spv', 'soopstreaming']
result = lambda_function.lambda_handler({'galleries': galleries}, {})
print(json.dumps(json.loads(result['body']), indent=2, ensure_ascii=False))
"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "========================================="
    echo "DC인사이드 크롤링 완료: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================="
else
    echo "========================================="
    echo "DC인사이드 크롤링 실패: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Exit code: $EXIT_CODE"
    echo "========================================="
fi

exit $EXIT_CODE
