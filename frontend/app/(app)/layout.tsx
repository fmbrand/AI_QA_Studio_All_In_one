"use client";

import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/components/providers/auth-provider";

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [status, router, pathname]);

  if (status !== "authenticated") {
    return (
      <div className="flex min-h-screen items-center justify-center" role="status" aria-label="Loading">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}
