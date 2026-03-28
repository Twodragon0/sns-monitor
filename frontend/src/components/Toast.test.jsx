import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import Toast, { ToastContainer, useToast } from './Toast';

// Stub CSS import
vi.mock('./Toast.css', () => ({}));

afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe('Toast', () => {
  it('renders without crashing', () => {
    const { container } = render(<Toast message="Hello" onClose={() => {}} />);
    expect(container).toBeTruthy();
  });

  it('displays the message text', () => {
    render(<Toast message="Test message" onClose={() => {}} />);
    expect(screen.getByText('Test message')).toBeInTheDocument();
  });

  it('renders with role="alert"', () => {
    render(<Toast message="Alert" onClose={() => {}} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('applies the correct type class', () => {
    const { container } = render(<Toast message="Success!" type="success" onClose={() => {}} />);
    expect(container.firstChild).toHaveClass('toast-success');
  });

  it('defaults to info type when no type prop given', () => {
    const { container } = render(<Toast message="Info" onClose={() => {}} />);
    expect(container.firstChild).toHaveClass('toast-info');
  });

  it('renders close button with accessible label', () => {
    render(<Toast message="Closeable" onClose={() => {}} />);
    expect(screen.getByRole('button', { name: /토스트 닫기/i })).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', async () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    render(<Toast message="Close me" duration={0} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /토스트 닫기/i }));
    // wait for the 300ms animation timeout
    act(() => { vi.advanceTimersByTime(300); });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('auto-closes after the given duration', async () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    render(<Toast message="Auto close" duration={1000} onClose={onClose} />);
    act(() => { vi.advanceTimersByTime(1000 + 300); });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not auto-close when duration is 0', async () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    render(<Toast message="Persistent" duration={0} onClose={onClose} />);
    act(() => { vi.advanceTimersByTime(5000); });
    expect(onClose).not.toHaveBeenCalled();
  });

  it.each([
    ['success', '✓'],
    ['error', '✗'],
    ['warning', '⚠'],
    ['info', 'ℹ'],
  ])('shows correct icon for type=%s', (type, expectedIcon) => {
    render(<Toast message="Icon test" type={type} onClose={() => {}} />);
    expect(screen.getByText(expectedIcon)).toBeInTheDocument();
  });
});

describe('ToastContainer', () => {
  it('renders without crashing with empty toasts', () => {
    const { container } = render(<ToastContainer toasts={[]} removeToast={() => {}} />);
    expect(container).toBeTruthy();
  });

  it('renders all provided toasts', () => {
    const toasts = [
      { id: 1, message: 'First', type: 'info', duration: 0 },
      { id: 2, message: 'Second', type: 'success', duration: 0 },
    ];
    render(<ToastContainer toasts={toasts} removeToast={() => {}} />);
    expect(screen.getByText('First')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
  });

  it('calls removeToast when a toast close button is clicked', async () => {
    vi.useFakeTimers();
    const removeToast = vi.fn();
    const toasts = [{ id: 42, message: 'Remove me', type: 'info', duration: 0 }];
    render(<ToastContainer toasts={toasts} removeToast={removeToast} />);
    fireEvent.click(screen.getByRole('button', { name: /토스트 닫기/i }));
    act(() => { vi.advanceTimersByTime(300); });
    expect(removeToast).toHaveBeenCalledWith(42);
  });
});

describe('useToast hook', () => {
  function TestComponent() {
    const { toasts, success, error, info, warning, removeToast } = useToast();
    return (
      <div>
        <button onClick={() => success('Success message')}>success</button>
        <button onClick={() => error('Error message')}>error</button>
        <button onClick={() => info('Info message')}>info</button>
        <button onClick={() => warning('Warning message')}>warning</button>
        {toasts.map(t => (
          <div key={t.id} data-testid="toast-item">
            <span>{t.message}</span>
            <span>{t.type}</span>
            <button onClick={() => removeToast(t.id)}>remove</button>
          </div>
        ))}
      </div>
    );
  }

  it('adds a success toast', () => {
    render(<TestComponent />);
    fireEvent.click(screen.getByRole('button', { name: 'success' }));
    expect(screen.getByText('Success message')).toBeInTheDocument();
  });

  it('adds an error toast', () => {
    render(<TestComponent />);
    fireEvent.click(screen.getByRole('button', { name: 'error' }));
    expect(screen.getByText('Error message')).toBeInTheDocument();
  });

  it('removes a toast by id', async () => {
    render(<TestComponent />);
    fireEvent.click(screen.getByRole('button', { name: 'info' }));
    expect(screen.getByText('Info message')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'remove' }));
    await waitFor(() => {
      expect(screen.queryByText('Info message')).not.toBeInTheDocument();
    });
  });

  it('accumulates multiple toasts', () => {
    render(<TestComponent />);
    fireEvent.click(screen.getByRole('button', { name: 'success' }));
    fireEvent.click(screen.getByRole('button', { name: 'error' }));
    expect(screen.getAllByTestId('toast-item')).toHaveLength(2);
  });
});
