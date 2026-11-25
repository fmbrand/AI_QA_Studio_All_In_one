import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { JobStatus, Priority, ProcessingStatus, ProjectStatus, RequirementStatus, RoleKey } from "@/lib/types";
import { PRIORITY_LABELS, PROCESSING_LABELS, REQUIREMENT_STATUS_LABELS, ROLE_LABELS } from "@/lib/utils";

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

const REQ_STATUS_VARIANT: Record<RequirementStatus, BadgeProps["variant"]> = {
  draft: "outline",
  approved: "success",
  rejected: "destructive",
};

export function RequirementStatusBadge({ status }: { status: RequirementStatus }) {
  return <Badge variant={REQ_STATUS_VARIANT[status]}>{REQUIREMENT_STATUS_LABELS[status]}</Badge>;
}

const PRIORITY_VARIANT: Record<Priority, BadgeProps["variant"]> = {
  critical: "destructive",
  high: "warning",
  medium: "default",
  low: "outline",
};

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <Badge variant={PRIORITY_VARIANT[priority]}>{PRIORITY_LABELS[priority]}</Badge>;
}

export function OriginBadge({ origin, confidence }: { origin: string; confidence: string | null }) {
  if (origin !== "ai") return <Badge variant="outline">{origin === "manual" ? "Manual" : "Edited"}</Badge>;
  return (
    <Badge variant="primary" title="Extracted by AI; review before approving">
      AI{confidence ? ` · ${confidence} confidence` : ""}
    </Badge>
  );
}
