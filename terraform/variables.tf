# GitHub OIDC 관련 변수만 정의
# (S3, DynamoDB, Secrets Manager 등은 EKS pods에서 직접 처리)

variable "aws_account_id" {
  description = "AWS Account ID"
  type        = string
  default     = ""  # Set via terraform.tfvars or environment variable
}

variable "github_org" {
  description = "GitHub organization name"
  type        = string
  default     = ""  # Set via terraform.tfvars or environment variable
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "sns-monitoring-system"
}

variable "eks_cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = ""  # Set via terraform.tfvars or environment variable
}

# Tagging policy variables
variable "service" {
  description = "Service identifier (lowercase, predefined list)"
  type        = string
  default     = "sns-monitor"
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.service))
    error_message = "Service must be lowercase alphanumeric with hyphens only."
  }
}

variable "env" {
  description = "Deployment environment (dev, sbx, or prod)"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "sbx", "prod"], var.env)
    error_message = "Environment must be one of: dev, sbx, prod."
  }
}

variable "team" {
  description = "Team identifier managing this resource (lowercase, free format)"
  type        = string
  default     = "platform"
  validation {
    condition     = can(regex("^[a-z0-9/-]+$", var.team))
    error_message = "Team must be lowercase alphanumeric with hyphens and slashes only."
  }
}

variable "group" {
  description = "Group identifier for resource grouping (lowercase, free format)"
  type        = string
  default     = "data-storage"
  validation {
    condition     = can(regex("^[a-z0-9/-]+$", var.group))
    error_message = "Group must be lowercase alphanumeric with hyphens and slashes only."
  }
}

# S3 관련 변수
variable "s3_bucket_name" {
  description = "S3 bucket name for SNS Monitor data backup"
  type        = string
  default     = ""  # Will be auto-generated as sns-monitor-data-{account_id} if empty
}

# Kubernetes 관련 변수
variable "kubernetes_namespace" {
  description = "Kubernetes namespace for SNS Monitor"
  type        = string
  default     = "sns-monitor"
}

# Pod Identity용 ServiceAccount
variable "sns_monitor_service_account_name" {
  description = "Kubernetes ServiceAccount name for SNS Monitor Pod Identity"
  type        = string
  default     = "sns-monitoring"
}
