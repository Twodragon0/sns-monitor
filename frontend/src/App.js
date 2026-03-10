import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import Dashboard from './components/Dashboard';
import ArchiveStudioDetail from './components/ArchiveStudioDetail';
import SkoshismDetail from './components/SkoshismDetail';
import BarabaraDetail from './components/BarabaraDetail';
import PsyChordDetail from './components/PsyChordDetail';
import URLAnalyzer from './components/URLAnalyzer';
import { ToastContainer, useToast } from './components/Toast';

function App() {
  const [servicesStatus, setServicesStatus] = useState({});
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const { toasts, removeToast, error: showError } = useToast();

  const checkServicesStatus = useCallback(async () => {
    const services = [
      { name: 'API Backend', endpoint: '/api/health' },
    ];
    
    const status = {};
    for (const service of services) {
      try {
        const response = await fetch(service.endpoint);
        const isOnline = response.ok;
        status[service.name] = isOnline ? 'online' : 'offline';
        
        // 상태 변경 시 토스트 표시 (초기 로드 제외)
        if (servicesStatus[service.name] && servicesStatus[service.name] !== status[service.name]) {
          if (isOnline) {
            // 서비스 복구 알림은 조용히 (너무 많은 알림 방지)
          } else {
            showError(`${service.name} 서비스에 연결할 수 없습니다.`);
          }
        }
      } catch (err) {
        status[service.name] = 'offline';
        if (servicesStatus[service.name] === 'online') {
          showError(`${service.name} 서비스에 연결할 수 없습니다.`);
        }
      }
    }
    setServicesStatus(status);
  }, [servicesStatus, showError]);

  useEffect(() => {
    checkServicesStatus();
    const interval = setInterval(checkServicesStatus, 60000); // 1분마다 체크
    return () => clearInterval(interval);
  }, [checkServicesStatus]);

  // 경로 변경 감지 (더 강력한 감지)
  useEffect(() => {
    // 초기 경로 설정 (즉시 실행)
    const initialPath = window.location.pathname;
    console.log('🚀 Initial path on mount:', initialPath);
    setCurrentPath(initialPath);

    const updatePath = () => {
      const newPath = window.location.pathname;
      console.log('🔄 updatePath called, newPath:', newPath);
      setCurrentPath(prevPath => {
        if (prevPath !== newPath) {
          console.log('✅ Path changed:', prevPath, '->', newPath);
          return newPath;
        }
        return prevPath;
      });
    };

    // popstate 이벤트 (뒤로가기/앞으로가기)
    const handlePopState = () => {
      console.log('🔙 PopState event triggered');
      updatePath();
    };
    window.addEventListener('popstate', handlePopState);

    // pushstate/replacestate 감지를 위한 인터셉터
    const originalPushState = window.history.pushState;
    const originalReplaceState = window.history.replaceState;

    window.history.pushState = function(...args) {
      originalPushState.apply(window.history, args);
      console.log('➡️ PushState called with:', args[2]);
      setTimeout(updatePath, 10);
    };

    window.history.replaceState = function(...args) {
      originalReplaceState.apply(window.history, args);
      console.log('🔄 ReplaceState called with:', args[2]);
      setTimeout(updatePath, 10);
    };

    // 주기적으로 경로 확인 (fallback) - ref를 사용하여 최신 값 참조
    const interval = setInterval(() => {
      const currentLocationPath = window.location.pathname;
      setCurrentPath(prevPath => {
        if (prevPath !== currentLocationPath) {
          console.log('⏰ Interval check: path mismatch detected', currentLocationPath, 'vs', prevPath);
          return currentLocationPath;
        }
        return prevPath;
      });
    }, 100);

    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.history.pushState = originalPushState;
      window.history.replaceState = originalReplaceState;
      clearInterval(interval);
    };
  }, []); // 의존성 배열을 비워서 마운트 시 한 번만 실행

  const renderMainContent = () => {
    // currentPath와 window.location.pathname 모두 확인 (직접 URL 접근 대응)
    const path = currentPath || window.location.pathname;
    console.log('🔍 renderMainContent - path:', path, 'currentPath:', currentPath, 'window.location.pathname:', window.location.pathname);

    // /akaiv-studio 경로 체크 (정확한 매칭 또는 포함)
    if (path === '/akaiv-studio' || path.startsWith('/akaiv-studio')) {
      console.log('✅ Rendering ArchiveStudioDetail for path:', path);
      return <ArchiveStudioDetail />;
    }
    // /skoshism 경로 체크
    if (path === '/skoshism' || path.startsWith('/skoshism')) {
      console.log('✅ Rendering SkoshismDetail for path:', path);
      return <SkoshismDetail />;
    }
    // /barabara 경로 체크
    if (path === '/barabara' || path.startsWith('/barabara')) {
      console.log('✅ Rendering BarabaraDetail for path:', path);
      return <BarabaraDetail />;
    }
    // /psy-chord 경로 체크
    if (path === '/psy-chord' || path.startsWith('/psy-chord')) {
      console.log('✅ Rendering PsyChordDetail for path:', path);
      return <PsyChordDetail />;
    }
    // /analyze 경로 체크
    if (path === '/analyze' || path.startsWith('/analyze')) {
      return <URLAnalyzer />;
    }
    console.log('📊 Rendering Dashboard for path:', path);
    return <Dashboard />;
  };

  // 현재 경로 확인
  const path = currentPath || window.location.pathname;
  const isDetailPage = (path === '/akaiv-studio' || path.startsWith('/akaiv-studio')) ||
                       (path === '/skoshism' || path.startsWith('/skoshism')) ||
                       (path === '/barabara' || path.startsWith('/barabara')) ||
                       (path === '/psy-chord' || path.startsWith('/psy-chord')) ||
                       (path === '/analyze' || path.startsWith('/analyze'));

  return (
    <div className="App">
      {!isDetailPage && (
        <header className="App-header">
          <h1>📊 SNS 모니터링 시스템</h1>
          <p>YouTube, Twitter/X, DC인사이드, Vuddy 크리에이터 실시간 모니터링 & AI 분석</p>
          <div className="header-status">
            {Object.entries(servicesStatus).map(([name, status]) => (
              <span key={name} className={`service-status-badge ${status}`}>
                {name}: {status === 'online' ? '✓' : '✗'}
              </span>
            ))}
          </div>
        </header>
      )}

      <main className="App-main">
        {renderMainContent()}
      </main>

      {!isDetailPage && (
        <footer className="App-footer">
          <p>SNS 모니터링 시스템 v1.0 - 로컬 개발 환경</p>
          <p>
            <a href="/docs/LOCAL_DEVELOPMENT.md" target="_blank" rel="noopener noreferrer">문서 보기</a>
          </p>
        </footer>
      )}

      {/* 토스트 컨테이너 */}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}

export default App;
