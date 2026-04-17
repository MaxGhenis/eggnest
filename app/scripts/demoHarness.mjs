import { chromium } from "@playwright/test";

const mousePositions = new WeakMap();
const paceMultiplier = Number(process.env.DEMO_PACE_MULTIPLIER || "1.6");
const selectAllShortcut = process.platform === "darwin" ? "Meta+A" : "Control+A";

function scaleTime(ms) {
  return Math.round(ms * paceMultiplier);
}

export function resolveDemoConfig() {
  const appUrl = process.env.DEMO_APP_URL || "http://localhost:5174";
  return {
    appUrl,
    simulatorUrl: new URL("/simulator", appUrl).toString(),
  };
}

export async function pause(page, ms = 700) {
  await page.waitForTimeout(scaleTime(ms));
}

export async function installDemoCursor(page) {
  await page.addStyleTag({
    content: `
      html, body, a, button, input, select, textarea, label, [role="button"] {
        cursor: none !important;
      }

      #eggnest-demo-cursor {
        position: fixed;
        left: 0;
        top: 0;
        width: 18px;
        height: 18px;
        margin-left: -9px;
        margin-top: -9px;
        border-radius: 999px;
        pointer-events: none;
        z-index: 2147483647;
        background: rgba(255, 255, 255, 0.95);
        border: 2px solid rgba(15, 23, 42, 0.92);
        transform: translate(var(--cursor-x, 120px), var(--cursor-y, 120px)) scale(var(--cursor-scale, 1));
        box-shadow:
          0 8px 22px rgba(15, 23, 42, 0.22),
          0 0 0 8px rgba(245, 158, 11, 0.18);
        transition:
          transform 120ms ease,
          box-shadow 120ms ease,
          background 120ms ease,
          opacity 120ms ease;
      }

      #eggnest-demo-cursor.eggnest-demo-cursor-clicking {
        --cursor-scale: 0.86;
        background: rgba(245, 158, 11, 0.95);
        box-shadow:
          0 10px 28px rgba(15, 23, 42, 0.26),
          0 0 0 12px rgba(245, 158, 11, 0.28);
      }
    `,
  });

  await page.evaluate(() => {
    if (document.getElementById("eggnest-demo-cursor")) {
      return;
    }

    const cursor = document.createElement("div");
    cursor.id = "eggnest-demo-cursor";
    document.body.appendChild(cursor);

    const update = (x, y) => {
      cursor.style.setProperty("--cursor-x", `${x}px`);
      cursor.style.setProperty("--cursor-y", `${y}px`);
    };

    document.addEventListener(
      "mousemove",
      (event) => update(event.clientX, event.clientY),
      true,
    );
    document.addEventListener(
      "mousedown",
      () => cursor.classList.add("eggnest-demo-cursor-clicking"),
      true,
    );
    document.addEventListener(
      "mouseup",
      () => cursor.classList.remove("eggnest-demo-cursor-clicking"),
      true,
    );

    update(120, 120);
  });

  mousePositions.set(page, { x: 120, y: 120 });
  await page.mouse.move(120, 120, { steps: 8 });
}

async function moveMouse(page, x, y, steps = 18) {
  const previous = mousePositions.get(page) ?? { x: 120, y: 120 };
  await page.mouse.move(previous.x, previous.y);
  await page.mouse.move(x, y, { steps: Math.max(steps, Math.round(steps * paceMultiplier)) });
  mousePositions.set(page, { x, y });
}

async function moveMouseToLocator(locator, page, steps = 18) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (!box) {
    throw new Error("Could not determine locator bounds for demo mouse movement");
  }

  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await moveMouse(page, x, y, steps);
}

export async function clickAndPause(locator, page, ms = 700) {
  await moveMouseToLocator(locator, page);
  await pause(page, 180);
  await page.mouse.down();
  await page.waitForTimeout(scaleTime(110));
  await page.mouse.up();
  await pause(page, ms);
}

export async function fillAndPause(locator, value, page, ms = 250) {
  await moveMouseToLocator(locator, page);
  await pause(page, 140);
  await page.mouse.click(
    mousePositions.get(page)?.x ?? 120,
    mousePositions.get(page)?.y ?? 120,
    { delay: scaleTime(60) },
  );
  await page.keyboard.press(selectAllShortcut);
  await page.waitForTimeout(scaleTime(80));
  await page.keyboard.type(String(value), { delay: scaleTime(85) });
  await page.waitForTimeout(scaleTime(120));

  let actualValue = await locator.inputValue();
  if (actualValue !== String(value)) {
    await page.keyboard.press(selectAllShortcut);
    await page.waitForTimeout(scaleTime(80));
    await page.keyboard.type(String(value), { delay: scaleTime(85) });
    await page.waitForTimeout(scaleTime(120));
    actualValue = await locator.inputValue();
  }

  if (actualValue !== String(value)) {
    throw new Error(`Demo input mismatch: expected ${value}, got ${actualValue}`);
  }
  await pause(page, ms);
}

export async function selectOptionAndPause(locator, value, page, ms = 250) {
  await moveMouseToLocator(locator, page);
  await pause(page, 120);
  await page.mouse.click(
    mousePositions.get(page)?.x ?? 120,
    mousePositions.get(page)?.y ?? 120,
    { delay: scaleTime(60) },
  );
  await locator.selectOption(value);
  await pause(page, ms);
}

export async function fulfillJson(route, body, delayMs = 0) {
  if (delayMs > 0) {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

export async function fulfillSse(route, events, delayMs = 0) {
  if (delayMs > 0) {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
  const body = events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
  await route.fulfill({
    status: 200,
    contentType: "text/event-stream",
    headers: {
      "cache-control": "no-cache",
      connection: "keep-alive",
    },
    body,
  });
}

export function createMockTracker(names) {
  const hits = Object.fromEntries(names.map((name) => [name, 0]));
  return {
    hit(name) {
      if (!(name in hits)) {
        throw new Error(`Unknown demo mock: ${name}`);
      }
      hits[name] += 1;
    },
    assertAllHit() {
      const missing = Object.entries(hits)
        .filter(([, count]) => count === 0)
        .map(([name]) => name);

      if (missing.length > 0) {
        throw new Error(`Expected demo mocks to be used for: ${missing.join(", ")}`);
      }
    },
    snapshot() {
      return { ...hits };
    },
  };
}

function assertClose(actual, expected, label, tolerance = 1e-9) {
  if (typeof actual !== "number" || typeof expected !== "number") {
    throw new Error(`${label} must be numeric`);
  }
  if (Math.abs(actual - expected) > tolerance) {
    throw new Error(`${label} mismatch: expected ${expected}, got ${actual}`);
  }
}

function findBaselineScenario(rothOptimizationResult) {
  return (
    rothOptimizationResult.results.find(
      (item) => item.scenario_label === rothOptimizationResult.baseline_scenario_label,
    ) ??
    rothOptimizationResult.results.find(
      (item) =>
        item.annual_conversion_amount === rothOptimizationResult.baseline_conversion_amount,
    ) ??
    null
  );
}

export function assertDemoScenarioConsistency({
  simulationResult,
  historicalBacktestResult,
  rothOptimizationResult,
}) {
  const baseline = findBaselineScenario(rothOptimizationResult);
  if (!baseline) {
    throw new Error("Could not find a Roth baseline scenario to validate against the main result");
  }

  assertClose(
    baseline.monte_carlo.success_rate,
    simulationResult.success_rate,
    "Monte Carlo success_rate",
  );
  assertClose(
    baseline.monte_carlo.median_final_value,
    simulationResult.median_final_value,
    "Monte Carlo median_final_value",
  );
  assertClose(
    baseline.monte_carlo.median_final_value_real,
    simulationResult.median_final_value_real,
    "Monte Carlo median_final_value_real",
  );
  assertClose(
    baseline.monte_carlo.total_taxes_median,
    simulationResult.total_taxes_median,
    "Monte Carlo total_taxes_median",
  );
  assertClose(
    baseline.monte_carlo.total_withdrawn_median,
    simulationResult.total_withdrawn_median,
    "Monte Carlo total_withdrawn_median",
  );

  assertClose(
    baseline.historical.success_rate,
    historicalBacktestResult.success_rate,
    "Historical success_rate",
  );
  assertClose(
    baseline.historical.median_final_value,
    historicalBacktestResult.median_final_value,
    "Historical median_final_value",
  );
  assertClose(
    baseline.historical.median_final_value_real,
    historicalBacktestResult.median_final_value_real,
    "Historical median_final_value_real",
  );
  assertClose(
    baseline.historical.total_taxes_median,
    historicalBacktestResult.total_taxes_median,
    "Historical total_taxes_median",
  );
  assertClose(
    baseline.historical.total_withdrawn_median,
    historicalBacktestResult.total_withdrawn_median,
    "Historical total_withdrawn_median",
  );
}

export async function withRecordedPage(
  {
    outputDir,
    viewport = { width: 1512, height: 945 },
    videoSize = { width: 1512, height: 945 },
  },
  run,
) {
  const browser = await chromium.launch({ headless: true });
  let context;
  let page;
  let video;

  try {
    context = await browser.newContext({
      viewport,
      recordVideo: {
        dir: outputDir,
        size: videoSize,
      },
    });
    page = await context.newPage();
    video = page.video();
    await run({ browser, context, page });
  } finally {
    if (context) {
      await context.close().catch(() => {});
    }
    await browser.close().catch(() => {});
  }

  if (!video) {
    throw new Error("Playwright did not produce a video artifact.");
  }

  return { video };
}
