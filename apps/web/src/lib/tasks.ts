/**
 * Task registry — the task-first toolkit.
 *
 * Each entry is one concrete job a user picks from the home grid (like iLovePDF). A task
 * declares its inputs/options and a `run` that calls the existing backend API. The home
 * grid (TaskGrid) and the focused flow screen (TaskRunner) are both driven by this list, so
 * adding a capability is a single declarative entry — no new screen.
 */

import {
  askDocument,
  classifyDocument,
  compressPdf,
  deletePages,
  diffDocuments,
  downloadExport,
  downloadSearchablePdf,
  fetchExtract,
  fetchIntelligence,
  fetchSummary,
  mergePdfs,
  parsePageList,
  protectPdf,
  redactSensitive,
  remediateAccessibility,
  reorderPages,
  rotatePdf,
  sanitizeMetadata,
  signDocument,
  splitPdf,
  translateDocument,
  watermarkPdf,
  type ExportFormat,
} from "./api";

export type TaskCategory =
  | "Create"
  | "Workflow"
  | "Organize PDF"
  | "Convert"
  | "Edit"
  | "Secure"
  | "Ask AI"
  | "Review";

export const CATEGORY_ORDER: TaskCategory[] = [
  "Create",
  "Workflow",
  "Organize PDF",
  "Convert",
  "Edit",
  "Secure",
  "Ask AI",
  "Review",
];

export interface OptionField {
  name: string;
  label: string;
  type: "text" | "password" | "pages" | "select";
  placeholder?: string;
  default?: string;
  choices?: { value: string; label: string }[];
  help?: string;
}

export type TaskResult =
  | { kind: "downloaded"; validation?: { status: "pass" | "warn" | "fail"; summary: string } }
  | { kind: "navigate"; href: string }
  | { kind: "text"; title: string; body: string; citations?: string[] }
  | { kind: "list"; title: string; items: string[] };

export interface TaskContext {
  docIds: string[];
  options: Record<string, string>;
}

export interface TaskDef {
  slug: string;
  title: string;
  blurb: string;
  category: TaskCategory;
  emoji: string;
  accept: string; // input "accept" attribute
  acceptLabel: string; // human-readable accepted input
  multiple?: boolean;
  minFiles?: number;
  options?: OptionField[];
  needsAI?: boolean;
  cta?: string;
  run: (ctx: TaskContext) => Promise<TaskResult>;
}

const PDF = "application/pdf";
const ANY =
  "application/pdf,.docx,.xlsx,.pptx,.rtf,.txt,.md,.csv,.html,image/png,image/jpeg,image/tiff,text/plain,text/markdown,text/csv,text/html";

const downloaded = async (): Promise<TaskResult> => ({ kind: "downloaded" });

export const TASKS: TaskDef[] = [
  {
    slug: "build-form",
    title: "Build a form",
    blurb: "Detect blanks, add fields, set required inputs, and turn any document into a reusable form.",
    category: "Create",
    emoji: "📋",
    accept: ANY,
    acceptLabel: "any document",
    cta: "Open builder",
    run: async ({ docIds }) => ({ kind: "navigate", href: `/documents/${docIds[0]}?tab=forms` }),
  },
  {
    slug: "make-template",
    title: "Make a template",
    blurb: "Open a document, add placeholders, then save it to the template gallery.",
    category: "Create",
    emoji: "🧩",
    accept: ANY,
    acceptLabel: "any document",
    cta: "Open template",
    run: async ({ docIds }) => ({ kind: "navigate", href: `/documents/${docIds[0]}?tab=modify` }),
  },
  {
    slug: "create-from-template",
    title: "Create from template",
    blurb: "Browse saved templates and stamp out a fresh editable copy.",
    category: "Create",
    emoji: "✨",
    accept: ANY,
    acceptLabel: "optional starter document",
    minFiles: 0,
    cta: "Open templates",
    run: async () => ({ kind: "navigate", href: "/#templates" }),
  },

  {
    slug: "create-contract-packet",
    title: "Create contract packet",
    blurb: "Review clauses, prepare fields, route approval, and export a validated packet.",
    category: "Workflow",
    emoji: "📑",
    accept: ANY,
    acceptLabel: "contract, SOW, proposal, or agreement",
    cta: "Open workflow",
    run: async ({ docIds }) => ({
      kind: "navigate",
      href: `/documents/${docIds[0]}?tab=autopilot&workflow=contract_packet`,
    }),
  },
  {
    slug: "vendor-onboarding",
    title: "Vendor onboarding",
    blurb: "Turn vendor forms, policies, W-9s, and approvals into a reusable onboarding packet.",
    category: "Workflow",
    emoji: "🏢",
    accept: ANY,
    acceptLabel: "vendor packet document",
    cta: "Build packet",
    run: async ({ docIds }) => ({
      kind: "navigate",
      href: `/documents/${docIds[0]}?tab=autopilot&workflow=vendor_onboarding`,
    }),
  },
  {
    slug: "invoice-approval",
    title: "Invoice approval",
    blurb: "Check invoice fields, totals, red flags, and prepare an approval route.",
    category: "Workflow",
    emoji: "🧾",
    accept: ANY,
    acceptLabel: "invoice, quote, or receipt",
    cta: "Review invoice",
    run: async ({ docIds }) => ({
      kind: "navigate",
      href: `/documents/${docIds[0]}?tab=autopilot&workflow=invoice_approval`,
    }),
  },
  {
    slug: "employee-form-packet",
    title: "Employee form packet",
    blurb: "Create intake, consent, checklist, and approval forms from one packet.",
    category: "Workflow",
    emoji: "👤",
    accept: ANY,
    acceptLabel: "HR or intake packet",
    cta: "Prepare forms",
    run: async ({ docIds }) => ({
      kind: "navigate",
      href: `/documents/${docIds[0]}?tab=autopilot&workflow=employee_form_packet`,
    }),
  },
  {
    slug: "proposal-to-signature",
    title: "Proposal to signature",
    blurb: "Analyze a proposal/SOW, add fields, and prepare approval before sending.",
    category: "Workflow",
    emoji: "🚀",
    accept: ANY,
    acceptLabel: "proposal, SOW, or pitch document",
    cta: "Prepare send",
    run: async ({ docIds }) => ({
      kind: "navigate",
      href: `/documents/${docIds[0]}?tab=autopilot&workflow=proposal_to_signature`,
    }),
  },
  {
    slug: "bulk-send-from-template",
    title: "Bulk send from template",
    blurb: "Start with a reusable template, then prepare independent recipient packets.",
    category: "Workflow",
    emoji: "📨",
    accept: ANY,
    acceptLabel: "optional starter document",
    minFiles: 0,
    cta: "Open templates",
    run: async () => ({ kind: "navigate", href: "/#templates" }),
  },

  // ── Organize PDF ────────────────────────────────────────────────────────────
  {
    slug: "merge-pdf",
    title: "Merge PDF",
    blurb: "Combine several PDFs into one file, in the order you choose.",
    category: "Organize PDF",
    emoji: "🗂️",
    accept: PDF,
    acceptLabel: "PDF files",
    multiple: true,
    minFiles: 2,
    cta: "Merge",
    run: async ({ docIds }) => {
      await mergePdfs(docIds[0], docIds.slice(1));
      return { kind: "downloaded" };
    },
  },
  {
    slug: "split-pdf",
    title: "Split PDF",
    blurb: "Pull out specific pages into a new PDF.",
    category: "Organize PDF",
    emoji: "✂️",
    accept: PDF,
    acceptLabel: "a PDF",
    options: [
      { name: "pages", label: "Pages to extract", type: "pages", placeholder: "e.g. 1,3,5-7" },
    ],
    cta: "Split",
    run: async ({ docIds, options }) => {
      await splitPdf(docIds[0], parsePageList(options.pages ?? "").map((n) => n + 1));
      return { kind: "downloaded" };
    },
  },
  {
    slug: "rotate-pdf",
    title: "Rotate PDF",
    blurb: "Rotate selected pages by 90°, 180°, or 270°.",
    category: "Organize PDF",
    emoji: "🔄",
    accept: PDF,
    acceptLabel: "a PDF",
    options: [
      { name: "pages", label: "Pages", type: "pages", placeholder: "e.g. 1,2 (blank = all)" },
      {
        name: "degrees",
        label: "Rotation",
        type: "select",
        default: "90",
        choices: [
          { value: "90", label: "90° clockwise" },
          { value: "180", label: "180°" },
          { value: "270", label: "270° (90° counter-clockwise)" },
        ],
      },
    ],
    cta: "Rotate",
    run: async ({ docIds, options }) => {
      await rotatePdf(docIds[0], parsePageList(options.pages ?? ""), Number(options.degrees ?? 90));
      return { kind: "downloaded" };
    },
  },
  {
    slug: "delete-pages",
    title: "Delete pages",
    blurb: "Remove pages you don't need and download the rest.",
    category: "Organize PDF",
    emoji: "🗑️",
    accept: PDF,
    acceptLabel: "a PDF",
    options: [
      { name: "pages", label: "Pages to delete", type: "pages", placeholder: "e.g. 2,4-5" },
    ],
    cta: "Delete pages",
    run: async ({ docIds, options }) => {
      await deletePages(docIds[0], parsePageList(options.pages ?? ""));
      return { kind: "downloaded" };
    },
  },
  {
    slug: "reorder-pdf",
    title: "Reorder pages",
    blurb: "Rearrange the pages of a PDF into a new order.",
    category: "Organize PDF",
    emoji: "↕️",
    accept: PDF,
    acceptLabel: "a PDF",
    options: [
      {
        name: "order",
        label: "New page order",
        type: "pages",
        placeholder: "e.g. 3,1,2",
        help: "List every page once, in the order you want.",
      },
    ],
    cta: "Reorder",
    run: async ({ docIds, options }) => {
      await reorderPages(docIds[0], parsePageList(options.order ?? ""));
      return { kind: "downloaded" };
    },
  },
  {
    slug: "compress-pdf",
    title: "Compress PDF",
    blurb: "Shrink a PDF's file size for easier sharing.",
    category: "Organize PDF",
    emoji: "🗜️",
    accept: PDF,
    acceptLabel: "a PDF",
    cta: "Compress",
    run: async ({ docIds }) => {
      await compressPdf(docIds[0]);
      return { kind: "downloaded" };
    },
  },

  // ── Convert ──────────────────────────────────────────────────────────────────
  {
    slug: "convert",
    title: "Convert document",
    blurb: "Turn any document into PDF, Word, Excel, PowerPoint, image, or text.",
    category: "Convert",
    emoji: "🔁",
    accept: ANY,
    acceptLabel: "any document",
    options: [
      {
        name: "target",
        label: "Convert to",
        type: "select",
        default: "pdf",
        choices: [
          { value: "pdf", label: "PDF (searchable)" },
          { value: "docx", label: "Word (.docx)" },
          { value: "xlsx", label: "Excel (.xlsx)" },
          { value: "pptx", label: "PowerPoint (.pptx)" },
          { value: "png", label: "Image (.png)" },
          { value: "txt", label: "Plain text (.txt)" },
          { value: "md", label: "Markdown (.md)" },
          { value: "html", label: "HTML (.html)" },
          { value: "csv", label: "CSV (.csv)" },
        ],
      },
    ],
    cta: "Convert",
    run: async ({ docIds, options }) => {
      const target = options.target ?? "pdf";
      const validation =
        target === "pdf"
          ? await downloadSearchablePdf(docIds[0])
          : await downloadExport(docIds[0], target as ExportFormat);
      return { kind: "downloaded", validation: validation ?? undefined };
    },
  },

  // ── Edit ──────────────────────────────────────────────────────────────────────
  {
    slug: "edit-pdf",
    title: "Basic PDF text edit",
    blurb: "Open a PDF in the audited basic editor. Full Acrobat-level editing needs a PDF SDK provider.",
    category: "Edit",
    emoji: "✏️",
    accept: PDF,
    acceptLabel: "a PDF",
    cta: "Open editor",
    run: async ({ docIds }) => ({ kind: "navigate", href: `/documents/${docIds[0]}` }),
  },
  {
    slug: "fill-form",
    title: "Fill a form",
    blurb: "Open a form, see what's still blank, and fill each field.",
    category: "Edit",
    emoji: "🖊️",
    accept: ANY,
    acceptLabel: "a form document",
    cta: "Open form",
    run: async ({ docIds }) => ({
      kind: "navigate",
      href: `/documents/${docIds[0]}?tab=forms`,
    }),
  },
  {
    slug: "edit-deck",
    title: "Edit a deck or visual",
    blurb: "Open slides, flyers, diagrams, or visual documents with slide/page controls.",
    category: "Edit",
    emoji: "🎞️",
    accept: ANY,
    acceptLabel: "PowerPoint, PDF, image, or document",
    cta: "Open visual editor",
    run: async ({ docIds }) => ({ kind: "navigate", href: `/documents/${docIds[0]}?tab=modify` }),
  },
  {
    slug: "edit-table",
    title: "Edit a table",
    blurb: "Change cell text, add rows or columns, and export back to Excel.",
    category: "Edit",
    emoji: "▦",
    accept: ANY,
    acceptLabel: "Excel, CSV, Word, PDF, or document",
    cta: "Open table editor",
    run: async ({ docIds }) => ({ kind: "navigate", href: `/documents/${docIds[0]}?tab=modify` }),
  },
  {
    slug: "insert-image-link",
    title: "Insert image or link",
    blurb: "Add images, replace visuals, write alt text, or link selected text.",
    category: "Edit",
    emoji: "🔗",
    accept: ANY,
    acceptLabel: "any editable document",
    cta: "Open modify tools",
    run: async ({ docIds }) => ({ kind: "navigate", href: `/documents/${docIds[0]}?tab=modify` }),
  },

  // ── Secure ──────────────────────────────────────────────────────────────────
  {
    slug: "redact",
    title: "Redact sensitive data",
    blurb: "Find and black out PII/secrets, then download a cleaned copy.",
    category: "Secure",
    emoji: "🚫",
    accept: ANY,
    acceptLabel: "any document",
    cta: "Redact & download",
    run: async ({ docIds }) => {
      const res = await redactSensitive(docIds[0]);
      await downloadSearchablePdf(docIds[0]);
      return {
        kind: "text",
        title: "Cleaned copy downloaded",
        body: res.intent ?? "Sensitive content was redacted (truly removed) from the download.",
      };
    },
  },
  {
    slug: "remove-metadata",
    title: "Remove metadata",
    blurb: "Strip hidden author, software, and tracking metadata from a PDF.",
    category: "Secure",
    emoji: "🧹",
    accept: PDF,
    acceptLabel: "a PDF",
    cta: "Clean & download",
    run: async ({ docIds }) => {
      await sanitizeMetadata(docIds[0]);
      await downloadExport(docIds[0], "pdf");
      return { kind: "downloaded" };
    },
  },
  {
    slug: "protect-pdf",
    title: "Protect PDF",
    blurb: "Add a password and AES-256 encryption to a PDF.",
    category: "Secure",
    emoji: "🔒",
    accept: PDF,
    acceptLabel: "a PDF",
    options: [
      { name: "password", label: "Password", type: "password", placeholder: "Choose a password" },
    ],
    cta: "Protect",
    run: async ({ docIds, options }) => {
      await protectPdf(docIds[0], options.password ?? "");
      return { kind: "downloaded" };
    },
  },
  {
    slug: "watermark-pdf",
    title: "Watermark PDF",
    blurb: "Stamp text across every page of a PDF.",
    category: "Secure",
    emoji: "💧",
    accept: PDF,
    acceptLabel: "a PDF",
    options: [
      { name: "text", label: "Watermark text", type: "text", placeholder: "e.g. CONFIDENTIAL" },
    ],
    cta: "Add watermark",
    run: async ({ docIds, options }) => {
      await watermarkPdf(docIds[0], options.text ?? "");
      return { kind: "downloaded" };
    },
  },
  {
    slug: "sign",
    title: "Add integrity seal",
    blurb: "Seal the document so any later change is detectable, recording who sealed it and when.",
    category: "Secure",
    emoji: "🖋️",
    accept: ANY,
    acceptLabel: "any document",
    options: [{ name: "signer", label: "Your name", type: "text", placeholder: "e.g. Jane Doe" }],
    cta: "Seal",
    run: async ({ docIds, options }) => {
      const res = await signDocument(docIds[0], options.signer ?? "");
      return {
        kind: "text",
        title: "Sealed",
        body: `Sealed by ${res.signer ?? options.signer}. The integrity seal detects any later change — it is not a legally-binding e-signature.`,
      };
    },
  },
  {
    slug: "make-accessible",
    title: "Make accessible",
    blurb: "Auto-tag headings, reading order, and missing image alt text before sharing.",
    category: "Secure",
    emoji: "♿",
    accept: ANY,
    acceptLabel: "any document",
    cta: "Fix accessibility",
    run: async ({ docIds }) => {
      const res = await remediateAccessibility(docIds[0]);
      return {
        kind: "text",
        title: "Accessibility fixes applied",
        body: res.intent ?? "The document was remediated with reversible accessibility fixes.",
      };
    },
  },
  {
    slug: "clean-sign-send",
    title: "Clean, seal, send",
    blurb: "Redact sensitive data, remove metadata, add an integrity seal, then route for approval.",
    category: "Secure",
    emoji: "🛡️",
    accept: ANY,
    acceptLabel: "any document",
    options: [{ name: "signer", label: "Signer", type: "text", placeholder: "Your name" }],
    cta: "Clean & seal",
    run: async ({ docIds, options }) => {
      await redactSensitive(docIds[0]);
      await sanitizeMetadata(docIds[0]);
      await signDocument(docIds[0], options.signer || "Signer");
      return { kind: "navigate", href: `/documents/${docIds[0]}?tab=approvals` };
    },
  },

  // ── Ask AI ────────────────────────────────────────────────────────────────────
  {
    slug: "ask",
    title: "Ask a question",
    blurb: "Ask anything about your document and get a cited answer.",
    category: "Ask AI",
    emoji: "💬",
    accept: ANY,
    acceptLabel: "any document",
    needsAI: true,
    options: [
      { name: "question", label: "Your question", type: "text", placeholder: "What is this about?" },
    ],
    cta: "Ask",
    run: async ({ docIds, options }) => {
      const res = await askDocument(docIds[0], options.question ?? "");
      return {
        kind: "text",
        title: "Answer",
        body: res.answer,
        citations: res.citations.map((c) => c.excerpt),
      };
    },
  },
  {
    slug: "summarize",
    title: "Summarize",
    blurb: "Get a concise summary of a long document, with citations.",
    category: "Ask AI",
    emoji: "📝",
    accept: ANY,
    acceptLabel: "any document",
    needsAI: true,
    cta: "Summarize",
    run: async ({ docIds }) => {
      const res = await fetchSummary(docIds[0]);
      return {
        kind: "text",
        title: "Summary",
        body: res.summary,
        citations: res.citations.map((c) => c.excerpt),
      };
    },
  },
  {
    slug: "translate",
    title: "Translate",
    blurb: "Translate a document's text into another language.",
    category: "Ask AI",
    emoji: "🌐",
    accept: ANY,
    acceptLabel: "any document",
    needsAI: true,
    options: [
      { name: "language", label: "Target language", type: "text", default: "French" },
    ],
    cta: "Translate",
    run: async ({ docIds, options }) => {
      const res = await translateDocument(docIds[0], options.language ?? "French");
      return { kind: "text", title: `In ${res.target_language}`, body: res.translated_text };
    },
  },
  {
    slug: "extract",
    title: "Extract data",
    blurb: "Pull out dates, emails, amounts, and form fields automatically.",
    category: "Ask AI",
    emoji: "🔎",
    accept: ANY,
    acceptLabel: "any document",
    cta: "Extract",
    run: async ({ docIds }) => {
      const res = await fetchExtract(docIds[0]);
      const items = [
        ...res.extraction.entities.map((e) => `${e.type}: ${e.value}`),
        ...res.extraction.fields.map((f) => `${f.key}: ${f.value}`),
      ];
      return { kind: "list", title: "Extracted data", items: items.length ? items : ["Nothing found."] };
    },
  },
  {
    slug: "classify",
    title: "Classify document",
    blurb: "Detect the document type (invoice, contract, resume, …).",
    category: "Ask AI",
    emoji: "🏷️",
    accept: ANY,
    acceptLabel: "any document",
    cta: "Classify",
    run: async ({ docIds }) => {
      const c = await classifyDocument(docIds[0]);
      return {
        kind: "text",
        title: "Document type",
        body: `${c.label} (${Math.round(c.confidence * 100)}% confidence)`,
      };
    },
  },
  {
    slug: "analyze",
    title: "Analyze & validate",
    blurb: "Check an invoice, contract, form, résumé, or pitch deck for problems.",
    category: "Ask AI",
    emoji: "🧠",
    accept: ANY,
    acceptLabel: "any document",
    cta: "Analyze",
    run: async ({ docIds }) => {
      const { insight } = await fetchIntelligence(docIds[0]);
      const items = [
        insight.summary,
        ...insight.checks.map(
          (c) =>
            `${c.passed ? "✓" : c.severity === "error" ? "✗" : "!"} ${c.label}` +
            (c.passed || !c.detail ? "" : ` — ${c.detail}`),
        ),
      ];
      return { kind: "list", title: `Analysis — ${insight.doc_type}`, items };
    },
  },

  // ── Review ────────────────────────────────────────────────────────────────────
  {
    slug: "compare",
    title: "Compare documents",
    blurb: "See what changed between two documents (a redline).",
    category: "Review",
    emoji: "🔬",
    accept: ANY,
    acceptLabel: "two documents",
    multiple: true,
    minFiles: 2,
    cta: "Compare",
    run: async ({ docIds }) => {
      const res = await diffDocuments(docIds[0], docIds[1]);
      const r = res.result;
      return {
        kind: "text",
        title: "Comparison",
        body: `${r.added} added · ${r.removed} removed · ${r.changed} changed · ${r.unchanged} unchanged blocks.`,
      };
    },
  },
  {
    slug: "prepare-approval",
    title: "Prepare approval",
    blurb: "Open approval routing, choose ordered or parallel approvers, and track decisions.",
    category: "Review",
    emoji: "✅",
    accept: ANY,
    acceptLabel: "any document",
    cta: "Open approvals",
    run: async ({ docIds }) => ({ kind: "navigate", href: `/documents/${docIds[0]}?tab=approvals` }),
  },
  {
    slug: "bulk-send",
    title: "Bulk send",
    blurb: "Prepare one document packet for many recipients with independent approval copies.",
    category: "Review",
    emoji: "✉️",
    accept: ANY,
    acceptLabel: "any document",
    cta: "Open approvals",
    run: async ({ docIds }) => ({ kind: "navigate", href: `/documents/${docIds[0]}?tab=approvals` }),
  },
];

export function getTask(slug: string): TaskDef | undefined {
  return TASKS.find((t) => t.slug === slug);
}

export function tasksByCategory(): { category: TaskCategory; tasks: TaskDef[] }[] {
  return CATEGORY_ORDER.map((category) => ({
    category,
    tasks: TASKS.filter((t) => t.category === category),
  })).filter((g) => g.tasks.length > 0);
}
