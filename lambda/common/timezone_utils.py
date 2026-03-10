"""
시간대 유틸리티 함수
UTC를 KST(한국 표준시)로 변환
"""

from datetime import datetime, timezone, timedelta

# KST는 UTC+9
KST = timezone(timedelta(hours=9))

def now_kst():
    """현재 KST 시간 반환"""
    return datetime.now(KST)

def utc_to_kst(utc_dt):
    """UTC datetime을 KST로 변환"""
    if utc_dt.tzinfo is None:
        # timezone 정보가 없으면 UTC로 간주
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(KST)

def format_kst(dt, include_timezone=True):
    """
    KST datetime을 한국어 형식으로 포맷

    Args:
        dt: datetime 객체
        include_timezone: 시간대 정보 포함 여부

    Returns:
        포맷된 문자열 (예: "2025. 11. 21. 오후 5:25:50 KST")
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    kst_dt = dt.astimezone(KST)

    # 한국어 형식으로 포맷
    formatted = kst_dt.strftime('%Y. %m. %d. ')

    # 오전/오후 구분
    hour = kst_dt.hour
    if hour >= 12:
        formatted += '오후 '
        if hour > 12:
            hour -= 12
    else:
        formatted += '오전 '
        if hour == 0:
            hour = 12

    formatted += f"{hour}:{kst_dt.strftime('%M:%S')}"

    if include_timezone:
        formatted += ' KST'

    return formatted

def isoformat_kst(dt=None):
    """
    KST datetime을 ISO 8601 형식으로 반환

    Args:
        dt: datetime 객체 (None이면 현재 시간)

    Returns:
        ISO 8601 형식 문자열 (예: "2025-11-21T17:25:50+09:00")
    """
    if dt is None:
        dt = now_kst()
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc).astimezone(KST)
    else:
        dt = dt.astimezone(KST)

    return dt.isoformat()

def filename_timestamp_kst():
    """
    파일명에 사용할 타임스탬프 생성 (KST)

    Returns:
        타임스탬프 문자열 (예: "2025-11-21-17-25-50")
    """
    return now_kst().strftime('%Y-%m-%d-%H-%M-%S')
