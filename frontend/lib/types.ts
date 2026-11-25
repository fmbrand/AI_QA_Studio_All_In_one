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
  index: DocumentIndex | null;
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
    requirements: number;
    approved_requirements: number;
  };
  recent_activity: Activity[];
  recent_jobs: Job[];
}

// ---- Phase 2: context engine and requirements -------------------------------------------------

export type RequirementType =
  | "functional"
  | "non_functional"
  | "business_rule"
  | "user_role"
  | "permission"
  | "validation"
  | "dependency"
  | "workflow"
  | "acceptance_criteria"
  | "constraint";
export type Priority = "critical" | "high" | "medium" | "low";
export type RequirementStatus = "draft" | "approved" | "rejected";

export interface SourceRef {
  document_id: string;
  document_version_id: string;
  document_title: string;
  chunk_id: string | null;
  page: number | null;
  sheet: string | null;
  char_start: number;
  char_end: number;
  quote: string;
}

export interface RequirementVersion {
  id: string;
  version: number;
  type: RequirementType;
  title: string;
  description: string;
  module_id: string | null;
  feature: string | null;
  user_role: string | null;
  priority: Priority;
  acceptance_criteria: string[];
  source_refs: SourceRef[];
  origin: "ai" | "manual" | "edit";
  confidence: "high" | "medium" | "low" | null;
  change_reason: string | null;
  created_by: string;
  created_at: string;
}

export interface Requirement {
  id: string;
  project_id: string;
  key: string;
  status: RequirementStatus;
  current_version_no: number;
  approved_version_no: number | null;
  possible_duplicate_of: string | null;
  possible_duplicate_key: string | null;
  rejection_reason: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
  current: RequirementVersion;
}

export interface RequirementDetail extends Requirement {
  versions: RequirementVersion[];
}

export interface RequirementInput {
  type: RequirementType;
  title: string;
  description: string;
  module_id: string | null;
  feature: string | null;
  user_role: string | null;
  priority: Priority;
  acceptance_criteria: string[];
}

export interface RequirementDiff {
  from_version: number;
  to_version: number;
  changes: { field: string; before: unknown; after: unknown }[];
  description_diff: string[];
}

export interface ContextHit {
  chunk_id: string;
  document_id: string;
  document_version_id: string;
  document_title: string;
  document_version: number;
  module_id: string | null;
  page: number | null;
  sheet: string | null;
  char_start: number;
  char_end: number;
  content: string;
  score: number;
  similarity: number | null;
  lexical_rank: number | null;
}

export interface AIStatus {
  llm: { configured: boolean; provider: string; model: string };
  embeddings: { provider: string; model: string; dimensions: number };
  ocr: { available: boolean; languages: string };
}

export interface DocumentIndex {
  chunk_count: number;
  char_count: number;
  warnings: string[];
  ocr_pages: number[];
  pages: number | null;
}

export interface ExtractionResult {
  created: number;
  keys: string[];
  discarded_uncited: number;
  dropped_citations: number;
  merged_duplicates: number;
  possible_duplicates: number;
  open_questions: string[];
  model_calls: number;
  windows: number;
}
