import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8080';

function uniqueEmail(): string {
  return `testuser_${Date.now()}@test.com`;
}

function uniqueUser() {
  const email = uniqueEmail();
  return {
    name: 'Test User',
    email,
    password: 'Test@1234',
    phone: '9876543210',
    gender: 'male',
    dob: '1995-06-15',
    profession: 'engineer',
  };
}

async function registerUserViaAPI(request: any, user: ReturnType<typeof uniqueUser>) {
  const response = await request.post(`${API_BASE}/api/auth/register`, {
    data: {
      name: user.name,
      email: user.email,
      password: user.password,
      phone: user.phone,
      gender: user.gender,
      dob: user.dob,
      profession: user.profession,
    },
  });
  return response;
}

// ---------------------------------------------------------------------------
// API-only tests
// ---------------------------------------------------------------------------

test.describe('Auth API Tests', () => {
  test('AUTH-01: Register a new user via API', async ({ request }) => {
    const user = uniqueUser();
    const response = await registerUserViaAPI(request, user);

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.token).toBeTruthy();
  });

  test('AUTH-02: Login with registered user via API', async ({ request }) => {
    const user = uniqueUser();
    await registerUserViaAPI(request, user);

    const response = await request.post(`${API_BASE}/api/auth/login`, {
      data: {
        email: user.email,
        password: user.password,
      },
    });

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.token).toBeTruthy();
  });

  test('AUTH-03: Verify token via API', async ({ request }) => {
    const user = uniqueUser();
    const regResponse = await registerUserViaAPI(request, user);
    const { token } = await regResponse.json();

    const verifyResponse = await request.get(`${API_BASE}/api/auth/verify`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    expect(verifyResponse.status()).toBe(200);
  });

  test('AUTH-04: Reject invalid token', async ({ request }) => {
    const verifyResponse = await request.get(`${API_BASE}/api/auth/verify`, {
      headers: {
        Authorization: 'Bearer fake_invalid_token_12345',
      },
    });

    expect(verifyResponse.status()).toBe(401);
  });

  test('AUTH-05: Reject duplicate email registration via API', async ({ request }) => {
    const user = uniqueUser();
    await registerUserViaAPI(request, user);

    const duplicateResponse = await registerUserViaAPI(request, user);

    expect([400, 409]).toContain(duplicateResponse.status());
  });
});

// ---------------------------------------------------------------------------
// UI tests
// ---------------------------------------------------------------------------

test.describe('Auth UI Tests', () => {
  test('AUTH-07: Login via UI', async ({ page, request }) => {
    // Pre-register a user via API
    const user = uniqueUser();
    await registerUserViaAPI(request, user);

    // Navigate to the frontend
    await page.goto('/');

    // Fill login form
    await page.locator('#email').fill(user.email);
    await page.locator('#password').fill(user.password);

    // Click Sign In
    await page.getByRole('button', { name: /sign in/i }).click();

    // Verify the chat page loads with 3ioNetra heading
    await expect(page.getByRole('heading', { name: /3ioNetra/i })).toBeVisible({
      timeout: 10000,
    });
  });

  test('AUTH-08: Register via UI', async ({ page }) => {
    const user = uniqueUser();

    await page.goto('/');

    // Switch to register form
    await page.getByText(/create account/i).click();

    // Step 1: basic info
    await page.locator('#name').fill(user.name);
    await page.locator('#email').fill(user.email);
    await page.locator('#password').fill(user.password);
    await page.locator('#confirmPassword').fill(user.password);

    // Advance to step 2
    await page.getByRole('button', { name: /next step/i }).click();

    // Step 2: additional details
    await page.locator('#phone').fill(user.phone);
    await page.locator('#gender').selectOption(user.gender);
    await page.locator('#dob').fill(user.dob);
    await page.locator('#profession').selectOption({ label: 'Working Professional' });

    // Submit registration
    await page.getByRole('button', { name: /create account/i }).click();

    // Verify the chat page loads
    await expect(page.getByRole('heading', { name: /3ioNetra/i })).toBeVisible({
      timeout: 10000,
    });
  });

  test('AUTH-09: Show error on wrong password via UI', async ({ page, request }) => {
    const user = uniqueUser();
    await registerUserViaAPI(request, user);

    await page.goto('/');

    await page.locator('#email').fill(user.email);
    await page.locator('#password').fill('WrongPassword!999');

    await page.getByRole('button', { name: /sign in/i }).click();

    // Expect an error message to appear on the page
    await expect(page.getByText(/invalid|incorrect|wrong|error|failed/i)).toBeVisible({
      timeout: 5000,
    });
  });

  test('AUTH-10: Show error on empty fields via UI', async ({ page }) => {
    await page.goto('/');

    // Click Sign In without filling any fields
    await page.getByRole('button', { name: /sign in/i }).click();

    // Expect a validation error or the form to remain visible (not navigate away)
    const emailInput = page.locator('#email');
    await expect(emailInput).toBeVisible();

    // Check for browser validation or custom error message
    const isInvalid =
      (await emailInput.evaluate((el: HTMLInputElement) => !el.validity.valid)) ||
      (await page.getByText(/required|empty|enter|invalid/i).isVisible().catch(() => false));

    expect(isInvalid).toBeTruthy();
  });

  test('AUTH-11: Logout clears auth state', async ({ page, request }) => {
    const user = uniqueUser();
    await registerUserViaAPI(request, user);

    // Login first
    await page.goto('/');
    await page.locator('#email').fill(user.email);
    await page.locator('#password').fill(user.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.getByRole('heading', { name: /3ioNetra/i })).toBeVisible({
      timeout: 10000,
    });

    // Sign Out is inside the sidebar — open it first
    const sidebarToggle = page.locator('header button').first();
    await sidebarToggle.click();
    await page.waitForTimeout(500);

    // Click Sign Out in the sidebar
    const signOutButton = page.locator('aside button', { hasText: 'Sign Out' });
    await expect(signOutButton).toBeVisible({ timeout: 5000 });
    await signOutButton.click();

    // Verify auth state is cleared
    await page.waitForTimeout(1000);
    const token = await page.evaluate(() => localStorage.getItem('auth_token'));
    expect(token).toBeFalsy();

    // Verify we're back on the login page
    await expect(page.locator('#email')).toBeVisible({ timeout: 5000 });
  });

  test('AUTH-13: Token persists across page reload', async ({ page, request }) => {
    const user = uniqueUser();
    await registerUserViaAPI(request, user);

    // Login
    await page.goto('/');
    await page.locator('#email').fill(user.email);
    await page.locator('#password').fill(user.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.getByRole('heading', { name: /3ioNetra/i })).toBeVisible({
      timeout: 10000,
    });

    // Capture the token
    const tokenBefore = await page.evaluate(() => localStorage.getItem('auth_token'));
    expect(tokenBefore).toBeTruthy();

    // Reload the page
    await page.reload();

    // Verify the token still exists
    const tokenAfter = await page.evaluate(() => localStorage.getItem('auth_token'));
    expect(tokenAfter).toBe(tokenBefore);

    // Verify the user is still on the authenticated chat page (not redirected to login)
    await expect(page.getByRole('heading', { name: /3ioNetra/i })).toBeVisible({
      timeout: 10000,
    });
  });
});
