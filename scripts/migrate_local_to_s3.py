#!/usr/bin/env python3
"""
로컬 파일 시스템 데이터를 S3로 마이그레이션하는 스크립트
로컬 개발 환경에서 프로덕션 환경으로 전환 시 사용
"""
import json
import os
import sys
import boto3
from datetime import datetime
from pathlib import Path

# 환경 변수
LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', './local-data')
S3_BUCKET = os.environ.get('S3_BUCKET', 'sns-monitor-data')
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'ap-northeast-2')
S3_ENDPOINT = os.environ.get('S3_ENDPOINT')  # LocalStack 사용 시

def init_s3_client():
    """S3 클라이언트 초기화"""
    if S3_ENDPOINT:
        return boto3.client('s3', endpoint_url=S3_ENDPOINT, region_name=AWS_REGION)
    else:
        return boto3.client('s3', region_name=AWS_REGION)

def ensure_s3_bucket(s3_client):
    """S3 버킷 존재 확인 및 생성"""
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET)
        print(f"✅ S3 버킷 '{S3_BUCKET}' 존재 확인")
    except s3_client.exceptions.ClientError:
        print(f"📦 S3 버킷 '{S3_BUCKET}' 생성 중...")
        if S3_ENDPOINT:
            # LocalStack
            s3_client.create_bucket(Bucket=S3_BUCKET)
        else:
            # AWS
            s3_client.create_bucket(
                Bucket=S3_BUCKET,
                CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
            )
        print(f"✅ S3 버킷 생성 완료")

def migrate_file(s3_client, local_filepath, s3_key):
    """단일 파일을 S3로 업로드"""
    try:
        with open(local_filepath, 'rb') as f:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=f,
                ContentType='application/json',
                Metadata={
                    'source': 'local-migration',
                    'migrated-at': datetime.utcnow().isoformat(),
                    'original-path': local_filepath
                }
            )
        print(f"  ✅ 업로드 완료: {s3_key}")
        return True
    except Exception as e:
        print(f"  ❌ 업로드 실패: {e}")
        return False

def migrate_platform_data(s3_client, platform):
    """특정 플랫폼의 모든 데이터 마이그레이션"""
    platform_dir = os.path.join(LOCAL_DATA_DIR, platform)
    
    if not os.path.exists(platform_dir):
        print(f"⚠️  플랫폼 디렉토리 없음: {platform_dir}")
        return 0
    
    migrated_count = 0
    total_size = 0
    
    print(f"\n📁 플랫폼: {platform}")
    print(f"   디렉토리: {platform_dir}")
    
    # 모든 JSON 파일 찾기
    for root, dirs, files in os.walk(platform_dir):
        for filename in files:
            if not filename.endswith('.json'):
                continue
            
            local_filepath = os.path.join(root, filename)
            
            # 상대 경로 계산
            relative_path = os.path.relpath(local_filepath, LOCAL_DATA_DIR)
            s3_key = f"raw-data/{relative_path.replace(os.sep, '/')}"
            
            # 파일 크기 확인
            file_size = os.path.getsize(local_filepath)
            total_size += file_size
            
            print(f"  📄 파일: {relative_path} ({file_size:,} bytes)")
            
            # S3에 이미 존재하는지 확인
            try:
                s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
                print(f"     ⚠️  이미 존재함 (건너뜀)")
                continue
            except:
                pass
            
            # 업로드
            if migrate_file(s3_client, local_filepath, s3_key):
                migrated_count += 1
    
    print(f"\n   📊 마이그레이션 결과:")
    print(f"      - 업로드된 파일: {migrated_count}개")
    print(f"      - 총 크기: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
    
    return migrated_count

def migrate_metadata(s3_client):
    """메타데이터 마이그레이션"""
    metadata_dir = os.path.join(LOCAL_DATA_DIR, 'metadata')
    
    if not os.path.exists(metadata_dir):
        print(f"⚠️  메타데이터 디렉토리 없음: {metadata_dir}")
        return 0
    
    migrated_count = 0
    
    print(f"\n📁 메타데이터 마이그레이션")
    print(f"   디렉토리: {metadata_dir}")
    
    for root, dirs, files in os.walk(metadata_dir):
        for filename in files:
            if not filename.endswith('.json'):
                continue
            
            local_filepath = os.path.join(root, filename)
            relative_path = os.path.relpath(local_filepath, LOCAL_DATA_DIR)
            s3_key = f"metadata/{relative_path.replace(os.sep, '/').replace('metadata/', '')}"
            
            print(f"  📄 메타데이터: {relative_path}")
            
            if migrate_file(s3_client, local_filepath, s3_key):
                migrated_count += 1
    
    print(f"\n   📊 메타데이터 마이그레이션 결과: {migrated_count}개")
    return migrated_count

def main():
    """메인 함수"""
    print("=" * 70)
    print("🔄 로컬 데이터 → S3 마이그레이션 시작")
    print("=" * 70)
    print(f"로컬 데이터 디렉토리: {LOCAL_DATA_DIR}")
    print(f"S3 버킷: {S3_BUCKET}")
    print(f"리전: {AWS_REGION}")
    if S3_ENDPOINT:
        print(f"S3 엔드포인트: {S3_ENDPOINT} (LocalStack)")
    print()
    
    # S3 클라이언트 초기화
    try:
        s3_client = init_s3_client()
    except Exception as e:
        print(f"❌ S3 클라이언트 초기화 실패: {e}")
        print("   AWS 자격 증명을 확인하세요.")
        sys.exit(1)
    
    # 버킷 확인/생성
    try:
        ensure_s3_bucket(s3_client)
    except Exception as e:
        print(f"❌ 버킷 확인/생성 실패: {e}")
        sys.exit(1)
    
    # 플랫폼별 데이터 마이그레이션
    platforms = ['vuddy', 'youtube', 'dcinside', 'telegram', 'rss']
    
    total_migrated = 0
    
    for platform in platforms:
        count = migrate_platform_data(s3_client, platform)
        total_migrated += count
    
    # 메타데이터 마이그레이션
    metadata_count = migrate_metadata(s3_client)
    total_migrated += metadata_count
    
    # 최종 요약
    print("\n" + "=" * 70)
    print("✅ 마이그레이션 완료")
    print("=" * 70)
    print(f"총 업로드된 파일: {total_migrated}개")
    print(f"S3 버킷: s3://{S3_BUCKET}/raw-data/")
    print("\n다음 단계:")
    print("1. S3 데이터 확인: aws s3 ls s3://{S3_BUCKET}/raw-data/")
    print("2. LOCAL_MODE=false로 설정하여 프로덕션 모드 전환")
    print("3. API Backend 재시작하여 S3 데이터 사용 확인")

if __name__ == '__main__':
    main()


























