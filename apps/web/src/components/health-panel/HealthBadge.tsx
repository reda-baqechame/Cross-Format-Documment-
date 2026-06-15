import type { HealthFinding } from "@docos/shared-types";

const STYLES: Record<HealthFinding["level"], string> = {
  ok: "bg-green-100 text-green-800",
  info: "bg-slate-100 text-slate-700",
  warn: "bg-amber-100 text-amber-800",
  fail: "bg-red-100 text-red-800",
};

export function HealthBadge({ finding }: { finding: HealthFinding }) {
  return (
    <li className={`rounded-md px-3 py-2 text-sm ${STYLES[finding.level]}`}>
      <span className="font-medium uppercase">{finding.level}</span> — {finding.message}
    </li>
  );
}
