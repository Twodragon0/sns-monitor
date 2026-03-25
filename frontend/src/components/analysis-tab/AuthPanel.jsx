import React, { useState } from 'react';
import axios from 'axios';

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
      <strong style={{ display: 'block', marginBottom: '10px' }}>API Key를 입력하면 AI 분석이 활성화됩니다</strong>

      {/* API Key input (primary) */}
      <div style={{ padding: '12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0', marginBottom: '10px' }}>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '6px' }}>
          <select
            value={keyProvider}
            onChange={e => setKeyProvider(e.target.value)}
            style={{ padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
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
            style={{ flex: 1, padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
          />
          <button
            type="button" onClick={submitKey} disabled={keySaving || !apiKey.trim()}
            style={{
              padding: '8px 18px', fontSize: '13px', fontWeight: '600',
              background: keySaving ? '#94a3b8' : '#3b82f6', color: 'white',
              border: 'none', borderRadius: '6px', cursor: keySaving ? 'not-allowed' : 'pointer',
            }}
          >
            {keySaving ? '...' : '연결'}
          </button>
        </div>
        {keyError && <div style={{ color: '#dc2626', fontSize: '12px', marginTop: '4px' }}>{keyError}</div>}
        <p style={{ margin: '6px 0 0', fontSize: '11px', color: '#94a3b8' }}>
          세션에만 저장됩니다 (브라우저 종료 시 삭제).
          {keyProvider === 'openai' && <> <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" style={{ color: '#64748b' }}>OpenAI Key 발급</a></>}
          {keyProvider === 'anthropic' && <> <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer" style={{ color: '#64748b' }}>Anthropic Key 발급</a></>}
        </p>
      </div>

      {/* OAuth (secondary) */}
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '12px', color: '#94a3b8' }}>또는 OAuth 로그인:</span>
        <button
          type="button"
          onClick={() => { window.location.href = `${apiBase}/api/auth/anthropic?return_to=/analysis`; }}
          style={{ padding: '5px 12px', fontSize: '12px', background: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '6px', cursor: 'pointer' }}
        >
          Claude
        </button>
        <button
          type="button"
          onClick={() => { window.location.href = `${apiBase}/api/auth/openai?return_to=/analysis`; }}
          style={{ padding: '5px 12px', fontSize: '12px', background: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '6px', cursor: 'pointer' }}
        >
          ChatGPT
        </button>
      </div>
    </>
  );
}
