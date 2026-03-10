#!/bin/bash
# 보안 개선 사항 배포 스크립트
# 사용법: ./scripts/deploy-security-updates.sh [namespace] [environment] [dry-run]

set -e

NAMESPACE="${1:-platform}"
ENVIRONMENT="${2:-dev}"
DRY_RUN="${3:-false}"

RELEASE_NAME="sns-monitor"
CHART_PATH="./helm/sns-monitor"

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "🚀 보안 개선 사항 배포"
echo "=========================================="
echo "Namespace: $NAMESPACE"
echo "Environment: $ENVIRONMENT"
echo "Release: $RELEASE_NAME"
echo "Dry Run: $DRY_RUN"
echo ""

# 1. 사전 검증
echo -e "${BLUE}=== 1. 사전 검증 ===${NC}"

# kubectl 연결 확인
if ! kubectl cluster-info > /dev/null 2>&1; then
    echo -e "${RED}❌ kubectl 연결 실패. kubeconfig를 확인하세요.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ kubectl 연결 확인${NC}"

# Helm 설치 확인
if ! command -v helm &> /dev/null; then
    echo -e "${RED}❌ Helm이 설치되어 있지 않습니다.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Helm 설치 확인${NC}"

# Chart 경로 확인
if [ ! -d "$CHART_PATH" ]; then
    echo -e "${RED}❌ Helm 차트를 찾을 수 없습니다: $CHART_PATH${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Helm 차트 경로 확인${NC}"

# Namespace 확인
if ! kubectl get namespace "$NAMESPACE" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Namespace '$NAMESPACE'가 존재하지 않습니다. 생성합니다...${NC}"
    if [ "$DRY_RUN" != "true" ]; then
        kubectl create namespace "$NAMESPACE"
        echo -e "${GREEN}✓ Namespace 생성 완료${NC}"
    else
        echo -e "${YELLOW}⚠ Dry-run 모드: Namespace 생성 건너뜀${NC}"
    fi
else
    echo -e "${GREEN}✓ Namespace 확인${NC}"
fi
echo ""

# 2. Helm 차트 검증
echo -e "${BLUE}=== 2. Helm 차트 검증 ===${NC}"

# Values 파일 확인
VALUES_FILE="$CHART_PATH/values.yaml"
if [ "$ENVIRONMENT" == "prod" ]; then
    VALUES_FILE="$CHART_PATH/values-production.yaml"
fi

if [ ! -f "$VALUES_FILE" ]; then
    echo -e "${YELLOW}⚠ $VALUES_FILE을 찾을 수 없습니다. values.yaml을 사용합니다.${NC}"
    VALUES_FILE="$CHART_PATH/values.yaml"
fi

echo "Values 파일: $VALUES_FILE"

# Helm lint
echo "Helm lint 실행 중..."
if helm lint "$CHART_PATH" -f "$VALUES_FILE" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Helm lint 통과${NC}"
else
    echo -e "${YELLOW}⚠ Helm lint 경고 발생 (계속 진행)${NC}"
    helm lint "$CHART_PATH" -f "$VALUES_FILE" || true
fi
echo ""

# 3. Helm 의존성 업데이트
echo -e "${BLUE}=== 3. Helm 의존성 업데이트 ===${NC}"
if [ "$DRY_RUN" != "true" ]; then
    helm dependency update "$CHART_PATH" > /dev/null 2>&1 || echo -e "${YELLOW}⚠ 의존성 업데이트 건너뜀${NC}"
    echo -e "${GREEN}✓ 의존성 업데이트 완료${NC}"
else
    echo -e "${YELLOW}⚠ Dry-run 모드: 의존성 업데이트 건너뜀${NC}"
fi
echo ""

# 4. 배포 (Dry-run 또는 실제)
echo -e "${BLUE}=== 4. 배포 실행 ===${NC}"

# Secrets 확인 (필요한 경우)
YOUTUBE_API_KEY="${YOUTUBE_API_KEY:-}"
if [ -z "$YOUTUBE_API_KEY" ] && [ "$DRY_RUN" != "true" ]; then
    echo -e "${YELLOW}⚠ YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.${NC}"
    echo -e "${YELLOW}  기존 Secret을 사용하거나 배포 후 수동으로 설정하세요.${NC}"
fi

# Helm upgrade 명령어 구성
HELM_CMD="helm upgrade --install $RELEASE_NAME $CHART_PATH \
  --namespace $NAMESPACE \
  -f $VALUES_FILE"

if [ -n "$YOUTUBE_API_KEY" ]; then
    HELM_CMD="$HELM_CMD --set secrets.youtubeApiKey=$YOUTUBE_API_KEY"
fi

if [ "$DRY_RUN" == "true" ]; then
    echo -e "${YELLOW}🔍 Dry-run 모드: 실제 배포 없이 변경 사항 확인${NC}"
    HELM_CMD="$HELM_CMD --dry-run --debug"
    eval "$HELM_CMD"
    echo ""
    echo -e "${GREEN}✓ Dry-run 완료. 실제 배포하려면 DRY_RUN=false로 실행하세요.${NC}"
    exit 0
else
    echo "배포 실행 중..."
    HELM_CMD="$HELM_CMD --wait --timeout 10m --atomic"
    
    if eval "$HELM_CMD"; then
        echo -e "${GREEN}✓ 배포 완료${NC}"
    else
        echo -e "${RED}❌ 배포 실패${NC}"
        exit 1
    fi
fi
echo ""

# 5. 배포 후 검증
if [ "$DRY_RUN" != "true" ]; then
    echo -e "${BLUE}=== 5. 배포 후 검증 ===${NC}"
    
    # Pod 상태 확인
    echo "Pod 상태 확인 중..."
    sleep 5
    kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/instance="$RELEASE_NAME"
    echo ""
    
    # NetworkPolicy 확인
    echo "NetworkPolicy 확인 중..."
    kubectl get networkpolicies -n "$NAMESPACE" | grep "$RELEASE_NAME" || echo -e "${YELLOW}⚠ NetworkPolicy를 찾을 수 없습니다.${NC}"
    echo ""
    
    echo -e "${GREEN}✅ 배포 완료!${NC}"
    echo ""
    echo "다음 단계:"
    echo "  1. 테스트 스크립트 실행: ./scripts/test-network-policy.sh $NAMESPACE"
    echo "  2. Pod 로그 확인: kubectl logs -n $NAMESPACE -l app.kubernetes.io/instance=$RELEASE_NAME"
    echo "  3. 서비스 접근 테스트: curl https://sns-monitor.example.com/api/health"
fi
