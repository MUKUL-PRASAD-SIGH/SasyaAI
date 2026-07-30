import { expect, test } from "@playwright/test";

test("the operations cockpit loads corpus coverage and switches theme", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("105 records", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Farmer profile").locator("option")).toHaveCount(18);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "field");

  await page.getByRole("button", { name: "Switch to night theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "night");
  await expect(page.getByRole("button", { name: "Switch to field theme" })).toBeVisible();
});

test("a delivered crop plan exposes the coordinated agent run", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Run advisory workflow" }).click();

  const agentRun = page.getByRole("region", { name: "Coordinated run" });
  await expect(agentRun).toBeVisible();
  await expect(agentRun.getByText("Root Manager", { exact: true })).toBeVisible();
  await expect(agentRun.getByText("Safety Verifier", { exact: true })).toBeVisible();
  await expect(page.getByText("Delivered after checks", { exact: true })).toBeVisible();
});

test("a failed deterministic dose check cannot be approved from the dashboard", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Demo scenario").selectOption("unsafe-dose");
  await page.getByRole("button", { name: "Run advisory workflow" }).click();

  await expect(page.getByText("Hard safety check failed.", { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Decision" })).toHaveValue("reject");
  await expect(page.getByRole("option", { name: "Approve draft" })).toHaveCount(0);
  await expect(page.getByRole("option", { name: "Edit and approve" })).toHaveCount(0);
});
