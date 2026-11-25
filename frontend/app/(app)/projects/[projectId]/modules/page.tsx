"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Layers, Link2, MoreHorizontal, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useCurrentProject } from "@/components/project/project-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Field, Input, Textarea } from "@/components/ui/form";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { api, ApiError, errorMessage } from "@/lib/api";
import { keys, useModules } from "@/lib/queries";
import type { Module } from "@/lib/types";

function ModuleFormDialog({
  projectId,
  module,
  open,
  onOpenChange,
}: {
  projectId: string;
  module: Module | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(module?.name ?? "");
  const [description, setDescription] = useState(module?.description ?? "");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      module
        ? api.patch(`/projects/${projectId}/modules/${module.id}`, { name: name.trim(), description }, module.version)
        : api.post(`/projects/${projectId}/modules`, { name: name.trim(), description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      toast.success(module ? "Module updated" : "Module created");
      onOpenChange(false);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === "version_conflict") {
        queryClient.invalidateQueries({ queryKey: keys.modules(projectId) });
        setError("Someone else changed this module. Close and reopen it to edit the latest version.");
      } else setError(errorMessage(err));
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{module ? "Edit module" : "New module"}</DialogTitle>
          <DialogDescription>Modules group requirements, designs and test cases, for example “Booking” or “Payments”.</DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            if (!name.trim()) return setError("Enter a module name");
            setError(null);
            save.mutate();
          }}
        >
          {error && (
            <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          <Field label="Name" htmlFor="module-name" required>
            <Input id="module-name" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Description" htmlFor="module-description">
            <Textarea id="module-description" rows={3} maxLength={5000} value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={save.isPending}>
              {module ? "Save" : "Create module"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ConnectionsDialog({
  projectId,
  module,
  modules,
  onClose,
}: {
  projectId: string;
  module: Module;
  modules: Module[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set(module.connected_module_ids));
  const save = useMutation({
    mutationFn: () => api.put(`/projects/${projectId}/modules/${module.id}/connections`, { to_module_ids: [...selected] }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.modules(projectId) });
      toast.success("Connections saved");
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const others = modules.filter((m) => m.id !== module.id);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connections for {module.name}</DialogTitle>
          <DialogDescription>
            Pick the modules {module.name} depends on or affects. Later phases use this graph for retrieval scope and change
            impact analysis.
          </DialogDescription>
        </DialogHeader>
        {others.length === 0 ? (
          <p className="text-sm text-muted-foreground">Create another module first.</p>
        ) : (
          <fieldset className="grid max-h-72 gap-2 overflow-y-auto">
            <legend className="sr-only">Connected modules</legend>
            {others.map((m) => (
              <label key={m.id} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={selected.has(m.id)}
                  onChange={(e) =>
                    setSelected((s) => {
                      const next = new Set(s);
                      if (e.target.checked) next.add(m.id);
                      else next.delete(m.id);
                      return next;
                    })
                  }
                />
                {m.name}
              </label>
            ))}
          </fieldset>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={save.isPending} onClick={() => save.mutate()} disabled={others.length === 0}>
            Save connections
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ModulesPage() {
  const { project, canEdit, canAdmin, archived } = useCurrentProject();
  const queryClient = useQueryClient();
  const modules = useModules(project.id);
  const [editing, setEditing] = useState<Module | null | "new">(null);
  const [connecting, setConnecting] = useState<Module | null>(null);
  const names = new Map(modules.data?.map((m) => [m.id, m.name]));

  const remove = useMutation({
    mutationFn: (m: Module) => api.delete(`/projects/${project.id}/modules/${m.id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", project.id] });
      toast.success("Module deleted");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <>
      <div className="mb-4 flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">Break the product into modules and record how they connect.</p>
        {canEdit && (
          <Button onClick={() => setEditing("new")}>
            <Plus />
            New module
          </Button>
        )}
      </div>
      {modules.isPending ? (
        <LoadingRows />
      ) : modules.isError ? (
        <ErrorState error={modules.error} onRetry={() => modules.refetch()} />
      ) : modules.data.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="No modules yet"
          description="Add the main areas of the product, for example Authentication, Booking and Payments."
          action={
            canEdit ? (
              <Button onClick={() => setEditing("new")}>
                <Plus />
                Add a module
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {modules.data.map((m) => (
            <Card key={m.id}>
              <CardContent className="grid gap-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-medium">{m.name}</h3>
                  {canEdit && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label={`Actions for ${m.name}`}>
                          <MoreHorizontal />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => setEditing(m)}>
                          <Pencil />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => setConnecting(m)}>
                          <Link2 />
                          Connections
                        </DropdownMenuItem>
                        {canAdmin && !archived && (
                          <DropdownMenuItem
                            destructive
                            onSelect={() => {
                              if (window.confirm(`Delete module “${m.name}”? Documents keep existing without a module.`))
                                remove.mutate(m);
                            }}
                          >
                            <Trash2 />
                            Delete
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </div>
                {m.description && <p className="whitespace-pre-wrap text-sm text-muted-foreground">{m.description}</p>}
                {m.connected_module_ids.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1 text-xs">
                    <span className="text-muted-foreground">Connects to</span>
                    {m.connected_module_ids.map((id) => (
                      <Badge key={id} variant="outline">
                        {names.get(id) ?? "Unknown"}
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {editing !== null && (
        <ModuleFormDialog
          key={editing === "new" ? "new" : `${editing.id}-${editing.version}`}
          projectId={project.id}
          module={editing === "new" ? null : editing}
          open
          onOpenChange={(o) => !o && setEditing(null)}
        />
      )}
      {connecting && (
        <ConnectionsDialog
          projectId={project.id}
          module={connecting}
          modules={modules.data ?? []}
          onClose={() => setConnecting(null)}
        />
      )}
    </>
  );
}
