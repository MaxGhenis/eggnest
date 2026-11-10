import { expect, test, type Page } from "@playwright/test";
import recorded from "../src/test/fixtures/us-drawdown-recorded.json" with { type: "json" };

const { envelope } = recorded.example;
const { sweep } = envelope.outputs.us_drawdown_year_result;

function wholeDollars(amount: number) {
  return `$${Math.round(amount).toLocaleString("en-US")}`;
}

function headlineAt(draw: number) {
  const row = sweep.find((candidate) => candidate.draw === draw);
  if (!row) throw new Error(`The recorded sweep has no row at ${draw}`);
  return `Draw ${wholeDollars(draw)} from your traditional IRA or 401(k) in 2026 and you’ll have ${wholeDollars(row.money_to_spend)} to spend.`;
}

/** Serves the run recorded from the real engine and fails on console errors. */
async function openPage(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.route("**/core/simulate", (route) => route.fulfill({ json: envelope }));
  await page.goto("/us-drawdown");
  await expect(page.getByText(headlineAt(30_000))).toBeVisible();
  return errors;
}

test("shows what the example person keeps and where each dollar goes", async ({ page }) => {
  const errors = await openPage(page);

  await expect(
    page.getByText("These figures describe an example person.", { exact: false }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Where each extra dollar goes" })).toBeVisible();
  await expect(page.getByText("SNAP ends, taking $75 all at once.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Medicare premiums in 2028" })).toBeVisible();
  await expect(page.getByRole("link", { name: "PolicyEngine-US", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("keeps the page out of search results", async ({ page }) => {
  await openPage(page);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
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

  const slider = page.getByRole("slider", { name: "Amount to draw" });
  const draw = Number(await slider.inputValue());
  // Halfway across a curve that runs to $100,000, to the nearest step.
  expect(draw).toBeGreaterThan(45_000);
  expect(draw).toBeLessThan(55_000);
  await expect(page.getByText(`Draw ${wholeDollars(draw)} from your traditional IRA`)).toBeVisible();
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
    await expect(page.getByLabel("Amount to draw in 2026")).toBeInViewport();
  });
});
