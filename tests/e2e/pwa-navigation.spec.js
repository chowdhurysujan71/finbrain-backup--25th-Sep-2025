// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('PWA Navigation & Core Functionality', () => {
  
  test.beforeEach(async ({ page }) => {
    // Start from the home page for each test
    await page.goto('/');
  });

  test('should display navigation correctly on all PWA pages', async ({ page }) => {
    // Test Chat page
    await page.goto('/chat');
    await expect(page.locator('.bottom-nav')).toBeVisible();
    await expect(page.locator('[href="/chat"]')).toHaveClass(/active/);
    await expect(page.locator('h1')).toContainText('Track your expenses');

    // Test Report page
    await page.goto('/report');
    await expect(page.locator('.bottom-nav')).toBeVisible();
    await expect(page.locator('[href="/report"]')).toHaveClass(/active/);
    await expect(page.locator('h1')).toContainText('Your Money Story');

    // Test Profile page
    await page.goto('/profile');
    await expect(page.locator('.bottom-nav')).toBeVisible();
    await expect(page.locator('[href="/profile"]')).toHaveClass(/active/);
    await expect(page.locator('h1')).toContainText('Your Profile');

    // Test Challenge page
    await page.goto('/challenge');
    await expect(page.locator('.bottom-nav')).toBeVisible();
    await expect(page.locator('[href="/challenge"]')).toHaveClass(/active/);
    await expect(page.locator('h1')).toContainText('3-Day Challenge');
  });

  test('should navigate between pages using bottom navigation', async ({ page }) => {
    await page.goto('/chat');
    
    // Navigate to Report
    await page.click('[href="/report"]');
    await expect(page).toHaveURL('/report');
    await expect(page.locator('h1')).toContainText('Your Money Story');
    
    // Navigate to Profile
    await page.click('[href="/profile"]');
    await expect(page).toHaveURL('/profile');
    await expect(page.locator('h1')).toContainText('Your Profile');
    
    // Navigate to Challenge
    await page.click('[href="/challenge"]');
    await expect(page).toHaveURL('/challenge');
    await expect(page.locator('h1')).toContainText('3-Day Challenge');
    
    // Navigate back to Chat
    await page.click('[href="/chat"]');
    await expect(page).toHaveURL('/chat');
    await expect(page.locator('h1')).toContainText('Track your expenses');
  });

  test('should have proper PWA manifest', async ({ page }) => {
    await page.goto('/');
    
    // Check manifest link exists
    const manifestLink = page.locator('link[rel="manifest"]');
    await expect(manifestLink).toBeVisible();
    await expect(manifestLink).toHaveAttribute('href', '/manifest.webmanifest');
    
    // Verify manifest is accessible
    const response = await page.request.get('/manifest.webmanifest');
    expect(response.status()).toBe(200);
    
    const manifest = await response.json();
    expect(manifest.name).toBe('FinBrain');
    expect(manifest.short_name).toBe('FinBrain');
    expect(manifest.display).toBe('standalone');
    expect(manifest.start_url).toBe('/chat');
    expect(manifest.scope).toBe('/');
  });

  test('should load service worker correctly', async ({ page }) => {
    await page.goto('/chat');
    
    // Wait for service worker registration
    await page.waitForTimeout(2000);
    
    // Check if service worker is registered
    const swRegistration = await page.evaluate(() => {
      return navigator.serviceWorker.ready.then(registration => {
        return {
          active: !!registration.active,
          scope: registration.scope
        };
      });
    });
    
    expect(swRegistration.active).toBe(true);
    expect(swRegistration.scope).toContain('localhost:5000');
  });

  test('should display proper meta tags for PWA', async ({ page }) => {
    await page.goto('/chat');
    
    // Check viewport meta tag
    const viewport = page.locator('meta[name="viewport"]');
    await expect(viewport).toHaveAttribute('content', 'width=device-width, initial-scale=1.0, viewport-fit=cover');
    
    // Check theme color
    const themeColor = page.locator('meta[name="theme-color"]');
    await expect(themeColor).toHaveAttribute('content', '#0066ff');
    
    // Check apple-mobile-web-app-capable
    const appleCapable = page.locator('meta[name="apple-mobile-web-app-capable"]');
    await expect(appleCapable).toHaveAttribute('content', 'yes');
    
    // Check apple-mobile-web-app-title
    const appleTitle = page.locator('meta[name="apple-mobile-web-app-title"]');
    await expect(appleTitle).toHaveAttribute('content', 'FinBrain');
  });

  test('should handle offline page gracefully', async ({ page }) => {
    await page.goto('/offline');
    
    // Check offline page content
    await expect(page.locator('h1')).toContainText('You\'re offline');
    await expect(page.locator('.offline-icon')).toBeVisible();
    await expect(page.locator('.offline-title')).toContainText('You\'re offline');
    
    // Check retry functionality exists
    await expect(page.locator('button')).toContainText('Try Again');
    
    // Check offline navigation links
    await expect(page.locator('[href="/chat"]')).toBeVisible();
    await expect(page.locator('[href="/report"]')).toBeVisible();
    await expect(page.locator('[href="/profile"]')).toBeVisible();
  });

  test('should have responsive design on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/chat');
    
    // Check if bottom navigation is visible and properly positioned
    await expect(page.locator('.bottom-nav')).toBeVisible();
    
    // Check if content is properly sized
    const pageContainer = page.locator('.page-container');
    await expect(pageContainer).toBeVisible();
    
    // Check if buttons are touch-friendly (minimum 44px)
    const buttons = page.locator('.btn');
    const buttonCount = await buttons.count();
    
    for (let i = 0; i < buttonCount; i++) {
      const button = buttons.nth(i);
      const box = await button.boundingBox();
      if (box) {
        expect(box.height).toBeGreaterThanOrEqual(36); // Allow some margin
      }
    }
  });

  test('should display icons and assets correctly', async ({ page }) => {
    await page.goto('/chat');
    
    // Check CSS loads
    const cssResponse = await page.request.get('/static/css/app.css');
    expect(cssResponse.status()).toBe(200);
    
    // Check PWA JS loads
    const jsResponse = await page.request.get('/static/js/pwa.js');
    expect(jsResponse.status()).toBe(200);
    
    // Check service worker loads
    const swResponse = await page.request.get('/static/js/sw.js');
    expect(swResponse.status()).toBe(200);
    
    // Check icons exist
    const icon192Response = await page.request.get('/static/icons/icon-192.png');
    expect(icon192Response.status()).toBe(200);
    
    const icon512Response = await page.request.get('/static/icons/icon-512.png');
    expect(icon512Response.status()).toBe(200);
  });

});