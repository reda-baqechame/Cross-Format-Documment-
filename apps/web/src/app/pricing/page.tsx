import { Suspense } from "react";
import PricingPageClient from "./PricingPageClient";

export default function PricingPage() {
  return (
    <Suspense fallback={<p className="p-8 text-center text-slate-500">Loading pricing…</p>}>
      <PricingPageClient />
    </Suspense>
  );
}
