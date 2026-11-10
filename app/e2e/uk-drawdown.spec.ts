import { expect, test, type Page } from "@playwright/test";
import recorded from "../src/test/fixtures/uk-drawdown-recorded.json" with { type: "json" };

const { envelope } = recorded.example;
const { sweep } = envelope.outputs.uk_drawdown_year_result;

function wholePounds(amount: number) {
  return `£${Math.round(amount).toLocaleString("en-GB")}`;
}

function headlineAt(draw: number) {
  const row = sweep.find((candidate) => candidate.draw === draw);
  if (!row) throw new Error(`The recorded sweep has no row at ${draw}`);
  return `Draw ${wholePounds(draw)} from your pension pot in 2026/27 and you’ll have ${wholePounds(row.money_to_spend)} to spend.`;
}

/** Serves the run recorded from the real engine and fails on console errors. */
async function openPage(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.route("**/core/simulate", (route) => route.fulfill({ json: envelope }));
  await page.goto("/uk-drawdown");
  await expect(page.getByText(headlineAt(2_500))).toBeVisible();
  return errors;
}

test("shows what the example person keeps and where each pound goes", async ({ page }) => {
  const errors = await openPage(page);

  await expect(page.getByText("These figures describe an example person.", { exact: false })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Where each extra pound goes" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Axiom rules engine" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("dragging across the curve sets the draw", async ({ page }) => {
  await openPage(page);
  const surface = page.getByTestId("curve-surface");
  await surface.scrollIntoViewIfNeeded();
  const box = await surface.boundingBox();
  if (!box) throw new Error("The curve has no layout box");

  await page.mouse.move(box.x + box.width * 0.2, box.y + 40);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.5, box.y + 40, { steps: 5 });

  await expect(page.getByRole("slider", { name: "Amount to draw in the tax year" })).toHaveValue("5000");
  await expect(page.getByText(headlineAt(5_000))).toBeVisible();
  await page.mouse.up();
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("fits the screen and jumps from the result to the form", async ({ page }) => {
    await openPage(page);

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBe(0);

    await page.getByRole("link", { name: "Change your figures" }).click();
    await expect(page.getByLabel("Amount to draw in 2026/27")).toBeInViewport();
  });
});
