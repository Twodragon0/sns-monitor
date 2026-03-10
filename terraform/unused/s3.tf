# S3 버킷 - 원본 데이터 저장

# 크롤링 데이터 저장 버킷
resource "aws_s3_bucket" "crawled_data" {
  bucket = "${var.project_name}-crawled-data-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-crawled-data"
  }
}

# 버킷 암호화
resource "aws_s3_bucket_server_side_encryption_configuration" "crawled_data" {
  bucket = aws_s3_bucket.crawled_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 퍼블릭 액세스 차단
resource "aws_s3_bucket_public_access_block" "crawled_data" {
  bucket = aws_s3_bucket.crawled_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 수명 주기 정책 (비용 절감)
resource "aws_s3_bucket_lifecycle_configuration" "crawled_data" {
  bucket = aws_s3_bucket.crawled_data.id

  rule {
    id     = "archive-old-data"
    status = "Enabled"

    filter {
      prefix = ""
    }

    # 30일 후 Glacier로 이동
    transition {
      days          = 30
      storage_class = "GLACIER"
    }

    # 90일 후 삭제
    expiration {
      days = 90
    }
  }
}

# 프론트엔드 호스팅 버킷
resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project_name}-frontend-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-frontend"
  }
}

# 프론트엔드 암호화
resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 프론트엔드 퍼블릭 액세스 차단 (CloudFront를 통해서만 접근)
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CloudFront OAC (Origin Access Control)
resource "aws_cloudfront_origin_access_control" "frontend" {
  count = var.enable_cloudfront ? 1 : 0

  name                              = "${var.project_name}-frontend-oac"
  description                       = "OAC for frontend S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# S3 버킷 정책 - CloudFront 접근 허용 (CloudFront 활성화 시에만 생성)
resource "aws_s3_bucket_policy" "frontend" {
  count  = var.enable_cloudfront ? 1 : 0
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontAccess"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend.arn}/*"
      }
    ]
  })
}

# S3 출력
output "crawled_data_bucket_name" {
  description = "크롤링 데이터 S3 버킷 이름"
  value       = aws_s3_bucket.crawled_data.id
}

output "frontend_bucket_name" {
  description = "프론트엔드 S3 버킷 이름"
  value       = aws_s3_bucket.frontend.id
}
