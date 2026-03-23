import { test, expect, _electron as electron } from '@playwright/test';
import path from 'node:path';

test.describe('App smoke test', () => {
  test('app launches and shows window', async () => {
    // electron-vite build must be run before this test (see test:e2e script)
    const electronApp = await electron.launch({
      args: [path.join(__dirname, '../../out/main/index.js')],
    });

    // Wait for the first window
    const window = await electronApp.firstWindow();
    expect(window).toBeTruthy();

    // Verify title is defined
    const title = await window.title();
    expect(title).toBeDefined();

    // Wait for loading state to clear (if present)
    await window
      .waitForSelector('text=Loading...', { state: 'hidden', timeout: 10000 })
      .catch(() => {
        // Loading text already gone or never appeared — OK
      });

    // Save screenshot for debugging
    await window.screenshot({ path: 'tests/e2e/screenshots/smoke.png' });

    await electronApp.close();
  });
});
