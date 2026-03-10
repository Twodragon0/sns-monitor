#!/bin/bash
# LocalStack S3 버킷 초기화 스크립트

set -e

echo "=========================================="
echo "LocalStack S3 버킷 초기화"
echo "=========================================="

LOCALSTACK_ENDPOINT="${LOCALSTACK_ENDPOINT:-http://localstack:4566}"
BUCKET_NAME="${S3_BUCKET:-sns-monitor-data}"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-2}"

echo "LocalStack Endpoint: $LOCALSTACK_ENDPOINT"
echo "Bucket Name: $BUCKET_NAME"
echo "Region: $REGION"

# LocalStack이 준비될 때까지 대기
echo "LocalStack 연결 대기 중..."
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if curl -s "$LOCALSTACK_ENDPOINT/health" | grep -q "\"s3\": \"available\""; then
        echo "✓ LocalStack 연결 성공!"
        break
    fi
    retry_count=$((retry_count + 1))
    echo "  재시도 $retry_count/$max_retries..."
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "✗ LocalStack 연결 실패!"
    exit 1
fi

# S3 버킷 생성
echo ""
echo "S3 버킷 생성 중: $BUCKET_NAME"

# 버킷이 이미 존재하는지 확인
if aws s3 ls "s3://$BUCKET_NAME" --endpoint-url "$LOCALSTACK_ENDPOINT" 2>/dev/null; then
    echo "✓ 버킷 '$BUCKET_NAME' 이미 존재합니다."
else
    # 버킷 생성
    aws s3 mb "s3://$BUCKET_NAME" \
        --endpoint-url "$LOCALSTACK_ENDPOINT" \
        --region "$REGION" || {
        echo "✗ 버킷 생성 실패!"
        exit 1
    }
    echo "✓ 버킷 '$BUCKET_NAME' 생성 완료!"
fi

# 버킷 목록 확인
echo ""
echo "생성된 버킷 목록:"
aws s3 ls --endpoint-url "$LOCALSTACK_ENDPOINT"

echo ""
echo "=========================================="
echo "✓ LocalStack 초기화 완료!"
echo "=========================================="

