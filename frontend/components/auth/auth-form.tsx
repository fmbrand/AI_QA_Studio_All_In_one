"use client";

import { FlaskConical } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { ApiError, errorMessage } from "@/lib/api";

export type AuthMode = "login" | "register";

export interface AuthValues {
  name: string;
  email: string;
  password: string;
}

export function validateAuth(mode: AuthMode, v: AuthValues): Partial<Record<keyof AuthValues, string>> {
  const errors: Partial<Record<keyof AuthValues, string>> = {};
  if (mode === "register" && !v.name.trim()) errors.name = "Enter your name";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.email.trim())) errors.email = "Enter a valid email address";
  if (mode === "register" && v.password.length < 10) errors.password = "Use at least 10 characters";
  if (mode === "login" && !v.password) errors.password = "Enter your password";
  return errors;
}

interface AuthFormProps {
  mode: AuthMode;
  onSubmit: (values: AuthValues) => Promise<void>;
}

export function AuthForm({ mode, onSubmit }: AuthFormProps) {
  const [values, setValues] = useState<AuthValues>({ name: "", email: "", password: "" });
  const [errors, setErrors] = useState<Partial<Record<keyof AuthValues, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const isRegister = mode === "register";

  const set = (key: keyof AuthValues) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setValues((v) => ({ ...v, [key]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found = validateAuth(mode, values);
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length) return;
    setSubmitting(true);
    try {
      await onSubmit({ ...values, email: values.email.trim(), name: values.name.trim() });
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) {
        setErrors({
          name: err.fieldError("name"),
          email: err.fieldError("email"),
          password: err.fieldError("password"),
        });
      }
      setFormError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <span className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <FlaskConical className="size-5" />
          </span>
          <h1 className="text-xl font-semibold">{isRegister ? "Create your account" : "Sign in to AI QA Studio"}</h1>
          <p className="text-sm text-muted-foreground">
            {isRegister ? "Set up your QA workspace in a minute." : "Welcome back."}
          </p>
        </div>
        <form onSubmit={submit} noValidate className="grid gap-4 rounded-lg border bg-card p-6">
          {formError && (
            <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {formError}
            </p>
          )}
          {isRegister && (
            <Field label="Name" htmlFor="name" error={errors.name} required>
              <Input
                id="name"
                autoComplete="name"
                value={values.name}
                onChange={set("name")}
                aria-invalid={!!errors.name}
                aria-describedby={errors.name ? "name-error" : undefined}
              />
            </Field>
          )}
          <Field label="Email" htmlFor="email" error={errors.email} required>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              value={values.email}
              onChange={set("email")}
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? "email-error" : undefined}
            />
          </Field>
          <Field
            label="Password"
            htmlFor="password"
            error={errors.password}
            hint={isRegister ? "At least 10 characters." : undefined}
            required
          >
            <Input
              id="password"
              type="password"
              autoComplete={isRegister ? "new-password" : "current-password"}
              value={values.password}
              onChange={set("password")}
              aria-invalid={!!errors.password}
              aria-describedby={errors.password ? "password-error" : isRegister ? "password-hint" : undefined}
            />
          </Field>
          <Button type="submit" loading={submitting}>
            {isRegister ? "Create account" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          {isRegister ? "Already have an account? " : "New to AI QA Studio? "}
          <Link className="font-medium text-primary hover:underline" href={isRegister ? "/login" : "/register"}>
            {isRegister ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </div>
    </div>
  );
}
