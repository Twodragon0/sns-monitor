# 미사용 리소스 정리 보고서

## 📋 개요

SNS Monitoring System에서 미사용 IAM Role 및 ServiceAccount를 정리했습니다.

---

## ✅ 완료된 작업

### 1. 미사용 IAM Role 제거

#### `sns-monitor-s3-sync.platform.sa.dev`
- **파일**: `terraform/irsa-s3-sync.tf` 삭제
- **이유**: IRSA 방식에서 Pod Identity로 마이그레이션 완료
- **상태**: DEPRECATED로 표시되어 있었으며, 실제로는 사용되지 않음
- **조치**: Terraform 파일 삭제 완료

#### `sns-monitor-eks-deploy.iam.github`
- **파일**: `terraform/github-oidc.tf` 삭제
- **이유**: GitHub Actions 워크플로우에서 사용되지 않음
- **상태**: 정의만 되어 있고 실제 사용처 없음
- **조치**: Terraform 파일 삭제 완료

### 2. 미사용 변수 제거

#### `service_account_name` 변수
- **파일**: `terraform/variables.tf`, `terraform/terraform.tfvars`
- **이유**: `sns-monitor-s3-sync` ServiceAccount는 더 이상 사용되지 않음
- **현재 상태**: `sns-monitoring` ServiceAccount만 사용 (Pod Identity)
- **조치**: 변수 정의 및 참조 제거 완료

### 3. Pod Identity 설정 정리

#### `terraform/pod-identity.tf` 정리
- 주석 처리된 `s3_sync` Pod Identity Association 코드 제거
- `service_account_name` 변수 참조 제거
- 불필요한 output 제거

---

## 🔍 확인 필요 사항

### `sns-monitor-s3-sync` ServiceAccount (platform namespace)

**현재 상태:**
- Helm 차트에서는 `sns-monitoring` ServiceAccount만 생성됨
- `sns-monitor-s3-sync` ServiceAccount는 Helm 차트에서 생성하지 않음

**확인 방법:**
```bash
# platform namespace에서 ServiceAccount 확인
kubectl get serviceaccount -n platform | grep sns-monitor

# 만약 sns-monitor-s3-sync가 존재한다면 삭제
kubectl delete serviceaccount sns-monitor-s3-sync -n platform
```

**권장 조치:**
- platform namespace에 `sns-monitor-s3-sync` ServiceAccount가 수동으로 생성되어 있다면 삭제
- Helm 차트는 `sns-monitoring` ServiceAccount만 사용하므로 안전하게 삭제 가능

---

## ✅ ServiceAccount Pod Identity 상태 확인

### `sns-monitoring` ServiceAccount

**현재 상태:**
- ✅ **Pod Identity 설정 완료**
- **RoleArn**: `arn:aws:iam::123456789012:role/sns-monitor-pod-identity.platform.dev`
- **AssociationId**: `a-fcoj8usbety7s1xia`
- **Namespace**: `platform`
- **용도**: S3 접근 (s3-sync CronJob 포함)

**확인 명령어:**
```bash
aws eks describe-pod-identity-association \
  --profile your-cluster \
  --region ap-northeast-2 \
  --cluster-name your-cluster \
  --association-id a-fcoj8usbety7s1xia
```

### `sns-monitor-scaler` ServiceAccount

**현재 상태:**
- ✅ **Pod Identity 불필요** (올바른 구성)
- **기능**: Kubernetes Deployment/StatefulSet 스케일링 (scale up/down)
- **AWS 리소스 접근**: 없음
- **인증 방식**: Kubernetes RBAC만 사용

**Pod Identity 필요성:**
- ❌ **불필요**: Kubernetes 리소스만 조작하므로 Pod Identity가 필요 없음
- ✅ **현재 상태**: ServiceAccount는 RBAC Role만 사용 (올바름)

**현재 구성:**
```yaml
# ServiceAccount for scaler
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "sns-monitor.fullname" . }}-scaler

# Role for scaling (Kubernetes RBAC만 사용)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
rules:
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets"]
    verbs: ["get", "patch", "update"]
```

**결론:**
- Pod Identity 설정 불필요
- 현재 구성이 올바름 (RBAC만 사용)

---

## 📝 Terraform 적용 방법

### 1. Terraform Plan 실행
```bash
cd terraform
terraform plan
```

### 2. 변경 사항 확인
다음 리소스가 삭제될 예정:
- `aws_iam_role.sns_monitor_eks_deploy` (github-oidc.tf)
- `aws_iam_policy.eks_deploy` (github-oidc.tf)
- `aws_iam_role_policy_attachment.eks_deploy` (github-oidc.tf)

**참고**: `sns-monitor-s3-sync.platform.sa.dev` Role은 이미 주석 처리되어 있었으므로 Terraform state에 없을 수 있습니다. AWS Console에서 직접 확인 후 삭제가 필요할 수 있습니다.

### 3. Terraform Apply 실행
```bash
terraform apply
```

### 4. AWS Console에서 수동 확인 (필요시)
```bash
# IAM Role 확인
aws iam list-roles --query 'Roles[?contains(RoleName, `sns-monitor`)].RoleName'

# 미사용 Role이 있다면 삭제
aws iam delete-role --role-name sns-monitor-s3-sync.platform.sa.dev
aws iam delete-role --role-name sns-monitor-eks-deploy.iam.github
```

---

## 📊 정리 요약

| 리소스 | 타입 | 상태 | 조치 |
|--------|------|------|------|
| `sns-monitor-s3-sync.platform.sa.dev` | IAM Role | 미사용 | Terraform 파일 삭제 완료 |
| `sns-monitor-eks-deploy.iam.github` | IAM Role | 미사용 | Terraform 파일 삭제 완료 |
| `sns-monitor-s3-sync` | ServiceAccount | 미사용 | Helm에서 생성하지 않음 (수동 확인 필요) |
| `sns-monitor-scaler` | ServiceAccount | 사용 중 | Pod Identity 불필요 (RBAC만 사용) |

---

## 🔒 보안 고려사항

1. **최소 권한 원칙**: 미사용 Role 제거로 보안 강화
2. **Pod Identity**: IRSA 대신 Pod Identity 사용으로 관리 간소화
3. **RBAC**: scaler는 Kubernetes RBAC만 사용 (올바른 구성)

---

**Last Updated**: 2025-12-30  
**Maintainer**: DevSecOps Team
