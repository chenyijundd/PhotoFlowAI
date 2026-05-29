/**
 * PhotoFlow AI — React Error Boundary
 *
 * Catches any unhandled errors in the component tree and displays
 * a simple fallback UI instead of a white screen.
 *
 * Current phase: simple fallback UI only — no crash reporting.
 */

import React from "react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary] Component crashed:", error.message);
    console.error("[ErrorBoundary] Component stack:", info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="state-screen error-state">
          <div className="state-icon">⚠️</div>
          <h2>界面发生错误</h2>
          <p style={{ maxWidth: 500, margin: "0 auto", color: "#999", fontSize: 13 }}>
            {this.state.error?.message || "未知错误"}
          </p>
          <button
            className="btn-primary"
            onClick={this.handleReset}
            style={{ marginTop: 16 }}
          >
            重试
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
