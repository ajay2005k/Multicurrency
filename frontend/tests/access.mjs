import { chromium } from "playwright";
const browser = await chromium.launch({
  headless: true,
  ...(process.env.CHROMIUM_PATH
    ? { executablePath: process.env.CHROMIUM_PATH }
    : {}),
  args: ["--no-sandbox"],
});
try {
  const page = await browser.newPage();
  const key = "synthetic-browser-access-key";
  await page.route("**/api/**", (route) => {
    if (route.request().headers()["x-api-key"] === key) return route.continue();
    return route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "A valid API key is required" }),
    });
  });
  await page.goto(process.env.APP_URL || "http://127.0.0.1:5173");
  await page.getByRole("heading", { name: "Welcome to Sentinel" }).waitFor();
  await page
    .getByLabel("Workspace access key", { exact: true })
    .fill("incorrect-key");
  await page
    .getByRole("button", { name: "Connect workspace", exact: true })
    .click();
  await page
    .getByRole("alert")
    .getByText(
      "Access key not recognized. Please check your key and try again.",
    )
    .waitFor();
  await page.getByLabel("Workspace access key", { exact: true }).fill(key);
  await page
    .getByRole("button", { name: "Connect workspace", exact: true })
    .click();
  await page.getByRole("heading", { name: "Payment overview" }).waitFor();
  console.log("PASS: workspace sign-in, rejected key, successful access");
} finally {
  await browser.close();
}
