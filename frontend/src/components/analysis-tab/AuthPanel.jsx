import React, { useState } from 'react';
import axios from 'axios';
import './AuthPanel.css';

/** Map provider string to display name */
export function providerLabel(provider) {
  if (!provider) return 'AI';
  if (provider.includes('anthropic') || provider.includes('claude')) return 'Claude';
  if (provider.includes('openai') || provider.includes('opencode')) return 'ChatGPT';
  if (provider.includes('gemini')) return 'Gemini';
  if (provider.startsWith('cli:')) return provider.replace('cli:', '').toUpperCase();
  return provider;
}

/** Inline auth panel: OAuth login + API key input */
export function AuthPanel({ apiBase, onKeySet, openaiOAuthAvailable }) {
  const [keyProvider, setKeyProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [keyError, setKeyError] = useState('');
  const [keySaving, setKeySaving] = useState(false);

  const submitKey = async () => {
    if (!apiKey.trim()) return;
    setKeySaving(true);
    setKeyError('');
    try {
      const resp = await axios.post(`${apiBase}/api/auth/apikey`, {
        provider: keyProvider,
        api_key: apiKey.trim(),
      }, { withCredentials: true });
      if (resp.data.ok) {
        setApiKey('');
        onKeySet();
      }
    } catch (err) {
      setKeyError(err.response?.data?.error || err.message);
    } finally {
      setKeySaving(false);
    }
  };

  return (
    <>
      <strong className="auth-panel__label">API Key를 입력하면 AI 분석이 활성화됩니다</strong>

      {/* API Key input (primary) */}
      <div className="auth-panel__key-box">
        <div className="auth-panel__key-row">
          <select
            value={keyProvider}
            onChange={e => setKeyProvider(e.target.value)}
            className="auth-panel__select"
          >
            <option value="openai">OpenAI (ChatGPT)</option>
            <option value="anthropic">Anthropic (Claude)</option>
          </select>
          <input
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submitKey()}
            placeholder={keyProvider === 'anthropic' ? 'sk-ant-api03-...' : 'sk-proj-...'}
            className="auth-panel__input"
          />
          <button
            type="button" onClick={submitKey} disabled={keySaving || !apiKey.trim()}
            className={`auth-panel__submit-btn ${keySaving ? 'auth-panel__submit-btn--saving' : 'auth-panel__submit-btn--ready'}`}
          >
            {keySaving ? '...' : '연결'}
          </button>
        </div>
        {keyError && <div className="auth-panel__key-error">{keyError}</div>}
        <p className="auth-panel__key-hint">
          세션에만 저장됩니다 (브라우저 종료 시 삭제).
          {keyProvider === 'openai' && <> <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="auth-panel__key-link">OpenAI Key 발급</a></>}
          {keyProvider === 'anthropic' && <> <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer" className="auth-panel__key-link">Anthropic Key 발급</a></>}
        </p>
      </div>

      {/* OAuth (secondary) */}
      <div className="auth-panel__oauth-row">
        <span className="auth-panel__oauth-label">또는 OAuth 로그인:</span>
        <button
          type="button"
          onClick={() => { window.location.href = `${apiBase}/api/auth/anthropic?return_to=/analysis`; }}
          className="auth-panel__oauth-btn"
        >
          Claude
        </button>
        <button
          type="button"
          onClick={() => { window.location.href = `${apiBase}/api/auth/openai?return_to=/analysis`; }}
          className="auth-panel__oauth-btn"
        >
          ChatGPT
        </button>
      </div>
    </>
  );
}
