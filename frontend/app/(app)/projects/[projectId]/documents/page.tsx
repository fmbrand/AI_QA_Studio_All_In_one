"use client";

import { FileText, Search, Upload } from "lucide-react";
import { useDeferredValue, useState } from "react";

import { DocumentDialog } from "@/components/documents/document-dialog";
import { UploadDialog } from "@/components/documents/upload-dialog";
import { useCurrentProject } from "@/components/project/project-context";
import { ProcessingBadge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/form";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useDocuments, useModules } from "@/lib/queries";
import { formatBytes, KIND_LABELS, timeAgo } from "@/lib/utils";

export default function DocumentsPage() {
  const { project, canEdit } = useCurrentProject();
  const modules = useModules(project.id);
  const [kind, setKind] = useState("");
  const [moduleId, setModuleId] = useState("");
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const docs = useDocuments(project.id, { kind: kind || undefined, module_id: moduleId || undefined, q: q || undefined });
  const [uploading, setUploading] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const moduleName = (id: string | null) => modules.data?.find((m) => m.id === id)?.name;
  const filtered = !!(kind || moduleId || q);

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              aria-label="Search documents"
              placeholder="Search title or file name"
              className="pl-8 sm:w-64"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Select aria-label="Filter by type" className="sm:w-44" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">All types</option>
            {Object.entries(KIND_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Filter by module"
            className="sm:w-44"
            value={moduleId}
            onChange={(e) => setModuleId(e.target.value)}
          >
            <option value="">All modules</option>
            {modules.data?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </Select>
        </div>
        {canEdit && (
          <Button onClick={() => setUploading(true)}>
            <Upload />
            Upload documents
          </Button>
        )}
      </div>

      {docs.isPending ? (
        <LoadingRows />
      ) : docs.isError ? (
        <ErrorState error={docs.error} onRetry={() => docs.refetch()} />
      ) : docs.data.length === 0 ? (
        <EmptyState
          icon={FileText}
          title={filtered ? "No documents match these filters" : "No documents yet"}
          description={
            filtered
              ? undefined
              : "Upload requirements, business rules, API documentation or screenshots. They stay inside this project."
          }
          action={
            canEdit && !filtered ? (
              <Button onClick={() => setUploading(true)}>
                <Upload />
                Upload documents
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Title</TH>
              <TH className="hidden md:table-cell">Type</TH>
              <TH className="hidden lg:table-cell">Module</TH>
              <TH>Status</TH>
              <TH className="hidden sm:table-cell">Size</TH>
              <TH className="hidden md:table-cell">Updated</TH>
            </TR>
          </THead>
          <TBody>
            {docs.data.map((d) => (
              <TR key={d.id}>
                <TD className="max-w-xs">
                  <button className="block max-w-full truncate text-left font-medium hover:underline" onClick={() => setOpenId(d.id)}>
                    {d.title}
                  </button>
                  <span className="block truncate text-xs text-muted-foreground">
                    {d.current_version?.filename}
                    {d.version_count > 1 && ` · v${d.current_version?.version}`}
                  </span>
                </TD>
                <TD className="hidden md:table-cell">{KIND_LABELS[d.kind]}</TD>
                <TD className="hidden lg:table-cell">{moduleName(d.module_id) ?? <span className="text-muted-foreground">—</span>}</TD>
                <TD>{d.current_version && <ProcessingBadge status={d.current_version.processing_status} />}</TD>
                <TD className="hidden tabular-nums sm:table-cell">
                  {d.current_version ? formatBytes(d.current_version.size_bytes) : "—"}
                </TD>
                <TD className="hidden text-muted-foreground md:table-cell">{timeAgo(d.updated_at)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <UploadDialog projectId={project.id} modules={modules.data ?? []} open={uploading} onOpenChange={setUploading} />
      <DocumentDialog
        projectId={project.id}
        documentId={openId}
        modules={modules.data ?? []}
        canEdit={canEdit}
        onClose={() => setOpenId(null)}
      />
    </>
  );
}
