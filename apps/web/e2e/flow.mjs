/**
 * Drives the studio against the local API using the system Chrome.
 * Run while both servers are up:
 *   node apps/web/e2e/flow.mjs
 */
import { chromium } from "playwright";
import fs from "node:fs";

const outDir = "/tmp/sticky-shots";
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || "/usr/local/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const failures = [];

page.on("pageerror", (error) => failures.push(`pageerror: ${error.message}`));
page.on("response", (response) => {
  if (response.status() >= 400) failures.push(`${response.status()} ${response.url()}`);
});

await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
await page.getByRole("heading", { name: "Your stickers, wherever you go." }).waitFor();
await page.screenshot({ path: `${outDir}/01-landing.png` });

await page.getByRole("button", { name: "Try an example" }).click();
await page.waitForURL("**/studio");
await page.getByRole("button", { name: "Restore sticker" }).waitFor({ timeout: 20000 });
await page.screenshot({ path: `${outDir}/02-detected.png` });

await page.getByRole("button", { name: "Restore sticker" }).click();
await page.getByRole("img", { name: "Restored sticker" }).waitFor({ timeout: 30000 });
const restoredText = await page.locator("body").innerText();
if (/reflection/i.test(restoredText)) failures.push("false glare warning on the flat example");
await page.screenshot({ path: `${outDir}/03-restored.png` });

await page.getByRole("button", { name: "3 Vector" }).click();
await page.getByRole("button", { name: "logo" }).click();
await page.getByText(/Fidelity/).waitFor({ timeout: 30000 });
await page.screenshot({ path: `${outDir}/04-vector.png` });

await page.getByRole("button", { name: "4 Size" }).click();
const pngResponse = page.waitForResponse((response) => response.url().includes("/api/exports/png") && response.ok());
await page.getByRole("button", { name: "PNG", exact: true }).click();
const png = await pngResponse;
const pngBody = await png.json();
if (!String(pngBody.filename || "").endsWith(".png")) failures.push(`png filename ${pngBody.filename}`);
if (!(pngBody.occupied_width_mm > 0)) failures.push("png missing size");

await page.getByRole("button", { name: "5 Sheet" }).click();
await page.getByRole("button", { name: /Add / }).first().click();
await page.getByRole("button", { name: "Arrange" }).click();
await page.waitForTimeout(500);
const pdfResponse = page.waitForResponse((response) => response.url().includes("/api/exports/sheet") && !response.url().includes("layout") && response.request().method() === "POST");
await page.getByRole("button", { name: "Download PDF" }).click();
const pdf = await pdfResponse;
if (!pdf.ok()) failures.push(`pdf status ${pdf.status()} ${await pdf.text()}`);
else {
  const body = await pdf.json();
  if (body.page_width_mm !== 215.9) failures.push(`page width ${body.page_width_mm}`);
}

await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({ path: `${outDir}/05-mobile.png` });

await browser.close();
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("flow ok");
