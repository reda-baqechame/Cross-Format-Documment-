"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/layout/AppShell";
import { fetchBillingStatus, fetchMe, startCheckout } from "@/lib/api";

export default function PricingPageClient() {
  const params = useSearchParams();
  const success = params.get("success") === "1";
  const me = useQuery({ queryKey: ["auth", "me"], queryFn: fetchMe });
  const billing = useQuery({ queryKey: ["billing"], queryFn: fetchBillingStatus });
  const checkout = useMutation({
    mutationFn: (plan: "pro" | "team") => startCheckout(plan),
    onSuccess: (res) => {
      window.location.href = res.checkout_url;
    },
  });

  return (
    <AppShell subtitle="Plans for agencies and SMB operators">
      <main className="mx-auto max-w-6xl px-4 py-10">
        {success && (
          <p className="mb-6 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
            Payment received — your plan will update shortly.
          </p>
        )}
        <h1 className="text-3xl font-semibold text-slate-950">Pricing</h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          Client packet readiness checks stay free forever. Upgrade when you need shareable portal
          links and a saved account library.
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Current plan: <strong>{billing.data?.plan ?? "free"}</strong>
          {!billing.data?.configured && " · Billing not configured on this deployment yet"}
        </p>
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {(billing.data?.plans ?? []).map((plan) => (
            <div key={plan.id} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold">{plan.name}</h2>
              <p className="mt-2 text-3xl font-bold text-slate-900">
                {plan.price_monthly === 0 ? "Free" : `$${plan.price_monthly}`}
                {plan.price_monthly > 0 && (
                  <span className="text-sm font-normal text-slate-500">/mo</span>
                )}
              </p>
              <ul className="mt-4 space-y-2 text-sm text-slate-600">
                {plan.features.map((f) => (
                  <li key={f}>• {f}</li>
                ))}
              </ul>
              {plan.id === "free" ? (
                <Link
                  href="/"
                  className="mt-6 block rounded-lg border border-slate-300 py-2.5 text-center text-sm font-medium hover:bg-slate-50"
                >
                  Start free
                </Link>
              ) : me.data ? (
                <button
                  type="button"
                  disabled={checkout.isPending || !billing.data?.configured}
                  onClick={() => checkout.mutate(plan.id as "pro" | "team")}
                  className="mt-6 w-full rounded-lg bg-brand-600 py-2.5 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-50"
                >
                  {checkout.isPending ? "Redirecting…" : `Upgrade to ${plan.name}`}
                </button>
              ) : (
                <Link
                  href="/signup"
                  className="mt-6 block rounded-lg bg-brand-600 py-2.5 text-center text-sm font-medium text-white hover:bg-brand-500"
                >
                  Sign up to upgrade
                </Link>
              )}
            </div>
          ))}
        </div>
        {checkout.isError && (
          <p role="alert" className="mt-4 text-sm text-red-600">
            {checkout.error instanceof Error ? checkout.error.message : String(checkout.error)}
          </p>
        )}
      </main>
    </AppShell>
  );
}
