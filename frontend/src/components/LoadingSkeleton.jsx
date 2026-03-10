import React from 'react';
import './LoadingSkeleton.css';

/**
 * 스켈레톤 로딩 컴포넌트
 * 데이터 로딩 중 사용자에게 시각적 피드백 제공
 */
export const CardSkeleton = ({ count = 1 }) => {
  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="skeleton-card" aria-label="로딩 중">
          <div className="skeleton-header">
            <div className="skeleton-avatar"></div>
            <div className="skeleton-text-group">
              <div className="skeleton-line skeleton-title"></div>
              <div className="skeleton-line skeleton-subtitle"></div>
            </div>
          </div>
          <div className="skeleton-content">
            <div className="skeleton-line"></div>
            <div className="skeleton-line skeleton-short"></div>
          </div>
          <div className="skeleton-footer">
            <div className="skeleton-badge"></div>
            <div className="skeleton-badge"></div>
          </div>
        </div>
      ))}
    </>
  );
};

export const StatCardSkeleton = ({ count = 4 }) => {
  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="skeleton-stat-card" aria-label="통계 로딩 중">
          <div className="skeleton-icon"></div>
          <div className="skeleton-stat-content">
            <div className="skeleton-line skeleton-stat-label"></div>
            <div className="skeleton-line skeleton-stat-value"></div>
          </div>
        </div>
      ))}
    </>
  );
};

export const TableSkeleton = ({ rows = 5, columns = 4 }) => {
  return (
    <div className="skeleton-table" aria-label="테이블 로딩 중">
      <div className="skeleton-table-header">
        {Array.from({ length: columns }).map((_, index) => (
          <div key={index} className="skeleton-table-cell"></div>
        ))}
      </div>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="skeleton-table-row">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <div key={colIndex} className="skeleton-table-cell"></div>
          ))}
        </div>
      ))}
    </div>
  );
};

export default CardSkeleton;


























