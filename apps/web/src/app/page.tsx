import Link from "next/link";
import {
  BadgeCheck,
  Building2,
  FileCheck2,
  FileSignature,
  Files,
  Landmark,
  Layers3,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
} from "lucide-react";

import { DocumentList } from "@/components/documents/DocumentList";
import { SearchBar } from "@/components/documents/SearchBar";
import { AppShell, Section } from "@/components/layout/AppShell";
import { BackendStatus } from "@/components/system/BackendStatus";
import { PrivacyPanel } from "@/components/system/PrivacyPanel";
import { SystemStatusPanel } from "@/components/system/SystemStatusPanel";
import { TaskGrid } from "@/components/tasks/TaskGrid";
import { TemplateGallery } from "@/components/templates/TemplateGallery";
import { UploadDropzone } from "@/components/upload/UploadDropzone";
import { WORKFLOWS, type WorkflowDefinition } from "@/lib/workflows";

const TASK_SLUGS: Record<WorkflowDefinition["preset"], string> = {
  contract_packet: "create-contract-packet",
  invoice_approval: "invoice-approval",
  vendor_onboarding: "vendor-onboarding",
  employee_form_packet: "employee-form-packet",
  proposal_to_signature: "proposal-to-signature",
  bulk_send_template: "bulk-send-from-template",
};

const WORKFLOW_ICONS = {
  contract_packet: FileSignature,
  invoice_approval: Landmark,
  vendor_onboarding: Building2,
  employee_form_packet: UserRoundCheck,
  proposal_to_signature: FileCheck2,
  bulk_send_template: Files,
};

const TRUST_ITEMS = [
  { label: "Export validation", detail: "Proof before download", icon: BadgeCheck },
  { label: "True redaction", detail: "Removed, not hidden", icon: ShieldCheck },
  { label: "Approval routes", detail: "Audited handoffs", icon: Layers3 },
  { label: "Reusable templates", detail: "Repeatable packets", icon: Sparkles },
];

export default function HomePage() {
  return (
    <AppShell subtitle="Open, edit, convert & protect common document formats">
      <BackendStatus />

      <main className="mx-auto flex max-w-7xl flex-col gap-10 px-4 py-8 sm:px-6 lg:px-8">
        <section className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(380px,0.85fr)]">
          <div className="flex flex-col justify-center py-2">
            <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-trust-200 bg-trust-50 px-3 py-1 text-xs font-medium text-trust-700">
              <ShieldCheck className="h-3.5 w-3.5" /> Private to your session
            </span>
            <h1 className="mt-4 text-4xl font-semibold leading-[1.1] tracking-tight text-ink sm:text-5xl">
              Open common formats.
              <br />
              <span className="text-brand-600">Edit with proof.</span>
            </h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-slate-600">
              Drop in a PDF, Word file, spreadsheet, deck, or scan — extract structured content,
              apply audited edits, redact, fill forms, and export validated copies. Native layout
              fidelity varies by format.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <a href="#upload" className="btn-primary">
                Upload a document
              </a>
              <Link href="#tools" className="btn-secondary">
                Browse all tools
              </Link>
            </div>
            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              {TRUST_ITEMS.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.label} className="flex items-start gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-trust-50 text-trust-700">
                      <Icon className="h-5 w-5" />
                    </span>
                    <span>
                      <span className="block text-sm font-semibold text-ink">{item.label}</span>
                      <span className="block text-sm text-slate-500">{item.detail}</span>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          <div id="upload" className="card scroll-mt-20 p-5 sm:p-6">
            <h2 className="text-base font-semibold text-ink">Start here</h2>
            <p className="mt-1 text-sm text-slate-500">
              Drop a contract, invoice, form, spreadsheet, deck, or scan.
            </p>
            <div className="mt-4">
              <UploadDropzone />
            </div>
            <SystemStatusPanel className="mt-5 border-t border-line pt-4" />
            <PrivacyPanel className="mt-5 border-t border-line pt-4" />
          </div>
        </section>

        <section id="featured" className="scroll-mt-20">
          <div className="grid gap-4 md:grid-cols-3">
            <Link
              href="/tasks/pdf-to-excel"
              className="group rounded-2xl border border-amber-200 bg-amber-50 p-5 transition-colors hover:bg-amber-100"
            >
              <span className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                Free · no login
              </span>
              <h3 className="mt-2 text-lg font-semibold text-ink">📊 PDF → Excel</h3>
              <p className="mt-1 text-sm leading-6 text-slate-700">
                Pull tables and data out of a PDF or scan straight into a spreadsheet. Stop paying
                someone to retype it by hand.
              </p>
              <span className="mt-3 inline-block text-sm font-medium text-amber-800 group-hover:underline">
                Get my spreadsheet →
              </span>
            </Link>
            <Link
              href="/tasks/un-redact-test"
              className="group rounded-2xl border border-red-200 bg-red-50 p-5 transition-colors hover:bg-red-100"
            >
              <span className="text-xs font-semibold uppercase tracking-wide text-red-600">
                Free · no login
              </span>
              <h3 className="mt-2 text-lg font-semibold text-ink">🕵️ Un-Redact Test</h3>
              <p className="mt-1 text-sm leading-6 text-slate-700">
                Drop a “redacted” PDF and see if the blacked-out text is still recoverable. If our
                tool can pull it back, so can anyone you sent it to.
              </p>
              <span className="mt-3 inline-block text-sm font-medium text-red-700 group-hover:underline">
                Test my redactions →
              </span>
            </Link>
            <Link
              href="/tasks/send-ready-check"
              className="group rounded-2xl border border-trust-200 bg-trust-50 p-5 transition-colors hover:bg-trust-100"
            >
              <span className="text-xs font-semibold uppercase tracking-wide text-trust-700">
                Before you hit send
              </span>
              <h3 className="mt-2 text-lg font-semibold text-ink">🛡️ Send-Ready Check</h3>
              <p className="mt-1 text-sm leading-6 text-slate-700">
                One click reveals hidden metadata, exposed PII, and unsafe redactions — then cleans
                it and proves the removed text is unrecoverable.
              </p>
              <span className="mt-3 inline-block text-sm font-medium text-trust-700 group-hover:underline">
                Check before sending →
              </span>
            </Link>
          </div>
        </section>

        <section id="workflows" className="scroll-mt-20">
          <div className="mb-4">
            <h2 className="text-lg font-semibold tracking-tight text-ink sm:text-xl">
              Guided workflows
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Multi-step packets for the jobs teams run every week.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {WORKFLOWS.map((workflow) => {
              const Icon = WORKFLOW_ICONS[workflow.preset];
              return (
                <Link
                  key={workflow.preset}
                  href={`/tasks/${TASK_SLUGS[workflow.preset]}`}
                  className="workflow-row group"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700 transition-colors group-hover:bg-brand-100">
                      <Icon className="h-5 w-5" />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold text-ink">{workflow.title}</span>
                      <span className="mt-1 block text-sm leading-5 text-slate-600">
                        {workflow.blurb}
                      </span>
                      <span className="mt-3 block text-xs font-medium text-trust-700">
                        {workflow.revenueSignal}
                      </span>
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
          <Section
            id="library"
            title="Recent documents"
            description="Private to this browser session. Search and reopen any document."
            className="card p-5"
          >
            <div className="space-y-4">
              <SearchBar />
              <DocumentList />
            </div>
          </Section>

          <Section
            id="templates"
            title="Templates"
            description="Stamp out fresh, independent documents from reusable packets."
            className="card p-5"
          >
            <TemplateGallery />
          </Section>
        </section>

        <Section
          id="tools"
          title="All document tools"
          description="Every capability, one click away — edit, convert, redact, sign, compare, and more."
          className="card scroll-mt-20 p-5"
        >
          <TaskGrid compact />
        </Section>
      </main>
    </AppShell>
  );
}
