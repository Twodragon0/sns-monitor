// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Navigation', () => {
  test('theme toggle changes data-theme attribute on html element', async ({ page }) => {
    await page.goto('/');

    const html = page.locator('html');
    const themeToggle = page.locator('.App-header__theme-toggle');
    await expect(themeToggle).toBeVisible();

    // Record current theme
    const initialTheme = await html.getAttribute('data-theme');

    // Click toggle
    await themeToggle.click();

    // Theme should have changed
    const newTheme = await html.getAttribute('data-theme');
    expect(newTheme).not.toBe(initialTheme);

    // Toggle back
    await themeToggle.click();
    const restoredTheme = await html.getAttribute('data-theme');
    expect(restoredTheme).toBe(initialTheme);
  });

  test('AI analysis page navigation button goes to /analysis', async ({ page }) => {
    await page.goto('/');

    const analysisBtn = page.getByRole('link', { name: /AI 분석 페이지로 이동/ }).or(
      page.getByRole('button', { name: /AI 분석 페이지로 이동/ })
    );
    await expect(analysisBtn).toBeVisible({ timeout: 10000 });

    await analysisBtn.click();

    await expect(page).toHaveURL(/\/analysis/, { timeout: 10000 });
  });
});
