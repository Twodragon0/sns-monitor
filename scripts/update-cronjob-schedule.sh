#!/bin/bash
# CronJob 스케줄 업데이트 스크립트
# YouTube 크롤러와 JSON 업데이트 CronJob의 스케줄을 2시간 10분 간격으로 변경

set -e

# kubeconfig 설정
export KUBECONFIG=~/.kube/config

NAMESPACE="platform"
RELEASE_NAME="sns-monitor"

echo "=========================================="
echo "CronJob 스케줄 업데이트 시작"
echo "=========================================="

# YouTube 크롤러 CronJob 업데이트
echo "YouTube 크롤러 CronJob 업데이트 중..."
kubectl patch cronjob ${RELEASE_NAME}-youtube-crawler -n ${NAMESPACE} --type='json' -p='[
  {"op": "replace", "path": "/spec/schedule", "value": "10 */2 * * *"}
]' || echo "YouTube 크롤러 CronJob 업데이트 실패 (이미 업데이트되었거나 존재하지 않음)"

# DCInside 크롤러 CronJob 업데이트
echo "DCInside 크롤러 CronJob 업데이트 중..."
kubectl patch cronjob ${RELEASE_NAME}-dcinside-crawler -n ${NAMESPACE} --type='json' -p='[
  {"op": "replace", "path": "/spec/schedule", "value": "10 */2 * * *"}
]' || echo "DCInside 크롤러 CronJob 업데이트 실패 (이미 업데이트되었거나 존재하지 않음)"

# JSON 업데이트 CronJob 업데이트
echo "JSON 업데이트 CronJob 업데이트 중..."
kubectl patch cronjob ${RELEASE_NAME}-json-update -n ${NAMESPACE} --type='json' -p='[
  {"op": "replace", "path": "/spec/schedule", "value": "40 */2 * * *"}
]' || echo "JSON 업데이트 CronJob 업데이트 실패 (이미 업데이트되었거나 존재하지 않음)"

echo ""
echo "=========================================="
echo "업데이트된 CronJob 스케줄 확인"
echo "=========================================="
kubectl get cronjobs -n ${NAMESPACE} -o custom-columns=NAME:.metadata.name,SCHEDULE:.spec.schedule

echo ""
echo "✅ 스케줄 업데이트 완료!"
echo ""
echo "변경 사항:"
echo "  - YouTube 크롤러: 매 2시간 10분마다 실행"
echo "  - DCInside 크롤러: 매 2시간 10분마다 실행"
echo "  - JSON 업데이트: 매 2시간 40분마다 실행 (크롤러 완료 후)"
