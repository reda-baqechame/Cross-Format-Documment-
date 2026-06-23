import Link from "next/link";

import { AppShell } from "@/components/layout/AppShell";

export default function NotFound() {
  return (
    <AppShell>
      <div className="flex min-h-[60vh] items-center justify-center px-4">
        <div className="card max-w-md p-8 text-center">
          <p className="text-5xl font-semibold text-brand-600">404</p>
          <h1 className="mt-3 text-lg font-semibold text-ink">Page not found</h1>
          <p className="mt-2 text-sm text-slate-600">
            That page doesn&apos;t exist or the document is no longer available.
          </p>
          <Link href="/" className="btn-primary mt-6 inline-block">
            Back to home
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
