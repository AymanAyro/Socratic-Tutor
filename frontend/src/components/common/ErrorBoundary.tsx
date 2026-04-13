import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { hasError: boolean; message: string | null };

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("UI crash captured by ErrorBoundary", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md rounded-xl border border-border bg-surface p-5 text-center space-y-2">
          <h1 className="text-lg font-semibold text-text">Something went wrong</h1>
          <p className="text-sm text-muted">Please reload the page to continue your session.</p>
          {this.state.message && <p className="text-xs text-red-600">{this.state.message}</p>}
        </div>
      </div>
    );
  }
}
