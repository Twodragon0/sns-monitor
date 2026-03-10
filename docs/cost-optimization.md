# 비용 최적화 가이드

## 월별 비용 예측

### 최소 구성 (~$15-20/월) ✅ 권장

이 구성으로 기본적인 모니터링이 가능합니다:

```hcl
# terraform.tfvars
enable_youtube = true
enable_telegram = true
enable_twitter = false
enable_instagram = false
enable_naver_cafe = false

crawl_schedule = "rate(1 hour)"
bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0"

enable_cloudwatch_logs = false
enable_waf = false
dynamodb_billing_mode = "PAY_PER_REQUEST"
```

**비용 구성**:
- Lambda 실행: $2-3
- DynamoDB (온디맨드): $2-3
- S3 저장: $1
- Bedrock Claude Haiku: $5-8
- CloudFront: $1-2
- API Gateway: $1
- **총합: $15-20/월**

### 표준 구성 (~$30-40/월)

더 빈번한 크롤링과 더 많은 플랫폼:

```hcl
enable_youtube = true
enable_telegram = true
enable_instagram = true

crawl_schedule = "rate(30 minutes)"
bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0"

enable_cloudwatch_logs = false
enable_waf = false
```

**비용 구성**:
- Lambda 실행: $5-8 (2배 빈도)
- DynamoDB: $5-8
- S3: $2
- Bedrock: $10-15
- CloudFront: $2-3
- **총합: $30-40/월**

### 실시간 구성 (~$120-150/월)

Twitter 포함, 15분마다 크롤링:

```hcl
enable_youtube = true
enable_telegram = true
enable_twitter = true  # +$100/월
enable_instagram = true

crawl_schedule = "rate(15 minutes)"
bedrock_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"

enable_cloudwatch_logs = true
enable_waf = true
```

**비용 구성**:
- Twitter API: $100 ⚠️
- Lambda: $10-15
- DynamoDB: $8-12
- Bedrock Sonnet: $20-30
- CloudWatch Logs: $3-5
- WAF: $8-10
- **총합: $150-170/월**

---

## 비용 절감 전략

### 1. 크롤링 빈도 조절 (가장 효과적) 💰

크롤링 빈도가 비용에 가장 큰 영향을 미칩니다.

| 빈도 | Lambda 호출/월 | 예상 비용 | 사용 사례 |
|------|----------------|-----------|-----------|
| 15분 | 2,880 | $10-15 | 실시간 모니터링 |
| 30분 | 1,440 | $5-8 | 표준 모니터링 (권장) |
| 1시간 | 720 | $2-3 | 비용 절감 |
| 2시간 | 360 | $1-2 | 최소 모니터링 |

**추천 설정**:
```hcl
# 근무 시간만 크롤링 (비용 70% 절감)
crawl_schedule = "cron(0 9-18 ? * MON-FRI *)"  # 평일 9-18시만
```

### 2. Twitter API 대신 Chrome Extension 사용 (-$100/월) 💰💰💰

Twitter API는 월 $100이 발생합니다. Chrome Extension으로 대체하면:

**Chrome Extension 장점**:
- ✅ 완전 무료
- ✅ API 제한 없음
- ✅ 실시간 수동 수집

**단점**:
- ❌ 자동화 불가
- ❌ 수동 작업 필요

**추천**: Twitter는 Extension으로만 수집

### 3. Bedrock 모델 선택 (-60% AI 비용) 💰💰

| 모델 | 입력 비용 | 1,000건 분석 시 | 성능 |
|------|-----------|----------------|------|
| Claude 3 Haiku | $0.25/1M 토큰 | ~$5 | 빠름 |
| Claude 3.5 Sonnet | $3.00/1M 토큰 | ~$30 | 고성능 |

**추천**: 대부분의 경우 Haiku로 충분

```hcl
bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0"
```

### 4. CloudWatch Logs 비활성화 (-$3-5/월) 💰

로깅은 디버깅 시에만 필요합니다.

```hcl
enable_cloudwatch_logs = false

# 문제 발생 시에만 활성화
# terraform apply -var="enable_cloudwatch_logs=true"
```

### 5. WAF 비활성화 (-$8-10/월) 💰

내부용이거나 트래픽이 적으면 WAF 불필요:

```hcl
enable_waf = false
enable_api_key = true  # API Key 인증으로 대체 (무료)
```

### 6. S3 수명 주기 정책 활용 (-$2-3/월) 💰

```hcl
# s3.tf에 이미 포함됨
# 30일 후 Glacier로 이동
# 90일 후 자동 삭제
```

### 7. DynamoDB TTL 설정 (-$2-3/월) 💰

```hcl
dynamodb_ttl_days = 90  # 90일 후 자동 삭제

# 더 짧게 설정 가능
dynamodb_ttl_days = 30  # 30일 후 삭제
```

### 8. 플랫폼 선택적 활성화

필요한 플랫폼만 활성화:

```hcl
# 무료 플랫폼만 사용 (권장)
enable_youtube = true      # 무료 (10,000 유닛/일)
enable_telegram = true     # 무료
enable_twitter = false     # $100/월
enable_instagram = false   # 제한적
```

### 9. 샘플링으로 AI 분석 비용 절감

LLM 분석기에서 이미 구현됨:

```python
# lambda/llm-analyzer/lambda_function.py
# 최대 50개만 샘플링하여 분석
sample_texts = texts[:50] if len(texts) > 50 else texts
```

### 10. Chrome Extension으로 API 비용 제로화

**시나리오**: Twitter, Instagram 등 유료 API 회피

```bash
# terraform.tfvars
enable_twitter = false
enable_instagram = false
enable_chrome_extension_api = true
```

**사용법**:
1. Twitter, Instagram 방문
2. Extension으로 수동 수집
3. API 비용 0원

---

## 비용 모니터링

### AWS Cost Explorer 활용

```bash
# 월별 비용 확인
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost

# 서비스별 비용 확인
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

### 비용 알림 설정

AWS Budgets로 예산 초과 알림:

```bash
# AWS Console → Budgets
# 1. 월 예산 설정 (예: $30)
# 2. 80% 도달 시 이메일 알림
# 3. 100% 초과 시 알림
```

### CloudWatch 대시보드

```bash
# Lambda 호출 횟수 모니터링
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=sns-monitor-youtube-crawler \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-31T23:59:59Z \
  --period 86400 \
  --statistics Sum
```

---

## 실제 비용 예시

### 케이스 1: 스타트업 (최소 구성)

**요구사항**:
- YouTube, Telegram만 모니터링
- 1시간마다 크롤링
- 3개 키워드

**설정**:
```hcl
enable_youtube = true
enable_telegram = true
crawl_schedule = "rate(1 hour)"
bedrock_model_id = "claude-3-haiku"
enable_cloudwatch_logs = false
```

**월별 비용**: $15-18

### 케이스 2: 중소기업 (표준 구성)

**요구사항**:
- YouTube, Telegram, Instagram
- 30분마다 크롤링
- 5개 키워드
- Slack 알림

**설정**:
```hcl
enable_youtube = true
enable_telegram = true
enable_instagram = true
crawl_schedule = "rate(30 minutes)"
bedrock_model_id = "claude-3-haiku"
slack_webhook_url = "https://hooks.slack.com/..."
```

**월별 비용**: $30-35

### 케이스 3: 대기업 (실시간 구성)

**요구사항**:
- 모든 플랫폼 (Twitter 포함)
- 15분마다 크롤링
- 10개 키워드
- 고성능 AI 분석
- WAF, 로깅 활성화

**설정**:
```hcl
enable_youtube = true
enable_telegram = true
enable_twitter = true
enable_instagram = true
crawl_schedule = "rate(15 minutes)"
bedrock_model_id = "claude-3-5-sonnet"
enable_waf = true
enable_cloudwatch_logs = true
```

**월별 비용**: $150-170

---

## 비용 절감 체크리스트

배포 전:

- [ ] Twitter API 정말 필요한가? → Chrome Extension 고려
- [ ] 크롤링 빈도는 적절한가? → 1시간 이상 권장
- [ ] Haiku 모델로 충분한가? → 대부분 충분
- [ ] CloudWatch Logs 필요한가? → 프로덕션에서는 비활성화
- [ ] WAF 필요한가? → 내부용이면 불필요
- [ ] Instagram 정말 필요한가? → 공개 계정만 가능

배포 후:

- [ ] 실제 비용 확인 (1주일 후)
- [ ] 불필요한 플랫폼 비활성화
- [ ] Lambda 호출 횟수 확인
- [ ] DynamoDB 읽기/쓰기 확인
- [ ] S3 저장 용량 확인
- [ ] Bedrock 토큰 사용량 확인

---

## FAQ

### Q: $100 예산으로 가능한가요?

A: 네, 충분합니다. Twitter를 제외하면 월 $15-40 정도입니다.

**추천 구성**:
- YouTube + Telegram (무료 API)
- 1시간마다 크롤링
- Claude 3 Haiku
- Chrome Extension으로 Twitter 보완

### Q: 비용을 $10 이하로 줄일 수 있나요?

A: 가능하지만 기능이 제한됩니다:

```hcl
# 최소 최소 구성
enable_youtube = true  # YouTube만
crawl_schedule = "rate(2 hours)"  # 2시간마다
bedrock_model_id = "claude-3-haiku"
enable_cloudwatch_logs = false
enable_chrome_extension_api = true  # 수동 수집 병행
```

**예상 비용**: $8-12/월

### Q: Twitter API 없이 Twitter 모니터링 가능한가요?

A: 네, Chrome Extension으로 가능합니다:

1. Extension 설치
2. Twitter 방문
3. 수동으로 데이터 수집
4. 자동 분석

**제약**: 자동화 불가, 수동 작업 필요

### Q: 비용이 갑자기 증가했어요

**확인사항**:
1. Lambda 호출 횟수 증가?
2. DynamoDB 읽기/쓰기 증가?
3. Bedrock 토큰 사용량 증가?
4. S3 저장 용량 증가?

**해결**:
```bash
# CloudWatch에서 Lambda 호출 확인
aws logs tail /aws/lambda/your-function-name --follow

# 비용 상세 확인
aws ce get-cost-and-usage --time-period Start=YYYY-MM-DD,End=YYYY-MM-DD --granularity DAILY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE
```

### Q: 무료 티어는 얼마나 되나요?

**AWS 무료 티어 (12개월)**:
- Lambda: 100만 요청/월
- DynamoDB: 25GB 저장, 25 WCU/RCU
- S3: 5GB 저장, 20,000 GET, 2,000 PUT

**주의**: Bedrock은 무료 티어 없음

---

## 결론

**최적 구성 추천**:

```hcl
# 비용 대비 성능이 가장 좋은 구성
project_name = "sns-monitor"
search_keywords = ["Levvels", "Vuddy", "굿즈"]

# 무료 플랫폼만 사용
enable_youtube = true
enable_telegram = true
enable_twitter = false  # Chrome Extension 사용

# 1시간 주기 (비용과 실시간성 균형)
crawl_schedule = "rate(1 hour)"

# Claude Haiku (충분한 성능)
bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0"

# 비용 절감 옵션
enable_cloudwatch_logs = false
enable_waf = false
dynamodb_billing_mode = "PAY_PER_REQUEST"
```

**예상 비용**: $15-20/월

**이 구성으로**:
- ✅ 2개 플랫폼 모니터링
- ✅ 24시간 자동 크롤링
- ✅ AI 분석 및 알림
- ✅ 웹 대시보드
- ✅ Chrome Extension 보완
- ✅ 월 $20 이하

---

**다음 문서**: [Deployment Guide](deployment-guide.md)
