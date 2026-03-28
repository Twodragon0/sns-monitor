import React from 'react';
import { render, screen } from '@testing-library/react';
import CardSkeleton, { StatCardSkeleton, TableSkeleton } from './LoadingSkeleton';

describe('CardSkeleton', () => {
  it('renders one card by default', () => {
    render(<CardSkeleton />);
    const cards = document.querySelectorAll('.skeleton-card');
    expect(cards.length).toBe(1);
  });

  it('renders the specified count of cards', () => {
    render(<CardSkeleton count={3} />);
    const cards = document.querySelectorAll('.skeleton-card');
    expect(cards.length).toBe(3);
  });

  it('each card has aria-label for accessibility', () => {
    render(<CardSkeleton count={2} />);
    const cards = screen.getAllByLabelText('로딩 중');
    expect(cards.length).toBe(2);
  });
});

describe('StatCardSkeleton', () => {
  it('renders four stat cards by default', () => {
    render(<StatCardSkeleton />);
    const cards = document.querySelectorAll('.skeleton-stat-card');
    expect(cards.length).toBe(4);
  });

  it('renders the specified count of stat cards', () => {
    render(<StatCardSkeleton count={2} />);
    const cards = document.querySelectorAll('.skeleton-stat-card');
    expect(cards.length).toBe(2);
  });

  it('each stat card has accessible label', () => {
    render(<StatCardSkeleton count={1} />);
    expect(screen.getByLabelText('통계 로딩 중')).toBeInTheDocument();
  });
});

describe('TableSkeleton', () => {
  it('renders with default rows and columns', () => {
    render(<TableSkeleton />);
    expect(screen.getByLabelText('테이블 로딩 중')).toBeInTheDocument();
  });

  it('renders header cells matching column count', () => {
    render(<TableSkeleton rows={2} columns={3} />);
    const headerCells = document.querySelector('.skeleton-table-header')
      .querySelectorAll('.skeleton-table-cell');
    expect(headerCells.length).toBe(3);
  });

  it('renders correct number of rows', () => {
    render(<TableSkeleton rows={4} columns={2} />);
    const rows = document.querySelectorAll('.skeleton-table-row');
    expect(rows.length).toBe(4);
  });
});
