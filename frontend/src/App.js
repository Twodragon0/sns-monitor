import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';
import { API_BASE } from './config';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Dashboard from './components/Dashboard';
import CreatorDetail from './components/CreatorDetail';
import AnalysisTab from './components/AnalysisTab';
import { ToastContainer, useToast } from './components/Toast';

if (API_BASE) axios.defaults.withCredentials = true;

const HEALTH_CHECK_INTERVAL_MS = 120000; // 2분

function App() {
  const [servicesStatus, setServicesStatus] = useState({});
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const { toasts, removeToast, error: showError } = useToast();
  const showErrorRef = useRef(showError);
  showErrorRef.current = showError;

  const checkServicesStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/health`);
      const isOnline = response.ok;
      const newStatus = { 'API Backend': isOnline ? 'online' : 'offline' };
      setServicesStatus(prev => {
        if (prev['API Backend'] === 'online' && !isOnline) {
          showErrorRef.current('API Backend 서비스에 연결할 수 없습니다.');
        }
        return newStatus;
      });
    } catch {
      setServicesStatus(prev => {
        if (prev['API Backend'] === 'online') {
          showErrorRef.current('API Backend 서비스에 연결할 수 없습니다.');
        }
        return { 'API Backend': 'offline' };
      });
    }
  }, []);

  useEffect(() => {
    checkServicesStatus();
    const interval = setInterval(checkServicesStatus, HEALTH_CHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [checkServicesStatus]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const authError = params.get('auth_error');
    if (authError) {
      showError('OpenAI 로그인에 실패했습니다. 다시 시도해 주세요.');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [showError]);

  useEffect(() => {
    const updatePath = () => setCurrentPath(window.location.pathname);

    window.addEventListener('popstate', updatePath);

    const origPush = window.history.pushState;
    const origReplace = window.history.replaceState;
    window.history.pushState = function (...args) {
      origPush.apply(window.history, args);
      setTimeout(updatePath, 10);
    };
    window.history.replaceState = function (...args) {
      origReplace.apply(window.history, args);
      setTimeout(updatePath, 10);
    };

    return () => {
      window.removeEventListener('popstate', updatePath);
      window.history.pushState = origPush;
      window.history.replaceState = origReplace;
    };
  }, []);

  const path = currentPath || window.location.pathname;

  const renderContent = () => {
    if (path.startsWith('/creator/')) {
      return <CreatorDetail creatorId={path.split('/creator/')[1]} />;
    }
    if (path === '/analysis' || path.startsWith('/analysis')) {
      return <AnalysisTabWithAuth />;
    }
    return <Dashboard onShowError={showError} />;
  };

  const isDetailPage = path.startsWith('/creator/') || path.startsWith('/analysis');
  const isBackendOnline = servicesStatus['API Backend'] === 'online';

  return (
    <AuthProvider>
    <div className="App">
      {!isDetailPage && (
        <header className="App-header">
          <div className="App-header__inner">
            <h1
              className="App-header__title"
              onClick={() => window.history.pushState({}, '', '/')}
            >
              🔍 SNS Monitor
            </h1>
            <p className="App-header__desc">
              YouTube · DCInside · Reddit · Telegram · Kakao · X(Twitter) · Instagram · Facebook · Threads
            </p>
            <div className="App-header__status">
              <span className={`status-dot ${isBackendOnline ? 'online' : 'offline'}`} />
              <span className="status-label">
                API {isBackendOnline ? 'Connected' : 'Offline'}
              </span>
            </div>
          </div>
        </header>
      )}

      <main className="App-main">
        {renderContent()}
      </main>

      {!isDetailPage && (
        <footer className="App-footer">
          <p>SNS Monitor v2.0</p>
        </footer>
      )}

      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
    </AuthProvider>
  );
}

function AnalysisTabWithAuth() {
  const { loggedIn, authRequired, loading, login } = useAuth();
  if (loading) return <div className="analysis-auth-gate"><p>인증 확인 중…</p></div>;
  if (authRequired && !loggedIn) {
    return (
      <div className="analysis-auth-gate">
        <h2>🐟 수집 데이터 분석 · 요약 (MiroFish)</h2>
        <p>이 기능을 사용하려면 OpenAI OAuth로 로그인해 주세요.</p>
        <button type="button" className="btn-openai-login" onClick={() => login('/analysis')}>
          OpenAI(GPT)로 로그인
        </button>
      </div>
    );
  }
  return <AnalysisTab />;
}

export default App;
