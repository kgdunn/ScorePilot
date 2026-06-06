import { expect, test, type Page } from '@playwright/test';

// Regression coverage for the UI shipped across the recent PRs: the version
// badge, the component explorer (live slider, no Apply, totals, R²/Q² table +
// current-row highlight), the colour/size encoding controls, the home-page
// sample list, and inline sample-import progress.
//
// Note: ECharts renders points to a <canvas>, so the brushing/lasso/deselect
// interactions (#61/#70) and point drill-downs (#62) have no addressable DOM
// and are not e2e-testable here; they're exercised manually. Everything with a
// DOM surface is covered below.

// A clean, multi-column numeric dataset so a 2-component PCA fits and
// cross-validation succeeds (giving the explorer a real range and the R²/Q²
// table/curve).
const CSV = [
  'id,a,b,c,d',
  'o1,1.0,2.1,0.5,3.2',
  'o2,2.0,3.9,1.2,2.8',
  'o3,3.1,6.2,0.9,3.6',
  'o4,4.0,7.8,1.8,2.2',
  'o5,5.2,10.1,1.1,4.1',
  'o6,6.0,12.2,2.4,1.9',
  'o7,7.1,13.8,1.6,4.7',
  'o8,8.0,16.1,2.9,1.4',
  'o9,9.2,17.9,2.1,5.2',
  'o10,10.0,20.2,3.4,1.1',
  'o11,11.1,21.8,2.6,5.7',
  'o12,12.0,24.1,3.9,0.8'
].join('\n');

async function fitModel(page: Page) {
  await page.goto('/');
  await page.getByTestId('file-input').setInputFiles({
    name: 'wide.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(CSV)
  });
  await page.waitForURL(/\/datasets\/.+/);
  await expect(page.getByTestId('explorer')).toBeVisible();
  await page.getByTestId('fit-model').click();
  await page.waitForURL(/\/models\/\d+/);
  await expect(page.getByTestId('diagnostics')).toBeVisible();
}

test('the app version badge is shown', async ({ page }) => {
  await page.goto('/');
  const badge = page.locator('.app-version');
  await expect(badge).toBeVisible();
  await expect(badge).toHaveText(/^v\d+\.\d+\.\d+/);
});

test('home lists the bundled demo datasets', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Try a sample dataset' })).toBeVisible();
  // A couple of the bundled samples, including the large one.
  await expect(page.getByTestId('sample-ldpe')).toBeVisible();
  await expect(page.getByTestId('sample-tablet-spectra')).toBeVisible();
});

test('importing a sample shows inline progress on the clicked row', async ({ page }) => {
  await page.goto('/');
  // Delay the import so the loading UI is observable before it navigates away.
  await page.route('**/api/datasets/samples/**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.continue();
  });
  const load = page.getByTestId('sample-food-consumption');
  await load.click();
  await expect(load).toHaveText('Loading…');
  await expect(page.getByRole('progressbar')).toBeVisible();
  // It still completes and navigates to the dataset.
  await page.waitForURL(/\/datasets\/.+/, { timeout: 20_000 });
});

test('component explorer: live slider, totals, no Apply button', async ({ page }) => {
  await fitModel(page);
  const explorer = page.getByTestId('component-explorer');
  await expect(explorer).toBeVisible();

  // Fitted at 2 components.
  const count = page.getByTestId('component-count');
  await expect(count).toHaveText('2');

  // The cumulative totals are shown up top.
  await expect(explorer).toContainText('R²');
  await expect(explorer).toContainText('Q²');

  // No Apply button - the slider applies live (regression guard for its removal).
  await expect(page.getByRole('button', { name: /Apply/ })).toHaveCount(0);

  // The stepper changes the count. (Step down: 2 -> 1.)
  await page.getByRole('button', { name: 'Remove a component' }).click();
  await expect(count).toHaveText('1');
  // Step back up: 1 -> 2.
  await page.getByRole('button', { name: 'Add a component' }).click();
  await expect(count).toHaveText('2');
});

test('component explorer: R²/Q² table highlights the current count', async ({ page }) => {
  await fitModel(page);
  const table = page.locator('.r2-table');
  await expect(table).toBeVisible();

  // The highlighted "current" row matches the fitted count (2).
  const current = table.locator('tr.current');
  await expect(current).toHaveCount(1);
  await expect(current.locator('td').first()).toHaveText('2');

  // Stepping the count moves the highlight to the matching row.
  await page.getByRole('button', { name: 'Remove a component' }).click();
  await expect(page.getByTestId('component-count')).toHaveText('1');
  await expect(table.locator('tr.current td').first()).toHaveText('1');
});

test('scores plot exposes colour/size encoding controls', async ({ page }) => {
  await fitModel(page);
  // Present on the multi-component scores scatter.
  await expect(page.getByTestId('color-by')).toBeVisible();
  await expect(page.getByTestId('size-by')).toBeVisible();
  // The encoding can be switched to a per-observation metric without error.
  await page.getByTestId('color-by').selectOption('spe');
  await expect(page.getByTestId('diagnostics').locator('canvas').first()).toBeVisible();
});
