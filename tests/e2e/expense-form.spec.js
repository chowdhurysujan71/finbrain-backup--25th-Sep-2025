// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Expense Form Functionality', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/chat');
  });

  test('should display expense form with all required fields', async ({ page }) => {
    // Check form exists
    await expect(page.locator('#expense-form')).toBeVisible();
    
    // Check all form fields
    await expect(page.locator('#amount')).toBeVisible();
    await expect(page.locator('#category')).toBeVisible();
    await expect(page.locator('#description')).toBeVisible();
    
    // Check submit button
    await expect(page.locator('button[type="submit"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Add Expense');
    
    // Check form labels
    await expect(page.locator('label[for="amount"]')).toContainText('Amount');
    await expect(page.locator('label[for="category"]')).toContainText('Category');
    await expect(page.locator('label[for="description"]')).toContainText('Description');
  });

  test('should validate required fields', async ({ page }) => {
    // Try to submit without filling required fields
    await page.click('button[type="submit"]');
    
    // Check if browser validation kicks in (amount is required)
    const amountField = page.locator('#amount');
    const isInvalid = await amountField.evaluate((el) => !el.validity.valid);
    expect(isInvalid).toBe(true);
  });

  test('should accept valid expense input', async ({ page }) => {
    // Fill out the form
    await page.fill('#amount', '250.50');
    await page.selectOption('#category', 'food');
    await page.fill('#description', 'Lunch at restaurant');
    
    // Check values are set correctly
    await expect(page.locator('#amount')).toHaveValue('250.50');
    await expect(page.locator('#category')).toHaveValue('food');
    await expect(page.locator('#description')).toHaveValue('Lunch at restaurant');
    
    // Submit form
    await page.click('button[type="submit"]');
    
    // Form should reset after submission (in demo mode)
    await page.waitForTimeout(1000);
    await expect(page.locator('#amount')).toHaveValue('');
    await expect(page.locator('#description')).toHaveValue('');
  });

  test('should display category options correctly', async ({ page }) => {
    // Click on category dropdown
    await page.click('#category');
    
    // Check default option
    await expect(page.locator('#category option[value=""]')).toContainText('Choose category');
    
    // Check all category options exist
    const expectedCategories = [
      { value: 'food', text: '🍽️ Food & Dining' },
      { value: 'transport', text: '🚗 Transport' },
      { value: 'shopping', text: '🛍️ Shopping' },
      { value: 'bills', text: '💡 Bills & Utilities' },
      { value: 'entertainment', text: '🎬 Entertainment' },
      { value: 'health', text: '🏥 Health & Medical' },
      { value: 'education', text: '📚 Education' },
      { value: 'other', text: '📝 Other' }
    ];
    
    for (const category of expectedCategories) {
      await expect(page.locator(`#category option[value="${category.value}"]`)).toContainText(category.text);
    }
  });

  test('should handle amount input validation', async ({ page }) => {
    const amountField = page.locator('#amount');
    
    // Check input type
    await expect(amountField).toHaveAttribute('type', 'number');
    await expect(amountField).toHaveAttribute('step', '0.01');
    await expect(amountField).toHaveAttribute('min', '0');
    
    // Test negative values are not accepted
    await amountField.fill('-100');
    const isValid = await amountField.evaluate((el) => el.validity.valid);
    expect(isValid).toBe(false);
    
    // Test positive values are accepted
    await amountField.fill('123.45');
    const isValidPositive = await amountField.evaluate((el) => el.validity.valid);
    expect(isValidPositive).toBe(true);
  });

  test('should display currency symbol correctly', async ({ page }) => {
    // Check if Bangladeshi Taka symbol is displayed
    await expect(page.locator('.input-prefix')).toContainText('৳');
  });

  test('should show help text for form fields', async ({ page }) => {
    // Check help text exists
    await expect(page.locator('#amount-help')).toContainText('Enter the expense amount');
    await expect(page.locator('#description-help')).toContainText('Brief description (optional)');
  });

  test('should be accessible with keyboard navigation', async ({ page }) => {
    // Tab through form fields
    await page.keyboard.press('Tab'); // Should focus on amount field
    await expect(page.locator('#amount')).toBeFocused();
    
    await page.keyboard.press('Tab'); // Should focus on category field
    await expect(page.locator('#category')).toBeFocused();
    
    await page.keyboard.press('Tab'); // Should focus on description field
    await expect(page.locator('#description')).toBeFocused();
    
    await page.keyboard.press('Tab'); // Should focus on submit button
    await expect(page.locator('button[type="submit"]')).toBeFocused();
  });

  test('should handle long description input', async ({ page }) => {
    const longDescription = 'A'.repeat(200); // 200 characters
    
    await page.fill('#description', longDescription);
    
    // Check maxlength attribute limits input
    const actualValue = await page.inputValue('#description');
    expect(actualValue.length).toBeLessThanOrEqual(100); // maxlength="100"
  });

  test('should display entries section', async ({ page }) => {
    // Check entries section exists
    await expect(page.locator('.entries-section')).toBeVisible();
    await expect(page.locator('#recent-entries-title')).toContainText('Recent Expenses');
    
    // Check loading state initially
    await expect(page.locator('.loading-state')).toBeVisible();
    
    // Wait for HTMX to load content
    await page.waitForTimeout(2000);
    
    // Either entries or empty state should be visible
    const hasEntries = await page.locator('.entries-list').isVisible();
    const hasEmptyState = await page.locator('.entries-empty').isVisible();
    
    expect(hasEntries || hasEmptyState).toBe(true);
  });

});