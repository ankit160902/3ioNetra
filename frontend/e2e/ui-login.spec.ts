import { test, expect } from '@playwright/test';

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3000';

test.describe('Login Page UI Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(FRONTEND_URL);
  });

  test('UI-01: Login page renders correctly', async ({ page }) => {
    // Verify logo image is visible
    const logo = page.locator('img[alt="3ioNetra"]');
    await expect(logo).toBeVisible();

    // Verify "Welcome Back" heading
    const heading = page.getByText('Welcome Back');
    await expect(heading).toBeVisible();

    // Verify email input
    const emailInput = page.locator('#email');
    await expect(emailInput).toBeVisible();

    // Verify password input
    const passwordInput = page.locator('#password');
    await expect(passwordInput).toBeVisible();

    // Verify Sign In button
    const signInButton = page.getByRole('button', { name: 'Sign In' });
    await expect(signInButton).toBeVisible();
  });

  test('UI-02: Password visibility toggle works', async ({ page }) => {
    const passwordInput = page.locator('#password');

    // Initially the input type should be 'password'
    await expect(passwordInput).toHaveAttribute('type', 'password');

    // Click the eye icon toggle button (the button inside the password field's relative container)
    const toggleButton = page.locator('#password ~ button');
    await toggleButton.click();

    // After clicking, the input type should change to 'text'
    await expect(passwordInput).toHaveAttribute('type', 'text');
  });

  test('UI-03: Register mode toggle', async ({ page }) => {
    // Click the "Create Account" link to switch to register mode
    const createAccountLink = page.getByRole('button', { name: 'Create Account' });
    await createAccountLink.click();

    // Verify "Create Account" heading appears
    const heading = page.getByText('Create Account', { exact: false }).first();
    await expect(heading).toBeVisible();

    // Verify name field is visible in register mode
    const nameInput = page.locator('#name');
    await expect(nameInput).toBeVisible();
  });

  test('UI-04: Registration step indicator shows', async ({ page }) => {
    // Switch to register mode
    const createAccountLink = page.getByRole('button', { name: 'Create Account' });
    await createAccountLink.click();

    // Verify 2 progress dots are visible
    const progressDots = page.locator('.rounded-full.transition-all.duration-500');
    await expect(progressDots).toHaveCount(2);

    // Verify the first dot (active) has the bg-orange-500 class
    const activeDot = progressDots.first();
    await expect(activeDot).toHaveClass(/bg-orange-500/);
  });

  test('UI-05: Login form validation - submit empty form shows error', async ({ page }) => {
    // Click Sign In without filling any fields
    const signInButton = page.getByRole('button', { name: 'Sign In' });
    await signInButton.click();

    // Wait for form submission to process (the browser native validation or app error)
    // The form uses HTML required attributes, so we check for either native validation
    // or the app's red error display
    // Since the inputs have `required`, we verify the email field triggers validation
    const emailInput = page.locator('#email');
    const isInvalid = await emailInput.evaluate(
      (el: HTMLInputElement) => !el.validity.valid
    );
    expect(isInvalid).toBe(true);
  });
});
