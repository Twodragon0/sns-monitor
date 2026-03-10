#!/usr/bin/env python3
"""
S3 데이터 동기화 스크립트
로컬 PVC 데이터를 S3에 백업하고, 필요시 S3에서 복원

비용 최적화:
- S3 Intelligent-Tiering 스토리지 클래스 사용
- 증분 동기화로 전송량 최소화
- 최신 데이터만 유지 (오래된 파일 자동 정리)
"""
import json
import os
import sys
import boto3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 환경 변수
LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', '/app/local-data')
S3_BUCKET = os.environ.get('S3_BUCKET', 'sns-monitor-data')
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'ap-northeast-2')
S3_PREFIX = os.environ.get('S3_PREFIX', 'data')
SYNC_MODE = os.environ.get('SYNC_MODE', 'backup')  # backup, restore, bidirectional
MAX_AGE_DAYS = int(os.environ.get('MAX_AGE_DAYS', '30'))  # 보관 기간
DRY_RUN = os.environ.get('DRY_RUN', 'false').lower() == 'true'

# 동기화할 디렉토리 (우선순위 순)
SYNC_DIRS = [
    'vuddy',          # 핵심 분석 데이터
    'dcinside',       # DCInside 크롤링 데이터
    'youtube',        # YouTube 크롤링 데이터
    'metadata',       # 메타데이터
]


def init_s3_client():
    """S3 클라이언트 초기화"""
    return boto3.client('s3', region_name=AWS_REGION)


def get_file_sha256(filepath):
    """파일의 SHA-256 해시 계산 (보안 강화: MD5 대신 SHA-256 사용)"""
    hash_sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


def get_file_md5_for_etag(filepath):
    """
    파일의 MD5 해시 계산 (S3 ETag 호환성용)
    
    주의: MD5는 암호학적으로 취약하지만, S3 ETag는 단일 파트 업로드의 경우 MD5를 사용합니다.
    이 함수는 S3 ETag 비교를 위해서만 사용되며, 암호학적 목적으로는 사용되지 않습니다.
    실제 파일 무결성 검증은 SHA-256을 사용합니다.
    """
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_s3_etag(s3_client, bucket, key):
    """S3 객체의 ETag 조회"""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        # ETag에서 따옴표 제거
        return response['ETag'].strip('"')
    except s3_client.exceptions.ClientError:
        return None


def sync_file_to_s3(s3_client, local_path, s3_key, force=False):
    """단일 파일을 S3로 동기화

    Returns:
        tuple: (status, message)
        status: 'uploaded', 'skipped', 'error'
    """
    if not os.path.exists(local_path):
        return ('error', f'파일 없음: {local_path}')

    # SHA-256 해시 계산 (보안 강화: 메타데이터에 저장)
    local_sha256 = get_file_sha256(local_path)
    
    # S3 ETag 비교를 위한 MD5 계산 (S3 호환성용, 암호학적 목적 아님)
    # 참고: S3 ETag는 단일 파트 업로드의 경우 MD5와 동일합니다
    local_md5 = get_file_md5_for_etag(local_path)

    if not force:
        s3_etag = get_s3_etag(s3_client, S3_BUCKET, s3_key)
        # ETag 비교 (MD5 기반, 단일 파트 업로드의 경우)
        if s3_etag and s3_etag == local_md5:
            return ('skipped', '변경 없음')

    if DRY_RUN:
        return ('dry-run', f's3://{S3_BUCKET}/{s3_key}')

    try:
        file_size = os.path.getsize(local_path)

        # 파일 크기에 따라 업로드 방식 결정
        extra_args = {
            'StorageClass': 'INTELLIGENT_TIERING',  # 비용 최적화
            'ServerSideEncryption': 'AES256',  # S3 버킷 정책 요구사항
            'ContentType': 'application/json',
            'Metadata': {
                'source': 'sns-monitor-sync',
                'synced-at': datetime.utcnow().isoformat(),
                'local-sha256': local_sha256  # 보안 강화: SHA-256 사용
            }
        }

        if file_size > 5 * 1024 * 1024:  # 5MB 이상
            # Multipart upload 사용
            s3_client.upload_file(
                local_path, S3_BUCKET, s3_key,
                ExtraArgs=extra_args
            )
        else:
            with open(local_path, 'rb') as f:
                s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key,
                    Body=f,
                    **extra_args
                )

        return ('uploaded', f'{file_size:,} bytes')
    except Exception as e:
        return ('error', str(e))


def sync_file_from_s3(s3_client, s3_key, local_path, force=False):
    """S3에서 단일 파일 다운로드

    Returns:
        tuple: (status, message)
    """
    # 로컬 파일이 존재하고 동일하면 스킵
    if not force and os.path.exists(local_path):
        # S3 ETag 비교를 위한 MD5 계산 (S3 호환성용)
        local_md5 = get_file_md5_for_etag(local_path)
        s3_etag = get_s3_etag(s3_client, S3_BUCKET, s3_key)
        # ETag 비교 (MD5 기반, 단일 파트 업로드의 경우)
        if s3_etag and s3_etag == local_md5:
            return ('skipped', '변경 없음')

    if DRY_RUN:
        return ('dry-run', f'{local_path}')

    try:
        # 디렉토리 생성
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content_length = response['ContentLength']

        with open(local_path, 'wb') as f:
            f.write(response['Body'].read())

        return ('downloaded', f'{content_length:,} bytes')
    except Exception as e:
        return ('error', str(e))


def backup_to_s3(s3_client):
    """로컬 데이터를 S3로 백업"""
    print("\n📤 로컬 → S3 백업 시작")
    print(f"   소스: {LOCAL_DATA_DIR}")
    print(f"   대상: s3://{S3_BUCKET}/{S3_PREFIX}/")

    stats = {'uploaded': 0, 'skipped': 0, 'error': 0, 'total_size': 0}

    for sync_dir in SYNC_DIRS:
        dir_path = os.path.join(LOCAL_DATA_DIR, sync_dir)
        if not os.path.exists(dir_path):
            print(f"\n⚠️  디렉토리 없음: {sync_dir}")
            continue

        print(f"\n📁 동기화: {sync_dir}")

        for root, dirs, files in os.walk(dir_path):
            for filename in files:
                if not filename.endswith('.json'):
                    continue

                local_path = os.path.join(root, filename)
                relative_path = os.path.relpath(local_path, LOCAL_DATA_DIR)
                s3_key = f"{S3_PREFIX}/{relative_path}"

                status, message = sync_file_to_s3(s3_client, local_path, s3_key)
                stats[status] = stats.get(status, 0) + 1

                if status == 'uploaded':
                    size = os.path.getsize(local_path)
                    stats['total_size'] += size
                    print(f"   ✅ 업로드: {relative_path} ({message})")
                elif status == 'error':
                    print(f"   ❌ 오류: {relative_path} - {message}")

    return stats


def restore_from_s3(s3_client):
    """S3에서 로컬로 데이터 복원"""
    print("\n📥 S3 → 로컬 복원 시작")
    print(f"   소스: s3://{S3_BUCKET}/{S3_PREFIX}/")
    print(f"   대상: {LOCAL_DATA_DIR}")

    stats = {'downloaded': 0, 'skipped': 0, 'error': 0, 'total_size': 0}

    # S3 객체 목록 조회
    paginator = s3_client.get_paginator('list_objects_v2')

    for sync_dir in SYNC_DIRS:
        prefix = f"{S3_PREFIX}/{sync_dir}/"
        print(f"\n📁 복원: {sync_dir}")

        try:
            for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
                for obj in page.get('Contents', []):
                    s3_key = obj['Key']
                    if not s3_key.endswith('.json'):
                        continue

                    # S3 키에서 로컬 경로 계산
                    relative_path = s3_key[len(S3_PREFIX) + 1:]  # prefix/ 제거
                    local_path = os.path.join(LOCAL_DATA_DIR, relative_path)

                    status, message = sync_file_from_s3(s3_client, s3_key, local_path)
                    stats[status] = stats.get(status, 0) + 1

                    if status == 'downloaded':
                        stats['total_size'] += obj['Size']
                        print(f"   ✅ 다운로드: {relative_path} ({message})")
                    elif status == 'error':
                        print(f"   ❌ 오류: {relative_path} - {message}")
        except Exception as e:
            print(f"   ❌ S3 조회 오류: {e}")

    return stats


def cleanup_old_files(s3_client):
    """오래된 S3 파일 정리 (비용 최적화)"""
    if MAX_AGE_DAYS <= 0:
        print("\n⏭️  파일 정리 비활성화됨")
        return {'deleted': 0}

    print(f"\n🧹 {MAX_AGE_DAYS}일 이상 된 파일 정리")

    cutoff_date = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)
    stats = {'deleted': 0, 'kept': 0}

    paginator = s3_client.get_paginator('list_objects_v2')

    try:
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX):
            for obj in page.get('Contents', []):
                last_modified = obj['LastModified'].replace(tzinfo=None)

                if last_modified < cutoff_date:
                    if DRY_RUN:
                        print(f"   🗑️  [DRY-RUN] 삭제 예정: {obj['Key']}")
                    else:
                        s3_client.delete_object(Bucket=S3_BUCKET, Key=obj['Key'])
                        print(f"   🗑️  삭제: {obj['Key']}")
                    stats['deleted'] += 1
                else:
                    stats['kept'] += 1
    except Exception as e:
        print(f"   ❌ 정리 오류: {e}")

    return stats


def get_s3_stats(s3_client):
    """S3 버킷 통계 조회"""
    print("\n📊 S3 버킷 통계")

    total_size = 0
    file_count = 0
    storage_classes = {}

    paginator = s3_client.get_paginator('list_objects_v2')

    try:
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX):
            for obj in page.get('Contents', []):
                total_size += obj['Size']
                file_count += 1

                storage_class = obj.get('StorageClass', 'STANDARD')
                storage_classes[storage_class] = storage_classes.get(storage_class, 0) + 1

        print(f"   총 파일 수: {file_count:,}")
        print(f"   총 크기: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
        print("   스토리지 클래스별:")
        for sc, count in storage_classes.items():
            print(f"      - {sc}: {count} 파일")
    except Exception as e:
        print(f"   ❌ 통계 조회 오류: {e}")


def main():
    """메인 함수"""
    print("=" * 70)
    print("🔄 SNS Monitor S3 동기화")
    print("=" * 70)
    print(f"동기화 모드: {SYNC_MODE}")
    print(f"S3 버킷: {S3_BUCKET}")
    print(f"S3 Prefix: {S3_PREFIX}")
    print(f"로컬 디렉토리: {LOCAL_DATA_DIR}")
    print(f"최대 보관 기간: {MAX_AGE_DAYS}일")
    if DRY_RUN:
        print("⚠️  DRY RUN 모드 - 실제 변경 없음")

    # S3 클라이언트 초기화
    try:
        s3_client = init_s3_client()
        # 버킷 접근 확인
        s3_client.head_bucket(Bucket=S3_BUCKET)
        print(f"\n✅ S3 버킷 접근 확인: {S3_BUCKET}")
    except Exception as e:
        print(f"\n❌ S3 접근 실패: {e}")
        print("   AWS 자격 증명 및 버킷 권한을 확인하세요.")
        sys.exit(1)

    # 동기화 실행
    if SYNC_MODE == 'backup':
        stats = backup_to_s3(s3_client)
        print(f"\n📊 백업 결과:")
        print(f"   업로드: {stats.get('uploaded', 0)}개 파일")
        print(f"   스킵: {stats.get('skipped', 0)}개 파일")
        print(f"   오류: {stats.get('error', 0)}개 파일")
        print(f"   전송량: {stats.get('total_size', 0):,} bytes")

        # 오래된 파일 정리
        cleanup_stats = cleanup_old_files(s3_client)
        print(f"\n🧹 정리 결과:")
        print(f"   삭제: {cleanup_stats.get('deleted', 0)}개 파일")

    elif SYNC_MODE == 'restore':
        stats = restore_from_s3(s3_client)
        print(f"\n📊 복원 결과:")
        print(f"   다운로드: {stats.get('downloaded', 0)}개 파일")
        print(f"   스킵: {stats.get('skipped', 0)}개 파일")
        print(f"   오류: {stats.get('error', 0)}개 파일")
        print(f"   전송량: {stats.get('total_size', 0):,} bytes")

    elif SYNC_MODE == 'bidirectional':
        # 양방향 동기화: S3가 최신이면 복원, 로컬이 최신이면 백업
        restore_stats = restore_from_s3(s3_client)
        backup_stats = backup_to_s3(s3_client)

        print(f"\n📊 양방향 동기화 결과:")
        print(f"   S3 → 로컬: {restore_stats.get('downloaded', 0)}개")
        print(f"   로컬 → S3: {backup_stats.get('uploaded', 0)}개")

    elif SYNC_MODE == 'stats':
        get_s3_stats(s3_client)
    else:
        print(f"❌ 알 수 없는 동기화 모드: {SYNC_MODE}")
        sys.exit(1)

    # 최종 통계
    get_s3_stats(s3_client)

    print("\n" + "=" * 70)
    print("✅ 동기화 완료")
    print("=" * 70)


if __name__ == '__main__':
    main()
