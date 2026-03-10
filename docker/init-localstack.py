#!/usr/bin/env python3
"""
LocalStack S3 버킷 초기화 스크립트

보안 및 효율성 개선:
- 환경 변수 검증 및 입력값 검증
- 구조화된 로깅 (민감 정보 마스킹)
- 지수 백오프 전략으로 재시도 최적화
- 구체적인 예외 처리 및 타입 힌트
- S3 버킷 이름 규칙 준수 검증
"""

import boto3
import logging
import re
import sys
import os
import time
from typing import Optional, Tuple
from botocore.exceptions import ClientError, BotoCoreError

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 환경 변수 설정 및 검증
LOCALSTACK_ENDPOINT = os.environ.get('LOCALSTACK_ENDPOINT', 'http://localstack:4566')
BUCKET_NAME = os.environ.get('S3_BUCKET', 'sns-monitor-data')
REGION = os.environ.get('AWS_DEFAULT_REGION', 'ap-northeast-2')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', 'test')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', 'test')

# 재시도 설정
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '30'))
INITIAL_RETRY_DELAY = float(os.environ.get('INITIAL_RETRY_DELAY', '1.0'))
MAX_RETRY_DELAY = float(os.environ.get('MAX_RETRY_DELAY', '10.0'))
RETRY_BACKOFF_MULTIPLIER = float(os.environ.get('RETRY_BACKOFF_MULTIPLIER', '1.5'))


def validate_bucket_name(bucket_name: str) -> bool:
    """
    S3 버킷 이름 규칙 검증
    
    AWS S3 버킷 이름 규칙:
    - 3-63자 사이
    - 소문자, 숫자, 하이픈(-), 마침표(.)만 허용
    - 하이픈으로 시작하거나 끝날 수 없음
    - IP 주소 형식이면 안됨
    
    Args:
        bucket_name: 검증할 버킷 이름
        
    Returns:
        유효하면 True, 그렇지 않으면 False
    """
    if not bucket_name:
        return False
    
    # 길이 검증
    if len(bucket_name) < 3 or len(bucket_name) > 63:
        logger.error(f"버킷 이름 길이 오류: {len(bucket_name)}자 (3-63자 필요)")
        return False
    
    # 문자 검증: 소문자, 숫자, 하이픈, 마침표만 허용
    if not re.match(r'^[a-z0-9.-]+$', bucket_name):
        logger.error(f"버킷 이름 문자 오류: 소문자, 숫자, 하이픈(-), 마침표(.)만 허용")
        return False
    
    # 하이픈으로 시작/끝 검증
    if bucket_name.startswith('-') or bucket_name.endswith('-'):
        logger.error("버킷 이름은 하이픈으로 시작하거나 끝날 수 없습니다")
        return False
    
    # 연속된 마침표 검증
    if '..' in bucket_name:
        logger.error("버킷 이름에 연속된 마침표를 사용할 수 없습니다")
        return False
    
    # IP 주소 형식 검증 (간단한 체크)
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ip_pattern, bucket_name):
        logger.error("버킷 이름은 IP 주소 형식일 수 없습니다")
        return False
    
    return True


def validate_endpoint_url(endpoint_url: str) -> bool:
    """
    엔드포인트 URL 검증
    
    Args:
        endpoint_url: 검증할 URL
        
    Returns:
        유효하면 True, 그렇지 않으면 False
    """
    if not endpoint_url:
        return False
    
    # 기본 URL 형식 검증
    url_pattern = r'^https?://[a-zA-Z0-9.-]+(:\d+)?(/.*)?$'
    if not re.match(url_pattern, endpoint_url):
        logger.error(f"유효하지 않은 엔드포인트 URL 형식: {endpoint_url}")
        return False
    
    return True


def init_s3_client() -> boto3.client:
    """
    S3 클라이언트 초기화
    
    Returns:
        초기화된 S3 클라이언트
        
    Raises:
        ValueError: 환경 변수 검증 실패 시
    """
    # 엔드포인트 URL 검증
    if not validate_endpoint_url(LOCALSTACK_ENDPOINT):
        raise ValueError(f"유효하지 않은 LocalStack 엔드포인트: {LOCALSTACK_ENDPOINT}")
    
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=LOCALSTACK_ENDPOINT,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name='us-east-1',  # LocalStack은 us-east-1 사용
            use_ssl=False,  # LocalStack은 기본적으로 HTTP 사용
            verify=False  # LocalStack은 자체 서명 인증서 사용
        )
        logger.info(f"S3 클라이언트 초기화 완료 (엔드포인트: {LOCALSTACK_ENDPOINT})")
        return s3_client
    except Exception as e:
        logger.error(f"S3 클라이언트 초기화 실패: {e}")
        raise


def wait_for_localstack(s3_client: boto3.client) -> bool:
    """
    LocalStack이 준비될 때까지 대기 (지수 백오프 전략)
    
    Args:
        s3_client: S3 클라이언트
        
    Returns:
        연결 성공 시 True, 실패 시 False
    """
    logger.info("LocalStack 연결 대기 중...")
    retry_count = 0
    current_delay = INITIAL_RETRY_DELAY
    
    while retry_count < MAX_RETRIES:
        try:
            # 연결 테스트
            s3_client.list_buckets()
            logger.info("✓ LocalStack 연결 성공!")
            return True
        except (ClientError, BotoCoreError) as e:
            retry_count += 1
            error_msg = str(e)[:100]  # 에러 메시지 길이 제한
            
            if retry_count < MAX_RETRIES:
                logger.debug(
                    f"재시도 {retry_count}/{MAX_RETRIES}... "
                    f"(대기 시간: {current_delay:.1f}초, 오류: {error_msg})"
                )
                time.sleep(current_delay)
                # 지수 백오프: 다음 재시도까지 대기 시간 증가
                current_delay = min(current_delay * RETRY_BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)
            else:
                logger.error(f"✗ LocalStack 연결 실패! (최대 재시도 횟수 초과)")
                logger.error(f"마지막 오류: {error_msg}")
                return False
        except Exception as e:
            # 예상치 못한 예외
            logger.error(f"예상치 못한 오류 발생: {e}")
            return False
    
    return False


def bucket_exists(s3_client: boto3.client, bucket_name: str) -> bool:
    """
    버킷 존재 여부 확인
    
    Args:
        s3_client: S3 클라이언트
        bucket_name: 버킷 이름
        
    Returns:
        존재하면 True, 그렇지 않으면 False
    """
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == '404':
            return False
        # 403 Forbidden도 버킷이 존재한다는 의미일 수 있음
        if error_code == '403':
            logger.warning(f"버킷 '{bucket_name}' 접근 권한 없음 (존재할 수 있음)")
            return True
        # 기타 오류는 예외로 전파
        raise
    except Exception as e:
        logger.error(f"버킷 존재 확인 중 오류 발생: {e}")
        raise


def create_bucket(s3_client: boto3.client, bucket_name: str) -> bool:
    """
    S3 버킷 생성
    
    Args:
        s3_client: S3 클라이언트
        bucket_name: 생성할 버킷 이름
        
    Returns:
        생성 성공 시 True, 실패 시 False
    """
    try:
        logger.info(f"→ 버킷 '{bucket_name}' 생성 중...")
        s3_client.create_bucket(Bucket=bucket_name)
        logger.info(f"✓ 버킷 '{bucket_name}' 생성 완료!")
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'BucketAlreadyExists':
            logger.info(f"✓ 버킷 '{bucket_name}' 이미 존재합니다.")
            return True
        elif error_code == 'BucketAlreadyOwnedByYou':
            logger.info(f"✓ 버킷 '{bucket_name}' 이미 소유하고 있습니다.")
            return True
        else:
            logger.error(f"버킷 생성 실패: {error_code} - {e}")
            return False
    except Exception as e:
        logger.error(f"버킷 생성 중 예상치 못한 오류: {e}")
        return False


def list_buckets(s3_client: boto3.client) -> None:
    """
    생성된 버킷 목록 출력
    
    Args:
        s3_client: S3 클라이언트
    """
    try:
        logger.info("생성된 버킷 목록:")
        response = s3_client.list_buckets()
        for bucket in response.get('Buckets', []):
            bucket_name = bucket.get('Name', 'Unknown')
            creation_date = bucket.get('CreationDate', 'Unknown')
            logger.info(f"  - {bucket_name} (생성일: {creation_date})")
    except Exception as e:
        logger.warning(f"버킷 목록 조회 중 오류 발생: {e}")


def init_s3_bucket() -> None:
    """
    S3 버킷 초기화 메인 함수
    
    Raises:
        SystemExit: 초기화 실패 시
    """
    logger.info("=" * 60)
    logger.info("LocalStack S3 버킷 초기화")
    logger.info("=" * 60)
    logger.info(f"LocalStack Endpoint: {LOCALSTACK_ENDPOINT}")
    logger.info(f"Bucket Name: {BUCKET_NAME}")
    logger.info(f"Region: {REGION}")
    logger.info(f"Max Retries: {MAX_RETRIES}")
    logger.info("")
    
    # 버킷 이름 검증
    if not validate_bucket_name(BUCKET_NAME):
        logger.error(f"유효하지 않은 버킷 이름: {BUCKET_NAME}")
        sys.exit(1)
    
    # S3 클라이언트 초기화
    try:
        s3_client = init_s3_client()
    except ValueError as e:
        logger.error(f"환경 변수 검증 실패: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"S3 클라이언트 초기화 실패: {e}")
        sys.exit(1)
    
    # LocalStack 연결 대기
    if not wait_for_localstack(s3_client):
        logger.error("LocalStack 연결 실패로 인해 초기화를 중단합니다.")
        sys.exit(1)
    
    # 버킷 생성 또는 확인
    try:
        if bucket_exists(s3_client, BUCKET_NAME):
            logger.info(f"✓ 버킷 '{BUCKET_NAME}' 이미 존재합니다.")
        else:
            if not create_bucket(s3_client, BUCKET_NAME):
                logger.error("버킷 생성 실패")
                sys.exit(1)
        
        # 버킷 목록 출력
        logger.info("")
        list_buckets(s3_client)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✓ LocalStack 초기화 완료!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ 오류 발생: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    try:
        init_s3_bucket()
    except KeyboardInterrupt:
        logger.warning("사용자에 의해 중단되었습니다.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}", exc_info=True)
        sys.exit(1)
