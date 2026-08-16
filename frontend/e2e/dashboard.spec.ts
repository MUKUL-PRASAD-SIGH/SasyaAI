import { expect, test } from "@playwright/test";

async function signInWithBypass(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByRole("button", { name: /Continue with local bypass/i }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

test("the first screen is the role-based login page", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByRole("radio", { name: /Farmer/i })).toBeVisible();
  await expect(page.getByRole("radio", { name: /Extension Officer/i })).toBeVisible();
  await expect(page.getByRole("radio", { name: /System Admin/i })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByRole("button", { name: /Continue with Google/i })).toBeVisible();
  await expect(page.getByText(/Advanced \/ reviewer API key/i)).toBeVisible();
  await expect(page.getByText("Operator access")).toHaveCount(0);
  await expect(page.getByText("Governed agricultural intelligence")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Connect" })).toHaveCount(0);
  await expect(page.getByText("Ask a safety-gated question")).toHaveCount(0);
});

test("local bypass enters the authenticated desk and sign-out returns to login", async ({
  page,
}) => {
  await signInWithBypass(page);
  // The bypass principal holds every role, so the desk resolves to the admin view.
  await expect(page.getByText("Inspect runtime, farmers, and audit trails.")).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("farmer registration completes without a 405 from the API proxy", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Register new farmer" }).click();
  await page.getByRole("textbox", { name: "Name" }).fill("Playwright Farmer");
  await page.getByRole("textbox", { name: "Email" }).fill("playwright.farmer@demo.sasyaai.local");
  await page.getByRole("textbox", { name: "District" }).fill("Pune");

  const registerResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/farmers/register") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Create profile & enter" }).click();
  const response = await registerResponse;

  expect(response.status()).toBe(200);
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
});

test("a delivered crop plan exposes the coordinated agent run", async ({ page }) => {
  await signInWithBypass(page);
  await page.getByRole("button", { name: "Run advisory workflow" }).click();

  // Agent names also render in the review queue, so assert against the advisory result.
  const advisoryResult = page.getByLabel("Advisory result");
  await expect(advisoryResult.getByText("Root Manager", { exact: true })).toBeVisible();
  await expect(advisoryResult.getByText("Safety Verifier", { exact: true })).toBeVisible();
  await expect(advisoryResult.getByText("Delivered after checks", { exact: true })).toBeVisible();
});
