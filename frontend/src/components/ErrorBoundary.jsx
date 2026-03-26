import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '40px', textAlign: 'center', color: '#666',
          maxWidth: '600px', margin: '80px auto',
        }}>
          <h2 style={{ color: '#e74c3c', marginBottom: '16px' }}>
            오류가 발생했습니다
          </h2>
          <p style={{ marginBottom: '24px', lineHeight: 1.6 }}>
            페이지를 새로고침하거나 잠시 후 다시 시도해 주세요.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '10px 24px', fontSize: '14px',
              backgroundColor: '#3498db', color: '#fff',
              border: 'none', borderRadius: '6px', cursor: 'pointer',
            }}
          >
            새로고침
          </button>
          {process.env.NODE_ENV === 'development' && this.state.error && (
            <pre style={{
              marginTop: '24px', padding: '16px', backgroundColor: '#f8f9fa',
              borderRadius: '6px', textAlign: 'left', fontSize: '12px',
              overflow: 'auto', maxHeight: '200px',
            }}>
              {this.state.error.toString()}
            </pre>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
