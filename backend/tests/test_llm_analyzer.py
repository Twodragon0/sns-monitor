"""Tests for app/services/llm_analyzer.py."""

import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_analyzer import (
    get_available_provider,
    get_llm_status,
    _get_model_name,
    _resolve_credentials,
)


class TestGetAvailableProvider:
    """Tests for get_available_provider."""

    @patch('app.services.llm_analyzer.Config')
    @patch('app.services.llm_analyzer._detect_cli_tools', return_value={})
    def test_no_provider_available(self, mock_tools, mock_config):
        mock_config.LLM_PROVIDER = ''
        mock_config.ANTHROPIC_API_KEY = ''
        mock_config.OPENAI_API_KEY = ''
        result = get_available_provider()
        assert result is None

    @patch('app.services.llm_analyzer.Config')
    def test_explicit_provider(self, mock_config):
        mock_config.LLM_PROVIDER = 'anthropic'
        result = get_available_provider()
        assert result == 'anthropic'

    @patch('app.services.llm_analyzer.Config')
    def test_anthropic_api_key(self, mock_config):
        mock_config.LLM_PROVIDER = ''
        mock_config.ANTHROPIC_API_KEY = 'sk-ant-test'
        result = get_available_provider()
        assert result == 'anthropic'

    @patch('app.services.llm_analyzer.Config')
    def test_openai_api_key(self, mock_config):
        mock_config.LLM_PROVIDER = ''
        mock_config.ANTHROPIC_API_KEY = ''
        mock_config.OPENAI_API_KEY = 'sk-test'
        result = get_available_provider()
        assert result == 'openai'

    @patch('app.services.llm_analyzer.Config')
    @patch('app.services.llm_analyzer._detect_cli_tools', return_value={})
    def test_session_api_key(self, mock_tools, mock_config):
        mock_config.LLM_PROVIDER = ''
        mock_config.ANTHROPIC_API_KEY = ''
        mock_config.OPENAI_API_KEY = ''
        result = get_available_provider(session_api_key='sk-test', session_api_provider='openai')
        assert result == 'openai_session'

    @patch('app.services.llm_analyzer.Config')
    @patch('app.services.llm_analyzer._detect_cli_tools', return_value={})
    def test_oauth_anthropic(self, mock_tools, mock_config):
        mock_config.LLM_PROVIDER = ''
        mock_config.ANTHROPIC_API_KEY = ''
        mock_config.OPENAI_API_KEY = ''
        result = get_available_provider(oauth_token='token123', token_provider='anthropic')
        assert result == 'anthropic_oauth'

    @patch('app.services.llm_analyzer.Config')
    @patch('app.services.llm_analyzer._detect_cli_tools', return_value={})
    def test_oauth_openai(self, mock_tools, mock_config):
        mock_config.LLM_PROVIDER = ''
        mock_config.ANTHROPIC_API_KEY = ''
        mock_config.OPENAI_API_KEY = ''
        result = get_available_provider(oauth_token='token123', token_provider='openai')
        assert result == 'openai_oauth'

    @patch('app.services.llm_analyzer.Config')
    @patch('app.services.llm_analyzer._detect_cli_tools', return_value={'claude': '/usr/bin/claude'})
    def test_cli_claude_fallback(self, mock_tools, mock_config):
        mock_config.LLM_PROVIDER = ''
        mock_config.ANTHROPIC_API_KEY = ''
        mock_config.OPENAI_API_KEY = ''
        result = get_available_provider()
        assert result == 'cli_claude'


class TestGetLlmStatus:
    """Tests for get_llm_status."""

    @patch('app.services.llm_analyzer.Config')
    @patch('app.services.llm_analyzer._detect_cli_tools', return_value={})
    def test_unavailable(self, mock_tools, mock_config):
        mock_config.LLM_PROVIDER = ''
        mock_config.ANTHROPIC_API_KEY = ''
        mock_config.OPENAI_API_KEY = ''
        mock_config.LLM_MODEL = ''
        status = get_llm_status()
        assert status['available'] is False
        assert status['provider'] is None

    @patch('app.services.llm_analyzer.Config')
    @patch('app.services.llm_analyzer._detect_cli_tools', return_value={})
    def test_available_with_anthropic(self, mock_tools, mock_config):
        mock_config.LLM_PROVIDER = ''
        mock_config.ANTHROPIC_API_KEY = 'sk-ant-test'
        mock_config.OPENAI_API_KEY = ''
        mock_config.LLM_MODEL = ''
        status = get_llm_status()
        assert status['available'] is True
        assert status['provider'] == 'anthropic'
        assert status['auth_mode'] == 'api_key_env'


class TestGetModelName:
    """Tests for _get_model_name."""

    @patch('app.services.llm_analyzer.Config')
    def test_explicit_model(self, mock_config):
        mock_config.LLM_MODEL = 'custom-model'
        assert _get_model_name('anthropic') == 'custom-model'

    @patch('app.services.llm_analyzer.Config')
    def test_anthropic_default(self, mock_config):
        mock_config.LLM_MODEL = ''
        name = _get_model_name('anthropic')
        assert 'claude' in name

    @patch('app.services.llm_analyzer.Config')
    def test_openai_default(self, mock_config):
        mock_config.LLM_MODEL = ''
        name = _get_model_name('openai')
        assert 'gpt' in name

    @patch('app.services.llm_analyzer.Config')
    def test_gemini(self, mock_config):
        mock_config.LLM_MODEL = ''
        name = _get_model_name('cli_gemini')
        assert 'gemini' in name

    @patch('app.services.llm_analyzer.Config')
    def test_none_provider(self, mock_config):
        mock_config.LLM_MODEL = ''
        assert _get_model_name(None) == ''


class TestResolveCredentials:
    """Tests for _resolve_credentials."""

    @patch('app.services.llm_analyzer.Config')
    def test_anthropic_env(self, mock_config):
        mock_config.ANTHROPIC_API_KEY = 'sk-ant-key'
        key, base = _resolve_credentials('anthropic')
        assert key == 'sk-ant-key'
        assert base == 'anthropic'

    @patch('app.services.llm_analyzer.Config')
    def test_openai_env(self, mock_config):
        mock_config.OPENAI_API_KEY = 'sk-key'
        key, base = _resolve_credentials('openai')
        assert key == 'sk-key'
        assert base == 'openai'

    def test_session_key(self):
        key, base = _resolve_credentials('anthropic_session', session_api_key='session-key')
        assert key == 'session-key'
        assert base == 'anthropic'

    def test_oauth(self):
        key, base = _resolve_credentials('openai_oauth', oauth_token='oauth-tok')
        assert key == 'oauth-tok'
        assert base == 'openai'

    def test_cli(self):
        key, base = _resolve_credentials('cli_claude')
        assert key is None
        assert base == 'cli'

    def test_unknown(self):
        key, base = _resolve_credentials(None)
        assert key is None
        assert base is None
