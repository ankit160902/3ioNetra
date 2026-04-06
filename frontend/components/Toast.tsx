import { useState, createContext, useContext, useCallback } from 'react';
import * as ToastPrimitive from '@radix-ui/react-toast';
import { X, Check, AlertCircle, Info } from 'lucide-react';

interface ToastItem {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface ToastContextType {
  toast: (message: string, type?: 'success' | 'error' | 'info') => void;
}

const ToastContext = createContext<ToastContextType>({ toast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((message: string, type: 'success' | 'error' | 'info' = 'success') => {
    const id = Math.random().toString(36).slice(2);
    setToasts(prev => [...prev, { id, message, type }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const Icon = ({ type }: { type: string }) => {
    if (type === 'success') return <Check className="w-3.5 h-3.5" />;
    if (type === 'error') return <AlertCircle className="w-3.5 h-3.5" />;
    return <Info className="w-3.5 h-3.5" />;
  };

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      <ToastPrimitive.Provider swipeDirection="right" duration={2500}>
        {children}
        {toasts.map(t => (
          <ToastPrimitive.Root
            key={t.id}
            open
            onOpenChange={(open) => { if (!open) removeToast(t.id); }}
            className={`
              flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border backdrop-blur-xl
              data-[state=open]:animate-toast-in data-[state=closed]:animate-toast-out
              data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)]
              data-[swipe=cancel]:translate-x-0 data-[swipe=cancel]:transition-transform
              data-[swipe=end]:animate-toast-out
              ${t.type === 'success'
                ? 'bg-green-50/90 dark:bg-green-900/40 border-green-200 dark:border-green-800 text-green-800 dark:text-green-200'
                : t.type === 'error'
                  ? 'bg-red-50/90 dark:bg-red-900/40 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200'
                  : 'bg-orange-50/90 dark:bg-orange-900/40 border-orange-200 dark:border-orange-800 text-orange-800 dark:text-orange-200'}
            `}
          >
            <Icon type={t.type} />
            <ToastPrimitive.Description className="text-xs font-bold flex-1">
              {t.message}
            </ToastPrimitive.Description>
            <ToastPrimitive.Close className="p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 transition-colors">
              <X className="w-3 h-3" />
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)] outline-none" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}
