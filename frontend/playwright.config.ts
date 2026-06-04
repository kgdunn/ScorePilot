import { defineConfig, devices } from '@playwright/test';

// End-to-end tests run against the packaged app: the Python backend serving the
// built Svelte bundle (production-like, single origin). The webServer command
// builds the frontend, then boots uvicorn on port 4173.
const PORT = 4173;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['list']] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure'
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run build && cd .. && uv run scorepilot --host 127.0.0.1 --port ${PORT} --no-browser`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000
  }
});
