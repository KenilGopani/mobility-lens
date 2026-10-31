import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

test.use({
  viewport: { width: 1440, height: 1000 },
  video: { mode: 'on', size: { width: 1440, height: 1000 } },
});
test('record the real-data decision workflow', async ({ page }) => {
  test.skip(
    process.env.RECORD_DEMO !== '1',
    'Opt-in portfolio capture; uses the real API and real city snapshots.',
  );
  test.setTimeout(60_000);
  const output = path.resolve('../docs/screenshots');
  await fs.mkdir(output, { recursive: true });
  const start = performance.now();
  await page.goto('/');
  await expect(page.getByRole('rowheader', { name: 'Foster City', exact: true })).toBeVisible();
  const usefulRenderMs = performance.now() - start;
  await expect(
    page.getByRole('heading', { name: 'Behind the recommendation', exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(1500); // Intentional pacing for the recorded walkthrough.
  await page.screenshot({ path: path.join(output, 'overview.png'), fullPage: true });
  await page.getByRole('link', { name: 'Interactive Map', exact: true }).click();
  await page
    .getByRole('combobox', { name: 'Service area', exact: true })
    .selectOption({ label: 'Mountain View' });
  await expect(
    page.getByRole('heading', { name: 'Visible cell values', exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(output, 'map.png'), fullPage: true });
  await page.getByRole('link', { name: 'Comparison', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Where the score comes from', exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(output, 'comparison.png'), fullPage: true });
  await page.getByRole('link', { name: 'Operations', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Scenario provenance', exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(output, 'operations.png'), fullPage: true });
  await fs.writeFile(
    path.join(output, 'capture.json'),
    JSON.stringify(
      {
        capturedAt: new Date().toISOString(),
        geographicData: 'Persisted public OSM/Census analysis runs',
        operationsData: 'Explicitly synthetic seeded scenarios',
        usefulOverviewRenderMs: Math.round(usefulRenderMs),
      },
      null,
      2,
    ),
  );
  const video = page.video();
  await page.close();
  if (video) await video.saveAs(path.resolve('../docs/demo.webm'));
});
