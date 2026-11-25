"use client";

import { useMutation } from "@tanstack/react-query";
import { FileText, Search } from "lucide-react";
import { useState } from "react";

import { useCurrentProject } from "@/components/project/project-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useModules } from "@/lib/queries";
import type { ContextHit } from "@/lib/types";
import { sourceLocation } from "@/lib/utils";

/** Highlight the query's words inside a passage, safely (no HTML injection). */
function Highlighted({ text, query }: { text: string; query: string }) {
  // Skip short filler words ("can", "the") so the highlight shows the meaningful matches.
  const words = query.toLowerCase().split(/\W+/).filter((w) => w.length > 3);
  if (!words.length) return <>{text}</>;
  const pattern = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return (
    <>
      {text.split(pattern).map((part, i) =>
        words.includes(part.toLowerCase()) ? (
          <mark key={i} className="rounded bg-warning/30 px-0.5 text-foreground">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

export default function KnowledgePage() {
  const { project } = useCurrentProject();
  const modules = useModules(project.id);
  const [query, setQuery] = useState("");
  const [moduleId, setModuleId] = useState("");
  const [searched, setSearched] = useState("");
  const search = useMutation({
    mutationFn: () =>
      api.post<ContextHit[]>(`/projects/${project.id}/context/search`, {
        query: query.trim(),
        module_ids: moduleId ? [moduleId] : [],
        k: 10,
      }),
  });

  return (
    <div className="grid gap-4">
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim()) {
            setSearched(query.trim());
            search.mutate();
          }
        }}
      >
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            aria-label="Search project knowledge"
            placeholder="Ask about the project, e.g. “when can a coupon not be applied?”"
            className="pl-8"
            maxLength={1000}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Select aria-label="Limit to module" className="sm:w-48" value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
          <option value="">All modules</option>
          {modules.data?.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </Select>
        <Button type="submit" loading={search.isPending} disabled={!query.trim()}>
          Search
        </Button>
      </form>
      <p className="text-xs text-muted-foreground">
        Searches the indexed text of this project’s current documents by meaning and by keyword. A module filter also
        includes its connected modules and documents without a module.
      </p>

      {search.isPending ? (
        <LoadingRows rows={3} />
      ) : search.isError ? (
        <ErrorState error={search.error} onRetry={() => search.mutate()} />
      ) : search.data ? (
        search.data.length === 0 ? (
          <EmptyState icon={Search} title="Nothing found" description="Try other words, or upload more documents." />
        ) : (
          <ol className="grid gap-3" aria-label="Search results">
            {search.data.map((hit) => (
              <li key={hit.chunk_id}>
                <Card>
                  <CardContent className="grid gap-2 p-4">
                    <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                      <FileText className="size-3" />
                      <span className="font-medium text-foreground">{hit.document_title}</span>
                      <span>v{hit.document_version}</span>
                      {sourceLocation(hit) && <span>{sourceLocation(hit)}</span>}
                      {hit.similarity !== null && <span>similarity {hit.similarity.toFixed(2)}</span>}
                      {hit.lexical_rank !== null && <span>keyword match</span>}
                    </p>
                    <p className="whitespace-pre-wrap text-sm">
                      <Highlighted text={hit.content} query={searched} />
                    </p>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ol>
        )
      ) : (
        <EmptyState
          icon={Search}
          title="Search this project’s knowledge"
          description="Results come only from documents uploaded to this project."
        />
      )}
    </div>
  );
}
