"use client";

import { downloadReadinessReport, exportUrl, type ExportFormat } from "@/lib/api";

export function DocumentExportProofPanel({
  docId,
  validationSummary,
  outputFormat,
}: {
  docId: string;
  validationSummary?: string;
  outputFormat?: string;
}) {
  return (
    <div className="card space-y-4 p-5">
      <p className="text-sm text-slate-600">
        Download a proof report or clean export. Every export is validated before download.
      </p>
      {validationSummary && (
        <p className="rounded-lg border border-trust-200 bg-trust-50 px-3 py-2 text-xs text-trust-800">
          Proof: {validationSummary}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="btn-primary"
          onClick={() => downloadReadinessReport(docId)}
        >
          Download proof report (HTML)
        </button>
        {outputFormat && (
          <a
            href={exportUrl(docId, outputFormat as ExportFormat)}
            className="btn-secondary inline-flex items-center"
          >
            Download clean copy (.{outputFormat})
          </a>
        )}
      </div>
    </div>
  );
}

export function PacketExportProofPanel({
  packetId,
  documentCount,
  onDownloadZip,
  onDownloadReport,
}: {
  packetId: string;
  documentCount: number;
  onDownloadZip: () => void;
  onDownloadReport: () => void;
}) {
  return (
    <div className="card space-y-4 p-5">
      <p className="text-sm text-slate-600">
        Download a validated export of all {documentCount} document(s). Each file is checked
        before download.
      </p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-primary" onClick={onDownloadZip}>
          Download clean packet (ZIP)
        </button>
        <button type="button" className="btn-secondary" onClick={onDownloadReport}>
          Download expert report (HTML)
        </button>
      </div>
    </div>
  );
}
