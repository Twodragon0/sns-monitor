import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import EmptyState, {
  EmptyStateNoData,
  EmptyStateError,
  EmptyStateLoading,
  EmptyStateNoResults,
} from './EmptyState';

describe('EmptyState', () => {
  it('renders without crashing', () => {
    const { container } = render(<EmptyState />);
    expect(container).toBeTruthy();
  });

  it('renders default title when no props provided', () => {
    render(<EmptyState />);
    expect(screen.getByText('데이터가 없습니다')).toBeInTheDocument();
  });

  it('renders custom title and description', () => {
    render(<EmptyState title="Custom Title" description="Custom description" />);
    expect(screen.getByText('Custom Title')).toBeInTheDocument();
    expect(screen.getByText('Custom description')).toBeInTheDocument();
  });

  it('does not render description when omitted', () => {
    render(<EmptyState title="Only Title" />);
    expect(screen.queryByRole('paragraph')).toBeNull();
  });

  it('renders action button when actionLabel and onAction are provided', () => {
    const onAction = vi.fn();
    render(<EmptyState actionLabel="Retry" onAction={onAction} />);
    const btn = screen.getByRole('button', { name: 'Retry' });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it('does not render action button when only actionLabel is provided without onAction', () => {
    render(<EmptyState actionLabel="Retry" />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('renders children content', () => {
    render(
      <EmptyState>
        <span data-testid="child">Child content</span>
      </EmptyState>
    );
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('has role=status for accessibility', () => {
    render(<EmptyState />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});

describe('EmptyStateNoData', () => {
  it('renders with refresh button', () => {
    const onRefresh = vi.fn();
    render(<EmptyStateNoData onRefresh={onRefresh} />);
    expect(screen.getByText('데이터가 없습니다')).toBeInTheDocument();
    const btn = screen.getByRole('button', { name: '새로고침' });
    fireEvent.click(btn);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});

describe('EmptyStateError', () => {
  it('renders with custom error message', () => {
    const onRetry = vi.fn();
    render(<EmptyStateError error="Custom error" onRetry={onRetry} />);
    expect(screen.getByText('Custom error')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('renders default error message when error prop is empty', () => {
    render(<EmptyStateError onRetry={vi.fn()} />);
    expect(screen.getByText(/오류가 발생했습니다/)).toBeInTheDocument();
  });
});

describe('EmptyStateLoading', () => {
  it('renders loading state', () => {
    render(<EmptyStateLoading />);
    expect(screen.getByText('데이터를 불러오는 중...')).toBeInTheDocument();
  });
});

describe('EmptyStateNoResults', () => {
  it('renders with search term', () => {
    render(<EmptyStateNoResults searchTerm="keyword" />);
    expect(screen.getByText(/"keyword"에 대한 검색 결과를 찾을 수 없습니다/)).toBeInTheDocument();
  });

  it('renders clear button when onClear provided', () => {
    const onClear = vi.fn();
    render(<EmptyStateNoResults searchTerm="foo" onClear={onClear} />);
    fireEvent.click(screen.getByRole('button', { name: '필터 초기화' }));
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
