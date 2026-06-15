import React from 'react';
import { createRoot } from 'react-dom/client';
import './i18n';
import App from './App';

/* Error Boundary — prevents black screen on React crash */
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error?: Error; info?: string }
> {
  state: { hasError: boolean; error?: Error; info?: string } = { hasError: false };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    this.setState({ info: info.componentStack ?? '' });
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ background: '#1a1a2e', color: '#e0e0e0', padding: 32, height: '100vh', overflow: 'auto', fontFamily: 'Consolas, monospace' }}>
          <h2 style={{ color: '#ff6b6b', margin: '0 0 16px' }}>cmux-win Error</h2>
          <pre style={{ color: '#ffa07a', whiteSpace: 'pre-wrap', fontSize: 13 }}>
            {this.state.error?.message}
          </pre>
          <pre style={{ color: '#888', whiteSpace: 'pre-wrap', fontSize: 11, marginTop: 12, maxHeight: 300, overflow: 'auto' }}>
            {this.state.info}
          </pre>
          <button
            onClick={() => this.setState({ hasError: false, error: undefined, info: undefined })}
            style={{ marginTop: 20, padding: '8px 24px', background: '#0091FF', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 14 }}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const root = createRoot(document.getElementById('root')!);
root.render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
