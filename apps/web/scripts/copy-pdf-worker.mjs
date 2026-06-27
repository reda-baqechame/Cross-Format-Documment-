// Copy the pdf.js worker into public/ so it's served as a static asset (workerSrc=/pdf.worker.min.mjs).
// Bundling the prebuilt .mjs worker via `new URL(...)` breaks `next build` (Terser can't minify it),
// so we copy it instead. Runs as pre(build|dev); the copied file is git-ignored to avoid drift.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const pkg = dirname(require.resolve("pdfjs-dist/package.json"));
const src = resolve(pkg, "build/pdf.worker.min.mjs");
const dest = resolve(here, "../public/pdf.worker.min.mjs");

mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log(`[copy-pdf-worker] ${src} -> ${dest}`);
