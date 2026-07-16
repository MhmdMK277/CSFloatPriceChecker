/** App-wide toast stack; fed by user actions and live WebSocket events. */

import { createContext, useCallback, useContext, useMemo, useState } from "react";

export interface Toast {
  id: number;
  title: string;
  body: string;
  kind: "info" | "deal" | "error";
  href?: string;
}

interface ToastApi {
  push: (toast: Omit<Toast, "id">) => void;
}

const ToastContext = createContext<ToastApi>({ push: () => {} });

export const useToasts = () => useContext(ToastContext);

let nextId = 1;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((toast: Omit<Toast, "id">) => {
    const id = nextId++;
    setToasts((prev) => [...prev.slice(-3), { ...toast, id }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 8000);
  }, []);

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>
            <div className="toast-title">{t.title}</div>
            {t.href ? (
              <a href={t.href} target="_blank" rel="noreferrer" className="link-accent">
                {t.body}
              </a>
            ) : (
              <div>{t.body}</div>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
