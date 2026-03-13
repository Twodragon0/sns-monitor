import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import Dashboard from './components/Dashboard';
import CreatorDetail from './components/CreatorDetail';
import AnalysisTab from './components/AnalysisTab';
import { ToastContainer, useToast } from './components/Toast';

function App() {
  const [servicesStatus, setServicesStatus] = useState({});
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const { toasts, removeToast, error: showError } = useToast();

  const checkServicesStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/health');
      const isOnline = response.ok;
      const newStatus = { 'API Backend': isOnline ? 'online' : 'offline' };
      setServicesStatus(prev => {
        if (prev['API Backend'] === 'online' && !isOnline) {
          showError('API Backend 서비스에 연결할 수 없습니다.');
        }
        return newStatus;
      });
    } catch {
      setServicesStatus(prev => {
        if (prev['API Backend'] === 'online') {
          showError('API Backend 서비스에 연결할 수 없습니다.');
        }
        return { 'API Backend': 'offline' };
      });
    }
  }, [showError]);

  useEffect(() => {
    checkServicesStatus();
    const interval = setInterval(checkServicesStatus, 60000);
    return () => clearInterval(interval);
  }, [checkServicesStatus]);

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
      return <AnalysisTab />;
    }
    return <Dashboard />;
  };

  const isDetailPage = path.startsWith('/creator/') || path.startsWith('/analysis');
  const isBackendOnline = servicesStatus['API Backend'] === 'online';

  return (
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
  );
}

export default App;
