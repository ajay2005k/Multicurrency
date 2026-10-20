import { chromium } from "playwright";
const browser = await chromium.launch({
  headless: true,
  ...(process.env.CHROMIUM_PATH
    ? { executablePath: process.env.CHROMIUM_PATH }
    : {}),
  args: ["--no-sandbox"],
});
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(process.env.APP_URL || "http://127.0.0.1:5173");
  if (process.env.WORKSPACE_ACCESS_KEY) {
    await page
      .getByLabel("Workspace access key", { exact: true })
      .fill(process.env.WORKSPACE_ACCESS_KEY);
    await page
      .getByRole("button", { name: "Connect workspace", exact: true })
      .click();
  }
  await page.getByRole("heading", { name: "Payment overview" }).waitFor();
  await page
    .getByRole("button", { name: "Validate payment", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog", { name: "Validate payment" });
  const customer = `browser-${Date.now()}@example.com`;
  await dialog.getByLabel("Amount", { exact: true }).fill("100");
  await dialog.getByLabel("Customer reference").fill(customer);
  await dialog
    .getByLabel("Merchant", { exact: true })
    .fill("Synthetic browser test");
  await dialog.getByRole("button", { name: "Validate payment" }).click();
  const result = page.getByRole("dialog", { name: "Payment result" });
  await result.getByText("Approved", { exact: true }).waitFor();
  await result
    .getByText("First payment from this customer", { exact: true })
    .waitFor();
  await page.getByRole("button", { name: "Back to workspace" }).click();
  await page
    .getByRole("textbox", { name: "Search transactions" })
    .fill(customer);
  await page.getByRole("cell", { name: customer, exact: false }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("button", { name: "Risk insights", exact: true })
    .click();
  await page.getByRole("heading", { name: "How decisions are made" }).waitFor();
  if (
    await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  )
    throw new Error("Mobile overflow");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "PASS: payment submission, decision detail, search, mobile navigation, no JavaScript errors",
  );
} finally {
  await browser.close();
}
