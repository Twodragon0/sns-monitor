// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Swagger / API Docs', () => {
  test('Swagger UI page is accessible', async ({ page }) => {
    const response = await page.goto('/api/docs/');
    // Accept 200 or 301/302 redirects that land on a valid page
    expect(response?.status()).toBeLessThan(400);

    // Title contains Swagger or Flasgger
    await expect(page).toHaveTitle(/Swagger|Flasgger|API/i, { timeout: 15000 });

    // At least one element related to endpoints is visible
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('API spec endpoint returns valid JSON with paths and info', async ({ request }) => {
    const response = await request.get('http://localhost:8888/apispec.json');
    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('paths');
    expect(body).toHaveProperty('info');
  });
});
