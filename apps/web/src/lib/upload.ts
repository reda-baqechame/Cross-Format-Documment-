/**
 * Client-side upload rules and friendly error mapping.
 *
 * The backend already validates (magic-byte sniff + allow-list + size limit), but
 * checking here first means the user gets an instant, human-readable explanation
 * instead of a raw `415: mime not allowed: …` string after a round-trip.
 */

/** Keep in sync with the backend allow-list (settings.allowed_mime_types). */
export const SUPPORTED_FORMATS: { ext: string; label: string }[] = [
  { ext: ".pdf", label: "PDF" },
  { ext: ".docx", label: "Word" },
  { ext: ".xlsx", label: "Excel" },
  { ext: ".pptx", label: "PowerPoint" },
  { ext: ".rtf", label: "Rich Text" },
  { ext: ".txt", label: "Text" },
  { ext: ".md", label: "Markdown" },
  { ext: ".csv", label: "CSV" },
  { ext: ".png", label: "PNG" },
  { ext: ".jpg", label: "JPEG" },
  { ext: ".jpeg", label: "JPEG" },
  { ext: ".tif", label: "TIFF" },
  { ext: ".tiff", label: "TIFF" },
];

/** Value for an <input type="file"> accept attribute. */
export const ACCEPT_ATTR = SUPPORTED_FORMATS.map((f) => f.ext).join(",");

/** Mirrors backend `max_upload_mb` (default 50). */
export const MAX_UPLOAD_MB = 50;

const SUPPORTED_EXTS = new Set(SUPPORTED_FORMATS.map((f) => f.ext));

function extensionOf(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot).toLowerCase();
}

/** A short, comma-separated list of what users can drop (de-duplicated labels). */
export function supportedSummary(): string {
  const seen = new Set<string>();
  const labels: string[] = [];
  for (const { label } of SUPPORTED_FORMATS) {
    if (!seen.has(label)) {
      seen.add(label);
      labels.push(label);
    }
  }
  return labels.join(", ");
}

/**
 * Validate a file before upload. Returns a friendly error message, or `null`
 * when the file looks acceptable.
 */
export function validateFile(file: File): string | null {
  if (file.size === 0) {
    return "That file is empty — pick a document with content.";
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    const mb = (file.size / (1024 * 1024)).toFixed(1);
    return `That file is ${mb} MB, over the ${MAX_UPLOAD_MB} MB limit. Try a smaller file.`;
  }
  const ext = extensionOf(file.name);
  if (ext && !SUPPORTED_EXTS.has(ext)) {
    return `“${ext}” files aren't supported yet. Try one of: ${supportedSummary()}.`;
  }
  return null;
}

/** Turn a thrown upload error (often `"<status>: <detail>"`) into plain language. */
export function friendlyUploadError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err);
  const status = Number(raw.match(/^(\d{3}):/)?.[1]);

  if (status === 415) {
    return `That file type isn't supported yet. Try one of: ${supportedSummary()}.`;
  }
  if (status === 413) {
    return `That file is too large (max ${MAX_UPLOAD_MB} MB).`;
  }
  if (status === 422) {
    return "The file couldn't be processed — it may be corrupted or failed a safety scan.";
  }
  if (status === 501) {
    return "That format is recognized but not fully supported yet. Try PDF, Word, or text.";
  }
  if (status === 502 || /unreachable|failed to fetch|networkerror/i.test(raw)) {
    return "Can't reach the server right now. Check your connection and try again.";
  }
  // Strip a leading "NNN: " status code so the user never sees a bare HTTP code.
  return raw.replace(/^\d{3}:\s*/, "") || "Upload failed. Please try again.";
}
