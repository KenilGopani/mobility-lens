import { defineConfig, devices } from '@playwright/test';
const fixture = process.env.E2E_FIXTURE === '1';
const api =
  process.env.E2E_API_URL ?? (fixture ? 'http://127.0.0.1:8011' : 'http://127.0.0.1:8000');
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5175',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    ...(fixture
      ? [
          {
            command: '../backend/.venv/bin/python tests/browser_fixture.py',
            url: `${api}/health`,
            reuseExistingServer: false,
          },
        ]
      : []),
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5175 --strictPort',
      url: 'http://127.0.0.1:5175',
      env: { VITE_API_BASE_URL: api },
      reuseExistingServer: false,
    },
  ],
});
