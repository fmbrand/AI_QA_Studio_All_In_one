"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, Textarea } from "@/components/ui/form";
import { LoadingRows } from "@/components/ui/states";
import { api, errorMessage } from "@/lib/api";
import { keys, useDocuments } from "@/lib/queries";
import type { Job } from "@/lib/types";
import { KIND_LABELS } from "@/lib/utils";

interface Props {
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onStarted: (job: Job) => void;
}

export function ExtractDialog({ projectId, open, onOpenChange, onStarted }: Props) {
  const queryClient = useQueryClient();
  const docs = useDocuments(projectId);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [instructions, setInstructions] = useState("");
  // One key per dialog session: a double click or a retry cannot start (and bill) a second run.
  const idempotencyKey = useRef(crypto.randomUUID());
  const ready = (docs.data ?? []).filter((d) => d.current_version?.processing_status === "processed");
  const notReady = (docs.data ?? []).length - ready.length;

  const start = useMutation({
    mutationFn: () =>
      api.post<Job>(
        `/projects/${projectId}/requirements/extract`,
        { document_ids: [...selected], instructions: instructions.trim() || null },
        { "Idempotency-Key": idempotencyKey.current },
      ),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: keys.jobs(projectId) });
      onStarted(job);
      onOpenChange(false);
      setSelected(new Set());
      setInstructions("");
      idempotencyKey.current = crypto.randomUUID();
      toast.success("Extraction started. Results arrive as drafts for review.");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const toggle = (id: string, on: boolean) =>
    setSelected((s) => {
      const next = new Set(s);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Extract requirements with AI</DialogTitle>
          <DialogDescription>
            The model reads the selected documents and proposes requirements. Each one cites the exact text it came
            from; anything it cannot cite is discarded. Nothing is approved automatically.
          </DialogDescription>
        </DialogHeader>
        {docs.isPending ? (
          <LoadingRows rows={3} />
        ) : ready.length === 0 ? (
          <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
            No indexed documents yet.{" "}
            <Link href={`/projects/${projectId}/documents`} className="text-primary hover:underline">
              Upload documents
            </Link>{" "}
            first; they are indexed automatically.
          </p>
        ) : (
          <fieldset className="grid max-h-64 gap-2 overflow-y-auto">
            <legend className="mb-2 flex w-full items-center justify-between text-sm font-medium">
              Documents
              <button
                type="button"
                className="text-xs text-primary hover:underline"
                onClick={() => setSelected(selected.size === ready.length ? new Set() : new Set(ready.map((d) => d.id)))}
              >
                {selected.size === ready.length ? "Clear" : "Select all"}
              </button>
            </legend>
            {ready.map((d) => (
              <label key={d.id} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                <input type="checkbox" checked={selected.has(d.id)} onChange={(e) => toggle(d.id, e.target.checked)} />
                <span className="min-w-0 flex-1 truncate">{d.title}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{KIND_LABELS[d.kind]}</span>
              </label>
            ))}
            {notReady > 0 && (
              <p className="text-xs text-muted-foreground">
                {notReady} document(s) are not listed because they are still processing or have no readable text.
              </p>
            )}
          </fieldset>
        )}
        <Field label="Instructions (optional)" htmlFor="extract-instructions" hint="For example: focus on the provider role.">
          <Textarea
            id="extract-instructions"
            rows={2}
            maxLength={2000}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
          />
        </Field>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => start.mutate()} disabled={selected.size === 0} loading={start.isPending}>
            <Sparkles />
            Extract from {selected.size || ""} document{selected.size === 1 ? "" : "s"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
