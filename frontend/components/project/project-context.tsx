"use client";

import { createContext, useContext } from "react";

import type { Project } from "@/lib/types";
import { hasRole } from "@/lib/utils";

export interface ProjectContextValue {
  project: Project;
  /** Write actions need the project to be active and the right role. */
  canEdit: boolean;
  canAdmin: boolean;
  isOwner: boolean;
  archived: boolean;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function projectContextValue(project: Project): ProjectContextValue {
  const archived = project.status === "archived";
  return {
    project,
    archived,
    canEdit: !archived && hasRole(project.my_role, "qa_engineer"),
    canAdmin: hasRole(project.my_role, "admin"),
    isOwner: project.my_role === "owner",
  };
}

export const ProjectProvider = ProjectContext.Provider;

export function useCurrentProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useCurrentProject must be used inside a project page");
  return ctx;
}
