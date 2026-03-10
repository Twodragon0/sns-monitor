# Secrets Manager - API 키 저장

# YouTube API 키
resource "aws_secretsmanager_secret" "youtube_api_key" {
  count = var.enable_youtube && var.youtube_api_key != "" ? 1 : 0

  name        = "${var.project_name}/youtube-api-key"
  description = "YouTube Data API v3 Key"

  tags = {
    Name = "${var.project_name}-youtube-api-key"
  }
}

resource "aws_secretsmanager_secret_version" "youtube_api_key" {
  count = var.enable_youtube && var.youtube_api_key != "" ? 1 : 0

  secret_id = aws_secretsmanager_secret.youtube_api_key[0].id
  secret_string = jsonencode({
    youtube_api_key = var.youtube_api_key
  })
}

# Twitter Bearer Token
resource "aws_secretsmanager_secret" "twitter_bearer_token" {
  count = var.enable_twitter && var.twitter_bearer_token != "" ? 1 : 0

  name        = "${var.project_name}/twitter-bearer-token"
  description = "Twitter API Bearer Token"

  tags = {
    Name = "${var.project_name}-twitter-bearer-token"
  }
}

resource "aws_secretsmanager_secret_version" "twitter_bearer_token" {
  count = var.enable_twitter && var.twitter_bearer_token != "" ? 1 : 0

  secret_id = aws_secretsmanager_secret.twitter_bearer_token[0].id
  secret_string = jsonencode({
    twitter_bearer_token = var.twitter_bearer_token
  })
}

# Telegram Bot Token
resource "aws_secretsmanager_secret" "telegram_bot_token" {
  count = var.enable_telegram && var.telegram_bot_token != "" ? 1 : 0

  name        = "${var.project_name}/telegram-bot-token"
  description = "Telegram Bot Token"

  tags = {
    Name = "${var.project_name}-telegram-bot-token"
  }
}

resource "aws_secretsmanager_secret_version" "telegram_bot_token" {
  count = var.enable_telegram && var.telegram_bot_token != "" ? 1 : 0

  secret_id = aws_secretsmanager_secret.telegram_bot_token[0].id
  secret_string = jsonencode({
    telegram_bot_token = var.telegram_bot_token
  })
}

# Instagram Access Token
resource "aws_secretsmanager_secret" "instagram_access_token" {
  count = var.enable_instagram && var.instagram_access_token != "" ? 1 : 0

  name        = "${var.project_name}/instagram-access-token"
  description = "Instagram Graph API Access Token"

  tags = {
    Name = "${var.project_name}-instagram-access-token"
  }
}

resource "aws_secretsmanager_secret_version" "instagram_access_token" {
  count = var.enable_instagram && var.instagram_access_token != "" ? 1 : 0

  secret_id = aws_secretsmanager_secret.instagram_access_token[0].id
  secret_string = jsonencode({
    instagram_access_token = var.instagram_access_token
  })
}

# Slack Webhook URL
resource "aws_secretsmanager_secret" "slack_webhook" {
  count = var.slack_webhook_url != "" ? 1 : 0

  name        = "${var.project_name}/slack-webhook-url"
  description = "Slack Webhook URL for notifications"

  tags = {
    Name = "${var.project_name}-slack-webhook"
  }
}

resource "aws_secretsmanager_secret_version" "slack_webhook" {
  count = var.slack_webhook_url != "" ? 1 : 0

  secret_id = aws_secretsmanager_secret.slack_webhook[0].id
  secret_string = jsonencode({
    slack_webhook_url = var.slack_webhook_url
  })
}

# Claude API Key (claude.ai)
resource "aws_secretsmanager_secret" "claude_api_key" {
  count = var.enable_multi_model_analysis && var.claude_api_key != "" ? 1 : 0

  name        = "${var.project_name}/claude-api-key"
  description = "Anthropic Claude API Key (claude.ai)"

  tags = {
    Name = "${var.project_name}-claude-api-key"
  }
}

resource "aws_secretsmanager_secret_version" "claude_api_key" {
  count = var.enable_multi_model_analysis && var.claude_api_key != "" ? 1 : 0

  secret_id = aws_secretsmanager_secret.claude_api_key[0].id
  secret_string = jsonencode({
    claude_api_key = var.claude_api_key
  })
}

# OpenAI API Key (Cursor Agents)
resource "aws_secretsmanager_secret" "openai_api_key" {
  count = var.enable_multi_model_analysis && var.openai_api_key != "" ? 1 : 0

  name        = "${var.project_name}/openai-api-key"
  description = "OpenAI API Key (for Cursor Agents)"

  tags = {
    Name = "${var.project_name}-openai-api-key"
  }
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  count = var.enable_multi_model_analysis && var.openai_api_key != "" ? 1 : 0

  secret_id = aws_secretsmanager_secret.openai_api_key[0].id
  secret_string = jsonencode({
    openai_api_key = var.openai_api_key
  })
}

# Secrets 출력
output "youtube_api_key_secret_arn" {
  description = "YouTube API Key Secret ARN"
  value       = var.enable_youtube && var.youtube_api_key != "" ? aws_secretsmanager_secret.youtube_api_key[0].arn : null
  sensitive   = true
}

output "telegram_bot_token_secret_arn" {
  description = "Telegram Bot Token Secret ARN"
  value       = var.enable_telegram && var.telegram_bot_token != "" ? aws_secretsmanager_secret.telegram_bot_token[0].arn : null
  sensitive   = true
}

output "claude_api_key_secret_arn" {
  description = "Claude API Key Secret ARN"
  value       = var.enable_multi_model_analysis && var.claude_api_key != "" ? aws_secretsmanager_secret.claude_api_key[0].arn : null
  sensitive   = true
}

output "openai_api_key_secret_arn" {
  description = "OpenAI API Key Secret ARN"
  value       = var.enable_multi_model_analysis && var.openai_api_key != "" ? aws_secretsmanager_secret.openai_api_key[0].arn : null
  sensitive   = true
}
