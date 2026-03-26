import React from 'react';
import { render, screen } from '@testing-library/react';
import ErrorBoundary from './ErrorBoundary';

// Component that throws on render when told to
function Bomb({ shouldThrow }) {
  if (shouldThrow) {
    throw new Error('Test error from Bomb');
  }
  return <div>Child content</div>;
}

// Suppress console.error noise from ErrorBoundary.componentDidCatch during tests
beforeEach(() => {
  jest.spyOn(console, 'error').mockImplementation(() => {});
});
afterEach(() => {
  console.error.mockRestore();
});

describe('ErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div>Normal child</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('Normal child')).toBeInTheDocument();
  });

  it('shows error UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow />
      </ErrorBoundary>
    );
    expect(screen.getByText('오류가 발생했습니다')).toBeInTheDocument();
    expect(screen.getByText(/페이지를 새로고침/)).toBeInTheDocument();
  });

  it('shows a reload button when error is caught', () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow />
      </ErrorBoundary>
    );
    expect(screen.getByRole('button', { name: '새로고침' })).toBeInTheDocument();
  });
});
