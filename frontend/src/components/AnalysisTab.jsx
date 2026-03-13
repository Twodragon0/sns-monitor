import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

import { API_BASE } from '../config';

function AnalysisTab() {
  const [mirofishAvailable, setMirofishAvailable] = useState(false);
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

  // Chat state
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Check MiroFish availability
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const resp = await axios.get(`${API_BASE}/api/analysis/status`);
        setMirofishAvailable(resp.data.mirofish_available);
      } catch {
        setMirofishAvailable(false);
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

    // When MiroFish is offline, use local analysis
    if (!mirofishAvailable) {
      return startLocalAnalysis();
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
      <h2 style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        수집 데이터 분석 · 요약 (MiroFish)
        <span style={{
          fontSize: '12px',
          padding: '2px 8px',
          borderRadius: '12px',
          backgroundColor: mirofishAvailable ? '#d4edda' : '#f8d7da',
          color: mirofishAvailable ? '#155724' : '#721c24',
        }}>
          {mirofishAvailable ? '연결됨' : '오프라인'}
        </span>
      </h2>

      {!mirofishAvailable && (
        <div style={{
          padding: '14px 16px',
          backgroundColor: '#fff8e6',
          border: '1px solid #f0c14b',
          borderRadius: '8px',
          marginBottom: '20px',
          fontSize: '14px',
        }}>
          <strong style={{ display: 'block', marginBottom: '6px' }}>MiroFish가 실행 중이 아닙니다.</strong>
          <p style={{ margin: '0 0 6px', color: '#5a5a5a' }}>
            터미널에서 <code style={{ background: '#eee', padding: '2px 6px', borderRadius: '4px' }}>docker-compose --profile analysis up -d</code> 로 서비스를 띄운 뒤,
            <strong> OpenAI(OAuth) 로그인</strong>으로 API 키 없이 GPT로 분석할 수 있습니다.
          </p>
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
            {loading ? '분석 중…' : selectedSources.length === 0 ? '소스 선택 후 분석' : mirofishAvailable ? `${selectedSources.length}개 소스 분석` : `${selectedSources.length}개 소스 기본 분석`}
          </button>
          {!mirofishAvailable && selectedSources.length > 0 && (
            <span style={{ marginLeft: '10px', fontSize: '12px', color: '#666' }}>
              MiroFish 없이 로컬 감성 분석을 수행합니다
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
            로컬 키워드 기반 분석입니다. MiroFish를 실행하면 AI 심화 분석과 대화가 가능합니다.
          </p>
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

      {/* Chat Interface */}
      {analysisState === 'completed' && (
        <div style={{
          backgroundColor: 'white',
          padding: '16px',
          borderRadius: '8px',
          border: '1px solid #dee2e6',
          marginBottom: '20px',
        }}>
          <h3 style={{ marginTop: 0 }}>AI Chat</h3>
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
                Ask questions about the analysis results...
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
              onKeyDown={e => e.key === 'Enter' && sendChatMessage()}
              placeholder="Ask about the analysis..."
              style={{
                flex: 1,
                padding: '10px 12px',
                border: '1px solid #dee2e6',
                borderRadius: '6px',
                fontSize: '14px',
              }}
            />
            <button
              onClick={sendChatMessage}
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
              Send
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
