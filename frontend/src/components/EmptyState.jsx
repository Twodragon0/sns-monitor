import React from 'react';
import './EmptyState.css';

/**
 * 빈 상태 컴포넌트
 * 데이터가 없을 때 사용자에게 친화적인 메시지 표시
 */
const EmptyState = ({
  icon = '📭',
  title = '데이터가 없습니다',
  description,
  actionLabel,
  onAction,
  children
}) => {
  return (
    <div className="empty-state" role="status" aria-live="polite">
      <div className="empty-state-content">
        <div className="empty-state-icon" aria-hidden="true">
          {icon}
        </div>
        <h3 className="empty-state-title">{title}</h3>
        {description && (
          <p className="empty-state-description">{description}</p>
        )}
        {children && (
          <div className="empty-state-children">{children}</div>
        )}
        {actionLabel && onAction && (
          <button
            className="empty-state-action"
            onClick={onAction}
            aria-label={actionLabel}
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
};

/**
 * 특정 타입의 빈 상태 컴포넌트들
 */
export const EmptyStateNoData = ({ onRefresh }) => (
  <EmptyState
    icon="📊"
    title="데이터가 없습니다"
    description="수집된 데이터가 없습니다. 크롤러를 실행하여 데이터를 수집해주세요."
    actionLabel="새로고침"
    onAction={onRefresh}
  />
);

export const EmptyStateError = ({ error, onRetry }) => (
  <EmptyState
    icon="⚠️"
    title="데이터를 불러올 수 없습니다"
    description={error || "데이터를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}
    actionLabel="다시 시도"
    onAction={onRetry}
  />
);

export const EmptyStateLoading = () => (
  <EmptyState
    icon="⏳"
    title="데이터를 불러오는 중..."
    description="잠시만 기다려주세요."
  />
);

export const EmptyStateNoResults = ({ searchTerm, onClear }) => (
  <EmptyState
    icon="🔍"
    title="검색 결과가 없습니다"
    description={`"${searchTerm}"에 대한 검색 결과를 찾을 수 없습니다.`}
    actionLabel={onClear ? "필터 초기화" : undefined}
    onAction={onClear}
  />
);

export default EmptyState;


























