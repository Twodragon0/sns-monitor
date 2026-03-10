# SNS Monitor - S3 Bucket for Crawler Data Storage
#
# S3 버킷 구성:
# - sns-monitor-data: 크롤러 데이터 저장 (YouTube, DCInside 등)
# - 서버 사이드 암호화 (AES256)
# - 퍼블릭 액세스 차단
# - 버킷 소유권 제어
# - Lifecycle 정책 (비용 최적화)
#
# 비용 절감을 위해 버전 관리 및 액세스 로깅은 비활성화됨

# Local values for tag normalization (S3 tags don't support slashes)
locals {
  # Convert slashes to hyphens for S3 tags (S3 tag values don't support '/')
  team_tag  = replace(var.team, "/", "-")
  group_tag = replace(var.group, "/", "-")
}

resource "aws_s3_bucket" "crawler_data" {
  bucket = "sns-monitor-data-${data.aws_caller_identity.current.account_id}"

  tags = {
    # Required tags per tagging policy
    # Note: S3 tags don't support slashes, so we convert them to hyphens
    # S3 tags also have restrictions on special characters (only _ . : / = + - @ allowed)
    name    = "sns-monitor-crawler-data"
    service = var.service
    env     = var.env
    team    = local.team_tag
    group   = local.group_tag
    # Additional tags (avoid special characters like parentheses, commas)
    managed-by = "terraform"
  }
}

# Server-side encryption (AES256 - AWS managed keys)
resource "aws_s3_bucket_server_side_encryption_configuration" "crawler_data" {
  bucket = aws_s3_bucket.crawler_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "crawler_data" {
  bucket = aws_s3_bucket.crawler_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Bucket ownership controls (ACLs disabled for security)
resource "aws_s3_bucket_ownership_controls" "crawler_data" {
  bucket = aws_s3_bucket.crawler_data.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Lifecycle rules for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "crawler_data" {
  bucket = aws_s3_bucket.crawler_data.id

  rule {
    id     = "crawler-data-lifecycle"
    status = "Enabled"

    filter {
      prefix = "raw-data/"
    }

    # Move to Infrequent Access after 30 days
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    # Move to Glacier after 60 days
    transition {
      days          = 60
      storage_class = "GLACIER"
    }

    # Delete after 180 days
    expiration {
      days = 180
    }
  }

  rule {
    id     = "analysis-data-lifecycle"
    status = "Enabled"

    filter {
      prefix = "analysis/"
    }

    # Keep analysis data longer - transition to IA after 90 days
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    # Delete after 365 days
    expiration {
      days = 365
    }
  }
}

# Data source for current AWS account ID
data "aws_caller_identity" "current" {}

# Bucket policy for additional security
resource "aws_s3_bucket_policy" "crawler_data" {
  bucket = aws_s3_bucket.crawler_data.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureConnections"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.crawler_data.arn,
          "${aws_s3_bucket.crawler_data.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "DenyUnencryptedObjectUploads"
        Effect    = "Deny"
        Principal = "*"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.crawler_data.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "AES256"
          }
        }
      }
    ]
  })
}

# IAM Policy for S3 access (to be attached to EKS pods)
resource "aws_iam_policy" "s3_crawler_access" {
  name        = "sns-monitor-s3-crawler-access-${var.env}"
  description = "Policy for SNS Monitor crawlers to access S3 bucket"

  tags = {
    name    = "sns-monitor-s3-crawler-access"
    service = var.service
    env     = var.env
    team    = local.team_tag
    group   = local.group_tag
  }

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3BucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.crawler_data.arn,
          "${aws_s3_bucket.crawler_data.arn}/*"
        ]
      },
      {
        Sid    = "S3BucketEncryptionRequired"
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.crawler_data.arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption" = "AES256"
          }
        }
      }
    ]
  })
}

# Outputs
output "s3_bucket_name" {
  description = "Name of the S3 bucket for crawler data"
  value       = aws_s3_bucket.crawler_data.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for crawler data"
  value       = aws_s3_bucket.crawler_data.arn
}

output "s3_access_policy_arn" {
  description = "ARN of the IAM policy for S3 access"
  value       = aws_iam_policy.s3_crawler_access.arn
}
