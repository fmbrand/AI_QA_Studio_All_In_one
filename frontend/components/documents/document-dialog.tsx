"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, RefreshCw, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { ProcessingBadge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/form";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { api, ApiError, errorMessage } from "@/lib/api";
import { keys, useDocument, useExtractions } from "@/lib/queries";
import type { DocumentKind, Module } from "@/lib/types";
import { ACCEPTED_EXTENSIONS, formatBytes, formatDateTime, KIND_LABELS } from "@/lib/utils";

import { checkFile } from "./upload-dialog";

interface Props {
  projectId: string;
  documentId: string | null;
  modules: Module[];
  canEdit: boolean;
  onClose: () => void;
}

export async function downloadVersion(projectId: string, documentId: string, versionId: string) {
  const { url } = await api.get<{ url: string }>(
    `/projects/${projectId}/documents/${documentId}/versions/${versionId}/download-url`,
  );
  window.location.assign(url);
}

export function DocumentDialog({ projectId, documentId, modules, canEdit, onClose }: Props) {
  const queryClient = useQueryClient();
  const doc = useDocument(projectId, documentId);
  const extractions = useExtractions(projectId, documentId);
  const versionInput = useRef<HTMLInputElement>(null);
  const [edits, setEdits] = useState<{ title?: string; kind?: DocumentKind; module?: string }>({});

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    queryClient.invalidateQueries({ queryKey: keys.dashboard });
  };

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {};
      if (edits.title !== undefined) body.title = edits.title;
      if (edits.kind !== undefined) body.kind = edits.kind;
      if (edits.module !== undefined) {
        if (edits.module) body.module_id = edits.module;
        else body.clear_module = true;
      }
      return api.patch(`/projects/${projectId}/documents/${documentId}`, body);
    },
    onSuccess: () => {
      setEdits({});
      invalidate();
      toast.success("Document updated");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const addVersion = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload(`/projects/${projectId}/documents/${documentId}/versions`, form);
    },
    onSuccess: () => {
      invalidate();
      toast.success("New version uploaded");
    },
    onError: (err) =>
      toast.error(
        err instanceof ApiError && err.code === "duplicate_document"
          ? "That file is identical to an existing version"
          : errorMessage(err),
      ),
    onSettled: () => {
      if (versionInput.current) versionInput.current.value = "";
    },
  });

  const remove = useMutation({
    mutationFn: () => api.delete(`/projects/${projectId}/documents/${documentId}`),
    onSuccess: () => {
      invalidate();
      toast.success("Document deleted");
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const reprocess = useMutation({
    mutationFn: () => api.post(`/projects/${projectId}/documents/${documentId}/reprocess`),
    onSuccess: () => {
      invalidate();
      toast.success("Reprocessing started");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const d = doc.data;
  const latestText = extractions.data?.[0];
  const dirty = Object.keys(edits).length > 0;

  return (
    <Dialog
      open={!!documentId}
      onOpenChange={(o) => {
        if (!o) {
          setEdits({});
          onClose();
        }
      }}
    >
      <DialogContent wide>
        {doc.isPending ? (
          <div className="grid gap-3">
            <DialogTitle className="sr-only">Loading document</DialogTitle>
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="h-40" />
          </div>
        ) : doc.isError ? (
          <>
            <DialogTitle className="sr-only">Document</DialogTitle>
            <ErrorState error={doc.error} onRetry={() => doc.refetch()} />
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="break-words">{d!.title}</DialogTitle>
              <DialogDescription>
                {d!.version_count} version{d!.version_count === 1 ? "" : "s"} · added {formatDateTime(d!.created_at)}
              </DialogDescription>
            </DialogHeader>

            <section className="grid gap-4 sm:grid-cols-3" aria-label="Details">
              <Field label="Title" htmlFor="doc-title">
                <Input
                  id="doc-title"
                  disabled={!canEdit}
                  maxLength={200}
                  value={edits.title ?? d!.title}
                  onChange={(e) => setEdits((x) => ({ ...x, title: e.target.value }))}
                />
              </Field>
              <Field label="Type" htmlFor="doc-kind">
                <Select
                  id="doc-kind"
                  disabled={!canEdit}
                  value={edits.kind ?? d!.kind}
                  onChange={(e) => setEdits((x) => ({ ...x, kind: e.target.value as DocumentKind }))}
                >
                  {Object.entries(KIND_LABELS).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Module" htmlFor="doc-module">
                <Select
                  id="doc-module"
                  disabled={!canEdit}
                  value={edits.module ?? d!.module_id ?? ""}
                  onChange={(e) => setEdits((x) => ({ ...x, module: e.target.value }))}
                >
                  <option value="">No module</option>
                  {modules.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </section>
            {canEdit && dirty && (
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setEdits({})}>
                  Discard
                </Button>
                <Button size="sm" loading={save.isPending} onClick={() => save.mutate()}>
                  Save details
                </Button>
              </div>
            )}

            <section aria-label="Versions" className="grid gap-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">Versions</h3>
                {canEdit && (
                  <>
                    <input
                      ref={versionInput}
                      type="file"
                      className="sr-only"
                      id="version-input"
                      accept={ACCEPTED_EXTENSIONS.join(",")}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        const problem = checkFile(file);
                        if (problem) {
                          toast.error(problem);
                          e.target.value = "";
                          return;
                        }
                        addVersion.mutate(file);
                      }}
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      loading={addVersion.isPending}
                      onClick={() => versionInput.current?.click()}
                    >
                      <Upload />
                      Upload new version
                    </Button>
                  </>
                )}
              </div>
              <ul className="divide-y rounded-md border text-sm">
                {d!.versions.map((v) => (
                  <li key={v.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
                    <span className="font-mono text-xs">v{v.version}</span>
                    <span className="min-w-0 flex-1 truncate">{v.filename}</span>
                    <span className="text-xs text-muted-foreground">{formatBytes(v.size_bytes)}</span>
                    <ProcessingBadge status={v.processing_status} />
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Download version ${v.version}`}
                      onClick={() =>
                        downloadVersion(projectId, d!.id, v.id).catch((err) => toast.error(errorMessage(err)))
                      }
                    >
                      <Download />
                    </Button>
                    {v.processing_error && <p className="w-full text-xs text-destructive">{v.processing_error}</p>}
                  </li>
                ))}
              </ul>
            </section>

            <section aria-label="Extracted text" className="grid gap-2">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold">Extracted text</h3>
                {canEdit && ["processed", "stored", "failed"].includes(d!.current_version?.processing_status ?? "") && (
                  <Button size="sm" variant="ghost" loading={reprocess.isPending} onClick={() => reprocess.mutate()}>
                    <RefreshCw />
                    Reprocess
                  </Button>
                )}
              </div>
              {d!.index && (
                <p className="text-xs text-muted-foreground">
                  {d!.index.chunk_count} searchable passage{d!.index.chunk_count === 1 ? "" : "s"}
                  {d!.index.pages ? ` · ${d!.index.pages} page${d!.index.pages === 1 ? "" : "s"}` : ""}
                  {d!.index.ocr_pages.length > 0 && ` · OCR used on page ${d!.index.ocr_pages.join(", ")}`}
                </p>
              )}
              {d!.index?.warnings.map((w) => (
                <p key={w} className="rounded-md border border-warning/50 bg-warning/10 px-3 py-2 text-xs">
                  {w}
                </p>
              ))}
              {extractions.isPending ? (
                <Skeleton className="h-24" />
              ) : latestText?.text ? (
                <>
                  <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md border bg-muted/40 p-3 font-mono text-xs">
                    {latestText.text.slice(0, 20000)}
                  </pre>
                  <p className="text-xs text-muted-foreground">
                    {latestText.char_count.toLocaleString()} characters
                    {latestText.text.length > 20000 && " · preview shows the first 20,000"}
                  </p>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {d!.current_version?.processing_status === "stored"
                    ? "No text could be read from this file. Scanned pages and images need OCR (Tesseract) on the server; reprocess after it is installed."
                    : d!.current_version?.processing_status === "failed"
                      ? "Processing failed. Upload the file again as a new version, or reprocess it."
                      : "Processing… this updates automatically."}
                </p>
              )}
            </section>

            {canEdit && (
              <div className="flex justify-start border-t pt-4">
                <Button
                  variant="ghost"
                  className="text-destructive"
                  loading={remove.isPending}
                  onClick={() => {
                    if (window.confirm(`Delete “${d!.title}” and all its versions?`)) remove.mutate();
                  }}
                >
                  <Trash2 />
                  Delete document
                </Button>
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
