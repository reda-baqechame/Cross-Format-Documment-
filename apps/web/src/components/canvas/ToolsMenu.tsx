"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { classifyDocument, compressPdf, protectPdf, saveAsTemplate, watermarkPdf } from "@/lib/api";
import { PromptModal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { useDismissOnOutside } from "@/lib/useDismiss";
import { friendlyApiError } from "@/lib/upload";

type PromptKind = "password" | "watermark" | "template";

const PROMPTS: Record<PromptKind, { title: string; label: string; placeholder: string; cta: string }> = {
  password: {
    title: "Password-protect PDF",
    label: "Set a password",
    placeholder: "Choose a strong password",
    cta: "Protect",
  },
  watermark: {
    title: "Add a watermark",
    label: "Watermark text",
    placeholder: "e.g. CONFIDENTIAL",
    cta: "Apply",
  },
  template: {
    title: "Save as template",
    label: "Template name",
    placeholder: "e.g. Standard MSA",
    cta: "Save",
  },
};

/**
 * Document tools — compress, protect, watermark, classify (PDF-focused where noted).
 */
export function ToolsMenu({ docId, sourceFormat }: { docId: string; sourceFormat?: string }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [prompt, setPrompt] = useState<PromptKind | null>(null);
  const ref = useDismissOnOutside(open, () => setOpen(false));
  const isPdf = sourceFormat === "pdf";
  const toast = useToast();
  const queryClient = useQueryClient();

  const run = async (fn: () => Promise<unknown>, success?: string, mutates = false) => {
    setOpen(false);
    setBusy(true);
    try {
      await fn();
      // Compress/watermark persist a new version server-side — refresh the canvas to match.
      if (mutates) void queryClient.invalidateQueries({ queryKey: ["model", docId] });
      if (success) toast.success(success);
    } catch (e) {
      toast.error(friendlyApiError(e, "That tool failed."));
    } finally {
      setBusy(false);
    }
  };

  const onPromptConfirm = (value: string) => {
    if (prompt === "password") void run(() => protectPdf(docId, value), "PDF password protection applied.");
    if (prompt === "watermark") void run(() => watermarkPdf(docId, value), "Watermark added.", true);
    if (prompt === "template")
      void run(
        () => saveAsTemplate(docId, value),
        `Saved “${value}” — find it under Templates on the home page.`,
      );
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        disabled={busy}
        className="min-h-[44px] rounded-xl border border-line px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-40"
      >
        {busy ? "Working…" : "Tools ▾"}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-10 mt-1 w-56 animate-slide-up overflow-hidden rounded-xl border border-line bg-white py-1 shadow-pop"
        >
          <MenuItem
            label="Classify document type"
            onClick={() =>
              void run(async () => {
                const c = await classifyDocument(docId);
                const detail = c.signals.length
                  ? ` (${Math.round(c.confidence * 100)}% — ${c.signals.join(", ")})`
                  : "";
                toast.success(`Detected type: ${c.label}${detail}`);
              })
            }
          />
          <MenuItem
            label="Compress PDF"
            disabled={!isPdf}
            hint={!isPdf ? "PDF only" : undefined}
            onClick={() => run(() => compressPdf(docId), "PDF compressed.", true)}
          />
          <MenuItem
            label="Password-protect PDF"
            disabled={!isPdf}
            hint={!isPdf ? "PDF only" : undefined}
            onClick={() => {
              setOpen(false);
              setPrompt("password");
            }}
          />
          <MenuItem
            label="Add watermark"
            disabled={!isPdf}
            hint={!isPdf ? "PDF only" : undefined}
            onClick={() => {
              setOpen(false);
              setPrompt("watermark");
            }}
          />
          <MenuItem
            label="Save as template"
            onClick={() => {
              setOpen(false);
              setPrompt("template");
            }}
          />
        </div>
      )}

      {prompt && (
        <PromptModal
          open
          title={PROMPTS[prompt].title}
          label={PROMPTS[prompt].label}
          placeholder={PROMPTS[prompt].placeholder}
          confirmLabel={PROMPTS[prompt].cta}
          onConfirm={onPromptConfirm}
          onClose={() => setPrompt(null)}
        />
      )}
    </div>
  );
}

function MenuItem({
  label,
  onClick,
  disabled,
  hint,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={onClick}
      className="block min-h-[44px] w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-40"
    >
      {label}
      {hint && <span className="ml-1 text-xs text-slate-400">({hint})</span>}
    </button>
  );
}
