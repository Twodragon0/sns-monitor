import React, { useState, useEffect } from 'react';
import './AuthLogin.css';

const AuthLogin = () => {
  const [loginStatus, setLoginStatus] = useState({
    claude: false,
    cursor: false
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    // OAuth 콜백 처리
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    const error = params.get('error');

    // OAuth 에러 처리
    if (error) {
      setMessage(`❌ 인증 실패: ${error}`);
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }

    // OAuth 콜백 (code와 state가 있는 경우)
    if (code && state) {
      handleOAuthCallback(code, state);
      return;
    }

    // 저장된 인증 상태 확인
    const claudeUserId = localStorage.getItem('claude_user_id');
    const cursorUserId = localStorage.getItem('cursor_user_id');

    if (claudeUserId) {
      setLoginStatus(prev => ({ ...prev, claude: true }));
    }
    if (cursorUserId) {
      setLoginStatus(prev => ({ ...prev, cursor: true }));
    }
  }, []);

  const handleOAuthCallback = async (code, state) => {
    try {
      setLoading(true);
      setMessage('🔄 인증 처리 중...');

      // Auth service의 callback 엔드포인트로 code와 state 전송
      const response = await fetch(`http://localhost:8081/api/auth/callback?code=${code}&state=${state}`);
      const data = await response.json();

      if (response.ok && data.user_id && data.provider) {
        // 로컬 스토리지에 저장
        localStorage.setItem(`${data.provider}_user_id`, data.user_id);
        localStorage.setItem(`${data.provider}_auth_time`, new Date().toISOString());

        // 상태 업데이트
        setLoginStatus(prev => ({
          ...prev,
          [data.provider]: true
        }));

        setMessage(`✅ ${data.provider === 'claude' ? 'Claude Console' : 'OpenAI'} 인증 성공!`);
      } else {
        throw new Error(data.error || 'Authentication failed');
      }
    } catch (err) {
      setMessage(`❌ 인증 처리 실패: ${err.message}`);
    } finally {
      setLoading(false);
      // URL 파라미터 제거
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  };

  const handleClaudeLogin = async () => {
    try {
      setLoading(true);
      setMessage('');

      // Claude Console OAuth URL 가져오기
      const response = await fetch('http://localhost:8081/api/auth/claude');
      const data = await response.json();

      if (data.auth_url) {
        // Claude Console OAuth로 리다이렉트
        window.location.href = data.auth_url;
      } else {
        throw new Error('Failed to get auth URL');
      }
    } catch (err) {
      setMessage(`❌ Claude 로그인 실패: ${err.message}`);
      setLoading(false);
    }
  };

  const handleCursorLogin = async () => {
    try {
      setLoading(true);
      setMessage('');

      // Cursor OAuth URL 가져오기
      const response = await fetch('http://localhost:8081/api/auth/openai');
      const data = await response.json();

      if (data.auth_url) {
        // Cursor/OpenAI OAuth로 리다이렉트
        window.location.href = data.auth_url;
      } else {
        throw new Error('Failed to get auth URL');
      }
    } catch (err) {
      setMessage(`❌ Cursor 로그인 실패: ${err.message}`);
      setLoading(false);
    }
  };

  const handleLogout = async (provider) => {
    try {
      const userId = localStorage.getItem(`${provider}_user_id`);

      if (!userId) return;

      await fetch('http://localhost:8081/api/auth/logout', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ user_id: userId })
      });

      // 로컬 스토리지에서 제거
      localStorage.removeItem(`${provider}_user_id`);
      localStorage.removeItem(`${provider}_auth_time`);

      // 상태 업데이트
      setLoginStatus(prev => ({
        ...prev,
        [provider]: false
      }));

      setMessage(`✅ ${provider === 'claude' ? 'Claude Console' : 'Cursor'} 로그아웃 완료`);
    } catch (err) {
      setMessage(`❌ 로그아웃 실패: ${err.message}`);
    }
  };

  return (
    <div className="auth-login">
      <h2>🔐 AI Console 인증</h2>

      <div className="auth-info">
        <p><strong>OAuth 2.0 웹 인증</strong>으로 Claude Console과 Cursor에 로그인하세요.</p>
        <p>API 키 없이 콘솔에서 직접 인증되며, 자동으로 토큰이 관리됩니다.</p>
      </div>

      {message && (
        <div className={`auth-message ${message.startsWith('✅') ? 'success' : message.startsWith('❌') ? 'error' : 'info'}`}>
          {message}
        </div>
      )}

      <div className="auth-providers">
        {/* Claude Console */}
        <div className="auth-provider">
          <div className="provider-header">
            <div>
              <h3>🤖 Claude Console</h3>
              <p className="provider-subtitle">Anthropic OAuth 2.0 + PKCE</p>
            </div>
            {loginStatus.claude && (
              <span className="status-badge connected">✓ 인증됨</span>
            )}
          </div>

          <div className="provider-features">
            <h4>인증 방식:</h4>
            <ul>
              <li>✨ Claude Console 웹 로그인</li>
              <li>🔐 OAuth 2.0 PKCE 보안</li>
              <li>🔄 자동 토큰 갱신</li>
              <li>🚀 Claude Code와 동일한 인증</li>
            </ul>
          </div>

          <div className="provider-instructions">
            <h4>인증 절차:</h4>
            <ol>
              <li>"Claude Console 로그인" 버튼 클릭</li>
              <li>Claude Console 웹페이지로 이동</li>
              <li>Anthropic 계정으로 로그인</li>
              <li>권한 승인 (API 키 생성 권한)</li>
              <li>자동으로 대시보드로 돌아옴</li>
            </ol>
          </div>

          {!loginStatus.claude ? (
            <button
              onClick={handleClaudeLogin}
              disabled={loading}
              className="btn-login claude-code"
            >
              {loading ? '🔄 로그인 중...' : '🔑 Claude Console 로그인'}
            </button>
          ) : (
            <div className="auth-actions">
              <span className="auth-success">✓ 인증 완료</span>
              <button
                onClick={() => handleLogout('claude')}
                className="btn-logout"
              >
                로그아웃
              </button>
            </div>
          )}

          <div className="provider-links">
            <a href="https://console.anthropic.com/"
               target="_blank"
               rel="noopener noreferrer">
              🌐 Console
            </a>
            <a href="https://docs.anthropic.com/claude-code"
               target="_blank"
               rel="noopener noreferrer">
              📚 Docs
            </a>
          </div>
        </div>

        {/* Cursor IDE */}
        <div className="auth-provider">
          <div className="provider-header">
            <div>
              <h3>⚡ Cursor</h3>
              <p className="provider-subtitle">AI-First Code Editor</p>
            </div>
            {loginStatus.cursor && (
              <span className="status-badge connected">✓ 설치됨</span>
            )}
          </div>

          <div className="provider-features">
            <h4>인증 방식:</h4>
            <ul>
              <li>🚀 Cursor 앱 내 인증</li>
              <li>🤖 GPT-4 + Claude 3.5 지원</li>
              <li>💡 자체 OAuth 시스템</li>
              <li>🔄 멀티 모델 자동 전환</li>
            </ul>
          </div>

          <div className="provider-instructions">
            <h4>인증 절차:</h4>
            <ol>
              <li>"Cursor 웹 로그인" 버튼 클릭</li>
              <li>OpenAI 계정으로 로그인</li>
              <li>권한 승인 (API 액세스)</li>
              <li>자동으로 대시보드로 돌아옴</li>
            </ol>
          </div>

          {!loginStatus.cursor ? (
            <button
              onClick={handleCursorLogin}
              disabled={loading}
              className="btn-login cursor"
            >
              {loading ? '🔄 로그인 중...' : '🔑 Cursor 웹 로그인'}
            </button>
          ) : (
            <div className="auth-actions">
              <span className="auth-success">✓ 인증 완료</span>
              <button
                onClick={() => handleLogout('cursor')}
                className="btn-logout"
              >
                로그아웃
              </button>
            </div>
          )}

          <div className="provider-links">
            <a href="https://www.cursor.com/"
               target="_blank"
               rel="noopener noreferrer">
              🌐 공식 웹사이트
            </a>
            <a href="https://docs.cursor.com/"
               target="_blank"
               rel="noopener noreferrer">
              📚 문서
            </a>
          </div>
        </div>
      </div>

      <div className="integration-section">
        <h3>🔗 OAuth 인증 플로우</h3>
        <div className="integration-diagram">
          <div className="integration-flow">
            <div className="integration-step">
              <div className="step-icon">🌐</div>
              <div className="step-content">
                <h4>1. 로그인 버튼</h4>
                <p>대시보드에서 클릭</p>
              </div>
            </div>
            <div className="integration-arrow">→</div>
            <div className="integration-step">
              <div className="step-icon">🔐</div>
              <div className="step-content">
                <h4>2. Console 인증</h4>
                <p>웹에서 로그인</p>
              </div>
            </div>
            <div className="integration-arrow">→</div>
            <div className="integration-step">
              <div className="step-icon">✅</div>
              <div className="step-content">
                <h4>3. 권한 승인</h4>
                <p>API 키 생성 허용</p>
              </div>
            </div>
            <div className="integration-arrow">→</div>
            <div className="integration-step">
              <div className="step-icon">🤖</div>
              <div className="step-content">
                <h4>4. AI 분석</h4>
                <p>자동 연동 완료</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="auth-note">
        <h4>📌 OAuth 2.0 PKCE 인증:</h4>
        <ul>
          <li><strong>Claude Console</strong>: Anthropic 공식 OAuth 2.0 + PKCE 보안 인증</li>
          <li><strong>API 키 불필요</strong>: 콘솔 로그인만으로 자동 API 키 생성</li>
          <li><strong>자동 토큰 관리</strong>: Access Token, Refresh Token 자동 갱신</li>
          <li><strong>보안</strong>: PKCE (Proof Key for Code Exchange) 사용으로 안전</li>
          <li><strong>Claude Code 호환</strong>: VS Code Extension과 동일한 인증 방식</li>
        </ul>
      </div>

      <div className="alternative-section">
        <h4>🔧 기술 세부사항</h4>
        <p>이 시스템은 Claude Code for VS Code와 동일한 OAuth 플로우를 사용합니다:</p>
        <ul>
          <li>
            <strong>Client ID</strong>: <code>9d1c250a-e61b-44d9-88ed-5944d1962f5e</code>
          </li>
          <li>
            <strong>Scopes</strong>: <code>org:create_api_key user:profile user:inference user:sessions:claude_code</code>
          </li>
          <li>
            <strong>Authorization URL</strong>: <code>https://console.anthropic.com/oauth/authorize</code>
          </li>
          <li>
            <strong>Token URL</strong>: <code>https://console.anthropic.com/oauth/token</code>
          </li>
          <li>
            <strong>PKCE</strong>: SHA-256 code challenge method
          </li>
        </ul>
      </div>
    </div>
  );
};

export default AuthLogin;
