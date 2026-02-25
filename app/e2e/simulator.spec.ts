import { test, expect } from '@playwright/test';

test.describe('Simulator Wizard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/simulator');
    // Dismiss the PersonaPicker by clicking "Start from scratch"
    await page.click('button:has-text("Start from scratch")');
    // Wait for wizard to appear
    await expect(page.locator('[role="form"][aria-label="Simulation setup wizard"]')).toBeVisible();
  });

  test('loads the simulator page', async ({ page }) => {
    // Check header elements
    await expect(page.locator('header')).toBeVisible();
    await expect(page.getByText('Financial simulator', { exact: false })).toBeVisible();

    // Check wizard is visible
    await expect(page.locator('[role="form"][aria-label="Simulation setup wizard"]')).toBeVisible();
  });

  test('displays wizard with progress indicators', async ({ page }) => {
    // Check all step indicators are present in the wizard nav
    const stepIndicators = page.locator('nav[aria-label="Wizard steps"] button');
    await expect(stepIndicators).toHaveCount(6);

    // First step should be current
    await expect(stepIndicators.first()).toHaveAttribute('aria-current', 'step');
  });

  test('navigates through wizard steps', async ({ page }) => {
    // Step 1: About you
    await expect(page.getByRole('heading', { level: 2, name: 'About you' })).toBeVisible();

    // Check default values are present
    const currentAgeInput = page.locator('input[type="number"]').first();
    await expect(currentAgeInput).toHaveValue('65');

    // Click Next
    await page.getByRole('button', { name: 'Go to next step' }).click();

    // Step 2: Your money
    await expect(page.getByRole('heading', { level: 2, name: 'Your money' })).toBeVisible();

    // Click Next
    await page.getByRole('button', { name: 'Go to next step' }).click();

    // Step 3: Income sources
    await expect(page.getByRole('heading', { level: 2, name: 'Income sources' })).toBeVisible();

    // Click Next
    await page.getByRole('button', { name: 'Go to next step' }).click();

    // Step 4: Spouse
    await expect(page.getByRole('heading', { level: 2, name: 'Spouse' })).toBeVisible();

    // Click Next
    await page.getByRole('button', { name: 'Go to next step' }).click();

    // Step 5: Annuity
    await expect(page.getByRole('heading', { level: 2, name: 'Annuity' })).toBeVisible();

    // Click Next
    await page.getByRole('button', { name: 'Go to next step' }).click();

    // Step 6: Review
    await expect(page.getByRole('heading', { level: 2, name: 'Review' })).toBeVisible();
  });

  test('can navigate back through steps', async ({ page }) => {
    // Go to step 2
    await page.getByRole('button', { name: 'Go to next step' }).click();
    await expect(page.getByRole('heading', { level: 2, name: 'Your money' })).toBeVisible();

    // Go back to step 1
    await page.getByRole('button', { name: 'Go to previous step' }).click();
    await expect(page.getByRole('heading', { level: 2, name: 'About you' })).toBeVisible();

    // Back button should be disabled on first step
    await expect(page.getByRole('button', { name: 'Go to previous step' })).toBeDisabled();
  });

  test('displays correct step counter', async ({ page }) => {
    await expect(page.getByText('1 / 6')).toBeVisible();

    await page.getByRole('button', { name: 'Go to next step' }).click();
    await expect(page.getByText('2 / 6')).toBeVisible();

    await page.getByRole('button', { name: 'Go to next step' }).click();
    await expect(page.getByText('3 / 6')).toBeVisible();
  });

  test('can click on step indicators to navigate', async ({ page }) => {
    // Go to step 2 first
    await page.getByRole('button', { name: 'Go to next step' }).click();

    // Click back to step 1 using indicator
    await page.getByRole('button', { name: /Step 1:.*completed/i }).click();
    await expect(page.getByRole('heading', { level: 2, name: 'About you' })).toBeVisible();
  });

  test('updates portfolio value input', async ({ page }) => {
    // Go to "Your money" step
    await page.getByRole('button', { name: 'Go to next step' }).click();
    await expect(page.getByRole('heading', { level: 2, name: 'Your money' })).toBeVisible();

    // Find portfolio input
    const portfolioInput = page.locator('input[type="number"]').first();
    await portfolioInput.clear();
    await portfolioInput.fill('750000');
    await expect(portfolioInput).toHaveValue('750000');
  });

  test('can enable spouse option', async ({ page }) => {
    // Navigate to Spouse step
    for (let i = 0; i < 3; i++) {
      await page.getByRole('button', { name: 'Go to next step' }).click();
    }

    await expect(page.getByRole('heading', { level: 2, name: 'Spouse' })).toBeVisible();

    // Check the checkbox
    const checkbox = page.locator('input[type="checkbox"]').first();
    await expect(checkbox).not.toBeChecked();

    await checkbox.check();
    await expect(checkbox).toBeChecked();

    // Spouse fields should now be visible
    await expect(page.getByText('Spouse age')).toBeVisible();
    await expect(page.getByText('Spouse monthly Social Security')).toBeVisible();
  });

  test('can enable annuity comparison option', async ({ page }) => {
    // Navigate to Annuity step
    for (let i = 0; i < 4; i++) {
      await page.getByRole('button', { name: 'Go to next step' }).click();
    }

    await expect(page.getByRole('heading', { level: 2, name: 'Annuity' })).toBeVisible();

    // Check the checkbox
    const checkbox = page.locator('input[type="checkbox"]').first();
    await expect(checkbox).not.toBeChecked();

    await checkbox.check();
    await expect(checkbox).toBeChecked();

    // Annuity fields should now be visible
    await expect(page.getByText('Monthly annuity payment')).toBeVisible();
    await expect(page.getByText('Annuity type')).toBeVisible();
  });

  test('review step shows summary of inputs', async ({ page }) => {
    // Navigate to Review step
    for (let i = 0; i < 5; i++) {
      await page.getByRole('button', { name: 'Go to next step' }).click();
    }

    await expect(page.getByRole('heading', { level: 2, name: 'Review' })).toBeVisible();

    // Check review content is visible
    const wizard = page.locator('[role="form"][aria-label="Simulation setup wizard"]');
    await expect(wizard).toContainText('65 to 95'); // Age range
    await expect(wizard).toContainText('CA'); // State
    await expect(wizard).toContainText('$500K'); // Portfolio
  });

  test('run simulation button is shown on review step', async ({ page }) => {
    // Navigate to Review step
    for (let i = 0; i < 5; i++) {
      await page.getByRole('button', { name: 'Go to next step' }).click();
    }

    await expect(page.getByRole('heading', { level: 2, name: 'Review' })).toBeVisible();

    // Button should say "Run simulation"
    await expect(page.getByRole('button', { name: 'Run simulation' })).toBeVisible();
  });

  test('state dropdown has all US states', async ({ page }) => {
    const stateSelect = page.locator('select').filter({ has: page.locator('option[value="CA"]') });
    await expect(stateSelect).toBeVisible();

    // Check default selection
    await expect(stateSelect).toHaveValue('CA');

    // Change to NY and verify
    await stateSelect.selectOption('NY');
    await expect(stateSelect).toHaveValue('NY');
  });

  test('filing status dropdown has correct options', async ({ page }) => {
    const filingSelect = page.locator('select').filter({ has: page.locator('option[value="single"]') });
    await expect(filingSelect).toBeVisible();

    // Check default is single
    await expect(filingSelect).toHaveValue('single');

    // Can change to married
    await filingSelect.selectOption('married_filing_jointly');
    await expect(filingSelect).toHaveValue('married_filing_jointly');
  });

  test('gender dropdown has male and female options', async ({ page }) => {
    const genderSelect = page.locator('select').filter({ has: page.locator('option[value="male"]') }).first();
    await expect(genderSelect).toBeVisible();

    // Default is male
    await expect(genderSelect).toHaveValue('male');

    // Can change to female
    await genderSelect.selectOption('female');
    await expect(genderSelect).toHaveValue('female');
  });
});
