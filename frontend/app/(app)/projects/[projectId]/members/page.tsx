"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { useCurrentProject } from "@/components/project/project-context";
import { useAuth } from "@/components/providers/auth-provider";
import { RoleBadge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/form";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api, errorMessage } from "@/lib/api";
import { keys, useMembers, useRoles } from "@/lib/queries";
import type { Member, RoleKey } from "@/lib/types";
import { formatDate, ROLE_LABELS, ROLE_RANK } from "@/lib/utils";

export default function MembersPage() {
  const { project, canAdmin, isOwner, archived } = useCurrentProject();
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const members = useMembers(project.id);
  const roles = useRoles();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<RoleKey>("qa_engineer");
  const myRank = ROLE_RANK[project.my_role];
  const canManage = canAdmin && !archived;
  const assignable = (Object.keys(ROLE_LABELS) as RoleKey[]).filter((r) => (r === "owner" ? isOwner : ROLE_RANK[r] <= myRank));

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: keys.members(project.id) });
    queryClient.invalidateQueries({ queryKey: keys.project(project.id) });
    queryClient.invalidateQueries({ queryKey: keys.activity(project.id) });
  };

  const add = useMutation({
    mutationFn: () => api.post<Member>(`/projects/${project.id}/members`, { email: email.trim(), role }),
    onSuccess: (m) => {
      invalidate();
      setEmail("");
      toast.success(`Added ${m.name} as ${ROLE_LABELS[m.role]}`);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const change = useMutation({
    mutationFn: ({ userId, newRole }: { userId: string; newRole: RoleKey }) =>
      api.patch<Member>(`/projects/${project.id}/members/${userId}`, { role: newRole }),
    onSuccess: (m) => {
      invalidate();
      toast.success(`${m.name} is now ${ROLE_LABELS[m.role]}`);
    },
    onError: (err) => {
      invalidate();
      toast.error(errorMessage(err));
    },
  });

  const remove = useMutation({
    mutationFn: (m: Member) => api.delete(`/projects/${project.id}/members/${m.user_id}`),
    onSuccess: (_, m) => {
      if (m.user_id === user?.id) {
        queryClient.invalidateQueries({ queryKey: keys.me });
        queryClient.invalidateQueries({ queryKey: ["projects"] });
        toast.success(`You left ${project.name}`);
        router.replace("/projects");
        return;
      }
      invalidate();
      toast.success(`Removed ${m.name}`);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const canChange = (m: Member) => canManage && m.user_id !== user?.id && (m.role !== "owner" || isOwner);

  return (
    <div className="grid gap-6">
      {canManage && (
        <Card>
          <CardHeader>
            <CardTitle>Add a member</CardTitle>
            <CardDescription>The person needs an AI QA Studio account. Email invitations arrive in a later phase.</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-3 sm:grid-cols-[1fr_12rem_auto] sm:items-end"
              onSubmit={(e) => {
                e.preventDefault();
                if (email.trim()) add.mutate();
              }}
            >
              <Field label="Email" htmlFor="member-email">
                <Input id="member-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com" />
              </Field>
              <Field label="Role" htmlFor="member-role">
                <Select id="member-role" value={role} onChange={(e) => setRole(e.target.value as RoleKey)}>
                  {assignable.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABELS[r]}
                    </option>
                  ))}
                </Select>
              </Field>
              <Button type="submit" loading={add.isPending} disabled={!email.trim()}>
                <UserPlus />
                Add
              </Button>
            </form>
            {roles.data && (
              <dl className="mt-4 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
                {roles.data.map((r) => (
                  <div key={r.key}>
                    <dt className="inline font-medium text-foreground">{r.name}: </dt>
                    <dd className="inline">{r.description}</dd>
                  </div>
                ))}
              </dl>
            )}
          </CardContent>
        </Card>
      )}

      {members.isPending ? (
        <LoadingRows />
      ) : members.isError ? (
        <ErrorState error={members.error} onRetry={() => members.refetch()} />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Member</TH>
              <TH>Role</TH>
              <TH className="hidden sm:table-cell">Added</TH>
              <TH className="text-right">
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {members.data.map((m) => (
              <TR key={m.user_id}>
                <TD>
                  <span className="block font-medium">
                    {m.name}
                    {m.user_id === user?.id && <span className="text-muted-foreground"> (you)</span>}
                  </span>
                  <span className="block text-xs text-muted-foreground">{m.email}</span>
                </TD>
                <TD>
                  {canChange(m) ? (
                    <Select
                      aria-label={`Role for ${m.name}`}
                      className="h-8 w-40"
                      value={m.role}
                      disabled={change.isPending}
                      onChange={(e) => change.mutate({ userId: m.user_id, newRole: e.target.value as RoleKey })}
                    >
                      {assignable.map((r) => (
                        <option key={r} value={r}>
                          {ROLE_LABELS[r]}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <RoleBadge role={m.role} />
                  )}
                </TD>
                <TD className="hidden text-muted-foreground sm:table-cell">{formatDate(m.added_at)}</TD>
                <TD className="text-right">
                  {m.user_id === user?.id ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => window.confirm(`Leave ${project.name}?`) && remove.mutate(m)}
                    >
                      Leave
                    </Button>
                  ) : (
                    canChange(m) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        onClick={() => window.confirm(`Remove ${m.name} from ${project.name}?`) && remove.mutate(m)}
                      >
                        Remove
                      </Button>
                    )
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
