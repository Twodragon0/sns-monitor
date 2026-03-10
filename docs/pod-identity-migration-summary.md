# SNS Monitor: IRSA → Pod Identity 마이그레이션 완료 보고서

## 📋 개요

SNS Monitoring System의 s3-sync CronJob을 IRSA(IAM Roles for Service Accounts) 방식에서 **Pod Identity** 방식으로 마이그레이션하여 보안성과 관리 편의성을 향상시켰습니다.

---

## 🎯 작업 목표

1. **보안 강화**: Secret 기반 자격 증명 제거
2. **관리 간소화**: ServiceAccount annotation 불필요
3. **자동화**: Pod Identity Agent가 자동으로 AWS 자격 증명 주입

---

## 📝 주요 변경 사항

### 1. Terraform 구성 변경

#### `terraform/pod-identity.tf` 수정

**변경 전:**
- `sns-monitoring` ServiceAccount에 대한 Pod Identity만 설정

**변경 후:**
- S3 버킷 데이터 소스 추가
- s3-sync도 같은 `sns-monitoring` ServiceAccount 사용하므로 별도 설정 불필요
- 출력 메시지에 s3-sync 테스트 방법 추가

```terraform
# S3 버킷 데이터 소스 (s3-sync에서 사용)
# s3.tf의 data.aws_caller_identity.current 참조
data "aws_s3_bucket" "sns_monitor_data" {
  bucket = var.s3_bucket_name != "" ? var.s3_bucket_name : "sns-monitor-data-${data.aws_caller_identity.current.account_id}"
}

# EKS Pod Identity Association
# ServiceAccount와 IAM Role을 연결
resource "aws_eks_pod_identity_association" "sns_monitor" {
  cluster_name    = var.eks_cluster_name
  namespace       = var.kubernetes_namespace
  service_account = var.sns_monitor_service_account_name
  role_arn        = aws_iam_role.sns_monitor_pod_identity.arn

  tags = {
    Name = "sns-monitor-pod-identity"
  }
}
```

#### `terraform/irsa-s3-sync.tf` Deprecated 표시

```terraform
# SNS Monitor S3 Sync - IRSA (IAM Roles for Service Accounts)
# 
# ⚠️ DEPRECATED: 이 파일은 더 이상 사용되지 않습니다.
# Pod Identity를 사용하도록 변경되었습니다. (terraform/pod-identity.tf 참조)
#
# 이 파일은 참고용으로만 유지됩니다.
# 실제 배포에서는 terraform/pod-identity.tf의 Pod Identity를 사용합니다.
```

### 2. Helm 템플릿 변경

#### `helm/sns-monitor/templates/cronjob-s3-sync.yaml`

**제거된 항목:**
- `AWS_ACCESS_KEY_ID` 환경 변수 (Secret 기반)
- `AWS_SECRET_ACCESS_KEY` 환경 변수 (Secret 기반)

**변경 사항:**
```yaml
# 이전 (IRSA 방식)
env:
  - name: AWS_ACCESS_KEY_ID
    valueFrom:
      secretKeyRef:
        name: {{ include "sns-monitor.fullname" . }}-secrets
        key: aws-access-key-id
        optional: true
  - name: AWS_SECRET_ACCESS_KEY
    valueFrom:
      secretKeyRef:
        name: {{ include "sns-monitor.fullname" . }}-secrets
        key: aws-secret-access-key
        optional: true

# 변경 후 (Pod Identity 방식)
env:
  - name: AWS_DEFAULT_REGION
    value: "{{ .Values.config.awsRegion | default "ap-northeast-2" }}"
  # Pod Identity를 사용하므로 AWS 자격증명 환경 변수 불필요
  # Pod Identity Agent가 자동으로 AWS 자격 증명을 주입합니다
```

**ServiceAccount 명시:**
```yaml
spec:
  template:
    spec:
      # Pod Identity를 사용하므로 ServiceAccount 명시 필요
      serviceAccountName: {{ .Values.serviceAccount.name | default (include "sns-monitor.fullname" .) }}
```

---

## 🔄 마이그레이션 전후 비교

| 항목 | IRSA 방식 (이전) | Pod Identity 방식 (현재) |
|------|-----------------|------------------------|
| **ServiceAccount Annotation** | ✅ 필요 (`eks.amazonaws.com/role-arn`) | ❌ 불필요 |
| **Secret 기반 자격 증명** | ✅ 필요 (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) | ❌ 불필요 |
| **자동 자격 증명 주입** | ❌ 수동 설정 필요 | ✅ Pod Identity Agent 자동 주입 |
| **설정 복잡도** | 높음 | 낮음 |
| **보안성** | Secret 관리 필요 | 자동 관리 |

---

## ✅ 검증 결과

### 1. Terraform Plan/Apply

```bash
# Plan 결과
Plan: 0 to add, 1 to change, 0 to destroy

# Apply 결과
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

### 2. Pod Identity Association 확인

```bash
$ aws eks list-pod-identity-associations --cluster-name your-cluster --namespace platform

{
    "associations": [
        {
            "clusterName": "your-cluster",
            "namespace": "platform",
            "serviceAccount": "sns-monitoring",
            "associationArn": "arn:aws:eks:ap-northeast-2:123456789012:podidentityassociation/your-cluster/a-fcoj8usbety7s1xia",
            "associationId": "a-fcoj8usbety7s1xia"
        }
    ]
}
```

### 3. ServiceAccount 확인

```bash
$ kubectl get serviceaccount sns-monitoring -n platform -o jsonpath='{.metadata.annotations}'

{"meta.helm.sh/release-name":"sns-monitor","meta.helm.sh/release-namespace":"platform"}
```

**✅ Annotation 없음 확인** - Pod Identity 사용 중

### 4. s3-sync Pod 환경 변수 확인

```bash
$ kubectl exec -n platform <s3-sync-pod> -- env | grep AWS_

AWS_DEFAULT_REGION=ap-northeast-2
AWS_STS_REGIONAL_ENDPOINTS=regional
AWS_CONTAINER_CREDENTIALS_FULL_URI=http://169.254.170.23/v1/credentials
AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE=/var/run/secrets/pods.eks.amazonaws.com/serviceaccount/eks-pod-identity-token
```

**✅ Pod Identity 환경 변수 자동 주입 확인**

### 5. s3-sync 실행 결과

```
📤 /app/local-data → s3://sns-monitor-data/data/
📁 vuddy
  ✅ vuddy/comprehensive_analysis/barabara-members.json
  ✅ vuddy/comprehensive_analysis/skoshism-members.json
  ...
📁 youtube
  ✅ youtube/channels/시니초코 레이토/2025-12-29-00-03-12.json
  ✅ youtube/channels/아오세이 준/2025-12-29-00-02-41.json
  ...
📊 ok=67 skip=8622 err=0 cleaned=0
✅ Done
```

**✅ S3 접근 및 업로드 성공 확인**

---

## 🔐 보안 개선 사항

### 제거된 보안 위험 요소

- [x] Secret에 저장된 AWS 자격 증명 제거
- [x] ServiceAccount annotation 관리 불필요
- [x] 자격 증명 로테이션 수동 관리 불필요

### 추가된 보안 기능

- [x] Pod Identity Agent가 자동으로 임시 자격 증명 발급
- [x] 자격 증명이 Pod 수명에 맞춰 자동 만료
- [x] AWS IAM Role 기반 세분화된 권한 관리

---

## 📊 아키텍처 변경

### 이전 (IRSA)

```
┌─────────────────────────────────────────┐
│  s3-sync CronJob                        │
│  ┌───────────────────────────────────┐  │
│  │ ServiceAccount                    │  │
│  │ (eks.amazonaws.com/role-arn)      │  │
│  └───────────┬───────────────────────┘  │
│              │                           │
│              ▼                           │
│  ┌───────────────────────────────────┐  │
│  │ OIDC Provider                     │  │
│  │ (Web Identity Token)              │  │
│  └───────────┬───────────────────────┘  │
│              │                           │
│              ▼                           │
│  ┌───────────────────────────────────┐  │
│  │ IAM Role (IRSA)                   │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 현재 (Pod Identity)

```
┌─────────────────────────────────────────┐
│  s3-sync CronJob                        │
│  ┌───────────────────────────────────┐  │
│  │ ServiceAccount                     │  │
│  │ (Annotation 불필요)                │  │
│  └───────────┬───────────────────────┘  │
│              │                           │
│              ▼                           │
│  ┌───────────────────────────────────┐  │
│  │ Pod Identity Agent                 │  │
│  │ (자동 자격 증명 주입)              │  │
│  └───────────┬───────────────────────┘  │
│              │                           │
│              ▼                           │
│  ┌───────────────────────────────────┐  │
│  │ IAM Role (Pod Identity)           │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 🚀 배포 및 테스트 절차

### 1. Terraform 적용

```bash
cd terraform
export AWS_PROFILE=your-cluster
terraform init -upgrade
terraform plan -out=tfplan
terraform apply tfplan
```

### 2. Pod Identity Association 확인

```bash
aws eks list-pod-identity-associations \
  --cluster-name your-cluster \
  --namespace platform \
  --region ap-northeast-2
```

### 3. s3-sync 테스트

```bash
# 수동 Job 생성
kubectl create job --from=cronjob/sns-monitor-s3-sync \
  sns-monitor-s3-sync-test-$(date +%s) \
  -n platform

# 로그 확인
kubectl logs -n platform -l job-name=<job-name> --tail=50
```

### 4. 환경 변수 확인

```bash
kubectl exec -n platform <pod-name> -- env | grep AWS_
```

---

## 📝 참고 사항

### Pod Identity vs IRSA

| 특징 | Pod Identity | IRSA |
|------|-------------|------|
| **설정 방법** | `aws_eks_pod_identity_association` | ServiceAccount annotation |
| **자격 증명 주입** | Pod Identity Agent 자동 | OIDC Web Identity Token |
| **지원 클러스터** | EKS 1.24+ | EKS 1.21+ |
| **관리 복잡도** | 낮음 | 중간 |

### 현재 설정

- **Cluster**: `your-cluster`
- **Namespace**: `platform`
- **ServiceAccount**: `sns-monitoring`
- **IAM Role**: `arn:aws:iam::123456789012:role/sns-monitor-pod-identity.platform.dev`
- **Association ID**: `a-fcoj8usbety7s1xia`

---

## ✅ 체크리스트

### 마이그레이션 완료 항목

- [x] Terraform 코드 수정 (pod-identity.tf)
- [x] Helm 템플릿 수정 (cronjob-s3-sync.yaml)
- [x] Secret 기반 자격 증명 제거
- [x] irsa-s3-sync.tf Deprecated 표시
- [x] Terraform plan 검증
- [x] Terraform apply 완료
- [x] Pod Identity Association 생성 확인
- [x] ServiceAccount annotation 제거 확인
- [x] s3-sync Pod 환경 변수 확인
- [x] S3 접근 테스트 성공
- [x] 실제 데이터 동기화 성공

---

## 🎉 결론

s3-sync CronJob이 성공적으로 **IRSA에서 Pod Identity로 마이그레이션**되었습니다.

### 주요 성과

1. ✅ **보안 강화**: Secret 기반 자격 증명 제거
2. ✅ **관리 간소화**: ServiceAccount annotation 불필요
3. ✅ **자동화**: Pod Identity Agent가 자동으로 자격 증명 주입
4. ✅ **검증 완료**: 모든 테스트 통과

### 다음 단계 (완료)

- [x] 다른 CronJob들도 Pod Identity로 마이그레이션 검토
  - 모든 CronJob이 이미 같은 `sns-monitoring` ServiceAccount 사용
  - Pod Identity가 자동으로 적용됨
  - ServiceAccount 명시적 설정으로 변경 완료
- [x] IRSA 관련 리소스 정리 (irsa-s3-sync.tf 제거 고려)
  - irsa-s3-sync.tf의 모든 리소스를 주석 처리 완료
  - 파일은 참고용으로 유지 (필요시 삭제 가능)
- [x] 문서화 업데이트
  - SYSTEM_ARCHITECTURE.md 업데이트 완료
  - README.md에 Pod Identity 섹션 추가 완료
  - 마이그레이션 보고서 업데이트 완료

---

**작업 완료일**: 2025-12-29  
**작업자**: DevSecOps Team  
**환경**: your-cluster (EKS 1.33)

