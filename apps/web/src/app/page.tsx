import { DocumentList } from "@/components/documents/DocumentList";
import { SearchBar } from "@/components/documents/SearchBar";
import { UploadDropzone } from "@/components/upload/UploadDropzone";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-8 p-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold">Cross-Format Document OS</h1>
        <p className="text-slate-600">
          Open almost any document, edit it semantically, and keep it correct as it moves across
          formats, teams, and trust boundaries.
        </p>
      </header>
      <UploadDropzone />
      <SearchBar />
      <DocumentList />
    </main>
  );
}
