import { test, expect } from '@playwright/test';

test('E2E-001: overview ranks areas and explains the leading score', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Executive Overview' })).toBeVisible();
  await expect(page.getByRole('rowheader', { name: 'Foster City', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Behind the recommendation' })).toBeVisible();
  await expect(page.getByRole('img', { name: 'Candidate scores', exact: true })).toBeVisible();
});

test('E2E-002/003: San Jose map loads cells and switches the metric', async ({ page }) => {
  await page.goto('/map');
  await page
    .getByRole('combobox', { name: 'Service area', exact: true })
    .selectOption({ label: 'San Jose' });
  await expect(page.getByRole('heading', { name: 'Visible cell values' })).toBeVisible();
  await page
    .getByRole('combobox', { name: 'Map metric', exact: true })
    .selectOption('road_density');
  await expect(page.getByRole('heading', { name: 'Road density', exact: true })).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Raw value', exact: true })).toBeVisible();
  await page.getByRole('table').getByRole('button').first().click();
  await expect(page.getByText('Boundary overlap', { exact: true })).toBeVisible();
});

test('E2E-004: comparison responds to two-area selection', async ({ page }) => {
  await page.goto('/comparison');
  await page.getByRole('checkbox', { name: 'San Jose', exact: true }).uncheck();
  await expect(page.getByRole('columnheader', { name: 'San Jose', exact: true })).toHaveCount(0);
  await expect(page.getByRole('columnheader', { name: 'Foster City', exact: true })).toBeVisible();
  await expect(
    page.getByRole('columnheader', { name: 'Mountain View', exact: true }),
  ).toBeVisible();
});

test('E2E-005: temporary weights recalculate scores and restore the model', async ({ page }) => {
  await page.goto('/what-if');
  await expect(page.getByRole('rowheader', { name: 'Overall score / 100' })).toBeVisible();
  const original = await page.getByRole('row', { name: /Overall score \/ 100/ }).textContent();
  const slider = page.getByRole('slider', { name: 'Connectivity', exact: true });
  await slider.focus();
  await slider.press('End');
  await expect(slider).toHaveValue('100');
  await expect(page.getByRole('row', { name: /Overall score \/ 100/ })).not.toHaveText(
    original ?? '',
  );
  await page.getByRole('button', { name: 'Restore default model' }).click();
  await expect(slider).toHaveValue('20');
  await expect(page.getByRole('row', { name: /Overall score \/ 100/ })).toHaveText(original ?? '');
  await expect(page.getByText('TEMPORARY ASSUMPTIONS · NOT SAVED')).toBeVisible();
});

test('E2E-006: quality exposes warnings, missing values and provenance', async ({ page }) => {
  await page.goto('/quality');
  await expect(page.getByRole('heading', { name: 'Quality findings' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Missing metric values' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Source & provenance' })).toBeVisible();
  await page.getByRole('combobox', { name: 'Severity', exact: true }).selectOption('warning');
  if (process.env.E2E_FIXTURE === '1')
    await expect(
      page.getByText('Synthetic test warning: review metadata completeness.'),
    ).toBeVisible();
  else await expect(page.getByRole('heading', { name: 'Data Quality', exact: true })).toBeVisible();
});

test('synthetic operations keeps labeling and scenario provenance visible', async ({ page }) => {
  await page.goto('/operations');
  await expect(page.getByRole('note')).toContainText('Synthetic data · simulation only');
  await expect(
    page.getByRole('heading', { name: 'Scenario provenance', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Simulated daily completion', exact: true }),
  ).toBeVisible();
  await page
    .getByRole('combobox', { name: 'Service area', exact: true })
    .selectOption({ label: 'Mountain View' });
  await expect(
    page.getByRole('heading', { name: 'Scenario provenance', exact: true }),
  ).toBeVisible();
});
