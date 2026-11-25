"use client";

import { FileSearch, FolderKanban } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useProjects } from "@/lib/queries";
import { PLATFORM_LABELS } from "@/lib/utils";

/** Requirements always belong to one project, so this entry point asks which project to open. */
export default function RequirementAnalysisPage() {
  const projects = useProjects("active");
  return (
    <>
      <PageHeader
        title="Requirement Analysis"
        description="Extract requirements from a project's documents, review them, and keep their version history."
      />
      {projects.isPending ? (
        <LoadingRows />
      ) : projects.isError ? (
        <ErrorState error={projects.error} onRetry={() => projects.refetch()} />
      ) : projects.data.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title="No active projects"
          description="Create a project and upload its documents first."
          action={
            <Link href="/projects?new=1" className="text-sm font-medium text-primary hover:underline">
              Create a project
            </Link>
          }
        />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Choose a project">
          {projects.data.map((p) => (
            <li key={p.id}>
              <Link href={`/projects/${p.id}/requirements`} className="block h-full">
                <Card className="h-full transition-colors hover:bg-accent">
                  <CardContent className="flex gap-3 p-4">
                    <FileSearch className="mt-0.5 size-5 shrink-0 text-primary" />
                    <div className="min-w-0">
                      <p className="truncate font-medium">{p.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {PLATFORM_LABELS[p.platform]} · {p.stats.documents} document{p.stats.documents === 1 ? "" : "s"}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
