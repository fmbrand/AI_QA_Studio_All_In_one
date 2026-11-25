"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, FileText, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { OriginBadge, PriorityBadge, RequirementStatusBadge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/form";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { api, ApiError, errorMessage } from "@/lib/api";
import { keys, useRequirement, useRequirementDiff } from "@/lib/queries";
import type { Module, RequirementDetail, RequirementInput } from "@/lib/types";
import { cn, formatDateTime, sourceLocation } from "@/lib/utils";

import { RequirementForm } from "./requirement-form";

interface Props {
  projectId: string;
  requirementId: string | null;
  modules: Module[];
  canEdit: boolean;
  onClose: () => void;
}

function VersionHistory({ projectId, req }: { projectId: string; req: RequirementDetail }) {
  const [selected, setSelected] = useState<number | null>(null);
  const diff = useRequirementDiff(projectId, req.id, selected ? selected - 1 : null, selected);
  return (
    <section aria-label="Version history" className="grid gap-2">
      <h3 className="text-sm font-semibold">History</h3>
      <ol className="divide-y rounded-md border text-sm">
        {req.versions.map((v) => (
          <li key={v.id} className="px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs">v{v.version}</span>
              <OriginBadge origin={v.origin} confidence={v.confidence} />
              {req.approved_version_no === v.version && <span className="text-xs text-success">approved</span>}
              <span className="text-xs text-muted-foreground">{formatDateTime(v.created_at)}</span>
              {v.version > 1 && (
                <Button
                  variant="link"
                  size="sm"
                  className="ml-auto h-auto p-0"
                  onClick={() => setSelected(selected === v.version ? null : v.version)}
                  aria-expanded={selected === v.version}
                >
                  {selected === v.version ? "Hide changes" : `Compare with v${v.version - 1}`}
                </Button>
              )}
            </div>
            {v.change_reason && <p className="mt-1 text-xs text-muted-foreground">Reason: {v.change_reason}</p>}
            {selected === v.version && (
              <div className="mt-2 grid gap-2">
                {diff.isPending ? (
                  <Skeleton className="h-16" />
                ) : diff.data ? (
                  <>
                    <ul className="grid gap-1 text-xs">
                      {diff.data.changes
                        .filter((c) => c.field !== "description")
                        .map((c) => (
                          <li key={c.field}>
                            <span className="font-medium">{c.field}</span>:{" "}
                            <del className="text-destructive">{JSON.stringify(c.before)}</del> →{" "}
                            <ins className="text-success no-underline">{JSON.stringify(c.after)}</ins>
                          </li>
                        ))}
                    </ul>
                    {diff.data.description_diff.length > 0 && (
                      <pre className="overflow-auto rounded-md border bg-muted/40 p-2 font-mono text-xs">
                        {diff.data.description_diff.slice(2).map((line, i) => (
                          <span
                            key={i}
                            className={cn(
                              "block",
                              line.startsWith("+") && "text-success",
                              line.startsWith("-") && "text-destructive",
                            )}
                          >
                            {line}
                          </span>
                        ))}
                      </pre>
                    )}
                  </>
                ) : null}
              </div>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

export function RequirementDialog({ projectId, requirementId, modules, canEdit, onClose }: Props) {
  const queryClient = useQueryClient();
  const req = useRequirement(projectId, requirementId);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["project", projectId, "requirements"] });
    queryClient.invalidateQueries({ queryKey: keys.requirement(projectId, requirementId ?? "") });
    queryClient.invalidateQueries({ queryKey: keys.dashboard });
  };

  const review = useMutation({
    mutationFn: (action: "approve" | "reject") =>
      api.post(`/projects/${projectId}/requirements/${requirementId}/${action}`, action === "reject" ? { reason: reason || null } : undefined),
    onSuccess: (_, action) => {
      refresh();
      setRejecting(false);
      setReason("");
      toast.success(action === "approve" ? "Requirement approved" : "Requirement rejected");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const save = async (input: RequirementInput, changeReason: string | null) => {
    const r = req.data!;
    const body: Record<string, unknown> = { ...input, change_reason: changeReason };
    if (input.module_id === null) {
      delete body.module_id;
      body.clear_module = true;
    }
    try {
      await api.patch(`/projects/${projectId}/requirements/${r.id}`, body, r.current_version_no);
    } catch (err) {
      if (err instanceof ApiError && err.code === "version_conflict") {
        refresh();
        throw new ApiError(412, err.code, "Someone else edited this requirement. The latest version is loaded; apply your edit again.");
      }
      throw err;
    }
    refresh();
    toast.success(r.status === "approved" ? "Saved as a new draft version; it needs approval again" : "Saved as a new version");
  };

  const r = req.data;
  return (
    <Dialog
      open={!!requirementId}
      onOpenChange={(o) => {
        if (!o) {
          setRejecting(false);
          onClose();
        }
      }}
    >
      <DialogContent wide>
        {req.isPending ? (
          <div className="grid gap-3">
            <DialogTitle className="sr-only">Loading requirement</DialogTitle>
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="h-48" />
          </div>
        ) : req.isError || !r ? (
          <>
            <DialogTitle className="sr-only">Requirement</DialogTitle>
            <ErrorState error={req.error} onRetry={() => req.refetch()} />
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-base">{r.key}</span>
                <RequirementStatusBadge status={r.status} />
                <PriorityBadge priority={r.current.priority} />
                <OriginBadge origin={r.current.origin} confidence={r.current.confidence} />
              </DialogTitle>
              <DialogDescription>
                Version {r.current_version_no}
                {r.approved_version_no && r.approved_version_no !== r.current_version_no &&
                  ` · v${r.approved_version_no} is the last approved version`}
              </DialogDescription>
            </DialogHeader>

            {r.possible_duplicate_key && (
              <p className="flex items-center gap-2 rounded-md border border-warning/50 bg-warning/10 px-3 py-2 text-sm">
                <AlertTriangle className="size-4 shrink-0" />
                This looks very similar to {r.possible_duplicate_key}. Compare them before approving.
              </p>
            )}
            {r.status === "rejected" && r.rejection_reason && (
              <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm">Rejected: {r.rejection_reason}</p>
            )}

            {canEdit && (
              <div className="flex flex-wrap gap-2">
                {r.status !== "approved" && (
                  <Button size="sm" loading={review.isPending && review.variables === "approve"} onClick={() => review.mutate("approve")}>
                    <Check />
                    Approve v{r.current_version_no}
                  </Button>
                )}
                {r.status !== "rejected" && !rejecting && (
                  <Button size="sm" variant="outline" onClick={() => setRejecting(true)}>
                    <X />
                    Reject
                  </Button>
                )}
              </div>
            )}
            {rejecting && (
              <form
                className="flex flex-col gap-2 sm:flex-row sm:items-end"
                onSubmit={(e) => {
                  e.preventDefault();
                  review.mutate("reject");
                }}
              >
                <Field label="Reason (optional)" htmlFor="reject-reason" className="flex-1">
                  <Input id="reject-reason" maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
                </Field>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={() => setRejecting(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="destructive" size="sm" loading={review.isPending}>
                    Reject
                  </Button>
                </div>
              </form>
            )}

            <RequirementForm
              key={`${r.id}-${r.current_version_no}`}
              version={r.current}
              modules={modules}
              disabled={!canEdit}
              askReason
              submitLabel="Save as new version"
              onSubmit={save}
            />

            <section aria-label="Sources" className="grid gap-2">
              <h3 className="text-sm font-semibold">Sources</h3>
              {r.current.source_refs.length === 0 ? (
                <p className="text-sm text-muted-foreground">Added manually; no document source.</p>
              ) : (
                <ul className="grid gap-2">
                  {r.current.source_refs.map((s, i) => (
                    <li key={`${s.chunk_id}-${i}`} className="rounded-md border p-3 text-sm">
                      <p className="mb-1 flex items-center gap-1 text-xs text-muted-foreground">
                        <FileText className="size-3" />
                        {s.document_title}
                        {sourceLocation(s) && ` · ${sourceLocation(s)}`} · characters {s.char_start}–{s.char_end}
                      </p>
                      <blockquote className="border-l-2 border-primary/50 pl-3 italic">{s.quote}</blockquote>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <VersionHistory projectId={projectId} req={r} />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
