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
    <AppShell subtitle="Business document workflows, editing, trust, and export validation">
      <BackendStatus />

      <main className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-6 sm:px-6 lg:px-8">
        <section className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h1 className="text-3xl font-semibold tracking-tight text-slate-950">
                  Open any document. Do anything. Trust the output.
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
                  Start with a paid business workflow, or upload any file and turn it into a
                  validated packet with forms, approvals, redaction, templates, and export proof.
                </p>
              </div>
              <Link
                href="#workflows"
                className="inline-flex min-h-[40px] shrink-0 items-center justify-center rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
              >
                Launch workflow
              </Link>
            </div>

            <div id="workflows" className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {WORKFLOWS.map((workflow) => {
                const Icon = WORKFLOW_ICONS[workflow.preset];
                return (
                  <Link
                    key={workflow.preset}
                    href={`/tasks/${TASK_SLUGS[workflow.preset]}`}
                    className="workflow-row group"
                  >
                    <div className="flex items-start gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-blue-100 bg-blue-50 text-blue-700 group-hover:border-blue-200 group-hover:bg-white">
                        <Icon className="h-5 w-5" />
                      </span>
                      <span className="min-w-0">
                        <span className="block text-sm font-semibold text-slate-950">
                          {workflow.title}
                        </span>
                        <span className="mt-1 block text-sm leading-5 text-slate-600">
                          {workflow.blurb}
                        </span>
                        <span className="mt-3 block text-xs font-medium text-teal-700">
                          {workflow.revenueSignal}
                        </span>
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-slate-950">Command or upload</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Drop a contract, invoice, form, spreadsheet, deck, scan, or template.
                </p>
              </div>
              <span className="rounded-full border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-700">
                Private session
              </span>
            </div>
            <UploadDropzone />
          </div>
        </section>

        <section className="grid gap-3 md:grid-cols-4">
          {TRUST_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <Icon className="h-5 w-5 text-teal-700" />
                <p className="mt-3 text-sm font-semibold text-slate-950">{item.label}</p>
                <p className="mt-1 text-sm text-slate-500">{item.detail}</p>
              </div>
            );
          })}
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
          <Section
            id="library"
            title="Recent documents"
            description="Private to this browser session. Search and reopen any active packet."
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <div className="space-y-4">
              <SearchBar />
              <DocumentList />
            </div>
          </Section>

          <Section
            id="templates"
            title="Templates"
            description="Stamp out fresh independent documents from reusable packets."
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <TemplateGallery />
          </Section>
        </section>

        <Section
          title="All document tools"
          description="The complete toolkit stays available after the revenue workflows."
          className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <TaskGrid compact />
        </Section>
      </main>
    </AppShell>
  );
}
