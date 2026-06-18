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
  fetchSummary,
  mergePdfs,
  parsePageList,
  protectPdf,
  redactSensitive,
  reorderPages,
  rotatePdf,
  sanitizeMetadata,
  signDocument,
  splitPdf,
  translateDocument,
  watermarkPdf,
  type ExportFormat,
} from "./api";

export type TaskCategory = "Organize PDF" | "Convert" | "Edit" | "Secure" | "Ask AI" | "Review";

export const CATEGORY_ORDER: TaskCategory[] = [
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
  | { kind: "downloaded" }
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
  "application/pdf,.docx,.doc,.xlsx,.pptx,.rtf,.txt,image/png,image/jpeg,image/tiff,text/plain";

const downloaded = async (): Promise<TaskResult> => ({ kind: "downloaded" });

export const TASKS: TaskDef[] = [
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
      if (target === "pdf") await downloadSearchablePdf(docIds[0]);
      else await downloadExport(docIds[0], target as ExportFormat);
      return { kind: "downloaded" };
    },
  },

  // ── Edit ──────────────────────────────────────────────────────────────────────
  {
    slug: "edit-pdf",
    title: "Edit PDF text",
    blurb: "Open a PDF and edit its text directly on the page, then download.",
    category: "Edit",
    emoji: "✏️",
    accept: PDF,
    acceptLabel: "a PDF",
    cta: "Open editor",
    run: async ({ docIds }) => ({ kind: "navigate", href: `/documents/${docIds[0]}` }),
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
