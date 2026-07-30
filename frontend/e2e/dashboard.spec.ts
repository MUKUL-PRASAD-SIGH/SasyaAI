import { expect, test } from "@playwright/test";

test("a failed deterministic dose check cannot be approved from the dashboard", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Demo scenario").selectOption("unsafe-dose");
  await page.getByRole("button", { name: "Run advisory workflow" }).click();

  await expect(page.getByText("Hard safety check failed.", { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Decision" })).toHaveValue("reject");
  await expect(page.getByRole("option", { name: "Approve draft" })).toHaveCount(0);
  await expect(page.getByRole("option", { name: "Edit and approve" })).toHaveCount(0);
});
