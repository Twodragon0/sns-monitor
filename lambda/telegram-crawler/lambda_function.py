"""
Telegram 크롤러
Telegram Bot API를 사용하여 특정 채널/그룹의 메시지 수집
"""

import json
import os
import boto3
from datetime import datetime, timedelta
import requests

# AWS 클라이언트
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
secrets_client = boto3.client('secretsmanager')
dynamodb = boto3.resource('dynamodb')

# 환경 변수
S3_BUCKET = os.environ.get('S3_BUCKET')
LLM_ANALYZER_FUNCTION = os.environ.get('LLM_ANALYZER_FUNCTION')
SEARCH_KEYWORDS = os.environ.get('SEARCH_KEYWORDS', '').split(',')
TELEGRAM_BOT_TOKEN_SECRET = os.environ.get('TELEGRAM_BOT_TOKEN_SECRET')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')
TELEGRAM_CHANNELS = os.environ.get('TELEGRAM_CHANNELS', '').split(',')  # @channel1,@channel2

def get_telegram_bot_token():
    """Secrets Manager에서 Telegram Bot Token 가져오기"""
    try:
        response = secrets_client.get_secret_value(SecretId=TELEGRAM_BOT_TOKEN_SECRET)
        secret = json.loads(response['SecretString'])
        return secret['telegram_bot_token']
    except Exception as e:
        print(f"Error getting Telegram bot token: {e}")
        raise

def get_channel_messages(bot_token, channel_username, keywords, limit=100):
    """
    Telegram 채널에서 메시지 검색

    참고: Bot API는 공개 채널만 접근 가능
    봇이 채널의 관리자여야 함
    """
    base_url = f"https://api.telegram.org/bot{bot_token}"

    # 채널 정보 가져오기
    try:
        chat_response = requests.get(f"{base_url}/getChat", params={'chat_id': channel_username}, timeout=30, verify=True)
        if chat_response.status_code != 200:
            print(f"Failed to get chat info for {channel_username}: {chat_response.text}")
            return []

        chat_data = chat_response.json()
        if not chat_data.get('ok'):
            print(f"Telegram API error: {chat_data.get('description')}")
            return []

        print(f"Channel info: {chat_data['result']['title']}")

    except Exception as e:
        print(f"Error getting channel info: {e}")
        return []

    # 최근 업데이트 가져오기
    messages = []
    try:
        # getUpdates로 최근 메시지 가져오기 (제한적)
        updates_response = requests.get(
            f"{base_url}/getUpdates",
            params={'limit': limit, 'timeout': 30},
            timeout=30,
            verify=True
        )

        if updates_response.status_code != 200:
            print(f"Failed to get updates: {updates_response.text}")
            return []

        updates_data = updates_response.json()
        if not updates_data.get('ok'):
            print(f"Telegram API error: {updates_data.get('description')}")
            return []

        # 키워드 필터링
        for update in updates_data.get('result', []):
            if 'message' in update or 'channel_post' in update:
                message = update.get('message') or update.get('channel_post')
                text = message.get('text', '')

                # 키워드 포함 여부 확인
                if any(keyword.lower() in text.lower() for keyword in keywords):
                    messages.append({
                        'message_id': message.get('message_id'),
                        'chat_id': message.get('chat', {}).get('id'),
                        'chat_title': message.get('chat', {}).get('title', ''),
                        'text': text,
                        'date': message.get('date'),
                        'author': message.get('from', {}).get('username', 'Unknown') if 'from' in message else 'Channel',
                        'views': message.get('views', 0)
                    })

        print(f"Found {len(messages)} messages with keywords in {channel_username}")

    except Exception as e:
        print(f"Error getting messages: {e}")

    return messages

def search_telegram_public(keywords, bot_token):
    """
    공개 Telegram 검색 (제한적)

    참고: Telegram은 공식 검색 API가 없음
    대안: 텔레그램 검색 봇 또는 서드파티 API 사용
    """
    # 이 함수는 실제로는 제한적입니다
    # 더 나은 방법: 사용자가 봇을 특정 채널에 추가하고 해당 채널 모니터링
    print("Public Telegram search is limited. Use specific channels instead.")
    return []

def save_to_s3(data, keyword):
    """수집된 데이터를 S3에 저장"""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    key = f"raw-data/telegram/{keyword}/{timestamp}.json"

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        print(f"Data saved to s3://{S3_BUCKET}/{key}")
        return key
    except Exception as e:
        print(f"Error saving to S3: {e}")
        raise

def trigger_llm_analysis(s3_key, keyword, total_messages):
    """LLM 분석기 호출"""
    try:
        payload = {
            'source': 'telegram',
            's3_key': s3_key,
            'keyword': keyword,
            'total_items': total_messages,
            'timestamp': datetime.utcnow().isoformat()
        }

        lambda_client.invoke(
            FunctionName=LLM_ANALYZER_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        print(f"LLM analysis triggered for {s3_key}")
    except Exception as e:
        print(f"Error triggering LLM analysis: {e}")

def lambda_handler(event, context):
    """
    Lambda 핸들러

    Telegram Bot을 특정 채널에 추가해야 작동
    """

    print(f"Event: {json.dumps(event)}")

    # Bot token 가져오기
    try:
        bot_token = get_telegram_bot_token()
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to get Telegram bot token'})
        }

    # 키워드 준비
    keywords = [k.strip() for k in SEARCH_KEYWORDS if k.strip()]
    if not keywords:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'No search keywords provided'})
        }

    results = []

    # 각 채널에서 검색
    channels = [c.strip() for c in TELEGRAM_CHANNELS if c.strip()]

    if not channels:
        print("No channels configured. Using webhook/updates mode.")
        # 채널이 없으면 봇으로 들어온 업데이트만 처리
        channels = ['@general']  # 기본값

    for channel in channels:
        print(f"Searching in Telegram channel: {channel}")

        try:
            messages = get_channel_messages(bot_token, channel, keywords)

            if not messages:
                print(f"No messages found in {channel}")
                continue

            # S3에 저장
            crawl_result = {
                'platform': 'telegram',
                'channel': channel,
                'keywords': keywords,
                'crawled_at': datetime.utcnow().isoformat(),
                'total_messages': len(messages),
                'messages': messages
            }

            # 키워드별로 그룹화
            for keyword in keywords:
                keyword_messages = [
                    msg for msg in messages
                    if keyword.lower() in msg['text'].lower()
                ]

                if keyword_messages:
                    s3_key = save_to_s3({
                        **crawl_result,
                        'keyword': keyword,
                        'messages': keyword_messages
                    }, keyword)

                    # LLM 분석 트리거
                    trigger_llm_analysis(s3_key, keyword, len(keyword_messages))

                    results.append({
                        'channel': channel,
                        'keyword': keyword,
                        'messages_found': len(keyword_messages),
                        's3_key': s3_key
                    })

        except Exception as e:
            print(f"Error processing channel '{channel}': {e}")
            results.append({
                'channel': channel,
                'error': str(e)
            })

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Telegram crawling completed',
            'results': results
        }, ensure_ascii=False)
    }
