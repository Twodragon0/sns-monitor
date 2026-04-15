import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

import { API_BASE } from '../config';
import './AnalysisTab.css';
import { WordCloudAndCompare, DailyReportsPanel } from './analysis-tab/AnalysisWidgets';
import { AuthPanel, providerLabel } from './analysis-tab/AuthPanel';
import { LocalResultPanel, AiResultPanel } from './analysis-tab/ResultPanels';

/** Word Cloud + Gallery Comparison + Negative Alert */
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

  // Check SNS AI, LLM, and auth status
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

  // Apply preselect from Dashboard "AI 심화 분석" (same source as current URL result)
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
        // AI analysis service may not be running
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

    // When SNS AI is offline, use AI analysis (if available) or local analysis
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
      // Step 1: Transform SNS data and send to AI analysis service
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
      setError(err.response?.data?.error || err.message || '분석 실패');
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
      setError('그래프 데이터를 불러오지 못했습니다');
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
          className="analysis-tab__back-btn"
        >
          ← 대시보드로 돌아가기
        </button>
      </div>
      <h2 style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        수집 데이터 분석 · 요약
        {llmStatus.available ? (
          <span className="analysis-tab__status-badge analysis-tab__status-badge--ok">
            {providerLabel(llmStatus.provider)} 연결됨
          </span>
        ) : (
          <span className="analysis-tab__status-badge analysis-tab__status-badge--warn">
            AI 미연결 — 아래에서 API Key를 입력하세요
          </span>
        )}
      </h2>

      {/* URL Analysis Result context */}
      {urlAnalysisData && (
        <div className="analysis-tab__url-banner">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong className="analysis-tab__url-banner-title">
                URL 분석 결과 → AI 심화 분석
              </strong>
              <span className="analysis-tab__url-banner-sub">
                {urlAnalysisData.platform?.toUpperCase()} : {urlAnalysisData.title || urlAnalysisData.username || ''}
              </span>
            </div>
            <button
              type="button"
              onClick={() => { setUrlAnalysisData(null); setAiResult(null); setAnalysisState('idle'); setChatMessages([]); }}
              className="analysis-tab__url-banner-close"
            >
              닫기
            </button>
          </div>
          {loading && <p className="analysis-tab__url-banner-loading" style={{ margin: '8px 0 0' }}>AI 분석 진행 중...</p>}
        </div>
      )}

      {/* AI connection status / auth panel */}
      <div className={`analysis-tab__llm-panel ${llmStatus.available ? 'analysis-tab__llm-panel--ok' : 'analysis-tab__llm-panel--warn'}`}>
        {llmStatus.available ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong className="analysis-tab__llm-title--ok">
                {providerLabel(llmStatus.provider)} ({llmStatus.model}) 연결됨
              </strong>
              {authInfo.logged_in && (
                <button
                  type="button"
                  onClick={async () => {
                    await axios.post(`${API_BASE}/api/auth/logout`, {}, { withCredentials: true });
                    setAuthInfo({ logged_in: false, auth_required: false });
                    window.location.reload();
                  }}
                  className="analysis-tab__logout-btn"
                >
                  로그아웃
                </button>
              )}
            </div>
            <p className="analysis-tab__llm-desc">
              {llmStatus.auth_mode === 'cli' ? 'Docker 내부 SDK' : llmStatus.auth_mode === 'oauth' ? 'OAuth 인증' : llmStatus.auth_mode === 'api_key_session' ? '브라우저 API Key' : 'API Key'}로 AI 분석을 수행합니다.
            </p>
          </>
        ) : (
          <AuthPanel apiBase={API_BASE} onKeySet={() => window.location.reload()} openaiOAuthAvailable={authInfo.openai_oauth_available} />
        )}
      </div>

      {/* Data Source Selection */}
      <div className="analysis-tab__sources">
        <h3 style={{ marginTop: 0, marginBottom: '8px' }}>데이터 소스 선택</h3>
        {sources.length === 0 ? (
          <p className="analysis-tab__source-empty">수집된 소스가 없습니다. 크롤러를 먼저 실행하세요.</p>
        ) : (
          <>
            {selectedSources.length === 0 && (
              <p className="analysis-tab__source-hint">
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
                    className={`analysis-tab__source-btn ${isSelected ? 'analysis-tab__source-btn--selected' : 'analysis-tab__source-btn--unselected'}`}
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
            className={`analysis-tab__run-btn ${
              (selectedSources.length === 0 || loading)
                ? 'analysis-tab__run-btn--disabled'
                : mirofishAvailable
                  ? 'analysis-tab__run-btn--mirofish'
                  : 'analysis-tab__run-btn--ai'
            }`}
          >
            {loading ? '분석 중…' : selectedSources.length === 0 ? '소스 선택 후 분석' : llmStatus.available ? `${selectedSources.length}개 소스 AI 분석` : `${selectedSources.length}개 소스 기본 분석`}
          </button>
          {selectedSources.length > 0 && (
            <span className="analysis-tab__run-hint">
              {llmStatus.available
                ? `${providerLabel(llmStatus.provider)}로 AI 분석`
                : 'AI 미연결 — 키워드 기반 로컬 분석'}
            </span>
          )}
        </div>
      </div>

      {/* Progress */}
      {analysisState !== 'idle' && analysisState !== 'error' && analysisState !== 'completed' && (
        <div className="analysis-tab__progress">
          <h4 style={{ margin: '0 0 8px 0' }}>분석 진행 상황</h4>
          <div className="analysis-tab__progress-track">
            <div
              className="analysis-tab__progress-fill"
              style={{ width: `${getProgressPercent()}%` }}
            />
          </div>
          <p className="analysis-tab__progress-text">
            {analysisState === 'transforming' && 'SNS 데이터를 문서로 변환 중...'}
            {analysisState === 'building' && (taskProgress?.message || '지식 그래프 구축 중...')}
            {analysisState === 'generating' && '분석 보고서 생성 중...'}
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="analysis-tab__error">
          <strong>오류:</strong> {error}
        </div>
      )}

      {/* Local Analysis Result */}
      {localResult && <LocalResultPanel localResult={localResult} />}

      {/* Word Cloud + Gallery Comparison */}
      {(localResult || aiResult) && <WordCloudAndCompare keywords={localResult?.overall?.top_keywords || aiResult?.topics?.map(t => ({word: t.topic, count: t.count || 1})) || []} />}

      {/* AI Analysis Result */}
      {aiResult && <AiResultPanel aiResult={aiResult} />}

      {/* Completed - Graph Data */}
      {analysisState === 'completed' && currentProject && (
        <div className="analysis-tab__completed">
          <h4 className="analysis-tab__completed-title">분석 완료</h4>
          <p className="analysis-tab__completed-desc">
            프로젝트: <strong>{currentProject.project_name || currentProject.project_id}</strong>
          </p>
          {currentProject.ontology && (
            <p className="analysis-tab__completed-desc">
              개체: {currentProject.ontology.entity_types?.length || 0}종 /
              관계: {currentProject.ontology.edge_types?.length || 0}종
            </p>
          )}
          {taskProgress?.result?.graph_id && (
            <button
              onClick={() => viewGraphData(taskProgress.result.graph_id)}
              className="analysis-tab__view-graph-btn"
            >
              그래프 보기 ({taskProgress.result.node_count}개 노드, {taskProgress.result.edge_count}개 엣지)
            </button>
          )}
        </div>
      )}

      {/* Graph Visualization */}
      {report?.type === 'graph' && report.data && (
        <div className="analysis-tab__graph">
          <h3 style={{ marginTop: 0 }}>지식 그래프</h3>
          <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '300px' }}>
              <h4>개체 ({report.data.nodes?.length || 0})</h4>
              <div style={{ maxHeight: '400px', overflow: 'auto' }}>
                {(report.data.nodes || []).map((node, i) => (
                  <div key={node.id || node.name || i} className="analysis-tab__graph-node">
                    <strong>{node.name || node.label || node.id}</strong>
                    {node.type && <span className="analysis-tab__graph-node-type">({node.type})</span>}
                  </div>
                ))}
              </div>
            </div>
            <div style={{ flex: 1, minWidth: '300px' }}>
              <h4>관계 ({report.data.edges?.length || 0})</h4>
              <div style={{ maxHeight: '400px', overflow: 'auto' }}>
                {(report.data.edges || []).map((edge, i) => (
                  <div key={edge.source && edge.target ? `${edge.source}-${edge.target}-${i}` : i} className="analysis-tab__graph-edge">
                    {edge.source_name || edge.source}
                    <span className="analysis-tab__graph-edge-relation">{edge.relation || edge.type}</span>
                    {edge.target_name || edge.target}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Chat Interface - works with SNS AI, AI LLM, URL result, or all */}
      {analysisState === 'completed' && (currentProject || aiResult || urlAnalysisData || llmStatus.available) && (
        <div className="analysis-tab__chat">
          <h3 style={{ marginTop: 0 }}>
            AI 대화
            {aiResult && (
              <span className="analysis-tab__chat-provider">
                {providerLabel(aiResult.provider)}
              </span>
            )}
          </h3>
          <div className="analysis-tab__chat-messages">
            {chatMessages.length === 0 && (
              <p className="analysis-tab__chat-empty">
                분석 결과에 대해 질문하세요...
              </p>
            )}
            {chatMessages.map((msg, i) => (
              <div
                key={`${msg.role}-${i}`}
                className={`analysis-tab__chat-bubble ${msg.role === 'user' ? 'analysis-tab__chat-bubble--user' : 'analysis-tab__chat-bubble--assistant'}`}
              >
                {msg.content}
              </div>
            ))}
            {chatLoading && (
              <div className="analysis-tab__chat-loading">
                생각 중...
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
              className="analysis-tab__chat-input"
            />
            <button
              onClick={() => {
                if (urlAnalysisData && llmStatus.available) sendUrlAiChat();
                else if (currentProject && mirofishAvailable) sendChatMessage();
                else if (llmStatus.available) sendAiChat();
              }}
              disabled={chatLoading || !chatInput.trim()}
              className={`analysis-tab__chat-send-btn ${(chatLoading || !chatInput.trim()) ? 'analysis-tab__chat-send-btn--disabled' : 'analysis-tab__chat-send-btn--active'}`}
            >
              전송
            </button>
          </div>
        </div>
      )}

      {/* Existing Projects */}
      {projects.length > 0 && (
        <div className="analysis-tab__projects">
          <h3 style={{ marginTop: 0 }}>이전 분석</h3>
          <table className="analysis-tab__projects-table">
            <thead>
              <tr className="analysis-tab__projects-thead-row">
                <th>프로젝트</th>
                <th>상태</th>
                <th>개체</th>
                <th>생성일</th>
              </tr>
            </thead>
            <tbody>
              {projects.map(proj => (
                <tr key={proj.project_id} className="analysis-tab__projects-row">
                  <td style={{ padding: '8px' }}>{proj.name || proj.project_id}</td>
                  <td style={{ padding: '8px' }}>
                    <span className={`analysis-tab__project-status ${
                      proj.status === 'graph_completed' ? 'analysis-tab__project-status--completed' :
                      proj.status === 'graph_building' ? 'analysis-tab__project-status--building' :
                      'analysis-tab__project-status--default'
                    }`}>
                      {proj.status}
                    </span>
                  </td>
                  <td style={{ padding: '8px' }}>
                    {proj.ontology?.entity_types?.length || 0}종
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
      {/* Daily Reports */}
      <DailyReportsPanel />
    </div>
  );
}

/** Daily sentiment reports list + detail view */
export default AnalysisTab;
