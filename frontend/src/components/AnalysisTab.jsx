import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

import { API_BASE } from '../config';

/** Inline auth panel: OAuth login + API key input */
function AuthPanel({ apiBase, onKeySet, openaiOAuthAvailable }) {
  const [showApiKey, setShowApiKey] = useState(false);
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
      <strong style={{ display: 'block', marginBottom: '10px' }}>AI 분석을 사용하려면 로그인하세요</strong>

      {/* OAuth buttons */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '12px' }}>
        <button
          type="button"
          onClick={() => { window.location.href = `${apiBase}/api/auth/anthropic?return_to=/analysis`; }}
          style={{
            padding: '10px 20px', fontSize: '14px', fontWeight: '600',
            background: '#d97706', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}
        >
          Claude 로그인
        </button>
        {openaiOAuthAvailable && (
          <button
            type="button"
            onClick={() => { window.location.href = `${apiBase}/api/auth/openai?return_to=/analysis`; }}
            style={{
              padding: '10px 20px', fontSize: '14px', fontWeight: '600',
              background: '#10a37f', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '6px',
            }}
          >
            ChatGPT 로그인
          </button>
        )}
      </div>

      <p style={{ margin: '0 0 8px', fontSize: '12px', color: '#64748b' }}>
        Anthropic/OpenAI 계정으로 브라우저 인증 후 AI 분석이 활성화됩니다.
      </p>

      {/* API Key fallback (collapsible) */}
      <button
        type="button"
        onClick={() => setShowApiKey(!showApiKey)}
        style={{
          padding: '4px 10px', fontSize: '11px', color: '#94a3b8',
          background: 'transparent', border: 'none', cursor: 'pointer', textDecoration: 'underline',
        }}
      >
        {showApiKey ? 'API Key 입력 닫기' : 'API Key 직접 입력'}
      </button>

      {showApiKey && (
        <div style={{ padding: '10px', marginTop: '6px', background: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
          <div style={{ display: 'flex', gap: '6px', marginBottom: '6px' }}>
            <select
              value={keyProvider}
              onChange={e => setKeyProvider(e.target.value)}
              style={{ padding: '6px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '12px' }}
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submitKey()}
              placeholder={keyProvider === 'anthropic' ? 'sk-ant-...' : 'sk-...'}
              style={{ flex: 1, padding: '6px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '12px' }}
            />
            <button
              type="button" onClick={submitKey} disabled={keySaving || !apiKey.trim()}
              style={{
                padding: '6px 12px', fontSize: '12px', fontWeight: '600',
                background: keySaving ? '#94a3b8' : '#3b82f6', color: 'white',
                border: 'none', borderRadius: '4px', cursor: keySaving ? 'not-allowed' : 'pointer',
              }}
            >
              {keySaving ? '...' : '연결'}
            </button>
          </div>
          {keyError && <div style={{ color: '#dc2626', fontSize: '11px' }}>{keyError}</div>}
        </div>
      )}
    </>
  );
}

function AnalysisTab() {
  const [mirofishAvailable, setMirofishAvailable] = useState(false);
  const [llmStatus, setLlmStatus] = useState({ available: false, provider: null, model: null });
  const [sources, setSources] = useState([]);
  const [selectedSources, setSelectedSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [analysisState, setAnalysisState] = useState('idle'); // idle | transforming | building | generating | completed | error
  const [currentProject, setCurrentProject] = useState(null);
  const [currentTaskId, setCurrentTaskId] = useState(null);
  const [taskProgress, setTaskProgress] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [projects, setProjects] = useState([]);
  const [localResult, setLocalResult] = useState(null);
  const [aiResult, setAiResult] = useState(null);
  const [urlAnalysisData, setUrlAnalysisData] = useState(null); // Data from URL Analyzer
  const [authInfo, setAuthInfo] = useState({ logged_in: false, auth_required: false });

  // Chat state
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Check MiroFish, LLM, and auth status
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const resp = await axios.get(`${API_BASE}/api/analysis/status`);
        setMirofishAvailable(resp.data.mirofish_available);
      } catch {
        setMirofishAvailable(false);
      }
      try {
        const llmResp = await axios.get(`${API_BASE}/api/analysis/llm/status`);
        setLlmStatus(llmResp.data);
      } catch {
        setLlmStatus({ available: false, provider: null, model: null });
      }
      try {
        const authResp = await axios.get(`${API_BASE}/api/auth/me`, { withCredentials: true });
        setAuthInfo(authResp.data);
      } catch {
        setAuthInfo({ logged_in: false, auth_required: false });
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Load available sources
  useEffect(() => {
    const loadSources = async () => {
      try {
        const resp = await axios.get(`${API_BASE}/api/analysis/sources`);
        setSources(resp.data.sources || []);
      } catch (err) {
        console.error('Failed to load sources:', err);
      }
    };
    loadSources();
  }, []);

  // Apply preselect from Dashboard "MiroFish로 심화 분석" (same source as current URL result)
  useEffect(() => {
    if (sources.length === 0) return;
    try {
      const raw = sessionStorage.getItem('analysisPreselect');
      if (!raw) return;
      sessionStorage.removeItem('analysisPreselect');
      const preselect = JSON.parse(raw);
      if (!Array.isArray(preselect) || preselect.length === 0) return;
      const keySet = new Set(sources.map(s => `${s.type}:${s.id}`));
      const toSelect = preselect.filter(p => keySet.has(`${p.type}:${p.id}`));
      if (toSelect.length > 0) setSelectedSources(toSelect);
    } catch (_) { /* ignore */ }
  }, [sources]);

  // Receive URL analysis result from URLAnalyzer and auto-analyze
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem('urlAnalysisResult');
      if (!raw) return;
      sessionStorage.removeItem('urlAnalysisResult');
      const data = JSON.parse(raw);
      if (data && (data.platform || data.title)) {
        setUrlAnalysisData(data);
      }
    } catch (_) { /* ignore */ }
  }, []);

  // Load existing projects
  useEffect(() => {
    if (!mirofishAvailable) return;
    const loadProjects = async () => {
      try {
        const resp = await axios.get(`${API_BASE}/api/analysis/projects`);
        if (resp.data.success) {
          setProjects(resp.data.data || []);
        }
      } catch {
        // MiroFish may not be running
      }
    };
    loadProjects();
  }, [mirofishAvailable]);

  // Poll task progress
  useEffect(() => {
    if (!currentTaskId || analysisState === 'completed' || analysisState === 'error') return;

    const pollInterval = setInterval(async () => {
      try {
        const resp = await axios.get(`${API_BASE}/api/analysis/graph/task/${currentTaskId}`);
        const taskData = resp.data.data || resp.data;
        setTaskProgress(taskData);

        if (taskData.status === 'completed') {
          clearInterval(pollInterval);
          if (analysisState === 'building') {
            setAnalysisState('completed');
          }
        } else if (taskData.status === 'failed') {
          clearInterval(pollInterval);
          setAnalysisState('error');
          setError(taskData.message || taskData.error || 'Task failed');
        }
      } catch (err) {
        console.error('Poll error:', err);
      }
    }, 3000);

    return () => clearInterval(pollInterval);
  }, [currentTaskId, analysisState]);

  const toggleSource = useCallback((source) => {
    setSelectedSources(prev => {
      const key = `${source.type}:${source.id}`;
      const exists = prev.find(s => `${s.type}:${s.id}` === key);
      if (exists) {
        return prev.filter(s => `${s.type}:${s.id}` !== key);
      }
      return [...prev, source];
    });
  }, []);

  const startAiAnalysis = async () => {
    if (selectedSources.length === 0) return;
    setLoading(true);
    setError(null);
    setAiResult(null);
    setLocalResult(null);
    setAnalysisState('transforming');

    try {
      const resp = await axios.post(`${API_BASE}/api/analysis/ai-summary`, {
        sources: selectedSources.map(s => ({ type: s.type, id: s.id })),
      });
      setAiResult(resp.data);
      setAnalysisState('completed');
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'AI analysis failed');
      setAnalysisState('error');
    } finally {
      setLoading(false);
    }
  };

  // AI analysis of URL analysis result (from URLAnalyzer pass-through)
  const startUrlAiAnalysis = useCallback(async (resultData) => {
    setLoading(true);
    setError(null);
    setAiResult(null);
    setLocalResult(null);
    setAnalysisState('transforming');
    setChatMessages([]);

    try {
      const resp = await axios.post(`${API_BASE}/api/analysis/ai-url-analyze`, {
        result: resultData,
      });
      setAiResult(resp.data);
      setAnalysisState('completed');
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'AI analysis failed');
      setAnalysisState('error');
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-trigger AI analysis when URL result is passed
  useEffect(() => {
    if (!urlAnalysisData) return;
    if (!llmStatus.available) return;
    startUrlAiAnalysis(urlAnalysisData);
  }, [urlAnalysisData, llmStatus.available, startUrlAiAnalysis]);

  // Chat about URL analysis result
  const sendUrlAiChat = async () => {
    if (!chatInput.trim() || !urlAnalysisData) return;
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setChatLoading(true);

    try {
      const resp = await axios.post(`${API_BASE}/api/analysis/ai-url-chat`, {
        result: urlAnalysisData,
        message: userMsg,
        chat_history: chatMessages,
      });
      if (resp.data.success) {
        setChatMessages(prev => [...prev, { role: 'assistant', content: resp.data.response }]);
      }
    } catch (err) {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.response?.data?.error || err.message}`,
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  const sendAiChat = async () => {
    if (!chatInput.trim() || selectedSources.length === 0) return;

    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setChatLoading(true);

    try {
      const resp = await axios.post(`${API_BASE}/api/analysis/ai-chat`, {
        sources: selectedSources.map(s => ({ type: s.type, id: s.id })),
        message: userMsg,
        chat_history: chatMessages,
      });

      if (resp.data.success) {
        const reply = resp.data.response || JSON.stringify(resp.data);
        setChatMessages(prev => [...prev, { role: 'assistant', content: reply }]);
      }
    } catch (err) {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.response?.data?.error || err.message}`,
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  const startLocalAnalysis = async () => {
    if (selectedSources.length === 0) return;
    setLoading(true);
    setError(null);
    setLocalResult(null);
    setAnalysisState('transforming');

    try {
      const resp = await axios.post(`${API_BASE}/api/analysis/local-summary`, {
        sources: selectedSources.map(s => ({ type: s.type, id: s.id })),
      });
      setLocalResult(resp.data);
      setAnalysisState('completed');
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Local analysis failed');
      setAnalysisState('error');
    } finally {
      setLoading(false);
    }
  };

  const startAnalysis = async () => {
    if (selectedSources.length === 0) return;

    // When MiroFish is offline, use AI analysis (if available) or local analysis
    if (!mirofishAvailable) {
      return llmStatus.available ? startAiAnalysis() : startLocalAnalysis();
    }

    setLoading(true);
    setError(null);
    setAnalysisState('transforming');
    setReport(null);
    setChatMessages([]);
    setLocalResult(null);

    try {
      // Step 1: Transform SNS data and send to MiroFish
      const transformResp = await axios.post(`${API_BASE}/api/analysis/transform`, {
        sources: selectedSources.map(s => ({ type: s.type, id: s.id })),
        project_name: `SNS Analysis - ${new Date().toISOString().split('T')[0]}`,
        simulation_requirement: 'Analyze social media community sentiment, identify key trends, influencer dynamics, and predict audience reactions to content and events.',
      });

      if (!transformResp.data.success) {
        throw new Error(transformResp.data.error || 'Transform failed');
      }

      const projectId = transformResp.data.data.project_id;
      setCurrentProject(transformResp.data.data);
      setAnalysisState('building');

      // Step 2: Build knowledge graph
      const buildResp = await axios.post(`${API_BASE}/api/analysis/graph/build`, {
        project_id: projectId,
      });

      if (!buildResp.data.success) {
        throw new Error(buildResp.data.error || 'Graph build failed');
      }

      setCurrentTaskId(buildResp.data.data.task_id);
      setLoading(false);
    } catch (err) {
      setLoading(false);
      setAnalysisState('error');
      setError(err.response?.data?.error || err.message || 'Analysis failed');
    }
  };

  const viewGraphData = async (graphId) => {
    try {
      const resp = await axios.get(`${API_BASE}/api/analysis/graph/data/${graphId}`);
      if (resp.data.success) {
        setReport({
          type: 'graph',
          data: resp.data.data,
        });
      }
    } catch (err) {
      setError('Failed to load graph data');
    }
  };

  const sendChatMessage = async () => {
    if (!chatInput.trim() || !currentProject) return;

    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setChatLoading(true);

    try {
      const resp = await axios.post(`${API_BASE}/api/analysis/report/chat`, {
        simulation_id: currentProject.simulation_id || currentProject.project_id,
        message: userMsg,
        chat_history: chatMessages,
      });

      if (resp.data.success) {
        const reply = resp.data.data.response || resp.data.data.content || JSON.stringify(resp.data.data);
        setChatMessages(prev => [...prev, { role: 'assistant', content: reply }]);
      }
    } catch (err) {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.response?.data?.error || err.message}`,
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  const getProgressPercent = () => {
    if (taskProgress?.progress) return taskProgress.progress;
    if (analysisState === 'transforming') return 10;
    if (analysisState === 'building') return 30;
    return 0;
  };

  const goDashboard = (e) => {
    e.preventDefault();
    window.history.pushState({}, '', '/');
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <button
          type="button"
          onClick={goDashboard}
          style={{
            padding: '6px 12px',
            fontSize: '13px',
            color: '#666',
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          ← 대시보드로 돌아가기
        </button>
      </div>
      <h2 style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        수집 데이터 분석 · 요약
        <span style={{
          fontSize: '12px',
          padding: '2px 8px',
          borderRadius: '12px',
          backgroundColor: mirofishAvailable ? '#d4edda' : '#f8d7da',
          color: mirofishAvailable ? '#155724' : '#721c24',
        }}>
          MiroFish {mirofishAvailable ? '연결됨' : '오프라인'}
        </span>
        {llmStatus.available && (
          <span style={{
            fontSize: '12px',
            padding: '2px 8px',
            borderRadius: '12px',
            backgroundColor: '#d4edda',
            color: '#155724',
          }}>
            {llmStatus.provider === 'anthropic' ? 'Claude' : 'ChatGPT'} 사용 가능
          </span>
        )}
      </h2>

      {/* URL Analysis Result context */}
      {urlAnalysisData && (
        <div style={{
          padding: '14px 16px',
          backgroundColor: '#f0f4ff',
          border: '1px solid #c7d2fe',
          borderRadius: '8px',
          marginBottom: '16px',
          fontSize: '14px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong style={{ color: '#4338ca' }}>
                URL 분석 결과 → AI 심화 분석
              </strong>
              <span style={{ marginLeft: '8px', color: '#6366f1' }}>
                {urlAnalysisData.platform?.toUpperCase()} : {urlAnalysisData.title || urlAnalysisData.username || ''}
              </span>
            </div>
            <button
              type="button"
              onClick={() => { setUrlAnalysisData(null); setAiResult(null); setAnalysisState('idle'); setChatMessages([]); }}
              style={{
                padding: '4px 10px', fontSize: '12px', color: '#666',
                background: '#e2e8f0', border: 'none', borderRadius: '4px', cursor: 'pointer',
              }}
            >
              닫기
            </button>
          </div>
          {loading && <p style={{ margin: '8px 0 0', color: '#4338ca' }}>AI 분석 진행 중...</p>}
        </div>
      )}

      {!mirofishAvailable && (
        <div style={{
          padding: '14px 16px',
          backgroundColor: llmStatus.available ? '#e8f5e9' : '#fff8e6',
          border: `1px solid ${llmStatus.available ? '#a5d6a7' : '#f0c14b'}`,
          borderRadius: '8px',
          marginBottom: '20px',
          fontSize: '14px',
        }}>
          {llmStatus.available ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong style={{ color: '#2e7d32' }}>
                  AI 분석 사용 가능 ({llmStatus.provider === 'anthropic' ? 'Claude' : llmStatus.provider === 'openai_oauth' ? 'ChatGPT (OAuth)' : 'ChatGPT'} - {llmStatus.model})
                </strong>
                {authInfo.logged_in && (
                  <button
                    type="button"
                    onClick={async () => {
                      await axios.post(`${API_BASE}/api/auth/logout`, {}, { withCredentials: true });
                      setAuthInfo({ logged_in: false, auth_required: false });
                      window.location.reload();
                    }}
                    style={{ padding: '4px 10px', fontSize: '12px', color: '#666', background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: '4px', cursor: 'pointer' }}
                  >
                    로그아웃
                  </button>
                )}
              </div>
              <p style={{ margin: '4px 0 0', color: '#5a5a5a' }}>
                {llmStatus.auth_mode === 'oauth' ? 'OAuth 인증으로' : 'API Key로'} AI 심화 분석을 수행합니다.
              </p>
            </>
          ) : (
            <AuthPanel apiBase={API_BASE} onKeySet={() => window.location.reload()} openaiOAuthAvailable={authInfo.openai_oauth_available} />
          )}
        </div>
      )}

      {/* Data Source Selection */}
      <div style={{
        backgroundColor: '#f8f9fa',
        padding: '16px',
        borderRadius: '8px',
        marginBottom: '20px',
      }}>
        <h3 style={{ marginTop: 0, marginBottom: '8px' }}>데이터 소스 선택</h3>
        {sources.length === 0 ? (
          <p style={{ color: '#666', marginBottom: 0 }}>수집된 소스가 없습니다. 크롤러를 먼저 실행하세요.</p>
        ) : (
          <>
            {selectedSources.length === 0 && (
              <p style={{ color: '#555', fontSize: '13px', marginBottom: '10px' }}>
                아래 소스 중 <strong>하나 이상 클릭</strong>하여 선택한 뒤 [분석] 버튼을 누르세요.
              </p>
            )}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {sources.map(src => {
                const key = `${src.type}:${src.id}`;
                const isSelected = selectedSources.find(s => `${s.type}:${s.id}` === key);
                return (
                  <button
                    key={key}
                    onClick={() => toggleSource(src)}
                    type="button"
                    style={{
                      padding: '8px 16px',
                      border: `2px solid ${isSelected ? '#007bff' : '#dee2e6'}`,
                      borderRadius: '20px',
                      backgroundColor: isSelected ? '#007bff' : 'white',
                      color: isSelected ? 'white' : '#333',
                      cursor: 'pointer',
                      fontSize: '13px',
                      transition: 'all 0.2s',
                    }}
                  >
                    {src.type === 'youtube' ? 'YT' : 'DC'} {src.name}
                    {src.files != null && ` (${src.files}개)`}
                  </button>
                );
              })}
            </div>
          </>
        )}

        <div style={{ marginTop: '12px' }}>
          <button
            type="button"
            onClick={startAnalysis}
            disabled={selectedSources.length === 0 || loading}
            style={{
              padding: '10px 24px',
              backgroundColor: (selectedSources.length === 0 || loading) ? '#ccc' : mirofishAvailable ? '#28a745' : '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: (selectedSources.length === 0 || loading) ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: 'bold',
            }}
          >
            {loading ? '분석 중…' : selectedSources.length === 0 ? '소스 선택 후 분석' : mirofishAvailable ? `${selectedSources.length}개 소스 분석` : llmStatus.available ? `${selectedSources.length}개 소스 AI 분석` : `${selectedSources.length}개 소스 기본 분석`}
          </button>
          {!mirofishAvailable && selectedSources.length > 0 && (
            <span style={{ marginLeft: '10px', fontSize: '12px', color: '#666' }}>
              {llmStatus.available
                ? `${llmStatus.provider === 'anthropic' ? 'Claude' : 'ChatGPT'}로 AI 분석을 수행합니다`
                : 'MiroFish 없이 로컬 감성 분석을 수행합니다'}
            </span>
          )}
        </div>
      </div>

      {/* Progress */}
      {analysisState !== 'idle' && analysisState !== 'error' && analysisState !== 'completed' && (
        <div style={{
          backgroundColor: '#e3f2fd',
          padding: '16px',
          borderRadius: '8px',
          marginBottom: '20px',
        }}>
          <h4 style={{ margin: '0 0 8px 0' }}>Analysis Progress</h4>
          <div style={{
            width: '100%',
            backgroundColor: '#bbdefb',
            borderRadius: '4px',
            overflow: 'hidden',
            marginBottom: '8px',
          }}>
            <div style={{
              width: `${getProgressPercent()}%`,
              height: '8px',
              backgroundColor: '#1976d2',
              transition: 'width 0.5s ease',
            }} />
          </div>
          <p style={{ margin: 0, fontSize: '13px', color: '#1565c0' }}>
            {analysisState === 'transforming' && 'Transforming SNS data into documents...'}
            {analysisState === 'building' && (taskProgress?.message || 'Building knowledge graph...')}
            {analysisState === 'generating' && 'Generating analysis report...'}
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          padding: '16px',
          backgroundColor: '#f8d7da',
          border: '1px solid #f5c6cb',
          borderRadius: '8px',
          marginBottom: '20px',
          color: '#721c24',
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Local Analysis Result */}
      {localResult && (
        <div style={{
          backgroundColor: 'white',
          padding: '20px',
          borderRadius: '8px',
          border: '1px solid #dee2e6',
          marginBottom: '20px',
        }}>
          <h3 style={{ marginTop: 0, marginBottom: '16px' }}>로컬 분석 결과 ({localResult.total_items}건 분석)</h3>

          {/* Overall sentiment */}
          {localResult.overall && (
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>전체 감성 분포</h4>
              <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
                {['positive', 'neutral', 'negative'].map(key => {
                  const count = localResult.overall.sentiment?.[key] || 0;
                  const pct = localResult.overall.distribution?.[key] || 0;
                  const colors = { positive: '#10b981', neutral: '#9ca3af', negative: '#ef4444' };
                  const labels = { positive: '긍정', neutral: '중립', negative: '부정' };
                  return (
                    <div key={key} style={{
                      flex: 1, textAlign: 'center', padding: '12px',
                      backgroundColor: `${colors[key]}15`, borderRadius: '8px',
                      border: `1px solid ${colors[key]}40`,
                    }}>
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: colors[key] }}>
                        {Math.round(pct * 100)}%
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        {labels[key]} ({count}건)
                      </div>
                    </div>
                  );
                })}
              </div>
              {/* Sentiment bar */}
              <div style={{ display: 'flex', height: '8px', borderRadius: '4px', overflow: 'hidden' }}>
                {['positive', 'neutral', 'negative'].map(key => {
                  const pct = (localResult.overall.distribution?.[key] || 0) * 100;
                  const colors = { positive: '#10b981', neutral: '#9ca3af', negative: '#ef4444' };
                  return <div key={key} style={{ width: `${pct}%`, backgroundColor: colors[key] }} />;
                })}
              </div>
            </div>
          )}

          {/* Top keywords */}
          {localResult.overall?.top_keywords?.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>주요 키워드</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {localResult.overall.top_keywords.slice(0, 15).map((kw, i) => (
                  <span key={i} style={{
                    padding: '4px 10px', borderRadius: '12px',
                    backgroundColor: i < 3 ? '#dbeafe' : '#f1f5f9',
                    color: i < 3 ? '#1d4ed8' : '#475569',
                    fontSize: '13px', fontWeight: i < 3 ? '600' : '400',
                  }}>
                    {kw.word} <span style={{ color: '#999', fontSize: '11px' }}>({kw.count})</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Per-source breakdown */}
          {localResult.sources?.length > 1 && (
            <div>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>소스별 분석</h4>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                {localResult.sources.map((src, i) => (
                  <div key={i} style={{
                    flex: '1 1 280px', padding: '12px',
                    backgroundColor: '#f8f9fa', borderRadius: '6px',
                    border: '1px solid #e2e8f0',
                  }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '6px', fontSize: '13px' }}>
                      {src.type === 'youtube' ? 'YT' : 'DC'} {src.name}
                      <span style={{ fontWeight: 'normal', color: '#888', marginLeft: '6px' }}>({src.item_count}건)</span>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', fontSize: '12px' }}>
                      {['positive', 'neutral', 'negative'].map(key => {
                        const count = src.sentiment?.sentiment?.[key] || 0;
                        const labels = { positive: '긍정', neutral: '중립', negative: '부정' };
                        const colors = { positive: '#10b981', neutral: '#9ca3af', negative: '#ef4444' };
                        return (
                          <span key={key} style={{ color: colors[key] }}>
                            {labels[key]}: {count}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p style={{ marginTop: '16px', marginBottom: 0, fontSize: '12px', color: '#999' }}>
            로컬 키워드 기반 분석입니다. OPENAI_API_KEY 또는 ANTHROPIC_API_KEY를 설정하면 AI 심화 분석이 가능합니다.
          </p>
        </div>
      )}

      {/* AI Analysis Result */}
      {aiResult && (
        <div style={{
          backgroundColor: 'white',
          padding: '20px',
          borderRadius: '8px',
          border: '1px solid #dee2e6',
          marginBottom: '20px',
        }}>
          <h3 style={{ marginTop: 0, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            AI 분석 결과
            <span style={{
              fontSize: '11px', padding: '2px 8px', borderRadius: '12px',
              backgroundColor: '#e3f2fd', color: '#1565c0',
            }}>
              {aiResult.provider === 'anthropic' ? 'Claude' : 'ChatGPT'} ({aiResult.model})
            </span>
          </h3>

          {/* Summary */}
          {aiResult.summary && (
            <div style={{
              padding: '14px', backgroundColor: '#f8f9fa', borderRadius: '8px',
              marginBottom: '16px', lineHeight: '1.7', whiteSpace: 'pre-wrap',
            }}>
              {aiResult.summary}
            </div>
          )}

          {/* Sentiment from AI */}
          {aiResult.sentiment && (
            <div style={{ marginBottom: '16px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>AI 감성 분석</h4>
              <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
                {[
                  { key: 'positive_pct', label: '긍정', color: '#10b981' },
                  { key: 'neutral_pct', label: '중립', color: '#9ca3af' },
                  { key: 'negative_pct', label: '부정', color: '#ef4444' },
                ].map(({ key, label, color }) => (
                  <div key={key} style={{
                    flex: 1, textAlign: 'center', padding: '12px',
                    backgroundColor: `${color}15`, borderRadius: '8px',
                    border: `1px solid ${color}40`,
                  }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color }}>
                      {aiResult.sentiment[key] || 0}%
                    </div>
                    <div style={{ fontSize: '12px', color: '#666' }}>{label}</div>
                  </div>
                ))}
              </div>
              {aiResult.sentiment.positive_keywords?.length > 0 && (
                <div style={{ fontSize: '13px', marginTop: '8px' }}>
                  <span style={{ color: '#10b981', fontWeight: '600' }}>긍정 키워드:</span>{' '}
                  {aiResult.sentiment.positive_keywords.join(', ')}
                </div>
              )}
              {aiResult.sentiment.negative_keywords?.length > 0 && (
                <div style={{ fontSize: '13px', marginTop: '4px' }}>
                  <span style={{ color: '#ef4444', fontWeight: '600' }}>부정 키워드:</span>{' '}
                  {aiResult.sentiment.negative_keywords.join(', ')}
                </div>
              )}
            </div>
          )}

          {/* Topics */}
          {aiResult.topics?.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>주요 토픽</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {aiResult.topics.map((t, i) => (
                  <div key={i} style={{
                    padding: '8px 14px', borderRadius: '8px',
                    backgroundColor: i < 3 ? '#dbeafe' : '#f1f5f9',
                    border: `1px solid ${i < 3 ? '#93c5fd' : '#e2e8f0'}`,
                  }}>
                    <div style={{ fontWeight: '600', fontSize: '13px', color: i < 3 ? '#1d4ed8' : '#475569' }}>
                      {t.topic} {t.count ? `(${t.count})` : ''}
                    </div>
                    {t.description && (
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '2px' }}>{t.description}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Key Opinions */}
          {aiResult.key_opinions?.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>주요 의견</h4>
              {aiResult.key_opinions.map((op, i) => (
                <div key={i} style={{
                  padding: '10px 14px', marginBottom: '6px', borderRadius: '6px',
                  backgroundColor: op.type === 'positive' ? '#f0fdf4' : op.type === 'negative' ? '#fef2f2' : '#f8f9fa',
                  borderLeft: `3px solid ${op.type === 'positive' ? '#10b981' : op.type === 'negative' ? '#ef4444' : '#9ca3af'}`,
                  fontSize: '13px',
                }}>
                  {op.text}
                  {op.support && <span style={{ color: '#999', marginLeft: '8px', fontSize: '11px' }}>({op.support}건)</span>}
                </div>
              ))}
            </div>
          )}

          {/* Insights */}
          {aiResult.insights?.length > 0 && (
            <div>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#555' }}>인사이트</h4>
              {aiResult.insights.map((ins, i) => (
                <div key={i} style={{
                  padding: '8px 12px', marginBottom: '4px', fontSize: '13px',
                  color: '#374151', lineHeight: '1.5',
                }}>
                  {ins}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Completed - Graph Data */}
      {analysisState === 'completed' && currentProject && (
        <div style={{
          backgroundColor: '#d4edda',
          padding: '16px',
          borderRadius: '8px',
          marginBottom: '20px',
        }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#155724' }}>Analysis Complete</h4>
          <p style={{ margin: '0 0 8px 0', fontSize: '13px' }}>
            Project: <strong>{currentProject.project_name || currentProject.project_id}</strong>
          </p>
          {currentProject.ontology && (
            <p style={{ margin: '0 0 8px 0', fontSize: '13px' }}>
              Entities: {currentProject.ontology.entity_types?.length || 0} types /
              Relations: {currentProject.ontology.edge_types?.length || 0} types
            </p>
          )}
          {taskProgress?.result?.graph_id && (
            <button
              onClick={() => viewGraphData(taskProgress.result.graph_id)}
              style={{
                padding: '6px 16px',
                backgroundColor: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px',
              }}
            >
              View Graph ({taskProgress.result.node_count} nodes, {taskProgress.result.edge_count} edges)
            </button>
          )}
        </div>
      )}

      {/* Graph Visualization */}
      {report?.type === 'graph' && report.data && (
        <div style={{
          backgroundColor: 'white',
          padding: '16px',
          borderRadius: '8px',
          border: '1px solid #dee2e6',
          marginBottom: '20px',
        }}>
          <h3 style={{ marginTop: 0 }}>Knowledge Graph</h3>
          <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '300px' }}>
              <h4>Entities ({report.data.nodes?.length || 0})</h4>
              <div style={{ maxHeight: '400px', overflow: 'auto' }}>
                {(report.data.nodes || []).map((node, i) => (
                  <div key={i} style={{
                    padding: '8px',
                    marginBottom: '4px',
                    backgroundColor: '#f8f9fa',
                    borderRadius: '4px',
                    fontSize: '13px',
                  }}>
                    <strong>{node.name || node.label || node.id}</strong>
                    {node.type && <span style={{ color: '#666', marginLeft: '8px' }}>({node.type})</span>}
                  </div>
                ))}
              </div>
            </div>
            <div style={{ flex: 1, minWidth: '300px' }}>
              <h4>Relationships ({report.data.edges?.length || 0})</h4>
              <div style={{ maxHeight: '400px', overflow: 'auto' }}>
                {(report.data.edges || []).map((edge, i) => (
                  <div key={i} style={{
                    padding: '8px',
                    marginBottom: '4px',
                    backgroundColor: '#f0f7ff',
                    borderRadius: '4px',
                    fontSize: '13px',
                  }}>
                    {edge.source_name || edge.source}
                    <span style={{ color: '#007bff', margin: '0 6px' }}>{edge.relation || edge.type}</span>
                    {edge.target_name || edge.target}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Chat Interface - works with MiroFish, AI LLM, URL result, or all */}
      {analysisState === 'completed' && (currentProject || aiResult || urlAnalysisData || llmStatus.available) && (
        <div style={{
          backgroundColor: 'white',
          padding: '16px',
          borderRadius: '8px',
          border: '1px solid #dee2e6',
          marginBottom: '20px',
        }}>
          <h3 style={{ marginTop: 0 }}>
            AI 대화
            {aiResult && (
              <span style={{ fontSize: '12px', fontWeight: 'normal', color: '#888', marginLeft: '8px' }}>
                {aiResult.provider === 'anthropic' ? 'Claude' : 'ChatGPT'}
              </span>
            )}
          </h3>
          <div style={{
            maxHeight: '400px',
            overflow: 'auto',
            marginBottom: '12px',
            padding: '8px',
            backgroundColor: '#f8f9fa',
            borderRadius: '4px',
          }}>
            {chatMessages.length === 0 && (
              <p style={{ color: '#999', textAlign: 'center', margin: '20px 0' }}>
                분석 결과에 대해 질문하세요...
              </p>
            )}
            {chatMessages.map((msg, i) => (
              <div key={i} style={{
                padding: '8px 12px',
                marginBottom: '8px',
                borderRadius: '8px',
                backgroundColor: msg.role === 'user' ? '#007bff' : '#e9ecef',
                color: msg.role === 'user' ? 'white' : '#333',
                marginLeft: msg.role === 'user' ? '40px' : '0',
                marginRight: msg.role === 'assistant' ? '40px' : '0',
                whiteSpace: 'pre-wrap',
                fontSize: '14px',
              }}>
                {msg.content}
              </div>
            ))}
            {chatLoading && (
              <div style={{ textAlign: 'center', color: '#999', padding: '8px' }}>
                Thinking...
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  if (urlAnalysisData && llmStatus.available) sendUrlAiChat();
                  else if (currentProject && mirofishAvailable) sendChatMessage();
                  else if (llmStatus.available) sendAiChat();
                }
              }}
              placeholder="분석 결과에 대해 질문하세요..."
              style={{
                flex: 1,
                padding: '10px 12px',
                border: '1px solid #dee2e6',
                borderRadius: '6px',
                fontSize: '14px',
              }}
            />
            <button
              onClick={() => {
                if (urlAnalysisData && llmStatus.available) sendUrlAiChat();
                else if (currentProject && mirofishAvailable) sendChatMessage();
                else if (llmStatus.available) sendAiChat();
              }}
              disabled={chatLoading || !chatInput.trim()}
              style={{
                padding: '10px 20px',
                backgroundColor: chatLoading ? '#ccc' : '#007bff',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: chatLoading ? 'not-allowed' : 'pointer',
              }}
            >
              전송
            </button>
          </div>
        </div>
      )}

      {/* Existing Projects */}
      {projects.length > 0 && (
        <div style={{
          backgroundColor: 'white',
          padding: '16px',
          borderRadius: '8px',
          border: '1px solid #dee2e6',
        }}>
          <h3 style={{ marginTop: 0 }}>Previous Analyses</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #dee2e6' }}>
                <th style={{ textAlign: 'left', padding: '8px' }}>Project</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>Status</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>Entities</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>Created</th>
              </tr>
            </thead>
            <tbody>
              {projects.map(proj => (
                <tr key={proj.project_id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '8px' }}>{proj.name || proj.project_id}</td>
                  <td style={{ padding: '8px' }}>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: '12px',
                      fontSize: '11px',
                      backgroundColor: proj.status === 'graph_completed' ? '#d4edda' :
                                      proj.status === 'graph_building' ? '#fff3cd' : '#e2e3e5',
                      color: proj.status === 'graph_completed' ? '#155724' :
                             proj.status === 'graph_building' ? '#856404' : '#383d41',
                    }}>
                      {proj.status}
                    </span>
                  </td>
                  <td style={{ padding: '8px' }}>
                    {proj.ontology?.entity_types?.length || 0} types
                  </td>
                  <td style={{ padding: '8px' }}>
                    {proj.created_at ? new Date(proj.created_at).toLocaleDateString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default AnalysisTab;
