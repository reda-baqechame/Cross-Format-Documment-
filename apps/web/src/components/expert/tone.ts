"use client";

export const VERDICT_TONE: Record<
  string,
  { label: string; badge: string; box: string; dot: string; text: string }
> = {
  ready: {
    label: "Ready",
    badge: "bg-trust-100 text-trust-800",
    box: "border-trust-200 bg-trust-50",
    dot: "bg-trust-500",
    text: "text-trust-800",
  },
  needs_review: {
    label: "Needs review",
    badge: "bg-amber-100 text-amber-800",
    box: "border-amber-200 bg-amber-50",
    dot: "bg-amber-500",
    text: "text-amber-800",
  },
  needs_fixes: {
    label: "Needs fixes",
    badge: "bg-amber-100 text-amber-800",
    box: "border-amber-200 bg-amber-50",
    dot: "bg-amber-500",
    text: "text-amber-800",
  },
  blocked: {
    label: "Blocked",
    badge: "bg-red-100 text-red-800",
    box: "border-red-200 bg-red-50",
    dot: "bg-red-500",
    text: "text-red-800",
  },
};

export const SEVERITY_TONE: Record<string, { badge: string; dot: string; text: string }> = {
  blocking: { badge: "bg-red-100 text-red-800", dot: "bg-red-500", text: "text-red-800" },
  warning: { badge: "bg-amber-100 text-amber-800", dot: "bg-amber-500", text: "text-amber-800" },
  info: { badge: "bg-slate-100 text-slate-700", dot: "bg-slate-400", text: "text-slate-700" },
};

export function toneFor(verdict: string) {
  return VERDICT_TONE[verdict] ?? VERDICT_TONE.needs_review;
}

export function severityFor(severity: string) {
  return SEVERITY_TONE[severity] ?? SEVERITY_TONE.info;
}

/** Map readiness verdict strings to expert-style verdict for shared UI. */
export function normalizeVerdict(verdict: string): string {
  if (verdict === "needs_fixes") return "needs_review";
  return verdict;
}
