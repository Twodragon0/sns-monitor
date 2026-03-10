#!/usr/bin/env python3
"""
로컬 API 서버 시작 스크립트
로컬 모드로 API 백엔드를 실행합니다.
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 로컬 모드 활성화 (임포트 전에 설정)
os.environ['LOCAL_MODE'] = 'true'
os.environ['LOCAL_DATA_DIR'] = str(project_root / 'local-data')

# Lambda 함수 임포트 (로컬 모드 설정 후)
sys.path.insert(0, str(project_root / 'lambda' / 'api-backend'))
sys.path.insert(0, str(project_root / 'lambda' / 'common'))

# HTTP 서버 임포트
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

# Lambda 함수 임포트 (로컬 모드가 이미 설정되어 있음)
try:
    from lambda_function import lambda_handler
except ImportError as e:
    print(f"Error importing lambda_function: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """GET 요청 처리"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)
        
        # API Gateway 이벤트 형식으로 변환
        event = {
            'httpMethod': 'GET',
            'path': path,
            'queryStringParameters': {k: v[0] if len(v) == 1 else v for k, v in query_params.items()} if query_params else None
        }
        
        # Lambda 핸들러 실행
        try:
            response = lambda_handler(event, None)
            
            # 응답 전송
            self.send_response(response['statusCode'])
            for key, value in response.get('headers', {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response['body'].encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            error_response = json.dumps({'error': str(e)}, ensure_ascii=False)
            self.wfile.write(error_response.encode('utf-8'))
            print(f"Error handling request: {e}")
            import traceback
            traceback.print_exc()
    
    def do_POST(self):
        """POST 요청 처리"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # 요청 본문 읽기
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else None
        
        # API Gateway 이벤트 형식으로 변환
        event = {
            'httpMethod': 'POST',
            'path': path,
            'body': body
        }
        
        # Lambda 핸들러 실행
        try:
            response = lambda_handler(event, None)
            
            # 응답 전송
            self.send_response(response['statusCode'])
            for key, value in response.get('headers', {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response['body'].encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            error_response = json.dumps({'error': str(e)}, ensure_ascii=False)
            self.wfile.write(error_response.encode('utf-8'))
            print(f"Error handling request: {e}")
            import traceback
            traceback.print_exc()
    
    def do_OPTIONS(self):
        """CORS preflight 요청 처리"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """로그 메시지 출력"""
        print(f"[{self.address_string()}] {format % args}")

def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='로컬 API 서버 시작')
    parser.add_argument('--port', type=int, default=8080, help='서버 포트 (기본값: 8080)')
    parser.add_argument('--host', type=str, default='localhost', help='서버 호스트 (기본값: localhost)')
    
    args = parser.parse_args()
    
    server_address = (args.host, args.port)
    httpd = HTTPServer(server_address, APIHandler)
    
    print("=" * 60)
    print("로컬 API 서버 시작")
    print("=" * 60)
    print(f"서버 주소: http://{args.host}:{args.port}")
    print(f"로컬 데이터 디렉토리: {os.environ.get('LOCAL_DATA_DIR', './local-data')}")
    print("\n사용 가능한 엔드포인트:")
    print("  - GET /health")
    print("  - GET /api/scans")
    print("  - GET /api/dashboard/stats")
    print("  - GET /api/vuddy/creators")
    print("  - GET /api/channels")
    print("  - GET /api/data/{s3_key}")
    print("\n종료하려면 Ctrl+C를 누르세요.")
    print("=" * 60)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다...")
        httpd.shutdown()

if __name__ == '__main__':
    main()

