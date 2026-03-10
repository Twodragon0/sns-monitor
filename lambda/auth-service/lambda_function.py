"""
인증 서비스
Claude Console OAuth 웹 로그인 방식 인증
"""

import json
import os
import boto3
from datetime import datetime, timedelta
import base64
import hashlib
import secrets

# 환경 변수
DYNAMODB_TABLE = os.environ.get('AUTH_TABLE', 'sns-monitor-auth')
DYNAMODB_SESSION_TABLE = os.environ.get('OAUTH_SESSION_TABLE', 'sns-monitor-oauth-sessions')
DYNAMODB_ENDPOINT = os.environ.get('DYNAMODB_ENDPOINT')

# AWS 클라이언트 (LocalStack 지원)
dynamodb = boto3.resource('dynamodb', endpoint_url=DYNAMODB_ENDPOINT) if DYNAMODB_ENDPOINT else boto3.resource('dynamodb')
secretsmanager = boto3.client('secretsmanager')
CLAUDE_OAUTH_CLIENT_ID = os.environ.get('CLAUDE_OAUTH_CLIENT_ID', '')
CLAUDE_OAUTH_CLIENT_SECRET = os.environ.get('CLAUDE_OAUTH_CLIENT_SECRET', '')
OPENAI_OAUTH_CLIENT_ID = os.environ.get('OPENAI_OAUTH_CLIENT_ID', '')
OPENAI_OAUTH_CLIENT_SECRET = os.environ.get('OPENAI_OAUTH_CLIENT_SECRET', '')
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:3000/auth/callback')

def generate_state():
    """OAuth state 파라미터 생성 (CSRF 방지)"""
    return secrets.token_urlsafe(32)

def generate_pkce_pair():
    """PKCE code_verifier와 code_challenge 생성"""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode('utf-8')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).rstrip(b'=').decode('utf-8')

    return code_verifier, code_challenge

def get_claude_auth_url():
    """
    Claude Console OAuth 인증 URL 생성
    실제 OAuth 2.0 PKCE 플로우 사용
    """
    state = generate_state()
    code_verifier, code_challenge = generate_pkce_pair()

    # State와 code_verifier 저장 (세션 관리)
    session_table = dynamodb.Table(DYNAMODB_SESSION_TABLE)
    session_table.put_item(Item={
        'state': state,
        'code_verifier': code_verifier,
        'provider': 'claude',
        'created_at': datetime.utcnow().isoformat(),
        'ttl': int((datetime.utcnow() + timedelta(minutes=10)).timestamp())
    })

    # Claude Console OAuth URL (실제 Anthropic OAuth 엔드포인트)
    auth_url = "https://console.anthropic.com/oauth/authorize"

    # OAuth 파라미터
    from urllib.parse import urlencode

    params = {
        'client_id': CLAUDE_OAUTH_CLIENT_ID or '9d1c250a-e61b-44d9-88ed-5944d1962f5e',  # Claude Code client ID
        'response_type': 'code',
        'scope': 'org:create_api_key user:profile user:inference user:sessions:claude_code',
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'state': state,
        'redirect_uri': REDIRECT_URI
    }

    query_string = urlencode(params)
    return f"{auth_url}?{query_string}"

def get_openai_auth_url():
    """
    OpenAI OAuth 인증 URL 생성
    OpenAI Platform OAuth 2.0 사용
    """
    state = generate_state()
    code_verifier, code_challenge = generate_pkce_pair()

    # State와 code_verifier 저장
    session_table = dynamodb.Table(DYNAMODB_SESSION_TABLE)
    session_table.put_item(Item={
        'state': state,
        'code_verifier': code_verifier,
        'provider': 'openai',
        'created_at': datetime.utcnow().isoformat(),
        'ttl': int((datetime.utcnow() + timedelta(minutes=10)).timestamp())
    })

    # OpenAI OAuth URL
    auth_url = "https://auth.openai.com/authorize"

    params = {
        'client_id': OPENAI_OAUTH_CLIENT_ID or 'your-openai-client-id',
        'response_type': 'code',
        'scope': 'openid profile api.read api.write',
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'state': state,
        'redirect_uri': REDIRECT_URI
    }

    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    return f"{auth_url}?{query_string}"

def exchange_code_for_token(provider, code, state):
    """Authorization code를 access token으로 교환"""
    import requests

    # State 검증
    session_table = dynamodb.Table(DYNAMODB_SESSION_TABLE)
    response = session_table.get_item(Key={'state': state})

    if 'Item' not in response:
        raise ValueError("Invalid state parameter")

    session_data = response['Item']

    if session_data['provider'] != provider:
        raise ValueError("Provider mismatch")

    # Code 교환
    if provider == 'claude':
        # Claude Console OAuth token exchange
        token_url = "https://console.anthropic.com/oauth/token"

        # PKCE 방식으로 토큰 교환
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'client_id': CLAUDE_OAUTH_CLIENT_ID or '9d1c250a-e61b-44d9-88ed-5944d1962f5e',
            'code_verifier': session_data.get('code_verifier')
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        # Token 요청
        token_response = requests.post(token_url, data=data, headers=headers, timeout=30, verify=True)

        if token_response.status_code != 200:
            print(f"Token exchange failed: {token_response.text}")
            raise ValueError(f"Token exchange failed: {token_response.status_code}")

        token_data = token_response.json()

    elif provider == 'openai':
        # OpenAI OAuth token exchange
        token_url = "https://auth.openai.com/oauth/token"

        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'client_id': OPENAI_OAUTH_CLIENT_ID or 'your-openai-client-id',
            'code_verifier': session_data.get('code_verifier')
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        # Token 요청
        token_response = requests.post(token_url, data=data, headers=headers, timeout=30, verify=True)

        if token_response.status_code != 200:
            print(f"OpenAI token exchange failed: {token_response.text}")
            raise ValueError(f"Token exchange failed: {token_response.status_code}")

        token_data = token_response.json()

    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Token 저장
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in', 3600)

    if not access_token:
        raise ValueError("No access token received")

    # DynamoDB에 저장 (user auth table)
    user_id = hashlib.sha256(access_token.encode()).hexdigest()[:16]

    auth_table = dynamodb.Table(DYNAMODB_TABLE)
    auth_table.put_item(Item={
        'user_id': user_id,
        'provider': provider,
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_at': (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat(),
        'created_at': datetime.utcnow().isoformat(),
        'ttl': int((datetime.utcnow() + timedelta(days=30)).timestamp())
    })

    # State 세션 삭제
    session_table.delete_item(Key={'state': state})

    return {
        'user_id': user_id,
        'provider': provider,
        'expires_at': (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
    }

def get_access_token(user_id, provider):
    """저장된 access token 가져오기 (자동 갱신)"""
    import requests

    table = dynamodb.Table(DYNAMODB_TABLE)
    response = table.get_item(Key={'user_id': user_id})

    if 'Item' not in response:
        return None

    token_data = response['Item']

    if token_data['provider'] != provider:
        return None

    # Token 만료 확인
    expires_at = datetime.fromisoformat(token_data['expires_at'])

    if datetime.utcnow() >= expires_at:
        # Refresh token으로 갱신
        if not token_data.get('refresh_token'):
            return None

        if provider == 'claude':
            token_url = "https://console.anthropic.com/oauth/token"
            data = {
                'client_id': CLAUDE_OAUTH_CLIENT_ID,
                'client_secret': CLAUDE_OAUTH_CLIENT_SECRET,
                'refresh_token': token_data['refresh_token'],
                'grant_type': 'refresh_token'
            }
        elif provider == 'openai':
            token_url = "https://auth.openai.com/oauth/token"
            data = {
                'client_id': OPENAI_OAUTH_CLIENT_ID,
                'client_secret': OPENAI_OAUTH_CLIENT_SECRET,
                'refresh_token': token_data['refresh_token'],
                'grant_type': 'refresh_token'
            }
        else:
            return None

        # Token 갱신 요청
        refresh_response = requests.post(token_url, data=data, timeout=30, verify=True)

        if refresh_response.status_code != 200:
            return None

        new_token_data = refresh_response.json()
        new_access_token = new_token_data['access_token']
        new_expires_in = new_token_data.get('expires_in', 3600)

        # 갱신된 토큰 저장
        table.update_item(
            Key={'user_id': user_id},
            UpdateExpression='SET access_token = :token, expires_at = :expires',
            ExpressionAttributeValues={
                ':token': new_access_token,
                ':expires': (datetime.utcnow() + timedelta(seconds=new_expires_in)).isoformat()
            }
        )

        return new_access_token

    return token_data['access_token']

def lambda_handler(event, context):
    """
    Lambda 핸들러

    Endpoints:
    - GET /auth/claude - Claude 로그인 URL 반환
    - GET /auth/openai - OpenAI 로그인 URL 반환
    - GET /auth/callback - OAuth callback 처리
    - POST /auth/token - Access token 가져오기
    - DELETE /auth/logout - 로그아웃
    """

    print(f"Event: {json.dumps(event)}")

    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '')
    query_params = event.get('queryStringParameters') or {}
    body = json.loads(event.get('body', '{}')) if event.get('body') else {}

    try:
        # GET /auth/claude - Claude 로그인 URL
        if http_method == 'GET' and path.endswith('/auth/claude'):
            auth_url = get_claude_auth_url()
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'auth_url': auth_url,
                    'provider': 'claude'
                })
            }

        # GET /auth/openai - OpenAI 로그인 URL
        elif http_method == 'GET' and path.endswith('/auth/openai'):
            auth_url = get_openai_auth_url()
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'auth_url': auth_url,
                    'provider': 'openai'
                })
            }

        # GET /auth/callback - OAuth callback
        elif http_method == 'GET' and path.endswith('/auth/callback'):
            code = query_params.get('code')
            state = query_params.get('state')
            error = query_params.get('error')

            if error:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': error})
                }

            if not code or not state:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Missing code or state'})
                }

            # State로 provider 확인
            session_table = dynamodb.Table(DYNAMODB_SESSION_TABLE)
            session_response = session_table.get_item(Key={'state': state})

            if 'Item' not in session_response:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Invalid state'})
                }

            provider = session_response['Item']['provider']

            # Code 교환
            token_info = exchange_code_for_token(provider, code, state)

            # JSON 응답 반환 (프론트엔드에서 처리)
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'user_id': token_info['user_id'],
                    'provider': provider,
                    'expires_at': token_info['expires_at']
                })
            }

        # POST /auth/token - Access token 가져오기
        elif http_method == 'POST' and path.endswith('/auth/token'):
            user_id = body.get('user_id')
            provider = body.get('provider')

            if not user_id or not provider:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Missing user_id or provider'})
                }

            access_token = get_access_token(user_id, provider)

            if not access_token:
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'Token expired or invalid'})
                }

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'access_token': access_token,
                    'provider': provider
                })
            }

        # DELETE /auth/logout - 로그아웃
        elif http_method == 'DELETE' and path.endswith('/auth/logout'):
            user_id = body.get('user_id')

            if not user_id:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Missing user_id'})
                }

            # Token 삭제
            table = dynamodb.Table(DYNAMODB_TABLE)
            table.delete_item(Key={'user_id': user_id})

            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Logged out successfully'})
            }

        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Not found'})
            }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
