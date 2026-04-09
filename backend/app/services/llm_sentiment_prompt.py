"""
LLM Sentiment Analysis Prompt Prototype
Phase 1: Claude Haiku-based sentiment analysis for sns-monitor

Usage:
    from llm_sentiment_prompt import analyze_sentiment_llm, detect_threats

    # Single text analysis
    result = analyze_sentiment_llm("정말 최고의 방송이었어요!")

    # Batch analysis (cost-efficient)
    results = analyze_sentiment_batch(["댓글1", "댓글2", ...])

    # Threat detection
    threats = detect_threats(["악성 댓글 텍스트"])
"""

import json
import os
from typing import Optional

# Prompt templates for Claude API
SENTIMENT_SYSTEM_PROMPT = """당신은 한국어/영어 소셜 미디어 댓글의 감성을 분석하는 전문가입니다.

분석 규칙:
1. 반어법과 비꼼을 정확히 감지하세요 (예: "진짜 최고다 ㅋㅋ" = 부정적)
2. VTuber/크리에이터 팬덤 용어를 이해하세요 (예: "갓", "레전드", "입덕", "탈덕")
3. 한국어 인터넷 축약어를 해석하세요 (예: "ㄹㅇ", "ㅇㅈ", "ㄴㄴ", "ㅋㅋ")
4. 맥락 없는 짧은 댓글도 최선을 다해 분류하세요
5. 이모티콘/이모지의 감성을 반영하세요"""

SENTIMENT_USER_PROMPT = """다음 댓글들의 감성을 분석해주세요. 각 댓글에 대해 JSON 배열로 응답하세요.

댓글 목록:
{comments}

응답 형식 (JSON 배열만 출력):
[
  {{
    "index": 0,
    "sentiment": "positive|negative|neutral|mixed",
    "confidence": 0.0-1.0,
    "emotion": "joy|anger|sadness|fear|surprise|disgust|neutral",
    "is_sarcasm": false,
    "summary": "2-3단어 요약"
  }}
]"""

THREAT_SYSTEM_PROMPT = """당신은 온라인 콘텐츠 위협 탐지 전문가입니다.
크리에이터/VTuber를 대상으로 한 위협적 댓글을 식별합니다.

위협 카테고리:
- HARASSMENT: 인신공격, 비하, 차별 발언
- DOXXING: 개인정보 노출 시도
- THREAT: 물리적/정신적 위협
- HATE_SPEECH: 혐오 발언
- SPAM: 스팸/홍보성 댓글
- NONE: 위협 없음

한국어 인터넷 은어와 우회 표현도 탐지하세요."""

THREAT_USER_PROMPT = """다음 댓글들에서 위협을 탐지해주세요.

댓글 목록:
{comments}

응답 형식 (JSON 배열만 출력):
[
  {{
    "index": 0,
    "threat_level": "none|low|medium|high|critical",
    "category": "NONE|HARASSMENT|DOXXING|THREAT|HATE_SPEECH|SPAM",
    "confidence": 0.0-1.0,
    "reason": "탐지 근거 1줄"
  }}
]"""


def build_sentiment_messages(comments: list[str]) -> list[dict]:
    """Build Claude API messages for sentiment analysis."""
    numbered = "\n".join(f"[{i}] {c}" for i, c in enumerate(comments))
    return [
        {"role": "user", "content": SENTIMENT_USER_PROMPT.format(comments=numbered)}
    ]


def build_threat_messages(comments: list[str]) -> list[dict]:
    """Build Claude API messages for threat detection."""
    numbered = "\n".join(f"[{i}] {c}" for i, c in enumerate(comments))
    return [
        {"role": "user", "content": THREAT_USER_PROMPT.format(comments=numbered)}
    ]


def parse_llm_response(response_text: str) -> list[dict]:
    """Parse JSON array from LLM response, handling markdown code blocks."""
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


# -- Integration point for platform_analyzer.py --
#
# Replace the keyword-based _analyze_sentiment() method with:
#
# async def _analyze_sentiment_llm(self, comments: list[str]) -> dict:
#     """LLM-based sentiment analysis using Claude Haiku."""
#     import anthropic
#     client = anthropic.Anthropic()  # or Bedrock client
#
#     messages = build_sentiment_messages(comments[:50])  # batch max 50
#     response = client.messages.create(
#         model="claude-haiku-4-5-20251001",  # or bedrock model ID
#         max_tokens=2048,
#         system=SENTIMENT_SYSTEM_PROMPT,
#         messages=messages,
#     )
#
#     results = parse_llm_response(response.content[0].text)
#     sentiment_dist = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
#     for r in results:
#         sentiment_dist[r["sentiment"]] += 1
#
#     return {
#         "overall_sentiment": max(sentiment_dist, key=sentiment_dist.get),
#         "sentiment_distribution": sentiment_dist,
#         "details": results,
#         "method": "llm",
#         "model": "claude-haiku",
#     }
#
# -- Cost estimate --
# Claude Haiku: ~$0.25/1M input tokens, ~$1.25/1M output tokens
# 50 comments × ~30 tokens/comment = 1,500 input tokens ≈ $0.000375
# Response ~500 tokens ≈ $0.000625
# Total per batch: ~$0.001 (갤러리 5개 + YouTube = 월 ~$15)


# Test samples for prompt prototyping
TEST_COMMENTS_KR = [
    "진짜 최고의 방송이었어요! 다음에도 꼭 해주세요",
    "ㅋㅋㅋ 진짜 최고다 이 퀄리티가... 돈 받고 해라",
    "입덕 완료ㅠㅠ 너무 귀여워",
    "이거 개인정보 아닌가? 조심해야 할 듯",
    "ㄹㅇ 노잼 탈덕각",
    "평범한 방송이었네요",
    "이런 쓰레기 컨텐츠는 처음 봄 ㅉㅉ",
    "아 진짜 감동이다... 눈물 날 뻔",
]

if __name__ == "__main__":
    print("=== Sentiment Analysis Prompt Test ===")
    messages = build_sentiment_messages(TEST_COMMENTS_KR)
    print(f"System prompt ({len(SENTIMENT_SYSTEM_PROMPT)} chars):")
    print(SENTIMENT_SYSTEM_PROMPT[:200] + "...")
    print(f"\nUser prompt ({len(messages[0]['content'])} chars):")
    print(messages[0]["content"])

    print("\n=== Threat Detection Prompt Test ===")
    threat_msgs = build_threat_messages(TEST_COMMENTS_KR)
    print(f"System prompt ({len(THREAT_SYSTEM_PROMPT)} chars):")
    print(THREAT_SYSTEM_PROMPT[:200] + "...")
    print(f"\nUser prompt ({len(threat_msgs[0]['content'])} chars):")
    print(threat_msgs[0]["content"])

    print("\n=== Cost Estimate ===")
    print("50 comments/batch: ~$0.001")
    print("5 galleries × 2hr cycle × 12/day: ~60 batches/day = $0.06/day")
    print("Monthly estimate: ~$1.8 (DCInside) + YouTube ~$13 = ~$15/month")
