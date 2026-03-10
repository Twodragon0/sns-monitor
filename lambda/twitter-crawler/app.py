from flask import Flask, request, jsonify
from flask_cors import CORS
import lambda_function
import os
import json

app = Flask(__name__)
CORS(app)

@app.route("/invoke", methods=["POST"])
def invoke():
    event = request.get_json() or {}
    context = {}
    result = lambda_function.lambda_handler(event, context)
    return jsonify(result)

@app.route("/crawl", methods=["POST"])
def crawl():
    """트위터 크롤링 엔드포인트"""
    try:
        data = request.get_json() or {}
        keywords = data.get("keywords", [])

        if not keywords:
            return jsonify({"error": "No keywords provided", "results": []}), 400

        event = {"keywords": keywords}
        context = {}
        result = lambda_function.lambda_handler(event, context)

        # 결과 파싱
        if isinstance(result, dict):
            body = result.get("body", "{}")
            if isinstance(body, str):
                parsed = json.loads(body)
            else:
                parsed = body
            return jsonify(parsed)
        return jsonify(result)
    except Exception as e:
        print(f"Error in crawl: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "results": []}), 500

@app.route("/search", methods=["POST"])
def search():
    """트위터 검색 엔드포인트 (crawl과 동일)"""
    return crawl()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    # 보안: 기본값은 localhost로 설정
    # 컨테이너 환경에서는 FLASK_HOST=0.0.0.0 환경 변수로 명시적으로 설정 필요
    # Kubernetes/Docker 환경에서는 ClusterIP Service를 통해 내부 네트워크로만 접근 가능하므로
    # NetworkPolicy로 추가 보안 강화 권장
    flask_host = os.environ.get('FLASK_HOST', '127.0.0.1')
    flask_port = int(os.environ.get('FLASK_PORT', '5000'))
    app.run(host=flask_host, port=flask_port, threaded=True)
