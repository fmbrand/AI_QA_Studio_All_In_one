import { AlertTriangle, Inbox } from "lucide-react";
import type * as React from "react";

import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

import { Button } from "./button";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} aria-hidden />;
}

export function LoadingRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="grid gap-2" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

interface EmptyStateProps {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon = Inbox, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center rounded-lg border border-dashed px-6 py-10 text-center", className)}>
      <Icon className="mb-3 size-8 text-muted-foreground" />
      <p className="font-medium">{title}</p>
      {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: () => void; className?: string }) {
  return (
    <div
      role="alert"
      className={cn("flex flex-col items-center rounded-lg border border-destructive/40 px-6 py-8 text-center", className)}
    >
      <AlertTriangle className="mb-2 size-7 text-destructive" />
      <p className="font-medium">Could not load this</p>
      <p className="mt-1 text-sm text-muted-foreground">{errorMessage(error)}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
