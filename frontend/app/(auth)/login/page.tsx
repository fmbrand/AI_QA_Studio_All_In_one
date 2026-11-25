"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { AuthForm } from "@/components/auth/auth-form";
import { useAuth } from "@/components/providers/auth-provider";

function safeNext(next: string | null): string {
  // Only allow same-site relative paths to avoid open redirects.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

function LoginPage() {
  const { status, login } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));

  useEffect(() => {
    if (status === "authenticated") router.replace(next);
  }, [status, router, next]);

  return (
    <AuthForm
      mode="login"
      onSubmit={async ({ email, password }) => {
        await login(email, password);
        router.replace(next);
      }}
    />
  );
}

export default function Page() {
  return (
    <Suspense>
      <LoginPage />
    </Suspense>
  );
}
