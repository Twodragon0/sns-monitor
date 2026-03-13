# SNS Monitor - GitHub Actions OIDC for EKS Deployment
#
# 이 Terraform 구성은 GitHub Actions에서 EKS로 배포하기 위한
# IAM Role만 생성합니다. (S3, DynamoDB 등은 사용하지 않음)
#
# 사용법:
# 1. direnv allow (AWS 자격 증명 로드)
# 2. terraform init
# 3. terraform plan
# 4. terraform apply
# 5. output role_arn을 GitHub Secrets에 AWS_ROLE_ARN으로 설정

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.35"
    }
  }
}

provider "aws" {
  region = "ap-northeast-2"

  default_tags {
    tags = {
      # Tagging policy compliant tags
      name    = "sns-monitor"
      service = var.service
      env     = var.env
      team    = var.team
      group   = var.group
      # Additional tags
      managed-by = "terraform"
    }
  }
}
