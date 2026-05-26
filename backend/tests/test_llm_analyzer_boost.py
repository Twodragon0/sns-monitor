"""Tests to boost llm_analyzer.py coverage from 77% to 90%+.

Covers previously missing lines:
- _detect_cli_tools: cache hit path, openai_sdk detection
- _call_cli: opencode/gemini/unknown tool branches, OSError cleanup, generic exception
- _call_sdk_anthropic / _call_sdk_openai: success and exception paths
- get_available_provider: cli_openai and cli_gemini fallbacks
- get_llm_status: session/oauth/cli auth_mode branches
- _resolve_credentials: openai_session and anthropic_oauth paths
- analyze_with_llm: unknown base_provider branch
- summarize_with_llm: unknown base_provider (return None)
- chat_with_llm: unknown provider branch + exception
- _call_anthropic, _call_openai: full execution with mocked SDK
- _call_summarize_anthropic, _call_summarize_openai: full execution with mocked SDK
- _chat_anthropic, _chat_openai: full execution with mocked SDK
"""

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

import app.services.llm_analyzer as mod
from app.services.llm_analyzer import (
    _call_cli,
    _call_sdk_anthropic,
    _call_sdk_openai,
    _resolve_credentials,
    analyze_with_llm,
    chat_with_llm,
    get_available_provider,
    get_llm_status,
    summarize_with_llm,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_anthropic_mock(text: str = "response text") -> MagicMock:
    """Build a minimal mock that looks like an anthropic client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=text)]
    mock_client.messages.create.return_value = mock_response
    return mock_client


def _make_openai_mock(text: str = "gpt response") -> MagicMock:
    """Build a minimal mock that looks like an OpenAI client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=text))]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ---------------------------------------------------------------------------
# _detect_cli_tools: cache hit path and openai_sdk detection
# ---------------------------------------------------------------------------

class TestDetectCliToolsExtended:
    def test_cache_hit_returns_cached(self):
        """Line 80: cache hit returns without re-scanning."""
        mod._CLI_CACHE.clear()
        mod._CLI_CACHE["_checked"] = True
        mod._CLI_CACHE["some_tool"] = "/usr/bin/some"
        result = mod._detect_cli_tools()
        assert "some_tool" in result
        assert "_checked" not in result
        mod._CLI_CACHE.clear()

    @patch("shutil.which", return_value=None)
    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-oai-test"}, clear=True)
    def test_openai_sdk_detected(self, mock_which):
        """Line 99: OPENAI_API_KEY causes openai_sdk to be registered."""
        mod._CLI_CACHE.clear()
        tools = mod._detect_cli_tools()
        assert "openai_sdk" in tools
        mod._CLI_CACHE.clear()

    @patch("shutil.which", return_value=None)
    @patch.dict("os.environ", {}, clear=True)
    def test_no_keys_no_sdk(self, mock_which):
        """Neither SDK key present — no sdk entries."""
        mod._CLI_CACHE.clear()
        tools = mod._detect_cli_tools()
        assert "claude_sdk" not in tools
        assert "openai_sdk" not in tools
        mod._CLI_CACHE.clear()


# ---------------------------------------------------------------------------
# _call_cli: opencode, gemini, unknown tool branches + exception paths
# ---------------------------------------------------------------------------

class TestCallCliExtended:
    @patch("app.services.llm_analyzer.subprocess.run")
    @patch(
        "app.services.llm_analyzer._detect_cli_tools",
        return_value={"opencode": "/usr/bin/opencode"},
    )
    def test_opencode_binary_success(self, mock_tools, mock_run):
        """Line 176: opencode CLI branch executes successfully."""
        mock_run.return_value = MagicMock(returncode=0, stdout="opencode output", stderr="")
        result = _call_cli("opencode", "prompt text")
        assert result == "opencode output"

    @patch("app.services.llm_analyzer.subprocess.run")
    @patch(
        "app.services.llm_analyzer._detect_cli_tools",
        return_value={"gemini": "/usr/bin/gemini"},
    )
    def test_gemini_binary_success(self, mock_tools, mock_run):
        """Line 178: gemini CLI branch executes successfully."""
        mock_run.return_value = MagicMock(returncode=0, stdout="gemini output", stderr="")
        result = _call_cli("gemini", "prompt text")
        assert result == "gemini output"

    @patch("app.services.llm_analyzer.subprocess.run")
    @patch(
        "app.services.llm_analyzer._detect_cli_tools",
        return_value={"mytool": "/usr/bin/mytool"},
    )
    def test_unknown_tool_returns_none(self, mock_tools, mock_run):
        """Line 180: unknown CLI tool name hits the else branch → None."""
        result = _call_cli("mytool", "prompt text")
        assert result is None

    @patch("app.services.llm_analyzer.subprocess.run")
    @patch(
        "app.services.llm_analyzer._detect_cli_tools",
        return_value={"claude": "/usr/bin/claude"},
    )
    def test_oserror_on_unlink_is_swallowed(self, mock_tools, mock_run):
        """Lines 192-193: OSError raised in os.unlink is silently caught."""
        mock_run.return_value = MagicMock(returncode=0, stdout="result", stderr="")
        with patch("os.unlink", side_effect=OSError("unlink failed")):
            result = _call_cli("claude", "prompt text")
        # Despite OSError on cleanup, result should still be returned
        assert result == "result"

    @patch(
        "app.services.llm_analyzer._detect_cli_tools",
        return_value={"claude": "/usr/bin/claude"},
    )
    def test_generic_exception_returns_none(self, mock_tools):
        """Lines 202-204: unexpected exception → returns None."""
        with patch("tempfile.NamedTemporaryFile", side_effect=RuntimeError("disk full")):
            result = _call_cli("claude", "prompt text")
        assert result is None

    @patch("app.services.llm_analyzer.subprocess.run")
    @patch(
        "app.services.llm_analyzer._detect_cli_tools",
        return_value={"claude": "/usr/bin/claude"},
    )
    def test_stderr_logged_on_nonzero(self, mock_tools, mock_run):
        """Line 197: when returncode != 0 and stderr is present, warning is logged."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="bad error")
        result = _call_cli("claude", "prompt text")
        assert result is None


# ---------------------------------------------------------------------------
# _call_sdk_anthropic: success and exception paths
# ---------------------------------------------------------------------------

class TestCallSdkAnthropic:
    @patch("app.services.llm_analyzer.Config")
    def test_success(self, mock_config):
        """Lines 212-218: successful SDK call returns text."""
        mock_config.LLM_MODEL = ""
        mock_anthropic_module = MagicMock()
        mock_client = _make_anthropic_mock("Anthropic SDK answer")
        mock_anthropic_module.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic_module}):
            result = _call_sdk_anthropic("hello")
        assert result == "Anthropic SDK answer"

    @patch("app.services.llm_analyzer.Config")
    def test_exception_returns_none(self, mock_config):
        """Lines 219-221: exception from SDK → returns None."""
        mock_config.LLM_MODEL = ""
        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.side_effect = Exception("auth error")
        with patch.dict(sys.modules, {"anthropic": mock_anthropic_module}):
            result = _call_sdk_anthropic("hello")
        assert result is None

    @patch("app.services.llm_analyzer.Config")
    def test_with_explicit_model(self, mock_config):
        """LLM_MODEL config value is forwarded to SDK call."""
        mock_config.LLM_MODEL = "claude-3-haiku"
        mock_anthropic_module = MagicMock()
        mock_client = _make_anthropic_mock("haiku reply")
        mock_anthropic_module.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic_module}):
            result = _call_sdk_anthropic("prompt")
        assert result == "haiku reply"
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-3-haiku"


# ---------------------------------------------------------------------------
# _call_sdk_openai: success and exception paths
# ---------------------------------------------------------------------------

class TestCallSdkOpenai:
    @patch("app.services.llm_analyzer.Config")
    def test_success(self, mock_config):
        """Lines 229-235: successful SDK call returns content."""
        mock_config.LLM_MODEL = ""
        mock_openai_module = MagicMock()
        mock_client = _make_openai_mock("OpenAI SDK answer")
        mock_openai_module.OpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_openai_module}):
            result = _call_sdk_openai("hello")
        assert result == "OpenAI SDK answer"

    @patch("app.services.llm_analyzer.Config")
    def test_exception_returns_none(self, mock_config):
        """Lines 236-238 (exception path): SDK error → returns None."""
        mock_config.LLM_MODEL = ""
        mock_openai_module = MagicMock()
        mock_openai_module.OpenAI.side_effect = Exception("rate limit")
        with patch.dict(sys.modules, {"openai": mock_openai_module}):
            result = _call_sdk_openai("hello")
        assert result is None

    @patch("app.services.llm_analyzer.Config")
    def test_with_explicit_model(self, mock_config):
        """LLM_MODEL config value is forwarded."""
        mock_config.LLM_MODEL = "gpt-4"
        mock_openai_module = MagicMock()
        mock_client = _make_openai_mock("gpt-4 response")
        mock_openai_module.OpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_openai_module}):
            result = _call_sdk_openai("prompt")
        assert result == "gpt-4 response"
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4"


# ---------------------------------------------------------------------------
# get_available_provider: cli_openai and cli_gemini fallbacks
# ---------------------------------------------------------------------------

class TestGetAvailableProviderExtended:
    @patch("app.services.llm_analyzer.Config")
    @patch(
        "app.services.llm_analyzer._detect_cli_tools",
        return_value={"openai_sdk": "python:openai"},
    )
    def test_cli_openai_fallback(self, mock_tools, mock_config):
        """Line 279: openai_sdk present → cli_openai."""
        mock_config.LLM_PROVIDER = ""
        mock_config.ANTHROPIC_API_KEY = ""
        mock_config.OPENAI_API_KEY = ""
        result = get_available_provider()
        assert result == "cli_openai"

    @patch("app.services.llm_analyzer.Config")
    @patch(
        "app.services.llm_analyzer._detect_cli_tools",
        return_value={"gemini": "/usr/bin/gemini"},
    )
    def test_cli_gemini_fallback(self, mock_tools, mock_config):
        """Line 281: gemini present → cli_gemini."""
        mock_config.LLM_PROVIDER = ""
        mock_config.ANTHROPIC_API_KEY = ""
        mock_config.OPENAI_API_KEY = ""
        result = get_available_provider()
        assert result == "cli_gemini"

    @patch("app.services.llm_analyzer.Config")
    @patch(
        "app.services.llm_analyzer._detect_cli_tools",
        return_value={"opencode": "/usr/bin/opencode"},
    )
    def test_opencode_cli_fallback(self, mock_tools, mock_config):
        """opencode present → cli_openai (line 279 branch)."""
        mock_config.LLM_PROVIDER = ""
        mock_config.ANTHROPIC_API_KEY = ""
        mock_config.OPENAI_API_KEY = ""
        result = get_available_provider()
        assert result == "cli_openai"


# ---------------------------------------------------------------------------
# get_llm_status: all auth_mode branches
# ---------------------------------------------------------------------------

class TestGetLlmStatusExtended:
    @patch("app.services.llm_analyzer.Config")
    @patch("app.services.llm_analyzer._detect_cli_tools", return_value={})
    def test_auth_mode_session(self, mock_tools, mock_config):
        """Line 299: _session provider → auth_mode == 'api_key_session'."""
        mock_config.LLM_PROVIDER = ""
        mock_config.ANTHROPIC_API_KEY = ""
        mock_config.OPENAI_API_KEY = ""
        mock_config.LLM_MODEL = ""
        fake_session_key = "sk-" + "sess1234567890"
        status = get_llm_status(
            session_api_key=fake_session_key, session_api_provider="openai"
        )
        assert status["available"] is True
        assert status["auth_mode"] == "api_key_session"

    @patch("app.services.llm_analyzer.Config")
    @patch("app.services.llm_analyzer._detect_cli_tools", return_value={})
    def test_auth_mode_oauth(self, mock_tools, mock_config):
        """Line 301: _oauth provider → auth_mode == 'oauth'."""
        mock_config.LLM_PROVIDER = ""
        mock_config.ANTHROPIC_API_KEY = ""
        mock_config.OPENAI_API_KEY = ""
        mock_config.LLM_MODEL = ""
        status = get_llm_status(oauth_token="tok", token_provider="anthropic")
        assert status["available"] is True
        assert status["auth_mode"] == "oauth"

    @patch("app.services.llm_analyzer.Config")
    @patch(
        "app.services.llm_analyzer._detect_cli_tools",
        return_value={"claude_sdk": "python:anthropic"},
    )
    def test_auth_mode_cli(self, mock_tools, mock_config):
        """Line 297: cli_ provider → auth_mode == 'cli'."""
        mock_config.LLM_PROVIDER = ""
        mock_config.ANTHROPIC_API_KEY = ""
        mock_config.OPENAI_API_KEY = ""
        mock_config.LLM_MODEL = ""
        status = get_llm_status()
        assert status["available"] is True
        assert status["auth_mode"] == "cli"


# ---------------------------------------------------------------------------
# _resolve_credentials: openai_session and anthropic_oauth
# ---------------------------------------------------------------------------

class TestResolveCredentialsExtended:
    def test_openai_session(self):
        """Line 349: openai_session returns session key."""
        key, base = _resolve_credentials("openai_session", session_api_key="sess-key")
        assert key == "sess-key"
        assert base == "openai"

    def test_anthropic_oauth(self):
        """Line 351: anthropic_oauth returns oauth token."""
        key, base = _resolve_credentials("anthropic_oauth", oauth_token="oauth-token")
        assert key == "oauth-token"
        assert base == "anthropic"


# ---------------------------------------------------------------------------
# analyze_with_llm: unknown base_provider branch
# ---------------------------------------------------------------------------

class TestAnalyzeWithLlmExtended:
    @patch("app.services.llm_analyzer._resolve_credentials", return_value=(None, "unknown"))
    @patch("app.services.llm_analyzer.get_available_provider", return_value="mystery_provider")
    @patch("app.services.llm_analyzer.Config")
    def test_unknown_base_provider(self, mock_config, mock_provider, mock_creds):
        """Line 395: unknown base_provider returns error dict."""
        mock_config.LLM_MODEL = ""
        result = analyze_with_llm("doc")
        assert "error" in result
        assert "Unknown LLM provider" in result["error"]

    @patch("app.services.llm_analyzer._call_anthropic")
    @patch("app.services.llm_analyzer.get_available_provider", return_value="anthropic")
    @patch("app.services.llm_analyzer.Config")
    def test_analyze_with_question_uses_question_prompt(
        self, mock_config, mock_provider, mock_call
    ):
        """When question is set, prompt changes (covers the if-question branch)."""
        mock_config.ANTHROPIC_API_KEY = "sk-ant"
        mock_config.LLM_MODEL = ""
        mock_call.return_value = {"success": True, "response": "42"}
        result = analyze_with_llm("data", question="What is the meaning?")
        assert result["success"] is True
        # The is_question=True flag must be passed
        call_args = mock_call.call_args
        assert call_args[0][2] is True  # is_question positional arg


# ---------------------------------------------------------------------------
# summarize_with_llm: unknown base_provider → None
# ---------------------------------------------------------------------------

class TestSummarizeWithLlmExtended:
    @patch("app.services.llm_analyzer._resolve_credentials", return_value=(None, "unknown"))
    @patch("app.services.llm_analyzer.get_available_provider", return_value="mystery")
    @patch("app.services.llm_analyzer.Config")
    def test_unknown_base_provider_returns_none(
        self, mock_config, mock_provider, mock_creds
    ):
        """Line 431: unrecognised base_provider falls through to return None."""
        mock_config.LLM_MODEL = ""
        result = summarize_with_llm("doc")
        assert result is None

    @patch("app.services.llm_analyzer._call_summarize_anthropic")
    @patch("app.services.llm_analyzer.get_available_provider", return_value="anthropic")
    @patch("app.services.llm_analyzer.Config")
    def test_exception_returns_none(self, mock_config, mock_provider, mock_call):
        """summarize exception path → None."""
        mock_config.ANTHROPIC_API_KEY = "sk-ant"
        mock_config.LLM_MODEL = ""
        mock_call.side_effect = ValueError("bad format")
        result = summarize_with_llm("doc")
        assert result is None


# ---------------------------------------------------------------------------
# chat_with_llm: unknown provider + exception
# ---------------------------------------------------------------------------

class TestChatWithLlmExtended:
    @patch("app.services.llm_analyzer._resolve_credentials", return_value=(None, "unknown"))
    @patch("app.services.llm_analyzer.get_available_provider", return_value="mystery")
    @patch("app.services.llm_analyzer.Config")
    def test_unknown_base_provider(self, mock_config, mock_provider, mock_creds):
        """Lines 471-474: unknown base_provider in chat → error dict."""
        mock_config.LLM_MODEL = ""
        result = chat_with_llm("doc", "hi", [])
        assert "error" in result
        assert "Unknown provider" in result["error"]

    @patch("app.services.llm_analyzer._chat_anthropic")
    @patch("app.services.llm_analyzer.get_available_provider", return_value="anthropic")
    @patch("app.services.llm_analyzer.Config")
    def test_exception_returns_error(self, mock_config, mock_provider, mock_chat):
        """Exception in _chat_anthropic is caught and returned as error dict."""
        mock_config.ANTHROPIC_API_KEY = "sk-ant"
        mock_config.LLM_MODEL = ""
        mock_chat.side_effect = RuntimeError("timeout")
        result = chat_with_llm("doc", "hi", [])
        assert "error" in result


# ---------------------------------------------------------------------------
# _call_anthropic: full function with mocked SDK
# ---------------------------------------------------------------------------

class TestCallAnthropic:
    @patch("app.services.llm_analyzer.Config")
    def test_call_anthropic_analysis(self, mock_config):
        """Lines 481-500: _call_anthropic with is_question=False parses JSON response."""
        mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
        mock_anthropic = MagicMock()
        mock_client = _make_anthropic_mock(
            '{"summary": "test", "topics": [], "key_opinions": [], "insights": []}'
        )
        mock_anthropic.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            from app.services.llm_analyzer import _call_anthropic
            result = _call_anthropic(
                "claude-3", "analyze this", is_question=False, api_key="sk-ant-test"
            )
        assert result["success"] is True
        assert result["provider"] == "anthropic"

    @patch("app.services.llm_analyzer.Config")
    def test_call_anthropic_question(self, mock_config):
        """Lines 492-498: is_question=True returns response dict directly."""
        mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
        mock_anthropic = MagicMock()
        mock_client = _make_anthropic_mock("The answer is 42")
        mock_anthropic.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            from app.services.llm_analyzer import _call_anthropic
            result = _call_anthropic(
                "claude-3", "what is life?", is_question=True, api_key="sk-ant-test"
            )
        assert result["success"] is True
        assert result["response"] == "The answer is 42"
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-3"


# ---------------------------------------------------------------------------
# _call_openai: full function with mocked SDK
# ---------------------------------------------------------------------------

class TestCallOpenai:
    @patch("app.services.llm_analyzer.Config")
    def test_call_openai_analysis(self, mock_config):
        """Lines 507-524: _call_openai with is_question=False."""
        mock_config.OPENAI_API_KEY = "sk-test"
        mock_openai = MagicMock()
        mock_client = _make_openai_mock(
            '{"summary": "gpt summary", "topics": [], "key_opinions": [], "insights": []}'
        )
        mock_openai.OpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_openai}):
            from app.services.llm_analyzer import _call_openai
            result = _call_openai(
                "gpt-4o-mini", "analyze this", is_question=False, api_key="sk-test"
            )
        assert result["success"] is True
        assert result["provider"] == "openai"

    @patch("app.services.llm_analyzer.Config")
    def test_call_openai_question(self, mock_config):
        """Lines 521-524: is_question=True returns response dict."""
        mock_config.OPENAI_API_KEY = "sk-test"
        mock_openai = MagicMock()
        mock_client = _make_openai_mock("GPT says hello")
        mock_openai.OpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_openai}):
            from app.services.llm_analyzer import _call_openai
            result = _call_openai(
                "gpt-4o-mini", "hi?", is_question=True, api_key="sk-test"
            )
        assert result["success"] is True
        assert result["response"] == "GPT says hello"
        assert result["provider"] == "openai"


# ---------------------------------------------------------------------------
# _call_summarize_anthropic: full function with mocked SDK
# ---------------------------------------------------------------------------

class TestCallSummarizeAnthropic:
    @patch("app.services.llm_analyzer.Config")
    def test_summarize_returns_dict(self, mock_config):
        """Lines 531-541: successful summarize returns dict with summary key."""
        mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
        mock_anthropic = MagicMock()
        mock_client = _make_anthropic_mock("## 요약\n좋은 내용입니다.")
        mock_anthropic.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            from app.services.llm_analyzer import _call_summarize_anthropic
            result = _call_summarize_anthropic(
                "claude-3", "summarize this", api_key="sk-ant-test"
            )
        assert result["summary"] == "## 요약\n좋은 내용입니다."
        assert result["source"] == "anthropic"
        assert result["model"] == "claude-3"


# ---------------------------------------------------------------------------
# _call_summarize_openai: full function with mocked SDK
# ---------------------------------------------------------------------------

class TestCallSummarizeOpenai:
    @patch("app.services.llm_analyzer.Config")
    def test_summarize_returns_dict(self, mock_config):
        """Lines 548-561: successful summarize with OpenAI returns correct structure."""
        mock_config.OPENAI_API_KEY = "sk-test"
        mock_openai = MagicMock()
        mock_client = _make_openai_mock("## GPT Summary\nContent here.")
        mock_openai.OpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_openai}):
            from app.services.llm_analyzer import _call_summarize_openai
            result = _call_summarize_openai(
                "gpt-4o-mini", "summarize this", api_key="sk-test"
            )
        assert result["summary"] == "## GPT Summary\nContent here."
        assert result["source"] == "openai"
        assert result["model"] == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# _chat_anthropic: full function with mocked SDK
# ---------------------------------------------------------------------------

class TestChatAnthropic:
    @patch("app.services.llm_analyzer.Config")
    def test_chat_returns_response(self, mock_config):
        """Lines 576-598: _chat_anthropic builds message list and returns response."""
        mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
        mock_anthropic = MagicMock()
        mock_client = _make_anthropic_mock("Claude chat reply")
        mock_anthropic.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            from app.services.llm_analyzer import _chat_anthropic
            result = _chat_anthropic(
                "claude-3",
                "SNS context here",
                "What do you think?",
                [{"role": "user", "content": "prev msg"}, {"role": "assistant", "content": "prev reply"}],
                api_key="sk-ant-test",
            )
        assert result["success"] is True
        assert result["response"] == "Claude chat reply"
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-3"

    @patch("app.services.llm_analyzer.Config")
    def test_chat_empty_history(self, mock_config):
        """_chat_anthropic with empty chat_history works correctly."""
        mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
        mock_anthropic = MagicMock()
        mock_client = _make_anthropic_mock("Empty history reply")
        mock_anthropic.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            from app.services.llm_analyzer import _chat_anthropic
            result = _chat_anthropic(
                "claude-3", "context", "hello", [], api_key="sk-ant-test"
            )
        assert result["success"] is True
        # messages passed to create should only be the new user message
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["messages"] == [{"role": "user", "content": "hello"}]

    @patch("app.services.llm_analyzer.Config")
    def test_chat_history_truncated_to_10(self, mock_config):
        """Chat history is sliced to last 10 messages."""
        mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
        mock_anthropic = MagicMock()
        mock_client = _make_anthropic_mock("Truncated reply")
        mock_anthropic.Anthropic.return_value = mock_client
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
            for i in range(20)
        ]
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            from app.services.llm_analyzer import _chat_anthropic
            result = _chat_anthropic(
                "claude-3", "context", "new message", history, api_key="sk-ant-test"
            )
        call_kwargs = mock_client.messages.create.call_args[1]
        # 10 history + 1 new message = 11 total
        assert len(call_kwargs["messages"]) == 11


# ---------------------------------------------------------------------------
# _chat_openai: full function with mocked SDK
# ---------------------------------------------------------------------------

class TestChatOpenai:
    @patch("app.services.llm_analyzer.Config")
    def test_chat_returns_response(self, mock_config):
        """Lines 609-630: _chat_openai builds messages and returns response."""
        mock_config.OPENAI_API_KEY = "sk-test"
        mock_openai = MagicMock()
        mock_client = _make_openai_mock("GPT chat reply")
        mock_openai.OpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_openai}):
            from app.services.llm_analyzer import _chat_openai
            result = _chat_openai(
                "gpt-4o-mini",
                "SNS context",
                "Tell me more",
                [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
                api_key="sk-test",
            )
        assert result["success"] is True
        assert result["response"] == "GPT chat reply"
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4o-mini"

    @patch("app.services.llm_analyzer.Config")
    def test_chat_empty_history(self, mock_config):
        """_chat_openai with empty history includes only system + user messages."""
        mock_config.OPENAI_API_KEY = "sk-test"
        mock_openai = MagicMock()
        mock_client = _make_openai_mock("Empty history GPT")
        mock_openai.OpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_openai}):
            from app.services.llm_analyzer import _chat_openai
            result = _chat_openai(
                "gpt-4o-mini", "context", "question", [], api_key="sk-test"
            )
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        # system message + user message = 2
        assert len(call_kwargs["messages"]) == 2
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][-1]["role"] == "user"
        assert call_kwargs["messages"][-1]["content"] == "question"

    @patch("app.services.llm_analyzer.Config")
    def test_chat_history_truncated_to_10(self, mock_config):
        """Chat history is sliced to last 10 messages."""
        mock_config.OPENAI_API_KEY = "sk-test"
        mock_openai = MagicMock()
        mock_client = _make_openai_mock("Truncated GPT reply")
        mock_openai.OpenAI.return_value = mock_client
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
            for i in range(20)
        ]
        with patch.dict(sys.modules, {"openai": mock_openai}):
            from app.services.llm_analyzer import _chat_openai
            result = _chat_openai(
                "gpt-4o-mini", "context", "new", history, api_key="sk-test"
            )
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        # system + 10 history + 1 new = 12
        assert len(call_kwargs["messages"]) == 12
