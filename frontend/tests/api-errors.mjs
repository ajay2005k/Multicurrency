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
  const base = process.env.APP_URL || "http://127.0.0.1:5173";
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/**", (route) =>
    route.fulfill({ status: 500, body: "" }),
  );
  await page.goto(base);
  await page
    .getByRole("alert")
    .getByText(
      "API connection failed (HTTP 500). The payment service is temporarily unavailable. Please retry.",
    )
    .waitFor();
  await page.unroute("**/api/**");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await page.waitForFunction(() => !document.querySelector("[role=alert]"));
  await page.route("**/api/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<html>Wrong API address</html>",
    }),
  );
  await page.reload();
  await page
    .getByRole("alert")
    .getByText(
      "The payment service returned an invalid response. Please retry or contact your workspace administrator.",
    )
    .waitFor();
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "PASS: empty HTTP 500, non-JSON HTTP 200, and successful retry without JSON parsing crashes",
  );
} finally {
  await browser.close();
}
