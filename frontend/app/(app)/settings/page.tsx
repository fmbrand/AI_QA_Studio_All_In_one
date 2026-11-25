"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/app-shell";
import { useAuth } from "@/components/providers/auth-provider";
import { useTheme, type Theme } from "@/components/providers/theme-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/states";
import { api, errorMessage } from "@/lib/api";
import { keys, useAIStatus } from "@/lib/queries";
import type { User } from "@/lib/types";

export default function SettingsPage() {
  const { user, setUser, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [name, setName] = useState(user?.name ?? "");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const ai = useAIStatus();

  const saveName = useMutation({
    mutationFn: () => api.patch<User>("/me", { name: name.trim() }),
    onSuccess: (u) => {
      setUser(u);
      queryClient.invalidateQueries({ queryKey: keys.me });
      toast.success("Profile saved");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const changePassword = useMutation({
    mutationFn: () => api.post("/me/password", { current_password: current, new_password: next }),
    onSuccess: async () => {
      toast.success("Password changed. Sign in again with your new password.");
      await logout();
      router.replace("/login");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <>
      <PageHeader title="Settings" description="Your account and preferences." />
      <div className="grid max-w-2xl gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>{user?.email}</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="flex flex-col gap-3 sm:flex-row sm:items-end"
              onSubmit={(e) => {
                e.preventDefault();
                if (name.trim()) saveName.mutate();
              }}
            >
              <Field label="Name" htmlFor="profile-name" className="flex-1">
                <Input id="profile-name" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
              </Field>
              <Button type="submit" loading={saveName.isPending} disabled={!name.trim() || name.trim() === user?.name}>
                Save
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Password</CardTitle>
            <CardDescription>Changing it signs you out on every device.</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (next.length < 10) return toast.error("Use at least 10 characters for the new password");
                changePassword.mutate();
              }}
            >
              <Field label="Current password" htmlFor="current-password">
                <Input id="current-password" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
              </Field>
              <Field label="New password" htmlFor="new-password" hint="At least 10 characters.">
                <Input id="new-password" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
              </Field>
              <div>
                <Button type="submit" loading={changePassword.isPending} disabled={!current || !next}>
                  Change password
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
          </CardHeader>
          <CardContent>
            <Field label="Theme" htmlFor="theme" className="max-w-xs">
              <Select id="theme" value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </Select>
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI and document processing</CardTitle>
            <CardDescription>
              Configured on the server by an administrator (backend environment). API keys are never shown here.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {ai.isPending ? (
              <Skeleton className="h-16" />
            ) : ai.data ? (
              <dl className="grid gap-2 text-sm sm:grid-cols-[10rem_1fr]">
                <dt className="text-muted-foreground">Language model</dt>
                <dd>
                  {ai.data.llm.configured
                    ? `${ai.data.llm.provider}${ai.data.llm.model ? ` · ${ai.data.llm.model}` : ""}`
                    : "Not configured — AI extraction is off"}
                </dd>
                <dt className="text-muted-foreground">Embeddings</dt>
                <dd>
                  {ai.data.embeddings.provider} · {ai.data.embeddings.model}
                </dd>
                <dt className="text-muted-foreground">OCR</dt>
                <dd>{ai.data.ocr.available ? `Tesseract (${ai.data.ocr.languages})` : "Not installed — scanned pages and images are not read"}</dd>
              </dl>
            ) : null}
            <p className="mt-3 text-xs text-muted-foreground">Figma and GitHub integrations arrive in Phases 3 to 5.</p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
