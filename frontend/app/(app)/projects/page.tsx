"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderKanban, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useDeferredValue, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/app-shell";
import { ProjectForm } from "@/components/project/project-form";
import { ProjectStatusBadge, RoleBadge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/form";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api } from "@/lib/api";
import { keys, useProjects } from "@/lib/queries";
import type { Project, ProjectInput, ProjectStatus } from "@/lib/types";
import { cn, PLATFORM_LABELS, timeAgo } from "@/lib/utils";

const TABS: { value: ProjectStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "archived", label: "Archived" },
];

function ProjectsPage() {
  const params = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ProjectStatus>("active");
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const projects = useProjects(status, q || undefined);
  const [creating, setCreating] = useState(params.get("new") === "1");

  const create = useMutation({
    mutationFn: (input: ProjectInput) => api.post<Project>("/projects", input),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: keys.me });
      queryClient.invalidateQueries({ queryKey: keys.dashboard });
      toast.success(`Created ${project.name}`);
      router.push(`/projects/${project.id}`);
    },
  });

  return (
    <>
      <PageHeader
        title="Projects"
        description="Each project keeps its own knowledge base, members and QA history."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus />
            New project
          </Button>
        }
      />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div role="tablist" aria-label="Project status" className="inline-flex rounded-md border p-0.5">
          {TABS.map((t) => (
            <button
              key={t.value}
              role="tab"
              aria-selected={status === t.value}
              onClick={() => setStatus(t.value)}
              className={cn(
                "rounded px-3 py-1.5 text-sm",
                status === t.value ? "bg-secondary font-medium" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="relative sm:w-72">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            aria-label="Search projects"
            placeholder="Search by name or domain"
            className="pl-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {projects.isPending ? (
        <LoadingRows />
      ) : projects.isError ? (
        <ErrorState error={projects.error} onRetry={() => projects.refetch()} />
      ) : projects.data.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title={q ? "No projects match your search" : status === "active" ? "No projects yet" : "No archived projects"}
          description={
            status === "active" && !q
              ? "Create a project, then add its modules, members and documents. Its knowledge stays separate from every other project."
              : undefined
          }
          action={
            status === "active" && !q ? (
              <Button onClick={() => setCreating(true)}>
                <Plus />
                Create your first project
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Name</TH>
              <TH className="hidden md:table-cell">Platform</TH>
              <TH className="hidden lg:table-cell">Members</TH>
              <TH className="hidden lg:table-cell">Documents</TH>
              <TH>Your role</TH>
              <TH className="hidden sm:table-cell">Updated</TH>
            </TR>
          </THead>
          <TBody>
            {projects.data.map((p) => (
              <TR key={p.id}>
                <TD>
                  <Link href={`/projects/${p.id}`} className="font-medium hover:underline">
                    {p.name}
                  </Link>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {p.business_domain}
                    {p.status === "archived" && <ProjectStatusBadge status={p.status} />}
                  </div>
                </TD>
                <TD className="hidden md:table-cell">{PLATFORM_LABELS[p.platform]}</TD>
                <TD className="hidden tabular-nums lg:table-cell">{p.stats.members}</TD>
                <TD className="hidden tabular-nums lg:table-cell">{p.stats.documents}</TD>
                <TD>
                  <RoleBadge role={p.my_role} />
                </TD>
                <TD className="hidden text-muted-foreground sm:table-cell">{timeAgo(p.updated_at)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent wide>
          <DialogHeader>
            <DialogTitle>New project</DialogTitle>
            <DialogDescription>You become the project owner. You can invite members afterwards.</DialogDescription>
          </DialogHeader>
          <ProjectForm
            submitLabel="Create project"
            onSubmit={async (input) => {
              await create.mutateAsync(input);
              setCreating(false);
            }}
            onCancel={() => setCreating(false)}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <ProjectsPage />
    </Suspense>
  );
}
