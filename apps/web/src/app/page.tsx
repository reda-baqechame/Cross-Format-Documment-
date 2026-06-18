import { DocumentList } from "@/components/documents/DocumentList";
import { SearchBar } from "@/components/documents/SearchBar";
import { AppShell, Section } from "@/components/layout/AppShell";
import { BackendStatus } from "@/components/system/BackendStatus";
import { TaskGrid } from "@/components/tasks/TaskGrid";
import { TemplateGallery } from "@/components/templates/TemplateGallery";

export default function HomePage() {
  return (
    <AppShell>
      <BackendStatus />

      <main className="mx-auto max-w-6xl space-y-10 px-4 py-8 sm:space-y-14 sm:px-6 sm:py-12">
        {/* Hero */}
        <section className="text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Every document tool, in one place
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-slate-600 sm:text-lg">
            Merge, split, convert, edit, protect, and sign your documents. Pick a task, add your
            file, get it back — no account, no clutter.
          </p>
        </section>

        {/* Task picker — the main entry point */}
        <Section title="What do you want to do?" description="Choose a task to get started.">
          <TaskGrid />
        </Section>

        {/* Library */}
        <Section
          id="library"
          title="Your recent documents"
          description="Files you’ve opened recently. Search by keyword to find one fast."
        >
          <div className="space-y-4">
            <SearchBar />
            <DocumentList />
          </div>
        </Section>

        {/* Templates */}
        <Section
          id="templates"
          title="Start from a template"
          description="Reuse a saved document as a fresh, independent starting point."
        >
          <TemplateGallery />
        </Section>
      </main>
    </AppShell>
  );
}
