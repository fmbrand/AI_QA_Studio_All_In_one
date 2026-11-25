"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileUp, XCircle } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/form";
import { api, ApiError, errorMessage } from "@/lib/api";
import { keys } from "@/lib/queries";
import type { DocumentKind, Module } from "@/lib/types";
import { ACCEPTED_EXTENSIONS, cn, fileExtension, formatBytes, KIND_LABELS } from "@/lib/utils";

export const MAX_UPLOAD_MB = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB ?? 25);

/** Client-side pre-check; the server re-validates type, content and size. */
export function checkFile(file: File, maxMb = MAX_UPLOAD_MB): string | null {
  if (!ACCEPTED_EXTENSIONS.includes(fileExtension(file.name))) {
    return `Unsupported type. Allowed: ${ACCEPTED_EXTENSIONS.join(", ")}`;
  }
  if (file.size === 0) return "The file is empty";
  if (file.size > maxMb * 1024 * 1024) return `Larger than ${maxMb} MB`;
  return null;
}

type Result = { name: string; ok: boolean; message: string };

interface UploadDialogProps {
  projectId: string;
  modules: Module[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadDialog({ projectId, modules, open, onOpenChange }: UploadDialogProps) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [kind, setKind] = useState<DocumentKind>("requirement");
  const [moduleId, setModuleId] = useState("");
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const [dragging, setDragging] = useState(false);

  const reset = () => {
    setFiles([]);
    setTitle("");
    setResults([]);
    if (inputRef.current) inputRef.current.value = "";
  };

  const pick = (list: FileList | null) => {
    setResults([]);
    setFiles(list ? Array.from(list) : []);
  };

  const invalid = files.map((f) => checkFile(f));
  const canUpload = files.length > 0 && invalid.every((e) => e === null) && !uploading;

  async function upload() {
    setUploading(true);
    const out: Result[] = [];
    // Sequential: preserves order (screenshots) and keeps duplicate detection deterministic.
    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      form.append("kind", kind);
      if (moduleId) form.append("module_id", moduleId);
      if (files.length === 1 && title.trim()) form.append("title", title.trim());
      try {
        await api.upload(`/projects/${projectId}/documents`, form);
        out.push({ name: file.name, ok: true, message: "Uploaded" });
      } catch (err) {
        const message =
          err instanceof ApiError && err.code === "duplicate_document"
            ? "Already in this project (identical file)"
            : errorMessage(err);
        out.push({ name: file.name, ok: false, message });
      }
    }
    setResults(out);
    setUploading(false);
    queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    queryClient.invalidateQueries({ queryKey: keys.dashboard });
    if (out.every((r) => r.ok)) {
      reset();
      onOpenChange(false);
    } else {
      setFiles([]);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload documents</DialogTitle>
          <DialogDescription>
            Requirements, business rules, API docs, existing test cases or screenshots. Up to {MAX_UPLOAD_MB} MB per file.
          </DialogDescription>
        </DialogHeader>
        <label
          htmlFor="upload-input"
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            pick(e.dataTransfer.files);
          }}
          className={cn(
            "flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-center text-sm",
            dragging ? "border-primary bg-primary/5" : "hover:bg-muted/50",
          )}
        >
          <FileUp className="size-6 text-muted-foreground" />
          <span className="font-medium">Drop files here or click to choose</span>
          <span className="text-xs text-muted-foreground">{ACCEPTED_EXTENSIONS.join(" ")}</span>
          <input
            ref={inputRef}
            id="upload-input"
            type="file"
            multiple
            accept={ACCEPTED_EXTENSIONS.join(",")}
            className="sr-only"
            onChange={(e) => pick(e.target.files)}
          />
        </label>
        {files.length > 0 && (
          <ul className="grid gap-1 text-sm" aria-label="Selected files">
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`} className="flex justify-between gap-2">
                <span className="truncate">{f.name}</span>
                <span className={cn("shrink-0 text-xs", invalid[i] ? "text-destructive" : "text-muted-foreground")}>
                  {invalid[i] ?? formatBytes(f.size)}
                </span>
              </li>
            ))}
          </ul>
        )}
        {results.length > 0 && (
          <ul className="grid gap-1 text-sm" aria-label="Upload results">
            {results.map((r, i) => (
              <li key={`${r.name}-${i}`} className="flex items-center gap-2">
                {r.ok ? <CheckCircle2 className="size-4 text-success" /> : <XCircle className="size-4 text-destructive" />}
                <span className="truncate">{r.name}</span>
                <span className="ml-auto shrink-0 text-xs text-muted-foreground">{r.message}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Document type" htmlFor="upload-kind">
            <Select id="upload-kind" value={kind} onChange={(e) => setKind(e.target.value as DocumentKind)}>
              {Object.entries(KIND_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Module" htmlFor="upload-module">
            <Select id="upload-module" value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
              <option value="">No module</option>
              {modules.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </Select>
          </Field>
          {files.length <= 1 && (
            <Field label="Title" htmlFor="upload-title" hint="Defaults to the file name" className="sm:col-span-2">
              <Input id="upload-title" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
            </Field>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button onClick={upload} disabled={!canUpload} loading={uploading}>
            Upload {files.length > 1 ? `${files.length} files` : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
