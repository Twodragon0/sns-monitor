// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('URL Analyzer', () => {
  test('empty URL keeps analyze button disabled', async ({ page }) => {
    await page.goto('/');

    const urlInput = page.getByRole('textbox', { name: '분석할 URL' });
    const analyzeBtn = page.getByRole('button', { name: /^분석$/ });

    // Clear any pre-filled value
    await urlInput.clear();
    await expect(urlInput).toHaveValue('');

    // Button should be disabled when input is empty
    await expect(analyzeBtn).toBeDisabled();
  });

  test('platform detection shows correct badge for known URLs', async ({ page }) => {
    await page.goto('/');

    const urlInput = page.getByRole('textbox', { name: '분석할 URL' });

    const cases = [
      { url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', badge: 'YouTube' },
      { url: 'https://gall.dcinside.com/mgallery/board/list/?id=example', badge: 'DCInside' },
      { url: 'https://www.reddit.com/r/korea/', badge: 'Reddit' },
      { url: 'https://t.me/example_channel', badge: 'Telegram' },
    ];

    for (const { url, badge } of cases) {
      await urlInput.fill(url);
      // Platform badge/label should appear somewhere in the form area
      const badgeLocator = page.locator('.dash__hero').getByText(badge, { exact: false }).first();
      await expect(badgeLocator).toBeVisible({ timeout: 5000 });
    }
  });
});
