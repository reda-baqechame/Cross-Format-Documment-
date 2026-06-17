import { DocumentList } from "@/components/documents/DocumentList";
import { NotebookPanel } from "@/components/documents/NotebookPanel";
import { SearchBar } from "@/components/documents/SearchBar";
import { AppShell, Section } from "@/components/layout/AppShell";
import { CapabilityGrid } from "@/components/marketing/CapabilityGrid";
import { JobTiles } from "@/components/marketing/JobTiles";
import { WorkflowStrip } from "@/components/marketing/WorkflowStrip";
import { BackendStatus } from "@/components/system/BackendStatus";
import { UploadDropzone } from "@/components/upload/UploadDropzone";

export default function HomePage() {
  return (
    <AppShell>
      <BackendStatus />

      <main className="mx-auto max-w-6xl space-y-12 px-4 py-8 sm:space-y-16 sm:px-6 sm:py-12">
        {/* Hero */}
        <section className="text-center">
          <p className="mb-3 inline-block rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand-700">
            One stop for every document job
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Open anything. Edit once. Trust the output.
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-slate-600 sm:text-lg">
            Unlike single-purpose PDF or Word tools, this workspace keeps one canonical model across
            formats — so edit, redact, convert, and sign without losing fidelity.
          </p>
        </section>

        <JobTiles />

        {/* Primary action */}
        <Section
          id="upload"
          title="Start here — open a document"
          description="Upload from your phone or computer. Supported: PDF, Word, Excel, PowerPoint, RTF, text, and images."
        >
          <UploadDropzone />
        </Section>

        {/* How it works */}
        <Section
          title="How it works"
          description="Three steps from upload to a safe export — the same flow competitors split across multiple apps."
        >
          <WorkflowStrip />
        </Section>

        {/* Capabilities */}
        <Section
          title="What you can do here"
          description="Capabilities grouped by job — open & convert, edit & AI, trust & compliance, review & team."
        >
          <CapabilityGrid />
        </Section>

        {/* Research */}
        <Section
          id="research"
          title="Research your library"
          description="Ask one question across every document you’ve uploaded. Answers include citations back to the source."
        >
          <NotebookPanel />
        </Section>

        {/* Library */}
        <Section
          id="library"
          title="Your documents"
          description="Everything you’ve opened lives here. Search by keyword or semantic relevance."
        >
          <div className="space-y-4">
            <SearchBar />
            <DocumentList />
          </div>
        </Section>
      </main>
    </AppShell>
  );
}
