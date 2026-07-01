"use client";

import type { WorkspaceTab } from "@/components/canvas/DocumentWorkspaceHeader";

/** Five-mode command center shell: Ask | Edit | Verify | Export | Automate. */
const MODES: { id: WorkspaceTab; label: string }[] = [
  { id: "ai-helper", label: "Ask" },
  { id: "modify", label: "Edit" },
  { id: "verify", label: "Verify" },
  { id: "trust", label: "Export" },
  { id: "autopilot", label: "Automate" },
];

export function DocumentCommandCenter({
  activeTab,
  onTabChange,
}: {
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
}) {
  return (
    <nav
      className="flex flex-wrap gap-1 border-b border-line bg-white px-4 py-2"
      aria-label="Document command center"
    >
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          onClick={() => onTabChange(m.id)}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            activeTab === m.id
              ? "bg-brand-600 text-white"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {m.label}
        </button>
      ))}
    </nav>
  );
}
