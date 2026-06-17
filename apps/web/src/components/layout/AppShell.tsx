import type { ReactNode } from "react";
import Link from "next/link";

export function AppShell({
  children,
  subtitle = "Open, edit, convert, and protect any document",
}: {
  children: ReactNode;
  subtitle?: string;
}) {
  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
          <Link href="/" className="flex min-w-0 items-center gap-3">
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-600 to-brand-800 text-lg font-bold text-white shadow-sm"
              aria-hidden
            >
              D
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold leading-tight text-ink sm:text-base">
                Cross-Format Document OS
              </p>
              <p className="truncate text-xs text-slate-500">{subtitle}</p>
            </div>
          </Link>
        </div>
      </header>
      {children}
    </div>
  );
}

export function Section({
  id,
  title,
  description,
  children,
  className = "",
}: {
  id?: string;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={`scroll-mt-20 ${className}`}>
      <div className="mb-4 sm:mb-5">
        <h2 className="text-lg font-semibold tracking-tight text-ink sm:text-xl">{title}</h2>
        {description && <p className="mt-1 max-w-2xl text-sm text-slate-600">{description}</p>}
      </div>
      {children}
    </section>
  );
}
