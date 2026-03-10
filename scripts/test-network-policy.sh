#!/bin/bash
# NetworkPolicy 및 보안 설정 테스트 스크립트
# 사용법: ./scripts/test-network-policy.sh [namespace]

set -e

NAMESPACE="${1:-platform}"
RELEASE_NAME="sns-monitor"

echo "=========================================="
echo "🔒 NetworkPolicy 및 보안 설정 테스트"
echo "=========================================="
echo "Namespace: $NAMESPACE"
echo "Release: $RELEASE_NAME"
echo ""

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 테스트 결과 추적
PASSED=0
FAILED=0

# 테스트 함수
test_check() {
    local test_name="$1"
    local command="$2"
    
    echo -n "테스트: $test_name ... "
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        ((FAILED++))
        return 1
    fi
}

# 1. NetworkPolicy 존재 확인
echo "=== 1. NetworkPolicy 확인 ==="
test_check "NetworkPolicy 존재" "kubectl get networkpolicy -n $NAMESPACE | grep -q $RELEASE_NAME"
test_check "Default Deny Policy" "kubectl get networkpolicy -n $NAMESPACE | grep -q default-deny"
test_check "Frontend Allow Policy" "kubectl get networkpolicy -n $NAMESPACE | grep -q allow-frontend"
test_check "API Backend Allow Policy" "kubectl get networkpolicy -n $NAMESPACE | grep -q allow-api-backend"
test_check "Redis Allow Policy" "kubectl get networkpolicy -n $NAMESPACE | grep -q allow-redis"
echo ""

# 2. Pod 상태 확인
echo "=== 2. Pod 상태 확인 ==="
test_check "Frontend Pod 실행 중" "kubectl get pods -n $NAMESPACE -l app.kubernetes.io/component=frontend | grep -q Running"
test_check "API Backend Pod 실행 중" "kubectl get pods -n $NAMESPACE -l app.kubernetes.io/component=api-backend | grep -q Running"
test_check "Redis Pod 실행 중" "kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=redis | grep -q Running"
echo ""

# 3. 보안 컨텍스트 확인
echo "=== 3. 보안 컨텍스트 확인 ==="
FRONTEND_POD=$(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/component=frontend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$FRONTEND_POD" ]; then
    # readOnlyRootFilesystem 확인
    READ_ONLY=$(kubectl get pod "$FRONTEND_POD" -n $NAMESPACE -o jsonpath='{.spec.containers[0].securityContext.readOnlyRootFilesystem}' 2>/dev/null || echo "false")
    if [ "$READ_ONLY" == "true" ]; then
        echo -e "테스트: Frontend readOnlyRootFilesystem ... ${GREEN}✓ PASSED${NC}"
        ((PASSED++))
    else
        echo -e "테스트: Frontend readOnlyRootFilesystem ... ${RED}✗ FAILED (현재: $READ_ONLY)${NC}"
        ((FAILED++))
    fi
    
    # runAsNonRoot 확인
    RUN_AS_NON_ROOT=$(kubectl get pod "$FRONTEND_POD" -n $NAMESPACE -o jsonpath='{.spec.securityContext.runAsNonRoot}' 2>/dev/null || echo "false")
    if [ "$RUN_AS_NON_ROOT" == "true" ]; then
        echo -e "테스트: Frontend runAsNonRoot ... ${GREEN}✓ PASSED${NC}"
        ((PASSED++))
    else
        echo -e "테스트: Frontend runAsNonRoot ... ${RED}✗ FAILED (현재: $RUN_AS_NON_ROOT)${NC}"
        ((FAILED++))
    fi
else
    echo -e "테스트: Frontend Pod 찾기 ... ${RED}✗ FAILED (Pod를 찾을 수 없음)${NC}"
    ((FAILED++))
fi
echo ""

# 4. 네트워크 통신 테스트
echo "=== 4. 네트워크 통신 테스트 ==="
FRONTEND_POD=$(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/component=frontend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
API_BACKEND_POD=$(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/component=api-backend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
REDIS_POD=$(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$FRONTEND_POD" ] && [ -n "$API_BACKEND_POD" ]; then
    # Frontend → API Backend 통신 테스트
    if kubectl exec -n $NAMESPACE "$FRONTEND_POD" -- curl -s -f -m 5 http://${RELEASE_NAME}-api-backend:8080/api/health > /dev/null 2>&1; then
        echo -e "테스트: Frontend → API Backend 통신 ... ${GREEN}✓ PASSED${NC}"
        ((PASSED++))
    else
        echo -e "테스트: Frontend → API Backend 통신 ... ${RED}✗ FAILED${NC}"
        ((FAILED++))
    fi
fi

if [ -n "$API_BACKEND_POD" ] && [ -n "$REDIS_POD" ]; then
    # API Backend → Redis 통신 테스트
    if kubectl exec -n $NAMESPACE "$API_BACKEND_POD" -- sh -c "timeout 5 redis-cli -h ${RELEASE_NAME}-redis-master ping" 2>/dev/null | grep -q "PONG"; then
        echo -e "테스트: API Backend → Redis 통신 ... ${GREEN}✓ PASSED${NC}"
        ((PASSED++))
    else
        echo -e "테스트: API Backend → Redis 통신 ... ${YELLOW}⚠ SKIPPED (redis-cli 없음)${NC}"
    fi
fi
echo ""

# 5. Service 확인
echo "=== 5. Service 확인 ==="
test_check "Frontend Service" "kubectl get svc -n $NAMESPACE | grep -q ${RELEASE_NAME}-frontend"
test_check "API Backend Service" "kubectl get svc -n $NAMESPACE | grep -q ${RELEASE_NAME}-api-backend"
test_check "Redis Service" "kubectl get svc -n $NAMESPACE | grep -q ${RELEASE_NAME}-redis"
echo ""

# 6. Ingress 확인
echo "=== 6. Ingress 확인 ==="
test_check "Ingress 리소스 존재" "kubectl get ingress -n $NAMESPACE | grep -q $RELEASE_NAME"
echo ""

# 결과 요약
echo "=========================================="
echo "📊 테스트 결과 요약"
echo "=========================================="
echo -e "${GREEN}통과: $PASSED${NC}"
echo -e "${RED}실패: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ 모든 테스트 통과!${NC}"
    exit 0
else
    echo -e "${RED}❌ 일부 테스트 실패. 위의 결과를 확인하세요.${NC}"
    exit 1
fi
