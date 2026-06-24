import { AppShell } from "@/components/layout/AppShell";
import { AuthForm } from "@/components/auth/AccountMenu";

export default function SignupPage() {
  return (
    <AppShell subtitle="Create an account — your session documents are claimed automatically">
      <main className="mx-auto max-w-6xl px-4 py-12">
        <AuthForm mode="signup" />
      </main>
    </AppShell>
  );
}
