"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { useCurrentProject } from "@/components/project/project-context";
import { ProjectForm } from "@/components/project/project-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/form";
import { api, ApiError, errorMessage } from "@/lib/api";
import { keys } from "@/lib/queries";
import type { Project, ProjectInput } from "@/lib/types";

export default function ProjectSettingsPage() {
  const { project, canAdmin, isOwner, archived } = useCurrentProject();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [typedName, setTypedName] = useState("");

  const refresh = (updated?: Project) => {
    if (updated) queryClient.setQueryData(keys.project(project.id), updated);
    queryClient.invalidateQueries({ queryKey: ["projects"] });
    queryClient.invalidateQueries({ queryKey: keys.me });
    queryClient.invalidateQueries({ queryKey: keys.activity(project.id) });
    queryClient.invalidateQueries({ queryKey: keys.dashboard });
  };

  const save = async (input: ProjectInput) => {
    try {
      const updated = await api.patch<Project>(`/projects/${project.id}`, input, project.version);
      refresh(updated);
      toast.success("Project saved");
    } catch (err) {
      if (err instanceof ApiError && err.code === "version_conflict") {
        await queryClient.invalidateQueries({ queryKey: keys.project(project.id) });
        throw new ApiError(412, err.code, "Someone else changed this project. The latest version is loaded; apply your edit again.");
      }
      throw err;
    }
  };

  const archive = useMutation({
    mutationFn: () => api.post<Project>(`/projects/${project.id}/${archived ? "restore" : "archive"}`),
    onSuccess: (updated) => {
      refresh(updated);
      toast.success(updated.status === "archived" ? "Project archived" : "Project restored");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const remove = useMutation({
    mutationFn: () => api.delete(`/projects/${project.id}`),
    onSuccess: () => {
      refresh();
      toast.success(`Deleted ${project.name}`);
      router.replace("/projects");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Project details</CardTitle>
          <CardDescription>
            {canAdmin
              ? archived
                ? "Restore the project to edit its details."
                : "Changes are recorded in the activity log."
              : "Only admins and owners can edit project details."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ProjectForm
            key={project.version}
            project={project}
            submitLabel="Save changes"
            disabled={!canAdmin || archived}
            onSubmit={save}
          />
        </CardContent>
      </Card>

      {canAdmin && (
        <Card>
          <CardHeader>
            <CardTitle>{archived ? "Restore project" : "Archive project"}</CardTitle>
            <CardDescription>
              {archived
                ? "Make the project editable again."
                : "Archived projects are read-only and hidden from the active list. Nothing is deleted."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" loading={archive.isPending} onClick={() => archive.mutate()}>
              {archived ? "Restore project" : "Archive project"}
            </Button>
          </CardContent>
        </Card>
      )}

      {isOwner && (
        <Card className="border-destructive/40">
          <CardHeader>
            <CardTitle>Delete project</CardTitle>
            <CardDescription>
              Removes the project for every member. Data is kept for 30 days before it is purged.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
              Delete project
            </Button>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={confirmDelete}
        onOpenChange={(open) => {
          setConfirmDelete(open);
          setTypedName("");
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {project.name}?</DialogTitle>
            <DialogDescription>All members lose access immediately. Type the project name to confirm.</DialogDescription>
          </DialogHeader>
          <Field label="Project name" htmlFor="confirm-name">
            <Input id="confirm-name" value={typedName} onChange={(e) => setTypedName(e.target.value)} autoComplete="off" />
          </Field>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={typedName !== project.name}
              loading={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Delete project
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
