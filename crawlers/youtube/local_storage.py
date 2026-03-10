"""
로컬 파일 시스템 저장 유틸리티
S3/DynamoDB 대신 로컬 파일 시스템에 데이터를 저장하는 헬퍼 함수들
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# 로컬 데이터 저장 경로
LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', './local-data')
LOCAL_MODE = os.environ.get('LOCAL_MODE', 'false').lower() == 'true'

def ensure_local_dir(path: str):
    """로컬 디렉토리 생성"""
    Path(path).mkdir(parents=True, exist_ok=True)

def save_to_local_file(data: Dict[str, Any], platform: str, keyword: str, subdir: str = '') -> str:
    """
    로컬 파일 시스템에 데이터 저장 (S3 대신)
    
    Args:
        data: 저장할 데이터
        platform: 플랫폼 이름 (youtube, vuddy, etc.)
        keyword: 키워드 또는 식별자
        subdir: 하위 디렉토리 (선택사항)
    
    Returns:
        저장된 파일 경로
    """
    if not LOCAL_MODE:
        raise ValueError("LOCAL_MODE is not enabled")
    
    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    safe_keyword = keyword.replace('/', '_').replace('\\', '_').replace(':', '_')
    
    if subdir:
        file_dir = os.path.join(LOCAL_DATA_DIR, platform, subdir, safe_keyword)
    else:
        file_dir = os.path.join(LOCAL_DATA_DIR, platform, safe_keyword)
    
    ensure_local_dir(file_dir)
    
    filename = f"{timestamp}.json"
    filepath = os.path.join(file_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info("Data saved to local file: %s", filepath)
    return filepath

def save_metadata_to_local(metadata: Dict[str, Any], platform: str) -> str:
    """
    메타데이터를 로컬 JSON 파일에 저장 (DynamoDB 대신)
    
    Args:
        metadata: 저장할 메타데이터
        platform: 플랫폼 이름
    
    Returns:
        저장된 파일 경로
    """
    if not LOCAL_MODE:
        raise ValueError("LOCAL_MODE is not enabled")
    
    metadata_dir = os.path.join(LOCAL_DATA_DIR, 'metadata', platform)
    ensure_local_dir(metadata_dir)
    
    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    item_id = metadata.get('id', f"{platform}-{timestamp}")
    safe_id = item_id.replace('/', '_').replace('\\', '_').replace(':', '_')
    
    filename = f"{safe_id}.json"
    filepath = os.path.join(metadata_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    logger.info("Metadata saved to local file: %s", filepath)
    return filepath

def load_from_local_file(filepath: str) -> Dict[str, Any]:
    """로컬 파일에서 데이터 로드"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def list_local_files(platform: str, keyword: Optional[str] = None, subdir: Optional[str] = None) -> List[str]:
    """로컬 파일 목록 조회"""
    if keyword:
        safe_keyword = keyword.replace('/', '_').replace('\\', '_').replace(':', '_')
        if subdir:
            search_dir = os.path.join(LOCAL_DATA_DIR, platform, subdir, safe_keyword)
        else:
            search_dir = os.path.join(LOCAL_DATA_DIR, platform, safe_keyword)
    else:
        if subdir:
            search_dir = os.path.join(LOCAL_DATA_DIR, platform, subdir)
        else:
            search_dir = os.path.join(LOCAL_DATA_DIR, platform)
    
    if not os.path.exists(search_dir):
        return []
    
    files = []
    for root, dirs, filenames in os.walk(search_dir):
        for filename in filenames:
            if filename.endswith('.json'):
                files.append(os.path.join(root, filename))
    
    return sorted(files, reverse=True)  # 최신 파일 먼저

def load_latest_metadata(platform: str, keyword: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """최신 메타데이터 로드"""
    metadata_dir = os.path.join(LOCAL_DATA_DIR, 'metadata', platform)
    if not os.path.exists(metadata_dir):
        return None
    
    files = []
    for filename in os.listdir(metadata_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(metadata_dir, filename)
            try:
                metadata = load_from_local_file(filepath)
                if not keyword or metadata.get('keyword') == keyword:
                    files.append((filepath, metadata))
            except:
                continue
    
    if not files:
        return None
    
    # timestamp 기준으로 정렬하여 최신 항목 반환
    files.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
    return files[0][1]

def is_local_mode() -> bool:
    """로컬 모드인지 확인"""
    return LOCAL_MODE

