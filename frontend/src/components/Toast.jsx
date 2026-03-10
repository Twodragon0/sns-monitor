import React, { useState, useEffect } from 'react';
import './Toast.css';

/**
 * 토스트 메시지 컴포넌트
 * 사용자 액션에 대한 피드백 제공
 */
const Toast = ({ message, type = 'info', duration = 3000, onClose }) => {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        setIsVisible(false);
        setTimeout(() => {
          onClose?.();
        }, 300); // 애니메이션 완료 대기
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(() => {
      onClose?.();
    }, 300);
  };

  const icons = {
    success: '✓',
    error: '✗',
    warning: '⚠',
    info: 'ℹ'
  };

  return (
    <div
      className={`toast toast-${type} ${isVisible ? 'toast-visible' : 'toast-hidden'}`}
      role="alert"
      aria-live="polite"
      aria-atomic="true"
    >
      <div className="toast-content">
        <span className="toast-icon" aria-hidden="true">
          {icons[type]}
        </span>
        <span className="toast-message">{message}</span>
      </div>
      <button
        className="toast-close"
        onClick={handleClose}
        aria-label="토스트 닫기"
      >
        ×
      </button>
    </div>
  );
};

/**
 * 토스트 컨테이너 (여러 토스트 관리)
 */
export const ToastContainer = ({ toasts, removeToast }) => {
  return (
    <div className="toast-container" aria-live="polite" aria-atomic="true">
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          duration={toast.duration}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
};

/**
 * 토스트 Hook
 */
export const useToast = () => {
  const [toasts, setToasts] = useState([]);

  const showToast = (message, type = 'info', duration = 3000) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type, duration }]);
    return id;
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  const success = (message, duration) => showToast(message, 'success', duration);
  const error = (message, duration) => showToast(message, 'error', duration);
  const warning = (message, duration) => showToast(message, 'warning', duration);
  const info = (message, duration) => showToast(message, 'info', duration);

  return {
    toasts,
    showToast,
    removeToast,
    success,
    error,
    warning,
    info
  };
};

export default Toast;


























