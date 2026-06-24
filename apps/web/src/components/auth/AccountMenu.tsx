"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { fetchMe, loginUser, logoutUser, registerUser } from "@/lib/api";

export function AccountMenu() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["auth", "me"], queryFn: fetchMe });
  const logout = useMutation({
    mutationFn: logoutUser,
    onSuccess: () => {
      queryClient.setQueryData(["auth", "me"], null);
      router.refresh();
    },
  });

  if (me.isLoading) return null;

  if (me.data) {
    return (
      <div className="flex items-center gap-2">
        <span className="hidden text-sm text-slate-600 sm:inline">{me.data.email}</span>
        <button
          type="button"
          onClick={() => logout.mutate()}
          className="text-sm font-medium text-slate-500 hover:text-slate-800"
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <Link href="/login" className="font-medium text-slate-500 hover:text-slate-800">
        Sign in
      </Link>
      <Link href="/signup" className="rounded-lg bg-brand-600 px-3 py-1.5 font-medium text-white hover:bg-brand-500">
        Sign up
      </Link>
    </div>
  );
}

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () =>
      mode === "login"
        ? loginUser(email, password)
        : registerUser(email, password, name || undefined),
    onSuccess: (res) => {
      queryClient.setQueryData(["auth", "me"], res.user);
      router.push("/");
      router.refresh();
    },
    onError: (e) => setError(e instanceof Error ? e.message : String(e)),
  });

  return (
    <form
      className="mx-auto max-w-md space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        submit.mutate();
      }}
    >
      <h1 className="text-xl font-semibold text-slate-900">
        {mode === "login" ? "Sign in to DocOS" : "Create your DocOS account"}
      </h1>
      {mode === "signup" && (
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name (optional)"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
      )}
      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
      />
      <input
        type="password"
        required
        minLength={8}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password (8+ characters)"
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
      />
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={submit.isPending}
        className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-50"
      >
        {submit.isPending ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
      </button>
      <p className="text-center text-sm text-slate-500">
        {mode === "login" ? (
          <>
            No account? <Link href="/signup" className="text-brand-600 hover:underline">Sign up</Link>
          </>
        ) : (
          <>
            Already have one? <Link href="/login" className="text-brand-600 hover:underline">Sign in</Link>
          </>
        )}
      </p>
    </form>
  );
}
