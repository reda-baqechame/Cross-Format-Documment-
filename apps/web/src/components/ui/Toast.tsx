"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";

type ToastTone = "success" | "error" | "info";
type Toast = { id: number; tone: ToastTone; message: string };

type ToastApi = {
  toast: (message: string, tone?: ToastTone) => void;
  success: (message: string) => void;
  error: (message: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

/** Lightweight, dependency-free toast provider. Wrap the app once (see providers.tsx). */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((message: string, tone: ToastTone = "info") => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, tone, message }]);
  }, []);

  const api: ToastApi = {
    toast,
    success: (m) => toast(m, "success"),
    error: (m) => toast(m, "error"),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4 safe-bottom">
        {toasts.map((t) => (
          <ToastCard key={t.id} toast={t} onDone={() => remove(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ toast, onDone }: { toast: Toast; onDone: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDone, toast.tone === "error" ? 6000 : 3500);
    return () => clearTimeout(timer);
  }, [toast.tone, onDone]);

  const Icon = toast.tone === "success" ? CheckCircle2 : toast.tone === "error" ? XCircle : Info;
  const accent =
    toast.tone === "success"
      ? "text-trust-600"
      : toast.tone === "error"
        ? "text-red-600"
        : "text-brand-600";

  return (
    <div
      role="status"
      className="pointer-events-auto flex w-full max-w-sm animate-slide-up items-start gap-3 rounded-xl border border-line bg-white px-4 py-3 shadow-pop"
    >
      <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${accent}`} />
      <p className="flex-1 text-sm text-slate-700">{toast.message}</p>
      <button
        type="button"
        onClick={onDone}
        aria-label="Dismiss"
        className="shrink-0 text-slate-400 transition-colors hover:text-slate-600"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

/** Access the toast API. Falls back to a no-op if used outside a provider. */
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    return { toast: () => {}, success: () => {}, error: () => {} };
  }
  return ctx;
}
