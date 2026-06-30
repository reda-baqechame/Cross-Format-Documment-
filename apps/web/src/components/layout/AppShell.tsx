import type { ReactNode } from "react";
import Link from "next/link";

import { AccountMenu } from "@/components/auth/AccountMenu";
import { Logo } from "@/components/ui/Logo";

export function AppShell({
  children,
  subtitle = "Open, edit, convert & protect common document formats",
}: {
  children: ReactNode;
  subtitle?: string;
}) {
  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-40 border-b border-line/80 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link href="/" className="flex min-w-0 items-center gap-3 rounded-lg">
            <Logo subtitle={subtitle} />
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/packets" className="hidden text-sm font-medium text-slate-500 hover:text-slate-800 sm:block">
              Command Center
            </Link>
            <Link href="/pricing" className="hidden text-sm font-medium text-slate-500 hover:text-slate-800 sm:block">
              Pricing
            </Link>
            <AccountMenu />
          </div>
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
