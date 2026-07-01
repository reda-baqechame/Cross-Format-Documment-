#!/usr/bin/env node
/**
 * Competitor benchmark harness — score DocumentOS vs manual Acrobat / Copilot / ChatGPT passes.
 * Records a JSON row you can paste into docs/benchmarks/documentos-benchmark.md.
 *
 * Usage: node scripts/competitor-benchmark.mjs --case evals/golden_documents/case_clean_memo
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, basename } from "node:path";

const args = process.argv.slice(2);
const caseIdx = args.indexOf("--case");
const casePath = caseIdx >= 0 ? resolve(args[caseIdx + 1]) : null;

const template = {
  case: casePath ? basename(casePath) : "example",
  date: new Date().toISOString().slice(0, 10),
  documentos: {
    verdict_correct: null,
    evidence_bound: null,
    export_opens: null,
    time_minutes: null,
  },
  acrobat: { verdict_correct: null, evidence_bound: null, export_opens: null, time_minutes: null },
  copilot: { verdict_correct: null, evidence_bound: null, export_opens: null, time_minutes: null },
  chatgpt: { verdict_correct: null, evidence_bound: null, export_opens: null, time_minutes: null },
  notes: "",
};

if (casePath && existsSync(resolve(casePath, "expected/verdict.json"))) {
  template.expected = JSON.parse(
    readFileSync(resolve(casePath, "expected/verdict.json"), "utf8"),
  );
}

const out = resolve("evals/benchmarks/latest-competitor-row.json");
writeFileSync(out, JSON.stringify(template, null, 2));
console.log(`Wrote ${out}`);
console.log("Fill scores (true/false) and re-run golden evals before committing.");
