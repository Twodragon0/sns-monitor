#!/bin/bash
# Kubernetes 배포 스크립트
# 사용법: ./scripts/deploy-k8s.sh [namespace] [environment] [component]
# component: all, frontend, backend (기본값: all)

set -e

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 기본값 설정
NAMESPACE="${1:-platform}"
ENVIRONMENT="${2:-dev}"
COMPONENT="${3:-all}"
KUBECONFIG_PATH="${KUBECONFIG_PATH:-~/.kube/config}"

# kubeconfig 경로 확장
KUBECONFIG_PATH="${KUBECONFIG_PATH/#\~/$HOME}"

RELEASE_NAME="sns-monitor"
CHART_PATH="./helm/sns-monitor"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================="
echo "🚀 Kubernetes 배포 스크립트"
echo "=========================================="
echo "Namespace: $NAMESPACE"
echo "Environment: $ENVIRONMENT"
echo "Component: $COMPONENT"
echo "Kubeconfig: $KUBECONFIG_PATH"
echo ""

# 1. kubeconfig 확인 및 설정
echo -e "${BLUE}=== 1. kubeconfig 설정 ===${NC}"
if [ ! -f "$KUBECONFIG_PATH" ]; then
    echo -e "${RED}❌ kubeconfig 파일을 찾을 수 없습니다: $KUBECONFIG_PATH${NC}"
    exit 1
fi

export KUBECONFIG="$KUBECONFIG_PATH"
echo -e "${GREEN}✓ kubeconfig 설정 완료${NC}"

# kubectl 연결 확인
if ! kubectl cluster-info > /dev/null 2>&1; then
    echo -e "${RED}❌ kubectl 연결 실패. kubeconfig를 확인하세요.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ kubectl 연결 확인${NC}"

# 현재 클러스터 정보 출력
echo "현재 클러스터:"
kubectl cluster-info | head -n 1
echo ""

# 2. Namespace 확인
echo -e "${BLUE}=== 2. Namespace 확인 ===${NC}"
if ! kubectl get namespace "$NAMESPACE" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Namespace '$NAMESPACE'가 존재하지 않습니다. 생성합니다...${NC}"
    kubectl create namespace "$NAMESPACE"
    echo -e "${GREEN}✓ Namespace 생성 완료${NC}"
else
    echo -e "${GREEN}✓ Namespace 확인${NC}"
fi
echo ""

# 3. 프론트엔드 빌드 (필요한 경우)
if [ "$COMPONENT" == "all" ] || [ "$COMPONENT" == "frontend" ]; then
    echo -e "${BLUE}=== 3. 프론트엔드 빌드 ===${NC}"
    cd "$PROJECT_ROOT/frontend"
    
    echo "프론트엔드 빌드 중..."
    if npm run build; then
        echo -e "${GREEN}✓ 프론트엔드 빌드 완료${NC}"
    else
        echo -e "${RED}❌ 프론트엔드 빌드 실패${NC}"
        exit 1
    fi
    echo ""
    
    cd "$PROJECT_ROOT"
fi

# 4. Helm 차트 확인
echo -e "${BLUE}=== 4. Helm 차트 확인 ===${NC}"
if [ ! -d "$CHART_PATH" ]; then
    echo -e "${RED}❌ Helm 차트를 찾을 수 없습니다: $CHART_PATH${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Helm 차트 경로 확인${NC}"

# Values 파일 확인
VALUES_FILE="$CHART_PATH/values.yaml"
if [ "$ENVIRONMENT" == "prod" ] || [ "$ENVIRONMENT" == "production" ]; then
    VALUES_FILE="$CHART_PATH/values-production.yaml"
fi

if [ ! -f "$VALUES_FILE" ]; then
    echo -e "${YELLOW}⚠ $VALUES_FILE을 찾을 수 없습니다. values.yaml을 사용합니다.${NC}"
    VALUES_FILE="$CHART_PATH/values.yaml"
fi
echo "Values 파일: $VALUES_FILE"
echo ""

# 5. 백엔드 재시작
if [ "$COMPONENT" == "all" ] || [ "$COMPONENT" == "backend" ]; then
    echo -e "${BLUE}=== 5. 백엔드 재시작 ===${NC}"
    
    DEPLOYMENT_NAME="${RELEASE_NAME}-api-backend"
    
    # Deployment 존재 확인
    if kubectl get deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" > /dev/null 2>&1; then
        echo "백엔드 Deployment 재시작 중..."
        if kubectl rollout restart deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE"; then
            echo -e "${GREEN}✓ 백엔드 재시작 명령 실행 완료${NC}"
            
            # 롤아웃 상태 확인
            echo "롤아웃 상태 확인 중..."
            if kubectl rollout status deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" --timeout=5m; then
                echo -e "${GREEN}✓ 백엔드 롤아웃 완료${NC}"
            else
                echo -e "${YELLOW}⚠ 백엔드 롤아웃이 완료되지 않았습니다. 수동으로 확인하세요.${NC}"
            fi
        else
            echo -e "${RED}❌ 백엔드 재시작 실패${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠ 백엔드 Deployment를 찾을 수 없습니다. Helm으로 배포합니다...${NC}"
        
        # Helm으로 배포
        HELM_CMD="helm upgrade --install $RELEASE_NAME $CHART_PATH \
          --namespace $NAMESPACE \
          -f $VALUES_FILE \
          --set apiBackend.enabled=true \
          --set frontend.enabled=false \
          --wait \
          --timeout 10m"
        
        if eval "$HELM_CMD"; then
            echo -e "${GREEN}✓ 백엔드 배포 완료${NC}"
        else
            echo -e "${RED}❌ 백엔드 배포 실패${NC}"
            exit 1
        fi
    fi
    echo ""
fi

# 6. 프론트엔드 재시작
if [ "$COMPONENT" == "all" ] || [ "$COMPONENT" == "frontend" ]; then
    echo -e "${BLUE}=== 6. 프론트엔드 재시작 ===${NC}"
    
    DEPLOYMENT_NAME="${RELEASE_NAME}-frontend"
    
    # Deployment 존재 확인
    if kubectl get deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" > /dev/null 2>&1; then
        echo "프론트엔드 Deployment 재시작 중..."
        if kubectl rollout restart deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE"; then
            echo -e "${GREEN}✓ 프론트엔드 재시작 명령 실행 완료${NC}"
            
            # 롤아웃 상태 확인
            echo "롤아웃 상태 확인 중..."
            if kubectl rollout status deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" --timeout=5m; then
                echo -e "${GREEN}✓ 프론트엔드 롤아웃 완료${NC}"
            else
                echo -e "${YELLOW}⚠ 프론트엔드 롤아웃이 완료되지 않았습니다. 수동으로 확인하세요.${NC}"
            fi
        else
            echo -e "${RED}❌ 프론트엔드 재시작 실패${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠ 프론트엔드 Deployment를 찾을 수 없습니다. Helm으로 배포합니다...${NC}"
        
        # Helm으로 배포
        HELM_CMD="helm upgrade --install $RELEASE_NAME $CHART_PATH \
          --namespace $NAMESPACE \
          -f $VALUES_FILE \
          --set apiBackend.enabled=false \
          --set frontend.enabled=true \
          --wait \
          --timeout 10m"
        
        if eval "$HELM_CMD"; then
            echo -e "${GREEN}✓ 프론트엔드 배포 완료${NC}"
        else
            echo -e "${RED}❌ 프론트엔드 배포 실패${NC}"
            exit 1
        fi
    fi
    echo ""
fi

# 7. 배포 후 검증
echo -e "${BLUE}=== 7. 배포 후 검증 ===${NC}"

# Pod 상태 확인
echo "Pod 상태 확인 중..."
sleep 3
kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/instance="$RELEASE_NAME"
echo ""

# 서비스 상태 확인
echo "서비스 상태 확인 중..."
kubectl get services -n "$NAMESPACE" -l app.kubernetes.io/instance="$RELEASE_NAME"
echo ""

# 배포 상태 확인
echo "배포 상태 확인 중..."
kubectl get deployments -n "$NAMESPACE" -l app.kubernetes.io/instance="$RELEASE_NAME"
echo ""

echo -e "${GREEN}✅ 배포 완료!${NC}"
echo ""
echo "다음 단계:"
echo "  1. Pod 로그 확인: kubectl logs -n $NAMESPACE -l app.kubernetes.io/instance=$RELEASE_NAME"
echo "  2. 서비스 접근 테스트: kubectl port-forward -n $NAMESPACE svc/${RELEASE_NAME}-api-backend 8080:8080"
echo "  3. 프론트엔드 접근 테스트: kubectl port-forward -n $NAMESPACE svc/${RELEASE_NAME}-frontend 3000:3000"
