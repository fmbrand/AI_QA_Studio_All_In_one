"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { ApiError, errorMessage } from "@/lib/api";
import type { Platform, Project, ProjectInput } from "@/lib/types";
import { parseTechStack, PLATFORM_LABELS } from "@/lib/utils";

interface Values {
  name: string;
  platform: Platform | "";
  description: string;
  project_type: string;
  application_url: string;
  business_domain: string;
  tech_stack: string;
}

function initial(project?: Project): Values {
  return {
    name: project?.name ?? "",
    platform: project?.platform ?? "",
    description: project?.description ?? "",
    project_type: project?.project_type ?? "",
    application_url: project?.application_url ?? "",
    business_domain: project?.business_domain ?? "",
    tech_stack: project?.tech_stack.join(", ") ?? "",
  };
}

export function validateProject(v: Values): Partial<Record<keyof Values, string>> {
  const errors: Partial<Record<keyof Values, string>> = {};
  if (!v.name.trim()) errors.name = "Enter a project name";
  if (!v.platform) errors.platform = "Choose a platform";
  if (v.application_url.trim()) {
    try {
      const url = new URL(v.application_url.trim());
      if (!["http:", "https:"].includes(url.protocol)) errors.application_url = "Use an http or https URL";
    } catch {
      errors.application_url = "Enter a full URL, for example https://app.example.com";
    }
  }
  return errors;
}

interface ProjectFormProps {
  project?: Project;
  submitLabel: string;
  disabled?: boolean;
  onSubmit: (input: ProjectInput) => Promise<void>;
  onCancel?: () => void;
}

export function ProjectForm({ project, submitLabel, disabled, onSubmit, onCancel }: ProjectFormProps) {
  const [values, setValues] = useState<Values>(() => initial(project));
  const [errors, setErrors] = useState<Partial<Record<keyof Values, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set =
    (key: keyof Values) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setValues((v) => ({ ...v, [key]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found = validateProject(values);
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length) return;
    setSaving(true);
    try {
      await onSubmit({
        name: values.name.trim(),
        platform: values.platform as Platform,
        description: values.description.trim(),
        project_type: values.project_type.trim(),
        application_url: values.application_url.trim() || null,
        business_domain: values.business_domain.trim(),
        tech_stack: parseTechStack(values.tech_stack),
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors({ name: err.fieldError("name"), application_url: err.fieldError("application_url") });
      }
      setFormError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const invalid = (k: keyof Values) => ({ "aria-invalid": !!errors[k], "aria-describedby": errors[k] ? `${k}-error` : undefined });

  return (
    <form onSubmit={submit} noValidate className="grid gap-4">
      {formError && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {formError}
        </p>
      )}
      <fieldset disabled={disabled || saving} className="grid gap-4 sm:grid-cols-2">
        <Field label="Project name" htmlFor="name" error={errors.name} required>
          <Input id="name" maxLength={120} value={values.name} onChange={set("name")} {...invalid("name")} />
        </Field>
        <Field label="Platform" htmlFor="platform" error={errors.platform} required>
          <Select id="platform" value={values.platform} onChange={set("platform")} {...invalid("platform")}>
            <option value="">Select a platform</option>
            {Object.entries(PLATFORM_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Project type" htmlFor="project_type" hint="For example: SaaS, marketplace, internal tool">
          <Input id="project_type" maxLength={80} value={values.project_type} onChange={set("project_type")} />
        </Field>
        <Field label="Business domain" htmlFor="business_domain" hint="For example: home services, fintech">
          <Input id="business_domain" maxLength={120} value={values.business_domain} onChange={set("business_domain")} />
        </Field>
        <Field label="Application URL" htmlFor="application_url" error={errors.application_url} className="sm:col-span-2">
          <Input
            id="application_url"
            type="url"
            placeholder="https://app.example.com"
            value={values.application_url}
            onChange={set("application_url")}
            {...invalid("application_url")}
          />
        </Field>
        <Field label="Technology stack" htmlFor="tech_stack" hint="Comma-separated, for example: Laravel, React, Flutter" className="sm:col-span-2">
          <Input id="tech_stack" value={values.tech_stack} onChange={set("tech_stack")} />
        </Field>
        <Field label="Description" htmlFor="description" className="sm:col-span-2">
          <Textarea id="description" rows={4} maxLength={5000} value={values.description} onChange={set("description")} />
        </Field>
      </fieldset>
      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" loading={saving} disabled={disabled}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
