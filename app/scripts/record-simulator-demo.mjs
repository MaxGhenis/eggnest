import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  assertDemoScenarioConsistency,
  clickAndPause,
  createMockTracker,
  fillAndPause,
  fulfillJson,
  fulfillSse,
  installDemoCursor,
  pause,
  resolveDemoConfig,
  selectOptionAndPause,
  withRecordedPage,
} from "./demoHarness.mjs";
import {
  mockHistoricalBacktestResult,
  mockRothOptimizationResult,
  mockSimulationResult,
} from "./record-simulator-demo.fixtures.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "../..");
const outputDir = path.join(repoRoot, "output", "playwright");
const targetPath = path.join(outputDir, "eggnest-simulator-roth-demo.webm");

async function ensureOutputDir() {
  await fs.mkdir(outputDir, { recursive: true });
  await fs.rm(targetPath, { force: true });
}

async function recordDemo() {
  await ensureOutputDir();
  console.log("stage:setup");

  assertDemoScenarioConsistency({
    simulationResult: mockSimulationResult,
    historicalBacktestResult: mockHistoricalBacktestResult,
    rothOptimizationResult: mockRothOptimizationResult,
  });

  const { simulatorUrl } = resolveDemoConfig();
  const mockTracker = createMockTracker(["simulate", "backtest", "optimize"]);

  const { video } = await withRecordedPage({ outputDir }, async ({ context, page }) => {
    await context.route("**/simulate/stream", async (route) => {
      mockTracker.hit("simulate");
      console.log("mock:simulate");
      await fulfillSse(
        route,
        [
          { type: "progress", year: 4, total_years: 11 },
          { type: "progress", year: 8, total_years: 11 },
          { type: "complete", result: mockSimulationResult },
        ],
        900,
      );
    });
    await context.route("**/backtest/historical", async (route) => {
      mockTracker.hit("backtest");
      console.log("mock:backtest");
      await fulfillJson(route, mockHistoricalBacktestResult, 700);
    });
    await context.route("**/optimize-roth-conversions", async (route) => {
      mockTracker.hit("optimize");
      console.log("mock:optimize");
      await fulfillJson(route, mockRothOptimizationResult, 900);
    });

    console.log("stage:load-simulator");
    await page.goto(simulatorUrl, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");
    await installDemoCursor(page);
    await pause(page, 1200);

    console.log("stage:start-wizard");
    await clickAndPause(
      page.getByRole("button", { name: /Start from scratch with your own numbers/i }),
      page,
      900,
    );

    const ageInputs = page.locator('input[type="number"]');
    await fillAndPause(ageInputs.nth(0), 64, page);
    await fillAndPause(ageInputs.nth(1), 75, page, 900);
    if ((await ageInputs.nth(0).inputValue()) !== "64") {
      throw new Error("Current age input did not land on 64 during demo recording");
    }
    if ((await ageInputs.nth(1).inputValue()) !== "75") {
      throw new Error("Planning-to-age input did not land on 75 during demo recording");
    }

    await clickAndPause(page.getByRole("button", { name: /Go to next step/i }), page, 900);
    await clickAndPause(page.getByRole("button", { name: /By account type/i }), page, 900);

    for (let i = 0; i < 3; i += 1) {
      await clickAndPause(page.getByRole("button", { name: /Add a new holding/i }), page, 350);
    }

    await selectOptionAndPause(page.locator("#account-type-0"), "taxable", page, 300);
    await selectOptionAndPause(page.locator("#fund-0"), "sp500", page, 300);
    await fillAndPause(page.locator("#balance-0"), 150000, page);
    await fillAndPause(page.locator("#cost-basis-0"), 120000, page, 500);

    await selectOptionAndPause(page.locator("#account-type-1"), "traditional_401k", page, 300);
    await selectOptionAndPause(page.locator("#fund-1"), "treasury", page, 300);
    await fillAndPause(page.locator("#balance-1"), 400000, page, 500);

    await selectOptionAndPause(page.locator("#account-type-2"), "roth_ira", page, 300);
    await selectOptionAndPause(page.locator("#fund-2"), "sp500", page, 300);
    await fillAndPause(page.locator("#balance-2"), 100000, page, 1000);

    console.log("stage:review");
    await clickAndPause(page.getByRole("button", { name: /Go to next step/i }), page, 700);
    const employmentIncomeInput = page
      .locator('label:has-text("Current employment income")')
      .locator("xpath=..")
      .locator('input[type="number"]')
      .first();
    await fillAndPause(employmentIncomeInput, 0, page, 700);
    await clickAndPause(page.getByRole("button", { name: /Go to next step/i }), page, 700);
    await clickAndPause(page.getByRole("button", { name: /Go to next step/i }), page, 700);
    await clickAndPause(page.getByRole("button", { name: /Go to next step/i }), page, 700);

    console.log("stage:simulate");
    await clickAndPause(page.getByRole("button", { name: /Run simulation/i }), page, 1200);

    await page.getByText(/Modeled outcome/i).waitFor({ timeout: 180000 });
    await pause(page, 2200);

    console.log("stage:deeper-analysis");
    await clickAndPause(page.getByRole("button", { name: /Deeper analysis/i }), page, 1200);
    await page.getByText(/Monte Carlo vs historical cohorts/i).waitFor({ timeout: 120000 });
    await pause(page, 1500);

    const rothHeading = page.getByText(/How do Roth conversion paths compare/i);
    await rothHeading.scrollIntoViewIfNeeded();
    await pause(page, 600);

    console.log("stage:optimize-roth");
    await clickAndPause(
      page.getByRole("button", { name: /Search Roth conversion scenarios/i }),
      page,
      1200,
    );

    await page.getByRole("link", { name: /Open report page/i }).waitFor({ timeout: 180000 });
    await pause(page, 1800);

    console.log("stage:open-report");
    await Promise.all([
      page.waitForURL(/\/simulator\/roth-report\?/),
      clickAndPause(page.getByRole("link", { name: /Open report page/i }), page, 1200),
    ]);

    await page.getByRole("heading", { name: /Saved Roth conversion scenario comparison/i }).waitFor({
      timeout: 120000,
    });
    await pause(page, 1800);
    await page.mouse.wheel(0, 260);
    await pause(page, 900);
    await page.mouse.wheel(0, 260);
    await pause(page, 1100);
    await page.mouse.wheel(0, 220);
    await pause(page, 1800);

    mockTracker.assertAllHit();
  });

  console.log("stage:close");

  const recordedPath = await video.path();
  await fs.copyFile(recordedPath, targetPath);
  return targetPath;
}

recordDemo()
  .then((videoPath) => {
    console.log(videoPath);
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
