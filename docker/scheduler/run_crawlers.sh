#!/bin/sh

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting crawl cycle..."

# 크롤러 실행 함수
run_crawler() {
    CRAWLER_NAME=$1
    ENDPOINT=$2

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running $CRAWLER_NAME crawler..."

    curl -X POST "$ENDPOINT/invoke" \
        -H "Content-Type: application/json" \
        -d "{}" \
        --max-time 300 \
        --silent \
        --show-error

    if [ $? -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $CRAWLER_NAME crawler completed"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $CRAWLER_NAME crawler failed"
    fi
}

# 트위터 키워드 모니터링 실행
run_twitter_keyword_monitoring() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running Twitter keyword monitoring..."

    curl -X POST "$TWITTER_CRAWLER_ENDPOINT/crawl" \
        -H "Content-Type: application/json" \
        -d '{"keywords": ["버디", "레벨스", "스코시즘", "아카이브", "바라바라", "이브닛", "u32", "여르미", "한결", "비몽", "샤르망", "나나문"]}' \
        --max-time 600 \
        --silent \
        --show-error

    if [ $? -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Twitter keyword monitoring completed"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Twitter keyword monitoring failed"
    fi
}

# 모든 크롤러 실행
run_crawler "YouTube" "$YOUTUBE_CRAWLER_ENDPOINT"
run_crawler "DCInside" "$DCINSIDE_CRAWLER_ENDPOINT"
run_twitter_keyword_monitoring
run_crawler "Vuddy" "$VUDDY_CRAWLER_ENDPOINT"
run_crawler "Telegram" "$TELEGRAM_CRAWLER_ENDPOINT"
run_crawler "RSS" "$RSS_CRAWLER_ENDPOINT"
run_crawler "Instagram" "$INSTAGRAM_CRAWLER_ENDPOINT"
run_crawler "Facebook" "$FACEBOOK_CRAWLER_ENDPOINT"
run_crawler "Threads" "$THREADS_CRAWLER_ENDPOINT"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Crawl cycle completed!"
