import { expect, test } from '@playwright/test';

// A small dataset with a unique identifier (auto-detected as primary), a missing
// value, and a non-numeric value in a quantitative column - enough to exercise
// import, the grid, the inspector, data quality, and model fitting.
const CSV = [
  'sample,conc,yield,batch',
  'S1,1.2,90,A',
  'S2,3.4,88,A',
  'S3,,85,B',
  'S4,9.9,oops,B',
  'S5,12.1,80,C',
  'S6,7.4,79,C'
].join('\n');

async function importDataset(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.getByTestId('file-input').setInputFiles({
    name: 'demo.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(CSV)
  });
  await page.waitForURL(/\/datasets\/.+/);
  await expect(page.getByTestId('explorer')).toBeVisible();
}

test('import a dataset and land on the explorer grid', async ({ page }) => {
  await importDataset(page);
  // The grid header shows every column.
  for (const col of ['sample', 'conc', 'yield', 'batch']) {
    await expect(page.locator(`[data-col="${col}"]`)).toBeVisible();
  }
});

test('data-quality panel flags the invalid value', async ({ page }) => {
  await importDataset(page);
  const quality = page.getByTestId('quality');
  await expect(quality).toContainText('Primary id unique');
  await expect(quality).toContainText('flagged columns');
  // The text column with "oops" in a numeric column is flagged as invalid.
  await expect(quality).toContainText('yield');
});

test('variable inspector renders a histogram', async ({ page }) => {
  await importDataset(page);
  await page.locator('[data-col="conc"]').click();
  const inspector = page.getByTestId('inspector');
  await expect(inspector).toBeVisible();
  await expect(inspector).toContainText('conc');
  // ECharts renders the histogram to a canvas.
  await expect(page.getByTestId('hist-chart').locator('canvas')).toBeVisible();
});

test('assigning an X role and excluding a row update the status', async ({ page }) => {
  await importDataset(page);
  await page.locator('[data-col="conc"]').click();
  await page.getByRole('button', { name: 'X', exact: true }).click();
  await expect(page.getByTestId('ribbon-status')).toContainText('X: 1');

  await page.locator('.dg-cell.c-id').first().click();
  await expect(page.getByTestId('ribbon-status')).toContainText('excluded rows: 1');
});

test('arrow keys move the focused cell and follow the selected column', async ({ page }) => {
  await importDataset(page);
  // Click a cell in the "yield" column (value 90 is unique to it).
  await page.getByText('90', { exact: true }).click();
  const inspector = page.getByTestId('inspector');
  await expect(inspector).toContainText('yield');
  // Arrow left moves the focused cell one column and the inspector follows.
  await page.keyboard.press('ArrowLeft');
  await expect(inspector).toContainText('conc');
});

test('fit a PCA model and see it in the Hangar with diagnostics', async ({ page }) => {
  await importDataset(page);
  await page.getByTestId('fit-model').click();

  await page.waitForURL(/\/models\/\d+/);
  await expect(page.getByTestId('diagnostics')).toBeVisible();
  // Diagnostics charts render to canvases.
  await expect(page.getByTestId('diagnostics').locator('canvas').first()).toBeVisible();

  await page.goto('/models');
  await expect(page.getByRole('heading', { name: 'Hangar' })).toBeVisible();
  await expect(page.locator('ul.models li').first()).toBeVisible();
});
