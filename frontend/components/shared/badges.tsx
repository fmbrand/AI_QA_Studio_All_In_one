import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { JobStatus, ProcessingStatus, ProjectStatus, RoleKey } from "@/lib/types";
import { PROCESSING_LABELS, ROLE_LABELS } from "@/lib/utils";

const PROCESSING_VARIANT: Record<ProcessingStatus, BadgeProps["variant"]> = {
  queued: "outline",
  processing: "primary",
  processed: "success",
  stored: "default",
  failed: "destructive",
};

export function ProcessingBadge({ status }: { status: ProcessingStatus }) {
  return <Badge variant={PROCESSING_VARIANT[status]}>{PROCESSING_LABELS[status]}</Badge>;
}

const JOB_VARIANT: Record<JobStatus, BadgeProps["variant"]> = {
  queued: "outline",
  running: "primary",
  succeeded: "success",
  failed: "destructive",
  cancelled: "default",
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return <Badge variant={JOB_VARIANT[status]}>{status[0].toUpperCase() + status.slice(1)}</Badge>;
}

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  return status === "archived" ? <Badge variant="warning">Archived</Badge> : <Badge variant="success">Active</Badge>;
}

export function RoleBadge({ role }: { role: RoleKey }) {
  return <Badge variant={role === "owner" || role === "admin" ? "primary" : "default"}>{ROLE_LABELS[role]}</Badge>;
}
