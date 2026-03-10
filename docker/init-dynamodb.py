#!/usr/bin/env python3
"""
DynamoDB Local 테이블 초기화 스크립트
"""

import boto3
import time
import sys
import os

# DynamoDB Local 연결
dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url=os.environ.get('DYNAMODB_ENDPOINT', 'http://dynamodb-local:8000'),
    region_name='ap-northeast-2',
    aws_access_key_id='test',
    aws_secret_access_key='test'
)

def create_table_if_not_exists(table_name, key_schema, attribute_definitions, **kwargs):
    """테이블이 없으면 생성"""
    try:
        # 기존 테이블 확인
        table = dynamodb.Table(table_name)
        table.load()
        print(f"✓ 테이블 '{table_name}' 이미 존재합니다.")
        return table
    except:
        # 테이블 생성
        print(f"→ 테이블 '{table_name}' 생성 중...")
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=key_schema,
            AttributeDefinitions=attribute_definitions,
            BillingMode='PAY_PER_REQUEST',
            **kwargs
        )
        # 테이블 활성화 대기
        table.wait_until_exists()
        print(f"✓ 테이블 '{table_name}' 생성 완료!")
        return table

def init_tables():
    """모든 필요한 테이블 생성"""

    print("=" * 60)
    print("DynamoDB Local 테이블 초기화")
    print("=" * 60)

    # 1. SNS 모니터링 결과 테이블
    create_table_if_not_exists(
        table_name='sns-monitor-results',
        key_schema=[
            {'AttributeName': 'id', 'KeyType': 'HASH'},  # Partition key
            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}  # Sort key
        ],
        attribute_definitions=[
            {'AttributeName': 'id', 'AttributeType': 'S'},
            {'AttributeName': 'timestamp', 'AttributeType': 'S'},
            {'AttributeName': 'source', 'AttributeType': 'S'},
            {'AttributeName': 'severity', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'source-timestamp-index',
                'KeySchema': [
                    {'AttributeName': 'source', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            },
            {
                'IndexName': 'severity-timestamp-index',
                'KeySchema': [
                    {'AttributeName': 'severity', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }
        ]
    )

    # 2. 인증 테이블 (OAuth 토큰 저장)
    create_table_if_not_exists(
        table_name='sns-monitor-auth',
        key_schema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'}  # Partition key
        ],
        attribute_definitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'provider', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'provider-index',
                'KeySchema': [
                    {'AttributeName': 'provider', 'KeyType': 'HASH'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }
        ]
    )

    # 3. OAuth State 테이블 (PKCE 세션 관리)
    create_table_if_not_exists(
        table_name='sns-monitor-oauth-sessions',
        key_schema=[
            {'AttributeName': 'state', 'KeyType': 'HASH'}  # Partition key
        ],
        attribute_definitions=[
            {'AttributeName': 'state', 'AttributeType': 'S'}
        ]
    )

    print("\n" + "=" * 60)
    print("✓ 모든 테이블 초기화 완료!")
    print("=" * 60)

    # 테이블 목록 출력
    print("\n생성된 테이블:")
    for table_name in dynamodb.meta.client.list_tables()['TableNames']:
        table = dynamodb.Table(table_name)
        print(f"  - {table_name} (상태: {table.table_status})")

def wait_for_dynamodb():
    """DynamoDB Local이 준비될 때까지 대기"""
    print("DynamoDB Local 연결 대기 중...")
    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        try:
            dynamodb.meta.client.list_tables()
            print("✓ DynamoDB Local 연결 성공!")
            return True
        except Exception as e:
            retry_count += 1
            print(f"  재시도 {retry_count}/{max_retries}... ({e})")
            time.sleep(2)

    print("✗ DynamoDB Local 연결 실패!")
    return False

if __name__ == '__main__':
    # DynamoDB Local 연결 대기
    if not wait_for_dynamodb():
        sys.exit(1)

    # 테이블 초기화
    init_tables()
