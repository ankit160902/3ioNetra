import '../styles/globals.css';
import type { AppProps } from 'next/app';
import React from 'react';
import Head from 'next/head';
import { ThemeProvider } from '../hooks/useTheme';
import { ToastProvider } from '../components/Toast';

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center text-center p-8">
          <div>
            <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100">Something went wrong</h1>
            <p className="text-sm text-gray-500 mt-2">Please refresh the page.</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 bg-orange-500 text-white rounded-lg text-sm"
            >
              Refresh
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        <meta charSet="utf-8" />
        <meta name="description" content="3ioNetra — Mitra, your spiritual companion" />
      </Head>
      <ThemeProvider>
        <ToastProvider>
          <ErrorBoundary>
            <Component {...pageProps} />
          </ErrorBoundary>
        </ToastProvider>
      </ThemeProvider>
    </>
  );
}
