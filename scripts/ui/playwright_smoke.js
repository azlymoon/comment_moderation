// Simple Playwright smoke test for the demo UI.
// Requirements: Node.js + `npm i playwright` (and `npx playwright install chromium`).
// Usage:
// API_KEY=... SERVICE_ID=... BASE_URL=http://127.0.0.1:8000 node scripts/ui/playwright_smoke.js

const { chromium } = require("playwright");

async function main() {
  const baseUrl = process.env.BASE_URL || "http://127.0.0.1:8000";
  const apiKey = process.env.API_KEY;
  const serviceId = process.env.SERVICE_ID;
  const content = process.env.CONTENT_TEXT || "I hate this movie";

  if (!apiKey || !serviceId) {
    console.error("API_KEY and SERVICE_ID env vars are required");
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  await page.goto(`${baseUrl}/ui/client.html`, { waitUntil: "networkidle" });

  await page.fill("#service-id", serviceId);
  await page.fill("#api-key", apiKey);
  await page.fill("#content-text", content);
  await page.click("#submit-btn");

  // Wait for decision text to be updated (not the initial "—")
  const decisionLocator = page.locator("[data-testid='result-decision']");
  const statusLocator = page.locator("[data-testid='status']");

  await page.waitForFunction(
    () => {
      const el = document.querySelector("[data-testid='result-decision']");
      const text = (el?.textContent || "").trim();
      return text && text !== "—";
    },
    undefined,
    { timeout: 15000 },
  );

  const decision = (await decisionLocator.textContent())?.trim();
  const status = (await statusLocator.textContent())?.trim();
  const resultText = (await page.locator("[data-testid='result']").textContent())?.trim();

  console.log(`Status: ${status}`);
  console.log(`Decision: ${decision}`);
  if (resultText) {
    console.log(`Result JSON: ${resultText}`);
  }

  if (!decision || decision === "—" || decision === "error") {
    console.error("Did not receive a valid decision");
    await browser.close();
    process.exit(1);
  }

  await browser.close();
}

main().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
