#!/bin/bash
# 로컬 모드용 entrypoint 스크립트

# 로컬 데이터 디렉토리 생성 (볼륨 마운트 후)
mkdir -p /tmp/data
mkdir -p /tmp/data/metadata
mkdir -p /tmp/data/youtube
mkdir -p /tmp/data/vuddy

# 로컬 API 서버 시작
exec python start_local_api.py --host 0.0.0.0 --port 8080

