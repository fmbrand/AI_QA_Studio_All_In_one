"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ClipboardList, Loader2, Plus, Search, Sparkles, X } from "lucide-react";
import { useDeferredValue, useEffect, useState } from "react";
import { toast } from "sonner";

import { useCurrentProject } from "@/components/project/project-context";
import { ExtractDialog } from "@/components/requirements/extract-dialog";
import { RequirementDialog } from "@/components/requirements/requirement-dialog";
import { RequirementForm } from "@/components/requirements/requirement-form";
import { OriginBadge, PriorityBadge, RequirementStatusBadge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/form";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api, errorMessage } from "@/lib/api";
import { keys, useAIStatus, useJob, useJobs, useModules, useRequirements } from "@/lib/queries";
import type { ExtractionResult, Job, RequirementDetail } from "@/lib/types";
import { PRIORITY_LABELS, REQUIREMENT_STATUS_LABELS, REQUIREMENT_TYPE_LABELS, timeAgo } from "@/lib/utils";

const EXTRACTION = "requirement_extraction";

function ExtractionPanel({ projectId, jobId, onDismiss }: { projectId: string; jobId: string; onDismiss: () => void }) {
  const queryClient = useQueryClient();
  const job = useJob(jobId);
  const status = job.data?.status;
  useEffect(() => {
    if (status === "succeeded") {
      queryClient.invalidateQueries({ queryKey: ["project", projectId, "requirements"] });
      queryClient.invalidateQueries({ queryKey: keys.dashboard });
    }
  }, [status, projectId, queryClient]);
  if (!job.data) return null;
  const j = job.data;
  const result = j.result as unknown as ExtractionResult | null;
  return (
    <Card className="mb-4" role="status" aria-live="polite">
      <CardContent className="grid gap-2 p-4 text-sm">
        <div className="flex items-start justify-between gap-2">
          <p className="flex items-center gap-2 font-medium">
            {j.status === "queued" || j.status === "running" ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Extracting requirements… {j.stage ?? ""} ({j.progress}%)
              </>
            ) : j.status === "succeeded" ? (
              <>
                <Sparkles className="size-4 text-primary" />
                {result?.created ?? 0} draft requirement{result?.created === 1 ? "" : "s"} ready for review
              </>
            ) : (
              <>
                <AlertTriangle className="size-4 text-destructive" />
                Extraction {j.status}
              </>
            )}
          </p>
          {!["queued", "running"].includes(j.status) && (
            <Button variant="ghost" size="icon" aria-label="Dismiss" onClick={onDismiss}>
              <X />
            </Button>
          )}
        </div>
        {j.status === "queued" && j.attempts === 0 && (
          <p className="text-xs text-muted-foreground">Waiting for the worker. Make sure it is running.</p>
        )}
        {j.error && <p className="text-destructive">{j.error}</p>}
        {result && (
          <>
            <p className="text-xs text-muted-foreground">
              {result.discarded_uncited > 0 && `${result.discarded_uncited} discarded because their citations did not match the source. `}
              {result.merged_duplicates > 0 && `${result.merged_duplicates} merged as repeats. `}
              {result.possible_duplicates > 0 && `${result.possible_duplicates} flagged as possible duplicates of existing requirements. `}
              {result.model_calls} model call{result.model_calls === 1 ? "" : "s"}.
            </p>
            {result.open_questions.length > 0 && (
              <details>
                <summary className="cursor-pointer text-sm font-medium">
                  {result.open_questions.length} open question{result.open_questions.length === 1 ? "" : "s"} to clarify
                </summary>
                <ul className="mt-2 list-disc pl-5 text-sm">
                  {result.open_questions.map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </details>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default function RequirementsPage() {
  const { project, canEdit } = useCurrentProject();
  const queryClient = useQueryClient();
  const modules = useModules(project.id);
  const ai = useAIStatus();
  const jobs = useJobs(project.id);
  const [filters, setFilters] = useState({ status: "", type: "", priority: "", module_id: "" });
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const reqs = useRequirements(project.id, {
    status: filters.status || undefined,
    type: filters.type || undefined,
    priority: filters.priority || undefined,
    module_id: filters.module_id || undefined,
    q: q || undefined,
  });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [openId, setOpenId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [startedJob, setStartedJob] = useState<string | null>(null);
  const latest = jobs.data?.find((j) => j.kind === EXTRACTION);
  const panelJob = startedJob ?? latest?.id ?? null;
  const moduleName = (id: string | null) => modules.data?.find((m) => m.id === id)?.name;
  const filtered = Object.values(filters).some(Boolean) || !!q;
  const aiReady = ai.data?.llm.configured ?? false;

  const bulk = useMutation({
    mutationFn: (status: "approved" | "rejected") =>
      api.post<{ changed: string[] }>(`/projects/${project.id}/requirements/bulk-status`, {
        requirement_ids: [...selected],
        status,
      }),
    onSuccess: (res, status) => {
      setSelected(new Set());
      queryClient.invalidateQueries({ queryKey: ["project", project.id, "requirements"] });
      queryClient.invalidateQueries({ queryKey: keys.dashboard });
      toast.success(`${res.changed.length} requirement(s) ${status}`);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const setFilter = (key: keyof typeof filters) => (e: React.ChangeEvent<HTMLSelectElement>) =>
    setFilters((f) => ({ ...f, [key]: e.target.value }));
  const rows = reqs.data ?? [];
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));

  return (
    <>
      {ai.data && !aiReady && canEdit && (
        <p className="mb-4 rounded-md border px-3 py-2 text-sm text-muted-foreground">
          AI extraction is off because no language model is configured. You can still add and review requirements
          by hand. An administrator can enable it with <code className="font-mono">LLM_PROVIDER</code> in the backend
          settings.
        </p>
      )}
      {panelJob && panelJob !== dismissed && (
        <ExtractionPanel
          projectId={project.id}
          jobId={panelJob}
          onDismiss={() => {
            setDismissed(panelJob);
            setStartedJob(null);
          }}
        />
      )}

      <div className="mb-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              aria-label="Search requirements"
              placeholder="Search key, title or text"
              className="pl-8 sm:w-56"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Select aria-label="Filter by status" className="sm:w-36" value={filters.status} onChange={setFilter("status")}>
            <option value="">All statuses</option>
            {Object.entries(REQUIREMENT_STATUS_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by type" className="sm:w-40" value={filters.type} onChange={setFilter("type")}>
            <option value="">All types</option>
            {Object.entries(REQUIREMENT_TYPE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by priority" className="sm:w-36" value={filters.priority} onChange={setFilter("priority")}>
            <option value="">All priorities</option>
            {Object.entries(PRIORITY_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by module" className="sm:w-40" value={filters.module_id} onChange={setFilter("module_id")}>
            <option value="">All modules</option>
            {modules.data?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </Select>
        </div>
        {canEdit && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setCreating(true)}>
              <Plus />
              Add requirement
            </Button>
            <Button
              onClick={() => setExtracting(true)}
              disabled={!aiReady}
              title={aiReady ? undefined : "No language model is configured"}
            >
              <Sparkles />
              Extract with AI
            </Button>
          </div>
        )}
      </div>

      {canEdit && selected.size > 0 && (
        <div className="mb-3 flex items-center gap-2 rounded-md border bg-muted/40 px-3 py-2 text-sm">
          <span>{selected.size} selected</span>
          <Button size="sm" loading={bulk.isPending && bulk.variables === "approved"} onClick={() => bulk.mutate("approved")}>
            Approve
          </Button>
          <Button size="sm" variant="outline" loading={bulk.isPending && bulk.variables === "rejected"} onClick={() => bulk.mutate("rejected")}>
            Reject
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </div>
      )}

      {reqs.isPending ? (
        <LoadingRows />
      ) : reqs.isError ? (
        <ErrorState error={reqs.error} onRetry={() => reqs.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title={filtered ? "No requirements match these filters" : "No requirements yet"}
          description={
            filtered
              ? undefined
              : "Extract them from uploaded documents with AI, or add them by hand. Every requirement gets a stable REQ ID and a version history."
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              {canEdit && (
                <TH className="w-8">
                  <input
                    type="checkbox"
                    aria-label="Select all"
                    checked={allSelected}
                    onChange={(e) => setSelected(e.target.checked ? new Set(rows.map((r) => r.id)) : new Set())}
                  />
                </TH>
              )}
              <TH className="w-24">Key</TH>
              <TH>Requirement</TH>
              <TH className="hidden lg:table-cell">Type</TH>
              <TH className="hidden md:table-cell">Priority</TH>
              <TH>Status</TH>
              <TH className="hidden xl:table-cell">Origin</TH>
            </TR>
          </THead>
          <TBody>
            {rows.map((r) => (
              <TR key={r.id}>
                {canEdit && (
                  <TD>
                    <input
                      type="checkbox"
                      aria-label={`Select ${r.key}`}
                      checked={selected.has(r.id)}
                      onChange={(e) =>
                        setSelected((s) => {
                          const next = new Set(s);
                          if (e.target.checked) next.add(r.id);
                          else next.delete(r.id);
                          return next;
                        })
                      }
                    />
                  </TD>
                )}
                <TD className="font-mono text-xs">{r.key}</TD>
                <TD className="max-w-md">
                  <button className="block max-w-full text-left font-medium hover:underline" onClick={() => setOpenId(r.id)}>
                    {r.current.title}
                  </button>
                  <span className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                    {moduleName(r.current.module_id) ?? "No module"}
                    {r.current_version_no > 1 && <span>v{r.current_version_no}</span>}
                    {r.possible_duplicate_key && (
                      <span className="text-warning-foreground inline-flex items-center gap-1">
                        <AlertTriangle className="size-3" />
                        similar to {r.possible_duplicate_key}
                      </span>
                    )}
                    <span>{timeAgo(r.updated_at)}</span>
                  </span>
                </TD>
                <TD className="hidden lg:table-cell">{REQUIREMENT_TYPE_LABELS[r.current.type]}</TD>
                <TD className="hidden md:table-cell">
                  <PriorityBadge priority={r.current.priority} />
                </TD>
                <TD>
                  <RequirementStatusBadge status={r.status} />
                </TD>
                <TD className="hidden xl:table-cell">
                  <OriginBadge origin={r.current.origin} confidence={r.current.confidence} />
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent wide>
          <DialogHeader>
            <DialogTitle>Add requirement</DialogTitle>
            <DialogDescription>It gets the next REQ ID and starts as a draft.</DialogDescription>
          </DialogHeader>
          <RequirementForm
            modules={modules.data ?? []}
            submitLabel="Add requirement"
            onCancel={() => setCreating(false)}
            onSubmit={async (input) => {
              const created = await api.post<RequirementDetail>(`/projects/${project.id}/requirements`, input);
              queryClient.invalidateQueries({ queryKey: ["project", project.id, "requirements"] });
              queryClient.invalidateQueries({ queryKey: keys.dashboard });
              toast.success(`Added ${created.key}`);
              setCreating(false);
            }}
          />
        </DialogContent>
      </Dialog>
      <ExtractDialog
        projectId={project.id}
        open={extracting}
        onOpenChange={setExtracting}
        onStarted={(job: Job) => {
          setDismissed(null);
          setStartedJob(job.id);
        }}
      />
      <RequirementDialog
        projectId={project.id}
        requirementId={openId}
        modules={modules.data ?? []}
        canEdit={canEdit}
        onClose={() => setOpenId(null)}
      />
    </>
  );
}
