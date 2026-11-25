"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";

import { ApiError } from "@/lib/api";

import { AuthProvider } from "./auth-provider";
import { ThemeProvider } from "./theme-provider";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            refetchOnWindowFocus: false,
            // Do not retry client errors (404 for a project you lost access to, 403, validation).
            retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
          },
        },
      }),
  );
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          {children}
          <Toaster position="bottom-right" richColors closeButton />
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
