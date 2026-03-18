"""
Local LLM analysis service.
Supports OpenAI (ChatGPT) and Anthropic (Claude) APIs directly,
without requiring an external AI analysis service.

Authentication modes:
1. Direct API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY)
2. OAuth access token (from OpenAI OAuth login flow)
"""

import json
import logging
from typing import Optional

from ..config import Config

logger = logging.getLogger(__name__)

# System prompt for SNS analysis
_SYSTEM_PROMPT = """당신은 SNS 데이터 분석 전문가입니다. 수집된 소셜 미디어 데이터를 분석하여 다음을 제공합니다:

1. **핵심 요약**: 주요 내용과 트렌드를 3-5문장으로 요약
2. **감성 분석**: 긍정/부정/중립 비율과 주요 감성 키워드
3. **주요 토픽**: 가장 많이 논의되는 주제 5개
4. **주요 의견**: 대표적인 의견 3-5개 (긍정/부정 각각)
5. **인사이트**: 데이터에서 발견된 흥미로운 패턴이나 인사이트

분석 결과는 한국어로 작성하고, 구조화된 JSON 형식으로 반환하세요."""

_RESPONSE_FORMAT_HINT = """
응답은 반드시 아래 JSON 형식으로만 반환하세요 (다른 텍스트 없이):
{
  "summary": "핵심 요약 텍스트",
  "sentiment": {
    "positive_pct": 40,
    "neutral_pct": 35,
    "negative_pct": 25,
    "positive_keywords": ["좋다", "재밌다"],
    "negative_keywords": ["별로", "실망"]
  },
  "topics": [
    {"topic": "주제명", "count": 10, "description": "설명"}
  ],
  "key_opinions": [
    {"type": "positive", "text": "의견 내용", "support": 5},
    {"type": "negative", "text": "의견 내용", "support": 3}
  ],
  "insights": ["인사이트 1", "인사이트 2"]
}"""

# Simpler prompt for URL summarize (returns markdown, not JSON)
_SUMMARIZE_PROMPT = """당신은 SNS 데이터 분석 전문가입니다.
주어진 SNS 수집 데이터를 한국어로 분석·요약해 주세요.

포함할 내용:
1) 전체 요약 (3-5문장)
2) 주요 토픽/키워드
3) 감성 분석 (긍정/부정/중립 비율)
4) 주목할 만한 발견

마크다운 형식으로 작성하세요."""


def get_available_provider(oauth_token: Optional[str] = None,
                           token_provider: Optional[str] = None,
                           session_api_key: Optional[str] = None,
                           session_api_provider: Optional[str] = None) -> Optional[str]:
    """Detect which LLM provider is available.

    Priority:
    1. explicit LLM_PROVIDER env
    2. .env ANTHROPIC_API_KEY
    3. .env OPENAI_API_KEY
    4. Session API key (browser input)
    5. OAuth token (Anthropic or OpenAI)
    """
    if Config.LLM_PROVIDER:
        return Config.LLM_PROVIDER

    if Config.ANTHROPIC_API_KEY:
        return "anthropic"
    if Config.OPENAI_API_KEY:
        return "openai"
    if session_api_key and session_api_provider:
        return f"{session_api_provider}_session"
    if oauth_token and token_provider == "anthropic":
        return "anthropic_oauth"
    if oauth_token:
        return "openai_oauth"
    return None


def get_llm_status(oauth_token: Optional[str] = None,
                   token_provider: Optional[str] = None,
                   session_api_key: Optional[str] = None,
                   session_api_provider: Optional[str] = None) -> dict:
    """Return LLM availability status."""
    provider = get_available_provider(oauth_token, token_provider, session_api_key, session_api_provider)
    auth_mode = None
    if provider and provider.endswith("_session"):
        auth_mode = "api_key_session"
    elif provider and provider.endswith("_oauth"):
        auth_mode = "oauth"
    elif provider:
        auth_mode = "api_key_env"

    return {
        "available": provider is not None,
        "provider": provider,
        "model": _get_model_name(provider) if provider else None,
        "auth_mode": auth_mode,
    }


def _get_model_name(provider: Optional[str]) -> str:
    """Get model name for the provider."""
    if Config.LLM_MODEL:
        return Config.LLM_MODEL
    if provider in ("anthropic", "anthropic_oauth", "anthropic_session"):
        return "claude-sonnet-4-20250514"
    if provider in ("openai", "openai_oauth", "openai_session"):
        return "gpt-4o-mini"
    return ""


def _resolve_credentials(provider: Optional[str], oauth_token: Optional[str] = None,
                         session_api_key: Optional[str] = None) -> tuple:
    """Resolve API key and provider base type from provider string."""
    if provider in ("anthropic",):
        return Config.ANTHROPIC_API_KEY, "anthropic"
    if provider in ("openai",):
        return Config.OPENAI_API_KEY, "openai"
    if provider == "anthropic_session":
        return session_api_key, "anthropic"
    if provider == "openai_session":
        return session_api_key, "openai"
    if provider == "anthropic_oauth":
        return oauth_token, "anthropic"
    if provider == "openai_oauth":
        return oauth_token, "openai"
    return None, None


def analyze_with_llm(document: str, question: Optional[str] = None,
                     oauth_token: Optional[str] = None,
                     token_provider: Optional[str] = None,
                     session_api_key: Optional[str] = None,
                     session_api_provider: Optional[str] = None) -> dict:
    """
    Analyze SNS data using LLM (Claude or ChatGPT).
    Returns structured analysis result.
    """
    provider = get_available_provider(oauth_token, token_provider, session_api_key, session_api_provider)
    if not provider:
        return {"error": "LLM 인증이 필요합니다. Anthropic OAuth 로그인 또는 API Key를 입력하세요."}

    api_key, base_provider = _resolve_credentials(provider, oauth_token, session_api_key)
    model = _get_model_name(provider)
    user_prompt = f"다음 SNS 수집 데이터를 분석해 주세요:\n\n{document[:15000]}\n\n{_RESPONSE_FORMAT_HINT}"
    if question:
        user_prompt = f"다음 SNS 수집 데이터에 대해 질문에 답해주세요.\n\n질문: {question}\n\n데이터:\n{document[:15000]}"

    try:
        if base_provider == "anthropic":
            return _call_anthropic(model, user_prompt, bool(question), api_key=api_key)
        elif base_provider == "openai":
            return _call_openai(model, user_prompt, bool(question), api_key=api_key)
        else:
            return {"error": f"Unknown LLM provider: {provider}"}
    except Exception as e:
        logger.error("LLM analysis failed (%s): %s", provider, e, exc_info=True)
        return {"error": f"LLM analysis failed: {str(e)}"}


def summarize_with_llm(document: str, oauth_token: Optional[str] = None,
                       token_provider: Optional[str] = None,
                       session_api_key: Optional[str] = None,
                       session_api_provider: Optional[str] = None) -> dict:
    """
    Summarize SNS data using LLM. Returns markdown summary (for URL analyzer).
    Falls back gracefully if no LLM is available.
    """
    provider = get_available_provider(oauth_token, token_provider, session_api_key, session_api_provider)
    if not provider:
        return None

    api_key, base_provider = _resolve_credentials(provider, oauth_token, session_api_key)
    model = _get_model_name(provider)
    user_prompt = f"다음 SNS 수집 데이터를 분석·요약해 주세요:\n\n{document[:15000]}"

    try:
        if base_provider == "anthropic":
            return _call_summarize_anthropic(model, user_prompt, api_key=api_key)
        elif base_provider == "openai":
            return _call_summarize_openai(model, user_prompt, api_key=api_key)
        return None
    except Exception as e:
        logger.warning("LLM summarize failed (%s): %s", provider, e)
        return None


def chat_with_llm(document: str, message: str, chat_history: list,
                  oauth_token: Optional[str] = None,
                  token_provider: Optional[str] = None,
                  session_api_key: Optional[str] = None,
                  session_api_provider: Optional[str] = None) -> dict:
    """Chat about SNS data using LLM."""
    provider = get_available_provider(oauth_token, token_provider, session_api_key, session_api_provider)
    if not provider:
        return {"error": "LLM 인증이 필요합니다. OAuth 로그인 또는 API Key를 입력하세요."}

    api_key, base_provider = _resolve_credentials(provider, oauth_token, session_api_key)
    model = _get_model_name(provider)
    context = f"분석 대상 SNS 데이터:\n\n{document[:12000]}"

    try:
        if base_provider == "anthropic":
            return _chat_anthropic(model, context, message, chat_history, api_key=api_key)
        elif base_provider == "openai":
            return _chat_openai(model, context, message, chat_history, api_key=api_key)
        else:
            return {"error": f"Unknown provider: {provider}"}
    except Exception as e:
        logger.error("LLM chat failed (%s): %s", provider, e, exc_info=True)
        return {"error": f"LLM chat failed: {str(e)}"}


def _call_anthropic(model: str, user_prompt: str, is_question: bool,
                    api_key: Optional[str] = None) -> dict:
    """Call Anthropic Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key or Config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = response.content[0].text
    if is_question:
        return {"success": True, "response": text, "provider": "anthropic", "model": model}

    return _parse_analysis_response(text, "anthropic", model)


def _call_openai(model: str, user_prompt: str, is_question: bool,
                 api_key: Optional[str] = None) -> dict:
    """Call OpenAI ChatGPT API."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key or Config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=4096,
        temperature=0.3,
    )

    text = response.choices[0].message.content
    if is_question:
        return {"success": True, "response": text, "provider": "openai", "model": model}

    return _parse_analysis_response(text, "openai", model)


def _call_summarize_anthropic(model: str, user_prompt: str,
                              api_key: Optional[str] = None) -> dict:
    """Summarize with Anthropic."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key or Config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=_SUMMARIZE_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return {"summary": response.content[0].text, "source": "anthropic", "model": model}


def _call_summarize_openai(model: str, user_prompt: str,
                           api_key: Optional[str] = None) -> dict:
    """Summarize with OpenAI."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key or Config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SUMMARIZE_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=2048,
        temperature=0.3,
    )

    return {"summary": response.choices[0].message.content, "source": "openai", "model": model}


def _chat_anthropic(model: str, context: str, message: str, chat_history: list,
                    api_key: Optional[str] = None) -> dict:
    """Chat with Anthropic Claude."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key or Config.ANTHROPIC_API_KEY)

    messages = []
    for msg in chat_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    system = f"{_SYSTEM_PROMPT}\n\n{context}"
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=messages,
    )

    return {"success": True, "response": response.content[0].text, "provider": "anthropic", "model": model}


def _chat_openai(model: str, context: str, message: str, chat_history: list,
                 api_key: Optional[str] = None) -> dict:
    """Chat with OpenAI ChatGPT."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key or Config.OPENAI_API_KEY)

    messages = [{"role": "system", "content": f"{_SYSTEM_PROMPT}\n\n{context}"}]
    for msg in chat_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=2048,
        temperature=0.5,
    )

    return {"success": True, "response": response.choices[0].message.content, "provider": "openai", "model": model}


def _parse_analysis_response(text: str, provider: str, model: str) -> dict:
    """Parse LLM response, attempting JSON extraction."""
    json_str = text.strip()

    # Remove markdown code fences if present
    if json_str.startswith("```"):
        lines = json_str.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        json_str = "\n".join(lines)

    try:
        data = json.loads(json_str)
        data["success"] = True
        data["provider"] = provider
        data["model"] = model
        return data
    except json.JSONDecodeError:
        return {
            "success": True,
            "summary": text,
            "provider": provider,
            "model": model,
            "raw_response": True,
        }
