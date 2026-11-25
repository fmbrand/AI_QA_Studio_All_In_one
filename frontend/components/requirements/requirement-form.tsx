"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { ApiError, errorMessage } from "@/lib/api";
import type { Module, Priority, RequirementInput, RequirementType, RequirementVersion } from "@/lib/types";
import { parseLines, PRIORITY_LABELS, REQUIREMENT_TYPE_LABELS } from "@/lib/utils";

interface Values {
  type: RequirementType;
  title: string;
  description: string;
  module_id: string;
  feature: string;
  user_role: string;
  priority: Priority;
  criteria: string;
  change_reason: string;
}

function initial(v?: RequirementVersion): Values {
  return {
    type: v?.type ?? "functional",
    title: v?.title ?? "",
    description: v?.description ?? "",
    module_id: v?.module_id ?? "",
    feature: v?.feature ?? "",
    user_role: v?.user_role ?? "",
    priority: v?.priority ?? "medium",
    criteria: v?.acceptance_criteria.join("\n") ?? "",
    change_reason: "",
  };
}

export function toInput(v: Values): RequirementInput {
  return {
    type: v.type,
    title: v.title.trim(),
    description: v.description.trim(),
    module_id: v.module_id || null,
    feature: v.feature.trim() || null,
    user_role: v.user_role.trim() || null,
    priority: v.priority,
    acceptance_criteria: parseLines(v.criteria),
  };
}

interface Props {
  version?: RequirementVersion;
  modules: Module[];
  disabled?: boolean;
  submitLabel: string;
  askReason?: boolean;
  onSubmit: (input: RequirementInput, changeReason: string | null) => Promise<void>;
  onCancel?: () => void;
}

export function RequirementForm({ version, modules, disabled, submitLabel, askReason, onSubmit, onCancel }: Props) {
  const [values, setValues] = useState<Values>(() => initial(version));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const set =
    (key: keyof Values) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setValues((v) => ({ ...v, [key]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!values.title.trim()) return setError("Enter a title");
    setError(null);
    setSaving(true);
    try {
      await onSubmit(toInput(values), values.change_reason.trim() || null);
    } catch (err) {
      setError(err instanceof ApiError && err.code === "no_change" ? "Nothing has changed." : errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="grid gap-4" onSubmit={submit} noValidate>
      {error && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}
      <fieldset disabled={disabled || saving} className="grid gap-4 sm:grid-cols-2">
        <Field label="Title" htmlFor="req-title" required className="sm:col-span-2">
          <Input id="req-title" maxLength={300} value={values.title} onChange={set("title")} />
        </Field>
        <Field label="Type" htmlFor="req-type">
          <Select id="req-type" value={values.type} onChange={set("type")}>
            {Object.entries(REQUIREMENT_TYPE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Priority" htmlFor="req-priority">
          <Select id="req-priority" value={values.priority} onChange={set("priority")}>
            {Object.entries(PRIORITY_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Module" htmlFor="req-module">
          <Select id="req-module" value={values.module_id} onChange={set("module_id")}>
            <option value="">No module</option>
            {modules.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Feature" htmlFor="req-feature">
          <Input id="req-feature" maxLength={200} value={values.feature} onChange={set("feature")} />
        </Field>
        <Field label="User role" htmlFor="req-role" className="sm:col-span-2">
          <Input id="req-role" maxLength={120} value={values.user_role} onChange={set("user_role")} />
        </Field>
        <Field label="Description" htmlFor="req-description" className="sm:col-span-2">
          <Textarea id="req-description" rows={4} value={values.description} onChange={set("description")} />
        </Field>
        <Field
          label="Acceptance criteria"
          htmlFor="req-criteria"
          hint="One per line."
          className="sm:col-span-2"
        >
          <Textarea id="req-criteria" rows={4} value={values.criteria} onChange={set("criteria")} />
        </Field>
        {askReason && (
          <Field label="Reason for change" htmlFor="req-reason" hint="Shown in the version history." className="sm:col-span-2">
            <Input id="req-reason" maxLength={500} value={values.change_reason} onChange={set("change_reason")} />
          </Field>
        )}
      </fieldset>
      {!disabled && (
        <div className="flex justify-end gap-2">
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          )}
          <Button type="submit" loading={saving}>
            {submitLabel}
          </Button>
        </div>
      )}
    </form>
  );
}
