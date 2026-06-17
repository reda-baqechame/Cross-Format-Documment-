import { DocumentList } from "@/components/documents/DocumentList";
import { SearchBar } from "@/components/documents/SearchBar";
import { UploadDropzone } from "@/components/upload/UploadDropzone";

const STEPS = [
  {
    icon: "📤",
    title: "1 · Open",
    body: "Drop a PDF, Word, Excel, PowerPoint, RTF, text, or image file. It's parsed into one canonical model.",
  },
  {
    icon: "✏️",
    title: "2 · Edit & check",
    body: "Double-click any text to edit it. Ask AI to make changes, then review the document-health panel.",
  },
  {
    icon: "📥",
    title: "3 · Convert & download",
    body: "Export to Word, PDF, Markdown, HTML, or CSV — with edits and redactions safely applied.",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-ink text-lg text-white">
            ◆
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight">Cross-Format Document OS</p>
            <p className="text-xs leading-tight text-slate-500">
              Open, edit, convert, and protect any document
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-10 px-6 py-12">
        <section className="space-y-3 text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
            One workspace for every document
          </h1>
          <p className="mx-auto max-w-2xl text-slate-600">
            Open almost any file and keep it correct as it moves across formats, teams, and trust
            boundaries. Start by adding a document below.
          </p>
        </section>

        <UploadDropzone />

        <section className="grid gap-4 sm:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.title} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-2 text-2xl" aria-hidden>
                {s.icon}
              </div>
              <h3 className="text-sm font-semibold text-slate-800">{s.title}</h3>
              <p className="mt-1 text-sm text-slate-500">{s.body}</p>
            </div>
          ))}
        </section>

        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Your documents
          </h2>
          <SearchBar />
          <DocumentList />
        </section>
      </main>
    </div>
  );
}
