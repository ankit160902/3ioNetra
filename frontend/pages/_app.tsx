import '../styles/globals.css';
import type { AppProps } from 'next/app';
import { ThemeProvider } from '../hooks/useTheme';
import { ToastProvider } from '../components/Toast';

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ThemeProvider>
      <ToastProvider>
        <Component {...pageProps} />
      </ToastProvider>
    </ThemeProvider>
  );
}
