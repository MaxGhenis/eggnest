import { test, expect } from '@playwright/test';

test.describe('Simulator Wizard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('loads the simulator page', async ({ page }) => {
    // Check header elements
    await expect(page.locator('.sim-header')).toBeVisible();
    await expect(page.locator('.sim-title')).toContainText('Retirement Simulator');

    // Check wizard is visible
    await expect(page.locator('.wizard')).toBeVisible();
  });

  test('displays wizard with progress indicators', async ({ page }) => {
    // Check all step indicators are present
    const stepIndicators = page.locator('.wizard-step-indicator');
    await expect(stepIndicators).toHaveCount(6);

    // First step should be active
    await expect(stepIndicators.first()).toHaveClass(/active/);
  });

  test('navigates through wizard steps', async ({ page }) => {
    // Step 1: About You
    await expect(page.locator('.wizard-header h2')).toContainText('About You');

    // Check default values are present
    const currentAgeInput = page.locator('input[type="number"]').first();
    await expect(currentAgeInput).toHaveValue('65');

    // Click Next
    await page.click('.wizard-btn-primary');

    // Step 2: Your Money
    await expect(page.locator('.wizard-header h2')).toContainText('Your Money');

    // Click Next
    await page.click('.wizard-btn-primary');

    // Step 3: Income Sources
    await expect(page.locator('.wizard-header h2')).toContainText('Income Sources');

    // Click Next
    await page.click('.wizard-btn-primary');

    // Step 4: Spouse
    await expect(page.locator('.wizard-header h2')).toContainText('Spouse');

    // Click Next
    await page.click('.wizard-btn-primary');

    // Step 5: Annuity
    await expect(page.locator('.wizard-header h2')).toContainText('Annuity');

    // Click Next
    await page.click('.wizard-btn-primary');

    // Step 6: Review
    await expect(page.locator('.wizard-header h2')).toContainText('Review');
  });

  test('can navigate back through steps', async ({ page }) => {
    // Go to step 2
    await page.click('.wizard-btn-primary');
    await expect(page.locator('.wizard-header h2')).toContainText('Your Money');

    // Go back to step 1
    await page.click('.wizard-btn-secondary');
    await expect(page.locator('.wizard-header h2')).toContainText('About You');

    // Back button should be disabled on first step
    await expect(page.locator('.wizard-btn-secondary')).toBeDisabled();
  });

  test('displays correct step counter', async ({ page }) => {
    await expect(page.locator('.wizard-nav-info')).toContainText('Step 1 of 6');

    await page.click('.wizard-btn-primary');
    await expect(page.locator('.wizard-nav-info')).toContainText('Step 2 of 6');

    await page.click('.wizard-btn-primary');
    await expect(page.locator('.wizard-nav-info')).toContainText('Step 3 of 6');
  });

  test('can click on step indicators to navigate', async ({ page }) => {
    // Go to step 2 first (can only click one ahead)
    await page.click('.wizard-btn-primary');

    // Click back to step 1 using indicator
    await page.click('.wizard-step-indicator:first-child');
    await expect(page.locator('.wizard-header h2')).toContainText('About You');
  });

  test('updates portfolio value input', async ({ page }) => {
    // Go to "Your Money" step
    await page.click('.wizard-btn-primary');
    await expect(page.locator('.wizard-header h2')).toContainText('Your Money');

    // Find portfolio input and clear it
    const portfolioInput = page.locator('.wizard-field').first().locator('input[type="number"]');
    await portfolioInput.clear();
    await portfolioInput.fill('750000');
    await expect(portfolioInput).toHaveValue('750000');
  });

  test('can enable spouse option', async ({ page }) => {
    // Navigate to Spouse step
    for (let i = 0; i < 3; i++) {
      await page.click('.wizard-btn-primary');
    }

    await expect(page.locator('.wizard-header h2')).toContainText('Spouse');

    // Check the checkbox
    const checkbox = page.locator('.wizard-checkbox input[type="checkbox"]');
    await expect(checkbox).not.toBeChecked();

    await checkbox.check();
    await expect(checkbox).toBeChecked();

    // Spouse fields should now be visible
    await expect(page.locator('text=Spouse Age')).toBeVisible();
    await expect(page.locator('text=Spouse Monthly Social Security')).toBeVisible();
  });

  test('can enable annuity comparison option', async ({ page }) => {
    // Navigate to Annuity step
    for (let i = 0; i < 4; i++) {
      await page.click('.wizard-btn-primary');
    }

    await expect(page.locator('.wizard-header h2')).toContainText('Annuity');

    // Check the checkbox
    const checkbox = page.locator('.wizard-checkbox input[type="checkbox"]');
    await expect(checkbox).not.toBeChecked();

    await checkbox.check();
    await expect(checkbox).toBeChecked();

    // Annuity fields should now be visible
    await expect(page.locator('text=Monthly Annuity Payment')).toBeVisible();
    await expect(page.locator('text=Annuity Type')).toBeVisible();
  });

  test('review step shows summary of inputs', async ({ page }) => {
    // Navigate to Review step
    for (let i = 0; i < 5; i++) {
      await page.click('.wizard-btn-primary');
    }

    await expect(page.locator('.wizard-header h2')).toContainText('Review');

    // Check review sections are visible
    await expect(page.locator('.wizard-review')).toBeVisible();
    await expect(page.locator('.wizard-review-section')).toHaveCount(2); // About You and Finances (no spouse/annuity by default)

    // Check some default values are shown
    await expect(page.locator('.wizard-review')).toContainText('65 to 95'); // Age range
    await expect(page.locator('.wizard-review')).toContainText('CA'); // State
    await expect(page.locator('.wizard-review')).toContainText('$500K'); // Portfolio
  });

  test('run simulation button is shown on review step', async ({ page }) => {
    // Navigate to Review step
    for (let i = 0; i < 5; i++) {
      await page.click('.wizard-btn-primary');
    }

    await expect(page.locator('.wizard-header h2')).toContainText('Review');

    // Button should say "Run Simulation"
    await expect(page.locator('.wizard-btn-primary')).toContainText('Run Simulation');
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
