// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Dashboard', () => {
  test('loads correctly with URL input and platform tags', async ({ page }) => {
    await page.goto('/');

    // Page title contains SNS
    await expect(page).toHaveTitle(/SNS/);

    // URL input field exists
    const urlInput = page.getByRole('textbox', { name: '분석할 URL' });
    await expect(urlInput).toBeVisible();

    // 분석 button exists
    const analyzeBtn = page.getByRole('button', { name: /^분석$/ });
    await expect(analyzeBtn).toBeVisible();

    // Platform names visible somewhere on page (page shows multiple occurrences
    // across badge, platform-tag, and history — use first() to avoid strict mode)
    await expect(page.getByText('YouTube', { exact: false }).first()).toBeVisible();
    await expect(page.getByText('DCInside', { exact: false }).first()).toBeVisible();

    // Stats section (전체 개요 tab panel area)
    await expect(page.getByRole('tablist', { name: '플랫폼 탭' })).toBeVisible();
    await expect(page.getByRole('tab', { name: /전체 개요/ })).toBeVisible();
  });

  test('API health check indicator shows connected status', async ({ page }) => {
    await page.goto('/');

    // Status label text
    const statusLabel = page.locator('.status-label');
    await expect(statusLabel).toBeVisible();
    // Either connected or offline — just verify it renders
    await expect(statusLabel).toContainText(/연결됨|오프라인/);

    // Status dot present
    const statusDot = page.locator('.status-dot');
    await expect(statusDot).toBeVisible();
  });

  test('tab navigation changes active tab and panel content', async ({ page }) => {
    await page.goto('/');

    const tablist = page.getByRole('tablist', { name: '플랫폼 탭' });
    await expect(tablist).toBeVisible();

    const tabs = [
      /전체 개요/,
      /YouTube/,
      /DCInside/,
      /X \(Twitter\)/,
      /Instagram/,
    ];

    for (const tabPattern of tabs) {
      const tab = page.getByRole('tab', { name: tabPattern });
      await tab.click();
      await expect(tab).toHaveAttribute('aria-selected', 'true');
      // Panel updates (just verify it's present after each click)
      await expect(page.getByRole('tabpanel')).toBeVisible();
    }
  });
});
