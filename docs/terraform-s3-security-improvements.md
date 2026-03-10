# Terraform S3 보안 강화 및 태깅 정책 적용

## 변경 사항 요약

### 1. 태깅 정책 적용

모든 리소스에 필수 태그를 추가했습니다:

- **name**: 리소스의 사람이 읽을 수 있는 이름 (소문자)
- **service**: 서비스 식별자 (소문자, 사전 정의된 목록)
- **env**: 배포 환경 (dev, sbx, prod 중 하나)
- **team**: 리소스를 관리하는 팀 식별자 (소문자)
- **group**: 리소스 그룹화를 위한 식별자 (소문자)

### 2. 보안 강화 사항

#### ✅ 버전 관리 (Versioning)
- 모든 객체 버전 관리 활성화
- 실수로 삭제된 데이터 복구 가능
- MFA 삭제 옵션 제공 (필요시 활성화 가능)

#### ✅ 암호화 (Encryption)
- 서버 사이드 암호화 (SSE-S3, AES256)
- 버킷 키 활성화로 비용 최적화
- 암호화 없이 업로드 차단 (버킷 정책)

#### ✅ 퍼블릭 액세스 차단
- 모든 퍼블릭 액세스 차단
- ACL 비활성화
- 버킷 소유권 제어 (BucketOwnerEnforced)

#### ✅ 보안 정책
- HTTPS 연결만 허용 (비보안 연결 차단)
- 암호화 없이 업로드 차단
- 최소 권한 원칙 적용

#### ✅ 액세스 로깅
- 별도의 액세스 로그 버킷 생성
- 모든 접근 기록 저장
- 감사 및 보안 모니터링 가능

#### ✅ Lifecycle 정책
- 비용 최적화를 위한 자동 스토리지 클래스 전환
- 오래된 데이터 자동 삭제
- 버전 관리 비용 최적화

## 파일 구조

```
terraform/
├── main.tf              # Provider 설정 (태깅 정책 적용)
├── variables.tf         # 태깅 정책 변수 추가
└── s3.tf                # S3 버킷 설정 (보안 강화)
```

## 주요 리소스

### 1. 크롤러 데이터 버킷
- **이름**: `sns-monitor-data-{account-id}`
- **용도**: 크롤러 데이터 저장 (YouTube, DCInside 등)
- **보안**: 모든 보안 기능 적용

### 2. 액세스 로그 버킷
- **이름**: `sns-monitor-access-logs-{account-id}`
- **용도**: 크롤러 데이터 버킷의 접근 로그 저장
- **보안**: 동일한 보안 수준 적용

## 사용 방법

### 변수 설정

`terraform/variables.tf`에서 기본값을 확인하거나 `terraform.tfvars` 파일로 오버라이드:

```hcl
service = "sns-monitor"
env     = "dev"
team    = "platform"
group   = "data-storage"
```

### 배포

```bash
# Terraform 초기화
terraform init

# 변경 사항 확인
terraform plan

# 적용
terraform apply
```

## 보안 체크리스트

- [x] 버전 관리 활성화
- [x] 서버 사이드 암호화 (AES256)
- [x] 퍼블릭 액세스 차단
- [x] 버킷 소유권 제어
- [x] HTTPS만 허용
- [x] 암호화 없이 업로드 차단
- [x] 액세스 로깅 활성화
- [x] Lifecycle 정책 설정
- [x] 태깅 정책 준수
- [x] IAM 정책 최소 권한 원칙

## 추가 보안 권장사항

### 1. MFA 삭제 활성화 (선택사항)

MFA 디바이스가 설정되어 있다면 버전 관리에서 MFA 삭제를 활성화할 수 있습니다:

```hcl
resource "aws_s3_bucket_versioning" "crawler_data" {
  versioning_configuration {
    status     = "Enabled"
    mfa_delete = "Enabled"  # MFA 디바이스 필요
  }
}
```

### 2. KMS 암호화 (선택사항)

더 높은 보안이 필요한 경우 KMS 암호화로 변경:

```hcl
resource "aws_s3_bucket_server_side_encryption_configuration" "crawler_data" {
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
  }
}
```

### 3. 버킷 정책 추가 제한

특정 IP나 VPC 엔드포인트에서만 접근 허용:

```hcl
resource "aws_s3_bucket_policy" "crawler_data" {
  policy = jsonencode({
    Statement = [
      {
        Effect = "Deny"
        Principal = "*"
        Action = "s3:*"
        Resource = "${aws_s3_bucket.crawler_data.arn}/*"
        Condition = {
          IpAddress = {
            "aws:SourceIp" = ["!203.0.113.0/24"]  # 특정 IP만 허용
          }
        }
      }
    ]
  })
}
```

## 출력 값

Terraform 적용 후 다음 출력 값을 확인할 수 있습니다:

- `s3_bucket_name`: 크롤러 데이터 버킷 이름
- `s3_bucket_arn`: 크롤러 데이터 버킷 ARN
- `s3_access_logs_bucket_name`: 액세스 로그 버킷 이름
- `s3_access_logs_bucket_arn`: 액세스 로그 버킷 ARN
- `s3_access_policy_arn`: IAM 정책 ARN (EKS Pods에 연결)

## 참고 자료

- [AWS S3 보안 모범 사례](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
- [S3 버킷 정책 예제](https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-bucket-policies.html)
- [S3 버전 관리](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)















