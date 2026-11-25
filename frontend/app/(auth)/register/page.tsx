"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { AuthForm } from "@/components/auth/auth-form";
import { useAuth } from "@/components/providers/auth-provider";

export default function RegisterPage() {
  const { status, register } = useAuth();
  const router = useRouter();
  // Set once this page registers someone, so the "already signed in" redirect below does not race it.
  const justRegistered = useRef(false);

  useEffect(() => {
    if (status === "authenticated" && !justRegistered.current) router.replace("/dashboard");
  }, [status, router]);

  return (
    <AuthForm
      mode="register"
      onSubmit={async ({ name, email, password }) => {
        justRegistered.current = true;
        try {
          await register(name, email, password);
        } catch (err) {
          justRegistered.current = false;
          throw err;
        }
        // New accounts start on the projects page, where the first step is creating a project.
        router.replace("/projects");
      }}
    />
  );
}
