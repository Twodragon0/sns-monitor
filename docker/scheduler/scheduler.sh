#!/bin/sh

echo "========================================"
echo "Starting SNS Monitor Scheduler..."
echo "========================================"

# 환경변수 출력
echo "YOUTUBE_CRAWLER_ENDPOINT: $YOUTUBE_CRAWLER_ENDPOINT"
echo "DCINSIDE_CRAWLER_ENDPOINT: $DCINSIDE_CRAWLER_ENDPOINT"

# 크롤링 간격 설정 (기본값: 7200초 = 2시간)
INTERVAL_SECONDS="${CRAWL_INTERVAL_SECONDS:-7200}"
echo "CRAWL_INTERVAL_SECONDS: $INTERVAL_SECONDS seconds ($(($INTERVAL_SECONDS / 3600)) hours)"

# 로그 파일 생성
touch /var/log/scheduler.log

# 초기 실행
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running initial crawl..."
/bin/sh /app/run_crawlers.sh 2>&1 | tee -a /var/log/scheduler.log

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Initial crawl completed. Starting scheduler loop..."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Next crawl in $INTERVAL_SECONDS seconds ($(($INTERVAL_SECONDS / 3600)) hours)"

# 무한 루프로 스케줄 실행
while true; do
    sleep $INTERVAL_SECONDS

    echo "" >> /var/log/scheduler.log
    echo "========================================" >> /var/log/scheduler.log
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Scheduled crawl starting..." | tee -a /var/log/scheduler.log

    /bin/sh /app/run_crawlers.sh 2>&1 | tee -a /var/log/scheduler.log

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Crawl completed. Next crawl in $INTERVAL_SECONDS seconds" | tee -a /var/log/scheduler.log
done
