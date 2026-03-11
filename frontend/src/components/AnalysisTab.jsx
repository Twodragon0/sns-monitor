import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || '';

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

  const startAnalysis = async () => {
    if (selectedSources.length === 0) return;

    setLoading(true);
    setError(null);
    setAnalysisState('transforming');
    setReport(null);
    setChatMessages([]);

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

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        AI Analysis (MiroFish)
        <span style={{
          fontSize: '12px',
          padding: '2px 8px',
          borderRadius: '12px',
          backgroundColor: mirofishAvailable ? '#d4edda' : '#f8d7da',
          color: mirofishAvailable ? '#155724' : '#721c24',
        }}>
          {mirofishAvailable ? 'Connected' : 'Offline'}
        </span>
      </h2>

      {!mirofishAvailable && (
        <div style={{
          padding: '16px',
          backgroundColor: '#fff3cd',
          border: '1px solid #ffc107',
          borderRadius: '8px',
          marginBottom: '20px',
        }}>
          <strong>MiroFish service is not running.</strong>
          <br />
          <code style={{ fontSize: '13px' }}>docker-compose --profile analysis up -d</code>
          <br />
          <small>Configure API keys in <code>.env.mirofish</code> first.</small>
        </div>
      )}

      {/* Data Source Selection */}
      <div style={{
        backgroundColor: '#f8f9fa',
        padding: '16px',
        borderRadius: '8px',
        marginBottom: '20px',
      }}>
        <h3 style={{ marginTop: 0, marginBottom: '12px' }}>Select Data Sources</h3>
        {sources.length === 0 ? (
          <p style={{ color: '#666' }}>No data sources found. Run crawlers first.</p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {sources.map(src => {
              const key = `${src.type}:${src.id}`;
              const isSelected = selectedSources.find(s => `${s.type}:${s.id}` === key);
              return (
                <button
                  key={key}
                  onClick={() => toggleSource(src)}
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
                  {src.files && ` (${src.files} files)`}
                </button>
              );
            })}
          </div>
        )}

        <button
          onClick={startAnalysis}
          disabled={!mirofishAvailable || selectedSources.length === 0 || loading}
          style={{
            marginTop: '12px',
            padding: '10px 24px',
            backgroundColor: (!mirofishAvailable || selectedSources.length === 0 || loading) ? '#ccc' : '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: (!mirofishAvailable || selectedSources.length === 0 || loading) ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: 'bold',
          }}
        >
          {loading ? 'Analyzing...' : `Analyze ${selectedSources.length} Source(s)`}
        </button>
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
