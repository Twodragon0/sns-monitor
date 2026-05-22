import React, { useState, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { API_BASE } from '../../config';

/** AI 심화 분석 버튼: 상태 확인 후 이동, 현재 결과 소스 사전 선택. authRequired 시 로그인 유도. */
export function AiCtaButton({ result, onShowError }) {
  const [loading, setLoading] = useState(false);
  const { loggedIn, authRequired, login } = useAuth();

  const goToAiAnalysis = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API_BASE}/api/analysis/status`, { timeout: 5000 });
      if (!data.mirofish_available) {
        onShowError?.('AI 분석 서비스에 연결할 수 없습니다.\n\n시작 방법:\n1. .env.mirofish 파일에 OPENAI_API_KEY 설정\n2. docker-compose --profile analysis up -d\n3. 페이지 새로고침 후 다시 시도');
      }
      const preselect = [];
      if (result.platform === 'youtube' && (result.channel_id || result.channelId)) {
        preselect.push({ type: 'youtube', id: result.channel_id || result.channelId });
      }
      if (result.platform === 'dcinside' && result.gallery_id) {
        preselect.push({ type: 'dcinside', id: result.gallery_id });
      }
      if (preselect.length) {
        try {
          sessionStorage.setItem('analysisPreselect', JSON.stringify(preselect));
        } catch (_) { /* ignore */ }
      }
      window.history.pushState({}, '', '/analysis');
      window.dispatchEvent(new PopStateEvent('popstate'));
    } catch (_) {
      onShowError?.('AI 분석 상태 확인에 실패했습니다. API 서버 연결을 확인해 주세요.');
    } finally {
      setLoading(false);
    }
  }, [result, onShowError]);

  if (authRequired && !loggedIn) {
    return (
      <div className="result__mirofish-cta">
        <p className="result__mirofish-cta-desc">수집된 데이터를 엔티티 그래프로 구축하고 AI 채팅으로 인사이트를 질의할 수 있습니다. OpenAI 로그인 후 이용 가능합니다.</p>
        <button
          type="button"
          className="result__mirofish-cta-btn result__mirofish-cta-btn--login"
          onClick={() => login('/analysis')}
        >
          OpenAI(GPT)로 로그인 후 AI 심화 분석
        </button>
      </div>
    );
  }

  return (
    <div className="result__mirofish-cta">
      <p className="result__mirofish-cta-desc">수집된 데이터를 엔티티 그래프로 구축하고 AI 채팅으로 인사이트를 질의할 수 있습니다.</p>
      <button
        type="button"
        className="result__mirofish-cta-btn"
        onClick={goToAiAnalysis}
        disabled={loading}
      >
        {loading ? '확인 중…' : 'AI 심화 분석'}
      </button>
    </div>
  );
}
