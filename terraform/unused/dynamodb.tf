# DynamoDB 테이블 - 분석 결과 저장

resource "aws_dynamodb_table" "analysis_results" {
  name         = "${var.project_name}-analysis-results"
  billing_mode = var.dynamodb_billing_mode

  hash_key  = "analysis_id"
  range_key = "analyzed_at"

  attribute {
    name = "analysis_id"
    type = "S"
  }

  attribute {
    name = "analyzed_at"
    type = "S"
  }

  attribute {
    name = "platform"
    type = "S"
  }

  attribute {
    name = "keyword"
    type = "S"
  }

  # GSI - 플랫폼별 쿼리
  global_secondary_index {
    name            = "platform-index"
    hash_key        = "platform"
    range_key       = "analyzed_at"
    projection_type = "ALL"
  }

  # GSI - 키워드별 쿼리
  global_secondary_index {
    name            = "keyword-index"
    hash_key        = "keyword"
    range_key       = "analyzed_at"
    projection_type = "ALL"
  }

  # TTL 설정 (자동 삭제)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  # Point-in-time recovery (백업)
  point_in_time_recovery {
    enabled = true
  }

  # 서버 사이드 암호화
  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-analysis-results"
  }
}

# DynamoDB 출력
output "dynamodb_table_name" {
  description = "DynamoDB 테이블 이름"
  value       = aws_dynamodb_table.analysis_results.name
}

output "dynamodb_table_arn" {
  description = "DynamoDB 테이블 ARN"
  value       = aws_dynamodb_table.analysis_results.arn
}
