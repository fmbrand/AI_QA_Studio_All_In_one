"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { api } from "./api";
import type {
  Activity,
  Dashboard,
  DocumentDetail,
  Extraction,
  Job,
  Me,
  Member,
  Module,
  Project,
  ProjectDocument,
  ProjectStatus,
  Role,
} from "./types";

export const keys = {
  me: ["me"] as const,
  dashboard: ["dashboard"] as const,
  roles: ["roles"] as const,
  projects: (status?: ProjectStatus, q?: string) => ["projects", { status, q }] as const,
  project: (id: string) => ["project", id] as const,
  members: (id: string) => ["project", id, "members"] as const,
  modules: (id: string) => ["project", id, "modules"] as const,
  documents: (id: string, filters: Record<string, string | undefined> = {}) =>
    ["project", id, "documents", filters] as const,
  document: (id: string, docId: string) => ["project", id, "document", docId] as const,
  extractions: (id: string, docId: string) => ["project", id, "document", docId, "extractions"] as const,
  activity: (id: string) => ["project", id, "activity"] as const,
  jobs: (id: string) => ["project", id, "jobs"] as const,
};

function qs(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) search.set(k, v);
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const useMe = () => useQuery({ queryKey: keys.me, queryFn: ({ signal }) => api.get<Me>("/me", signal) });

export const useDashboard = () =>
  useQuery({ queryKey: keys.dashboard, queryFn: ({ signal }) => api.get<Dashboard>("/dashboard", signal) });

export const useRoles = () =>
  useQuery({ queryKey: keys.roles, queryFn: () => api.get<Role[]>("/roles"), staleTime: Infinity });

export const useProjects = (status?: ProjectStatus, q?: string) =>
  useQuery({
    queryKey: keys.projects(status, q),
    queryFn: ({ signal }) => api.get<Project[]>(`/projects${qs({ status, q, limit: "200" })}`, signal),
  });

export const useProject = (id: string) =>
  useQuery({ queryKey: keys.project(id), queryFn: ({ signal }) => api.get<Project>(`/projects/${id}`, signal) });

export const useMembers = (id: string) =>
  useQuery({
    queryKey: keys.members(id),
    queryFn: ({ signal }) => api.get<Member[]>(`/projects/${id}/members`, signal),
  });

export const useModules = (id: string) =>
  useQuery({
    queryKey: keys.modules(id),
    queryFn: ({ signal }) => api.get<Module[]>(`/projects/${id}/modules`, signal),
  });

const isProcessing = (docs: ProjectDocument[] | undefined) =>
  !!docs?.some((d) => d.current_version && ["queued", "processing"].includes(d.current_version.processing_status));

export const useDocuments = (id: string, filters: { kind?: string; module_id?: string; q?: string } = {}) =>
  useQuery({
    queryKey: keys.documents(id, filters),
    queryFn: ({ signal }) =>
      api.get<ProjectDocument[]>(`/projects/${id}/documents${qs({ ...filters, limit: "200" })}`, signal),
    // Poll while the worker is still processing an upload.
    refetchInterval: (query) => (isProcessing(query.state.data) ? 2000 : false),
  });

export const useDocument = (id: string, docId: string | null) =>
  useQuery({
    queryKey: keys.document(id, docId ?? ""),
    queryFn: ({ signal }) => api.get<DocumentDetail>(`/projects/${id}/documents/${docId}`, signal),
    enabled: !!docId,
    refetchInterval: (query) => (isProcessing(query.state.data ? [query.state.data] : undefined) ? 2000 : false),
  });

export const useExtractions = (id: string, docId: string | null) =>
  useQuery({
    queryKey: keys.extractions(id, docId ?? ""),
    queryFn: ({ signal }) => api.get<Extraction[]>(`/projects/${id}/documents/${docId}/extractions`, signal),
    enabled: !!docId,
  });

export const useJobs = (id: string) =>
  useQuery({
    queryKey: keys.jobs(id),
    queryFn: ({ signal }) => api.get<Job[]>(`/projects/${id}/jobs`, signal),
    refetchInterval: (query) =>
      query.state.data?.some((j) => j.status === "queued" || j.status === "running") ? 2000 : false,
  });

export const useActivity = (id: string) =>
  useInfiniteQuery({
    queryKey: keys.activity(id),
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => api.page<Activity[]>(`/projects/${id}/activity${qs({ cursor: pageParam, limit: "30" })}`),
    getNextPageParam: (last) => last.meta.page?.next_cursor ?? undefined,
  });
