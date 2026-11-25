import { expect, type Page, test } from "@playwright/test";

const password = "e2e-password-123";

const tab = (page: Page, name: string) =>
  page.getByRole("navigation", { name: "Project sections" }).getByRole("link", { name, exact: true }).click();

async function newProjectWithDocument(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Name").fill("Phase Two Tester");
  await page.getByLabel("Email").fill(`p2-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await page.getByRole("button", { name: "Create your first project" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Project name").fill(`Requirements ${Date.now()}`);
  await dialog.getByLabel("Platform").selectOption("web");
  await dialog.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("navigation", { name: "Project sections" })).toBeVisible();

  await tab(page, "Documents");
  await page.getByRole("button", { name: "Upload documents" }).first().click();
  await page.locator("#upload-input").setInputFiles({
    name: "booking-rules.md",
    mimeType: "text/markdown",
    buffer: Buffer.from(
      "# Booking\n\nA customer can book an available time slot.\n\nPast dates cannot be selected in the date picker.\n",
    ),
  });
  await page.getByRole("dialog").getByRole("button", { name: /^Upload/ }).click();
  await expect(page.getByRole("row", { name: /booking-rules/ }).getByText("Indexed")).toBeVisible({ timeout: 60_000 });
}

test("indexed documents are searchable in Knowledge search", async ({ page }) => {
  await newProjectWithDocument(page);
  await tab(page, "Knowledge search");
  await page.getByLabel("Search project knowledge").fill("can past dates be selected?");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const results = page.getByRole("list", { name: "Search results" });
  await expect(results.getByText("Past dates cannot be selected", { exact: false })).toBeVisible();
  await expect(results.getByText("booking-rules")).toBeVisible();
});

test("requirements: add, approve, edit into a new version and compare", async ({ page }) => {
  await newProjectWithDocument(page);
  await tab(page, "Requirements");
  await expect(page.getByText("No requirements yet")).toBeVisible();

  await page.getByRole("button", { name: "Add requirement" }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Title").fill("Customer can cancel a booking");
  await dialog.getByLabel("Priority").selectOption("high");
  await dialog.getByLabel("Acceptance criteria").fill("Cancel button is shown\nCancelled booking frees the slot");
  await dialog.getByRole("button", { name: "Add requirement" }).click();
  const row = page.getByRole("row", { name: /REQ-001/ });
  await expect(row.getByText("Draft")).toBeVisible();

  await row.getByRole("button", { name: "Customer can cancel a booking" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Approve v1" }).click();
  await expect(dialog.getByText("Approved", { exact: true })).toBeVisible();

  await dialog.getByLabel("Title").fill("Customer can cancel a booking up to 2 hours before start");
  await dialog.getByLabel("Reason for change").fill("Policy clarified");
  await dialog.getByRole("button", { name: "Save as new version" }).click();
  await expect(dialog.getByText("Version 2")).toBeVisible();
  await expect(dialog.getByText("Draft", { exact: true })).toBeVisible();
  await expect(dialog.getByText("v1 is the last approved version", { exact: false })).toBeVisible();
  await dialog.getByRole("button", { name: "Compare with v1" }).click();
  await expect(dialog.getByText('"Customer can cancel a booking up to 2 hours before start"')).toBeVisible();
  await page.keyboard.press("Escape");

  await expect(page.getByRole("row", { name: /REQ-001/ }).getByText("v2")).toBeVisible();
});
