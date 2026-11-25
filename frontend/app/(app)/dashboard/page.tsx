"use client";

import { Archive, CheckCircle2, ClipboardList, FileText, FolderKanban, Layers, Plus } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/app-shell";
import { NAV_ITEMS } from "@/components/layout/nav";
import { useAuth } from "@/components/providers/auth-provider";
import { ActivityList } from "@/components/shared/activity-list";
import { JobStatusBadge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useDashboard, useMe } from "@/lib/queries";
import { timeAgo } from "@/lib/utils";

function Stat({ label, value, icon: Icon }: { label: string; value: number; icon: typeof FolderKanban }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-5">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
        </div>
        <Icon className="size-5 text-muted-foreground" />
      </CardContent>
    </Card>
  );
}

const JOB_LABELS: Record<string, string> = {
  document_ingest: "Document indexing",
  requirement_extraction: "Requirement extraction (AI)",
};

export default function DashboardPage() {
  const { user } = useAuth();
  const dashboard = useDashboard();
  const me = useMe();
  const projectName = (id: string) => me.data?.memberships.find((m) => m.project_id === id)?.project_name ?? "Project";
  const upcoming = NAV_ITEMS.filter((n) => n.phase);

  return (
    <>
      <PageHeader
        title={`Welcome, ${user?.name.split(" ")[0] ?? ""}`}
        description="Your QA workspace across all projects."
        actions={
          <Button asChild>
            <Link href="/projects?new=1">
              <Plus />
              New project
            </Link>
          </Button>
        }
      />
      {dashboard.isError ? (
        <ErrorState error={dashboard.error} onRetry={() => dashboard.refetch()} />
      ) : (
        <div className="grid gap-6">
          <section aria-label="Totals" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {dashboard.isPending ? (
              Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-24" />)
            ) : (
              <>
                <Stat label="Active projects" value={dashboard.data.totals.active_projects} icon={FolderKanban} />
                <Stat label="Archived projects" value={dashboard.data.totals.archived_projects} icon={Archive} />
                <Stat label="Documents" value={dashboard.data.totals.documents} icon={FileText} />
                <Stat label="Modules" value={dashboard.data.totals.modules} icon={Layers} />
                <Stat label="Requirements" value={dashboard.data.totals.requirements} icon={ClipboardList} />
                <Stat label="Approved requirements" value={dashboard.data.totals.approved_requirements} icon={CheckCircle2} />
              </>
            )}
          </section>

          <div className="grid gap-6 lg:grid-cols-5">
            <Card className="lg:col-span-3">
              <CardHeader>
                <CardTitle>Recent activity</CardTitle>
                <CardDescription>Changes across your projects</CardDescription>
              </CardHeader>
              <CardContent>
                {dashboard.isPending ? (
                  <Skeleton className="h-40" />
                ) : dashboard.data.recent_activity.length === 0 ? (
                  <EmptyState
                    title="No activity yet"
                    description="Create a project and upload its requirements to get started."
                  />
                ) : (
                  <ActivityList items={dashboard.data.recent_activity} showProject={projectName} />
                )}
              </CardContent>
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Recent background jobs</CardTitle>
                <CardDescription>Document processing and, later, AI operations</CardDescription>
              </CardHeader>
              <CardContent>
                {dashboard.isPending ? (
                  <Skeleton className="h-40" />
                ) : dashboard.data.recent_jobs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No jobs have run yet.</p>
                ) : (
                  <ul className="grid gap-2 text-sm">
                    {dashboard.data.recent_jobs.map((j) => (
                      <li key={j.id} className="flex items-center justify-between gap-2">
                        <span className="min-w-0">
                          <span className="block truncate">{JOB_LABELS[j.kind] ?? j.kind}</span>
                          <span className="block text-xs text-muted-foreground">
                            {j.project_id ? projectName(j.project_id) : ""} · {timeAgo(j.created_at)}
                          </span>
                        </span>
                        <JobStatusBadge status={j.status} />
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>QA modules on the roadmap</CardTitle>
              <CardDescription>
                Test case, gap, bug and automation metrics appear here once those modules ship. Nothing on this
                dashboard is sample data.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
                {upcoming.map(({ href, label, icon: Icon, phase }) => (
                  <li key={href} className="flex items-center gap-2 rounded-md border px-3 py-2">
                    <Icon className="size-4 text-muted-foreground" />
                    <span className="flex-1">{label}</span>
                    <span className="text-xs text-muted-foreground">Phase {phase}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
