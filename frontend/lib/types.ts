// Types mirroring the backend API (see /api/openapi.json).

export type RoleKey = "owner" | "admin" | "qa_engineer" | "viewer";
export type Platform = "web" | "android" | "ios" | "api" | "multi_platform";
export type ProjectStatus = "active" | "archived";
export type DocumentKind =
  | "requirement"
  | "design"
  | "business_logic"
  | "api_spec"
  | "test_cases"
  | "screenshot"
  | "other";
export type ProcessingStatus = "queued" | "processing" | "processed" | "stored" | "failed";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface PageMeta {
  cursor: string | null;
  next_cursor: string | null;
  limit: number;
}

export interface Envelope<T> {
  data: T;
  meta: { request_id: string | null; page: PageMeta | null };
}

export interface User {
  id: string;
  email: string;
  name: string;
  is_superadmin: boolean;
  created_at: string;
}

export interface Membership {
  project_id: string;
  project_name: string;
  project_status: ProjectStatus;
  role: RoleKey;
}

export interface Me {
  user: User;
  memberships: Membership[];
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  project_type: string;
  application_url: string | null;
  platform: Platform;
  business_domain: string;
  tech_stack: string[];
  status: ProjectStatus;
  archived_at: string | null;
  version: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  my_role: RoleKey;
  stats: { members: number; modules: number; documents: number };
}

export interface ProjectInput {
  name: string;
  platform: Platform;
  description?: string;
  project_type?: string;
  application_url?: string | null;
  business_domain?: string;
  tech_stack?: string[];
}

export interface Member {
  user_id: string;
  email: string;
  name: string;
  role: RoleKey;
  added_at: string;
}

export interface Role {
  key: RoleKey;
  name: string;
  rank: number;
  description: string;
}

export interface Module {
  id: string;
  project_id: string;
  name: string;
  description: string;
  version: number;
  created_at: string;
  updated_at: string;
  connected_module_ids: string[];
}

export interface DocumentVersion {
  id: string;
  version: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  processing_status: ProcessingStatus;
  processing_error: string | null;
  uploaded_by: string;
  created_at: string;
}

export interface ProjectDocument {
  id: string;
  project_id: string;
  title: string;
  kind: DocumentKind;
  module_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  current_version: DocumentVersion | null;
  version_count: number;
}

export interface DocumentDetail extends ProjectDocument {
  versions: DocumentVersion[];
}

export interface Extraction {
  id: string;
  document_version_id: string;
  extractor: string;
  text: string;
  char_count: number;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface Job {
  id: string;
  project_id: string | null;
  kind: string;
  status: JobStatus;
  progress: number;
  stage: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Activity {
  id: string;
  project_id: string | null;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  created_at: string;
}

export interface Dashboard {
  totals: {
    projects: number;
    active_projects: number;
    archived_projects: number;
    documents: number;
    modules: number;
  };
  recent_activity: Activity[];
  recent_jobs: Job[];
}
