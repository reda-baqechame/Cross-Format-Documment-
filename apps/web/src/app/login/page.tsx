import { AppShell } from "@/components/layout/AppShell";
import { AuthForm } from "@/components/auth/AccountMenu";

export default function LoginPage() {
  return (
    <AppShell subtitle="Sign in to save documents and send client portal links">
      <main className="mx-auto max-w-6xl px-4 py-12">
        <AuthForm mode="login" />
      </main>
    </AppShell>
  );
}
