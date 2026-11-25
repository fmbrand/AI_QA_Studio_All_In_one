import { describe, expect, it } from "vitest";

import { checkFile } from "@/components/documents/upload-dialog";
import { validateProject } from "@/components/project/project-form";
import { fileExtension, formatBytes, hasRole, parseTechStack, timeAgo } from "@/lib/utils";

describe("formatBytes", () => {
  it.each([
    [0, "0 B"],
    [512, "512 B"],
    [1536, "1.5 KB"],
    [25 * 1024 * 1024, "25 MB"],
  ])("formats %i as %s", (bytes, expected) => {
    expect(formatBytes(bytes)).toBe(expected);
  });
});

describe("timeAgo", () => {
  const now = Date.parse("2026-11-25T12:00:00Z");
  it("describes recent times", () => {
    expect(timeAgo("2026-11-25T11:59:50Z", now)).toBe("just now");
    expect(timeAgo("2026-11-25T11:30:00Z", now)).toBe("30 min ago");
    expect(timeAgo("2026-11-25T09:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo("2026-11-20T12:00:00Z", now)).toBe("5 d ago");
  });
});

describe("parseTechStack", () => {
  it("trims, drops blanks and de-duplicates case-insensitively", () => {
    expect(parseTechStack(" React, react ,, Node ,Flutter")).toEqual(["React", "Node", "Flutter"]);
  });
});

describe("hasRole", () => {
  it("compares role rank", () => {
    expect(hasRole("owner", "admin")).toBe(true);
    expect(hasRole("qa_engineer", "qa_engineer")).toBe(true);
    expect(hasRole("viewer", "qa_engineer")).toBe(false);
    expect(hasRole(undefined, "viewer")).toBe(false);
  });
});

describe("checkFile", () => {
  const file = (name: string, size: number) => new File([new Uint8Array(size)], name);
  it("accepts supported files under the limit", () => {
    expect(checkFile(file("spec.PDF", 10), 1)).toBeNull();
    expect(fileExtension("a.b.CSV")).toBe(".csv");
  });
  it("rejects unsupported, empty and oversized files", () => {
    expect(checkFile(file("run.exe", 10), 1)).toMatch(/Unsupported type/);
    expect(checkFile(file("empty.txt", 0), 1)).toBe("The file is empty");
    expect(checkFile(file("big.txt", 1024 * 1024 + 1), 1)).toBe("Larger than 1 MB");
  });
});

describe("validateProject", () => {
  const base = {
    name: "Shop",
    platform: "web" as const,
    description: "",
    project_type: "",
    application_url: "",
    business_domain: "",
    tech_stack: "",
  };
  it("passes a minimal valid project", () => {
    expect(validateProject(base)).toEqual({});
  });
  it("requires name and platform and checks the URL", () => {
    const errors = validateProject({ ...base, name: " ", platform: "", application_url: "ftp://x" });
    expect(errors.name).toBeDefined();
    expect(errors.platform).toBeDefined();
    expect(errors.application_url).toBe("Use an http or https URL");
    expect(validateProject({ ...base, application_url: "not a url" }).application_url).toMatch(/full URL/);
  });
});
