"use client";

import { ArrowLeft, Lock } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";

import { projectContextValue, ProjectProvider } from "@/components/project/project-context";
import { ProjectStatusBadge, RoleBadge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { ApiError } from "@/lib/api";
import { useProject } from "@/lib/queries";
import { cn, PLATFORM_LABELS } from "@/lib/utils";

const TABS = [
  { segment: "", label: "Overview" },
  { segment: "requirements", label: "Requirements" },
  { segment: "documents", label: "Documents" },
  { segment: "knowledge", label: "Knowledge search" },
  { segment: "modules", label: "Modules" },
  { segment: "members", label: "Members" },
  { segment: "activity", label: "Activity" },
  { segment: "settings", label: "Settings" },
];

const UPCOMING = [
  { label: "Figma designs", phase: 3 },
  { label: "Gap analysis", phase: 3 },
  { label: "Test cases", phase: 3 },
  { label: "Bug reports", phase: 3 },
  { label: "Automation", phase: 4 },
];

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const { projectId } = useParams<{ projectId: string }>();
  const pathname = usePathname();
  const project = useProject(projectId);
  const base = `/projects/${projectId}`;

  if (project.isPending) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (project.isError) {
    if (project.error instanceof ApiError && project.error.status === 404) {
      return (
        <EmptyState
          title="Project not found"
          description="It may have been deleted, or you are no longer a member."
          action={
            <Button asChild variant="outline">
              <Link href="/projects">Back to projects</Link>
            </Button>
          }
        />
      );
    }
    return <ErrorState error={project.error} onRetry={() => project.refetch()} />;
  }

  const p = project.data;
  return (
    <ProjectProvider value={projectContextValue(p)}>
      <Link href="/projects" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" />
        Projects
      </Link>
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{p.name}</h1>
          <p className="text-sm text-muted-foreground">
            {PLATFORM_LABELS[p.platform]}
            {p.business_domain && ` · ${p.business_domain}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ProjectStatusBadge status={p.status} />
          <RoleBadge role={p.my_role} />
        </div>
      </div>
      {p.status === "archived" && (
        <p className="mb-4 flex items-center gap-2 rounded-md border border-warning/50 bg-warning/10 px-3 py-2 text-sm">
          <Lock className="size-4" />
          This project is archived and read-only. An admin can restore it from Settings.
        </p>
      )}
      <nav aria-label="Project sections" className="mb-6 overflow-x-auto border-b">
        <ul className="flex min-w-max gap-1">
          {TABS.map((t) => {
            const href = t.segment ? `${base}/${t.segment}` : base;
            const active = t.segment ? pathname.startsWith(href) : pathname === base;
            return (
              <li key={t.label}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "-mb-px inline-block border-b-2 px-3 py-2 text-sm",
                    active
                      ? "border-primary font-medium text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t.label}
                </Link>
              </li>
            );
          })}
          {UPCOMING.map((t) => (
            <li key={t.label}>
              <span
                className="inline-block cursor-not-allowed px-3 py-2 text-sm text-muted-foreground/60"
                title={`Arrives in Phase ${t.phase}`}
                aria-disabled="true"
              >
                {t.label}
              </span>
            </li>
          ))}
        </ul>
      </nav>
      {children}
    </ProjectProvider>
  );
}
