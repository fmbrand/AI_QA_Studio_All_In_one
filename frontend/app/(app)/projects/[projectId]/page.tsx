"use client";

import { ExternalLink } from "lucide-react";
import Link from "next/link";

import { useCurrentProject } from "@/components/project/project-context";
import { ActivityList } from "@/components/shared/activity-list";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/states";
import { useActivity } from "@/lib/queries";
import { formatDate, PLATFORM_LABELS } from "@/lib/utils";

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">{children}</dd>
    </div>
  );
}

export default function ProjectOverviewPage() {
  const { project } = useCurrentProject();
  const activity = useActivity(project.id);
  const recent = activity.data?.pages[0]?.data.slice(0, 8) ?? [];
  const base = `/projects/${project.id}`;

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="grid gap-6 lg:col-span-2">
        <Card>
          <CardHeader>
            <CardTitle>About this project</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <p className="whitespace-pre-wrap text-sm">
              {project.description || <span className="text-muted-foreground">No description yet.</span>}
            </p>
            <dl className="grid gap-4 sm:grid-cols-2">
              <Detail label="Platform">{PLATFORM_LABELS[project.platform]}</Detail>
              <Detail label="Project type">{project.project_type || "—"}</Detail>
              <Detail label="Business domain">{project.business_domain || "—"}</Detail>
              <Detail label="Application URL">
                {project.application_url ? (
                  <a
                    href={project.application_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    {project.application_url}
                    <ExternalLink className="size-3" />
                  </a>
                ) : (
                  "—"
                )}
              </Detail>
              <Detail label="Technology stack">
                {project.tech_stack.length ? (
                  <span className="flex flex-wrap gap-1">
                    {project.tech_stack.map((t) => (
                      <Badge key={t}>{t}</Badge>
                    ))}
                  </span>
                ) : (
                  "—"
                )}
              </Detail>
              <Detail label="Created">{formatDate(project.created_at)}</Detail>
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            {activity.isPending ? (
              <Skeleton className="h-32" />
            ) : recent.length ? (
              <>
                <ActivityList items={recent} />
                <Link href={`${base}/activity`} className="mt-4 inline-block text-sm text-primary hover:underline">
                  View all activity
                </Link>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No activity yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
      <Card className="h-fit">
        <CardHeader>
          <CardTitle>Knowledge base</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-3 text-sm">
            {[
              { label: "Documents", value: project.stats.documents, href: `${base}/documents` },
              { label: "Modules", value: project.stats.modules, href: `${base}/modules` },
              { label: "Members", value: project.stats.members, href: `${base}/members` },
            ].map((row) => (
              <li key={row.label} className="flex items-center justify-between">
                <Link href={row.href} className="hover:underline">
                  {row.label}
                </Link>
                <span className="font-medium tabular-nums">{row.value}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-muted-foreground">
            Documents uploaded here stay inside this project. Requirement extraction and semantic search over them
            arrive with the Phase 2 context engine.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
