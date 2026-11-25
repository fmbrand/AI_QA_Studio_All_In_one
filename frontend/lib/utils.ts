import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type {
  DocumentKind,
  Platform,
  Priority,
  ProcessingStatus,
  RequirementStatus,
  RequirementType,
  RoleKey,
} from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const ROLE_LABELS: Record<RoleKey, string> = {
  owner: "Owner",
  admin: "Admin",
  qa_engineer: "QA Engineer",
  viewer: "Viewer",
};

export const ROLE_RANK: Record<RoleKey, number> = { viewer: 10, qa_engineer: 20, admin: 30, owner: 40 };

export function hasRole(role: RoleKey | undefined, min: RoleKey): boolean {
  return !!role && ROLE_RANK[role] >= ROLE_RANK[min];
}

export const PLATFORM_LABELS: Record<Platform, string> = {
  web: "Web application",
  android: "Android application",
  ios: "iOS application",
  api: "API / backend",
  multi_platform: "Multi-platform",
};

export const KIND_LABELS: Record<DocumentKind, string> = {
  requirement: "Requirement",
  design: "Design",
  business_logic: "Business logic",
  api_spec: "API documentation",
  test_cases: "Existing test cases",
  screenshot: "Screenshot",
  other: "Other",
};

export const PROCESSING_LABELS: Record<ProcessingStatus, string> = {
  queued: "Queued",
  processing: "Processing",
  processed: "Indexed",
  stored: "No text found",
  failed: "Failed",
};

export const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md", ".json", ".png", ".jpg", ".jpeg", ".webp"];

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timeAgo(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} d ago`;
  return formatDate(iso);
}

export function parseTechStack(value: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of value.split(",")) {
    const item = raw.trim();
    if (item && !seen.has(item.toLowerCase())) {
      seen.add(item.toLowerCase());
      out.push(item);
    }
  }
  return out;
}

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

export const REQUIREMENT_TYPE_LABELS: Record<RequirementType, string> = {
  functional: "Functional",
  non_functional: "Non-functional",
  business_rule: "Business rule",
  user_role: "User role",
  permission: "Permission",
  validation: "Validation",
  dependency: "Dependency",
  workflow: "Workflow",
  acceptance_criteria: "Acceptance criteria",
  constraint: "Constraint",
};

export const PRIORITY_LABELS: Record<Priority, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const REQUIREMENT_STATUS_LABELS: Record<RequirementStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  rejected: "Rejected",
};

/** One acceptance criterion per non-empty line. */
export function parseLines(value: string): string[] {
  return value
    .split("\n")
    .map((l) => l.replace(/^\s*[-*•]\s*/, "").trim())
    .filter(Boolean);
}

export function sourceLocation(ref: { page: number | null; sheet: string | null }): string {
  if (ref.page) return `page ${ref.page}`;
  if (ref.sheet) return `sheet ${ref.sheet}`;
  return "";
}
