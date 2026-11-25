import { expect, type Page, test } from "@playwright/test";

const password = "e2e-password-123";

const tab = (page: Page, name: string) =>
  page.getByRole("navigation", { name: "Project sections" }).getByRole("link", { name }).click();

test("unauthenticated users are sent to sign in", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?next=%2Fdashboard/);
  await expect(page.getByRole("heading", { name: "Sign in to AI QA Studio" })).toBeVisible();
});

test("register, create a project, add a module, upload a document and see it persist", async ({ page }) => {
  const email = `qa-${Date.now()}@example.com`;
  const projectName = `Booking App ${Date.now()}`;

  // Register
  await page.goto("/register");
  await page.getByLabel("Name").fill("E2E Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByText("No projects yet")).toBeVisible();

  // Create a project
  await page.getByRole("button", { name: "Create your first project" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Project name").fill(projectName);
  await dialog.getByLabel("Platform").selectOption("web");
  await dialog.getByLabel("Business domain").fill("Home services");
  await dialog.getByLabel("Technology stack").fill("Laravel, React");
  await dialog.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("heading", { level: 1, name: projectName })).toBeVisible();
  await expect(page.getByText("Owner", { exact: true }).first()).toBeVisible();

  // Add a module
  await tab(page, "Modules");
  await page.getByRole("button", { name: "Add a module" }).click();
  await page.getByLabel("Name").fill("Booking");
  await page.getByRole("button", { name: "Create module" }).click();
  await expect(page.getByRole("heading", { name: "Booking", level: 3 })).toBeVisible();

  // Upload a requirements document; the worker extracts its text
  await tab(page, "Documents");
  await page.getByRole("button", { name: "Upload documents" }).first().click();
  await page.locator("#upload-input").setInputFiles({
    name: "booking-rules.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Booking\nA customer can book an available time slot.\n"),
  });
  await page.getByRole("dialog").getByLabel("Module", { exact: true }).selectOption({ label: "Booking" });
  await page.getByRole("dialog").getByRole("button", { name: /^Upload/ }).click();
  const row = page.getByRole("row", { name: /booking-rules/ });
  await expect(row).toBeVisible();
  await expect(row.getByText("Text extracted")).toBeVisible({ timeout: 30_000 });

  await row.getByRole("button", { name: "booking-rules" }).click();
  await expect(page.getByText("A customer can book an available time slot.")).toBeVisible();
  await page.keyboard.press("Escape");

  // Activity is recorded
  await tab(page, "Activity");
  await expect(page.getByText(/Uploaded booking-rules\.md/)).toBeVisible();

  // Sign out and back in: everything persisted
  await page.goto("/settings");
  await page.getByRole("button", { name: /E2E Tester/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.goto("/projects");
  await page.getByRole("link", { name: projectName }).click();
  await expect(page.getByText("Documents").first()).toBeVisible();
  await tab(page, "Documents");
  await expect(page.getByRole("row", { name: /booking-rules/ })).toBeVisible();
});

test("a page reload keeps the session through the refresh cookie", async ({ page }) => {
  const email = `reload-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Name").fill("Reload Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await page.reload();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
});
