// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('UI Components & Design System', () => {
  
  test('should display proper HIG-inspired design elements', async ({ page }) => {
    await page.goto('/chat');
    
    // Check if Inter font is loaded
    const fontFamily = await page.evaluate(() => {
      return getComputedStyle(document.body).fontFamily;
    });
    expect(fontFamily).toContain('Inter');
    
    // Check CSS custom properties are applied
    const primaryColor = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim();
    });
    expect(primaryColor).toBe('hsl(210, 100%, 50%)');
  });

  test('should have consistent button styling', async ({ page }) => {
    await page.goto('/chat');
    
    const submitButton = page.locator('button[type="submit"]');
    
    // Check button classes
    await expect(submitButton).toHaveClass(/btn/);
    await expect(submitButton).toHaveClass(/btn-primary/);
    
    // Check minimum touch target size (44px for accessibility)
    const buttonBox = await submitButton.boundingBox();
    expect(buttonBox?.height).toBeGreaterThanOrEqual(44);
  });

  test('should display cards with proper styling', async ({ page }) => {
    await page.goto('/report');
    
    // Check summary cards
    const summaryCards = page.locator('.summary-card');
    await expect(summaryCards.first()).toBeVisible();
    
    // Check card shadows and borders
    const cardStyle = await summaryCards.first().evaluate((el) => {
      const styles = getComputedStyle(el);
      return {
        borderRadius: styles.borderRadius,
        boxShadow: styles.boxShadow,
        padding: styles.padding
      };
    });
    
    expect(cardStyle.borderRadius).toBeTruthy();
    expect(cardStyle.boxShadow).toBeTruthy();
    expect(cardStyle.padding).toBeTruthy();
  });

  test('should have proper color scheme consistency', async ({ page }) => {
    await page.goto('/profile');
    
    // Check theme color meta tag
    const themeColor = await page.getAttribute('meta[name="theme-color"]', 'content');
    expect(themeColor).toBe('#0066ff');
    
    // Check background colors are consistent
    const bgColor = await page.evaluate(() => {
      return getComputedStyle(document.body).backgroundColor;
    });
    expect(bgColor).toBeTruthy();
  });

  test('should display icons and emojis correctly', async ({ page }) => {
    await page.goto('/chat');
    
    // Check category select has emoji icons
    await page.click('#category');
    const foodOption = page.locator('#category option[value="food"]');
    await expect(foodOption).toContainText('🍽️');
    
    // Navigate to other pages to check navigation icons
    await page.goto('/report');
    await expect(page.locator('.nav-icon')).toContainText('📊');
    
    await page.goto('/challenge');
    await expect(page.locator('.nav-icon')).toContainText('🎯');
  });

  test('should have proper spacing and typography', async ({ page }) => {
    await page.goto('/chat');
    
    // Check hero title styling
    const heroTitle = page.locator('.hero-title');
    await expect(heroTitle).toBeVisible();
    
    const titleStyles = await heroTitle.evaluate((el) => {
      const styles = getComputedStyle(el);
      return {
        fontSize: styles.fontSize,
        fontWeight: styles.fontWeight,
        marginBottom: styles.marginBottom
      };
    });
    
    expect(titleStyles.fontSize).toBeTruthy();
    expect(titleStyles.fontWeight).toBe('700');
    expect(titleStyles.marginBottom).toBeTruthy();
  });

  test('should handle form states correctly', async ({ page }) => {
    await page.goto('/chat');
    
    const amountField = page.locator('#amount');
    
    // Check focus state
    await amountField.focus();
    const focusedStyles = await amountField.evaluate((el) => {
      const styles = getComputedStyle(el);
      return {
        borderColor: styles.borderColor,
        outline: styles.outline
      };
    });
    
    expect(focusedStyles.borderColor).toBeTruthy();
  });

  test('should display proper loading states', async ({ page }) => {
    await page.goto('/chat');
    
    // Check loading spinner in entries section
    const loadingSpinner = page.locator('.loading-spinner');
    await expect(loadingSpinner).toBeVisible();
    
    // Check loading state styling
    const spinnerStyles = await loadingSpinner.evaluate((el) => {
      const styles = getComputedStyle(el);
      return {
        width: styles.width,
        height: styles.height,
        borderRadius: styles.borderRadius,
        animation: styles.animation
      };
    });
    
    expect(spinnerStyles.width).toBe('20px');
    expect(spinnerStyles.height).toBe('20px');
    expect(spinnerStyles.borderRadius).toBe('50%');
    expect(spinnerStyles.animation).toContain('spin');
  });

  test('should have accessible contrast ratios', async ({ page }) => {
    await page.goto('/profile');
    
    // Check text contrast on various elements
    const textElement = page.locator('.hero-title');
    const textStyles = await textElement.evaluate((el) => {
      const styles = getComputedStyle(el);
      return {
        color: styles.color,
        backgroundColor: styles.backgroundColor
      };
    });
    
    // Basic check that colors are defined
    expect(textStyles.color).toBeTruthy();
  });

  test('should handle safe area insets for mobile devices', async ({ page }) => {
    // Set iPhone viewport with safe areas
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/chat');
    
    // Check if bottom navigation accounts for safe areas
    const bottomNav = page.locator('.bottom-nav');
    await expect(bottomNav).toBeVisible();
    
    // Check if app container has proper padding
    const appContainer = page.locator('.app-container');
    const containerStyles = await appContainer.evaluate((el) => {
      const styles = getComputedStyle(el);
      return {
        paddingBottom: styles.paddingBottom
      };
    });
    
    expect(containerStyles.paddingBottom).toBeTruthy();
  });

  test('should display proper grid layouts', async ({ page }) => {
    await page.goto('/report');
    
    // Check summary grid layout
    const summaryGrid = page.locator('.summary-grid');
    await expect(summaryGrid).toBeVisible();
    
    const gridStyles = await summaryGrid.evaluate((el) => {
      const styles = getComputedStyle(el);
      return {
        display: styles.display,
        gridTemplateColumns: styles.gridTemplateColumns,
        gap: styles.gap
      };
    });
    
    expect(gridStyles.display).toBe('grid');
    expect(gridStyles.gap).toBeTruthy();
  });

  test('should have proper z-index layering', async ({ page }) => {
    await page.goto('/chat');
    
    // Check bottom navigation z-index
    const bottomNav = page.locator('.bottom-nav');
    const navZIndex = await bottomNav.evaluate((el) => {
      return getComputedStyle(el).zIndex;
    });
    
    expect(parseInt(navZIndex)).toBeGreaterThan(50); // Should be above content
  });

});