# SNS Monitor - EKS Pod Identity
# IRSA 대신 Pod Identity를 사용하여 S3 접근 권한 부여
#
# Pod Identity는 IRSA보다 간단한 설정을 제공:
# - ServiceAccount에 annotation 불필요
# - aws_eks_pod_identity_association으로 직접 연결

# IAM Role for Pod Identity (Trust Policy가 IRSA와 다름)
data "aws_iam_policy_document" "pod_identity_assume_role" {
  statement {
    sid    = "AllowEKSPodIdentity"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }

    actions = [
      "sts:AssumeRole",
      "sts:TagSession"
    ]
  }
}

# IAM Role for SNS Monitor Pod Identity
resource "aws_iam_role" "sns_monitor_pod_identity" {
  name               = "sns-monitor-pod-identity.${var.kubernetes_namespace}.${var.env}"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_assume_role.json
  description        = "Pod Identity role for SNS Monitor in ${var.kubernetes_namespace} namespace"
}

# S3 Access Policy for Pod Identity
data "aws_iam_policy_document" "sns_monitor_s3_access" {
  # S3 버킷 읽기/쓰기 권한
  statement {
    sid    = "S3BucketAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation"
    ]
    resources = [
      data.aws_s3_bucket.sns_monitor_data.arn,
      "${data.aws_s3_bucket.sns_monitor_data.arn}/*"
    ]
  }

  # S3 Intelligent-Tiering 설정 권한
  statement {
    sid    = "S3IntelligentTiering"
    effect = "Allow"
    actions = [
      "s3:PutIntelligentTieringConfiguration",
      "s3:GetIntelligentTieringConfiguration"
    ]
    resources = [
      data.aws_s3_bucket.sns_monitor_data.arn
    ]
  }
}

resource "aws_iam_policy" "sns_monitor_pod_identity" {
  name        = "sns-monitor-pod-identity.${var.kubernetes_namespace}.${var.env}.policy"
  description = "S3 access policy for SNS Monitor Pod Identity"
  policy      = data.aws_iam_policy_document.sns_monitor_s3_access.json
}

resource "aws_iam_role_policy_attachment" "sns_monitor_pod_identity" {
  role       = aws_iam_role.sns_monitor_pod_identity.name
  policy_arn = aws_iam_policy.sns_monitor_pod_identity.arn
}

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

# EKS Pod Identity Association for S3 Sync
# s3-sync CronJob도 같은 sns-monitoring ServiceAccount를 사용하므로
# 별도의 Pod Identity Association이 필요 없습니다.

# Outputs
output "pod_identity_role_arn" {
  description = "IAM Role ARN for SNS Monitor Pod Identity"
  value       = aws_iam_role.sns_monitor_pod_identity.arn
}

output "pod_identity_association_id" {
  description = "EKS Pod Identity Association ID"
  value       = aws_eks_pod_identity_association.sns_monitor.association_id
}


output "pod_identity_setup_instructions" {
  value = <<-EOT

    === SNS Monitor Pod Identity 설정 완료 ===

    Pod Identity Association이 생성되었습니다:
    - Cluster: ${var.eks_cluster_name}
    - Namespace: ${var.kubernetes_namespace}
    - ServiceAccount: ${var.sns_monitor_service_account_name} (s3-sync도 동일한 ServiceAccount 사용)
    - IAM Role: ${aws_iam_role.sns_monitor_pod_identity.arn}

    ServiceAccount에 annotation이 필요 없습니다!
    Pod Identity Agent가 자동으로 AWS 자격 증명을 주입합니다.

    확인 방법:
    1. Pod Identity Association 확인:
       aws eks list-pod-identity-associations --cluster-name ${var.eks_cluster_name}

    2. Pod에서 AWS 자격 증명 확인:
       kubectl exec -it <pod-name> -n ${var.kubernetes_namespace} -- aws sts get-caller-identity

    3. S3 접근 테스트:
       kubectl exec -it <pod-name> -n ${var.kubernetes_namespace} -- aws s3 ls s3://${var.s3_bucket_name}/

    4. S3 Sync CronJob 테스트:
       kubectl get pods -n ${var.kubernetes_namespace} -l app.kubernetes.io/component=s3-sync
       kubectl exec -it <s3-sync-pod-name> -n ${var.kubernetes_namespace} -- aws s3 ls s3://${var.s3_bucket_name}/

  EOT
}
