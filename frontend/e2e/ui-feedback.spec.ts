import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8080';

async function loginViaAPI(page: any, request: any) {
  const email = `e2etest_${Date.now()}@test.com`;
  const res = await request.post(`${API_BASE}/api/auth/register`, {
    data: { name: 'E2E Tester', email, password: 'TestPass123', phone: '9876543210', gender: 'Male', dob: '1995-06-15', profession: 'Working Professional' }
  });
  const data = await res.json();
  await page.evaluate(({ token, user }: any) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('auth_user', JSON.stringify(user));
  }, { token: data.token, user: data.user });
  await page.reload();
  await page.waitForSelector('input[placeholder="Share your spiritual journey..."]', { timeout: 10000 });
}

// ---------------------------------------------------------------------------
// Helper: send a chat message and wait for assistant response
// ---------------------------------------------------------------------------
async function sendChatMessage(page: any, text: string) {
  const input = page.locator('input[placeholder="Share your spiritual journey..."]');
  await input.fill(text);
  await page.locator('button[type="submit"]').click();
  await page.waitForFunction(
    () => {
      const msgs = document.querySelectorAll('.animate-fade-in');
      if (msgs.length < 2) return false;
      const last = msgs[msgs.length - 1];
      return last && last.textContent && last.textContent.trim().length > 10;
    },
    { timeout: 30000 }
  );
  await page.waitForTimeout(1500);
}

// ---------------------------------------------------------------------------
// Feedback Button Tests (ThumbsUp / ThumbsDown on assistant messages)
// ---------------------------------------------------------------------------

test.describe('Feedback Button Tests', () => {
  // Each test sends a message first to get an assistant response with feedback buttons

  test('UI-28: Thumbs up button visible on assistant message', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    await sendChatMessage(page, 'What does the Bhagavad Gita say about duty?');

    // The thumbs up button has title "Helpful" and contains a ThumbsUp icon
    const thumbsUpButton = page.locator('button[title="Helpful"]').first();
    await expect(thumbsUpButton).toBeVisible({ timeout: 5000 });
  });

  test('UI-29: Thumbs down button visible on assistant message', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    await sendChatMessage(page, 'Tell me about mindfulness in Hinduism');

    // The thumbs down button has title "Not helpful" and contains a ThumbsDown icon
    const thumbsDownButton = page.locator('button[title="Not helpful"]').first();
    await expect(thumbsDownButton).toBeVisible({ timeout: 5000 });
  });

  test('UI-30: Clicking thumbs up changes button style to green', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    await sendChatMessage(page, 'How can I find inner peace through meditation?');

    const thumbsUpButton = page.locator('button[title="Helpful"]').first();
    await expect(thumbsUpButton).toBeVisible({ timeout: 5000 });

    // Before clicking, the button should have default gray styling
    const classesBefore = await thumbsUpButton.getAttribute('class');
    expect(classesBefore).not.toContain('bg-green-100');

    // Click thumbs up
    await thumbsUpButton.click();
    await page.waitForTimeout(500);

    // After clicking, the button class should include green styles
    const classesAfter = await thumbsUpButton.getAttribute('class');
    expect(classesAfter).toContain('bg-green-100');
    expect(classesAfter).toContain('text-green-600');
  });

  test('UI-31: Clicking thumbs down changes button style to red', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    await sendChatMessage(page, 'What mantras help with anxiety?');

    const thumbsDownButton = page.locator('button[title="Not helpful"]').first();
    await expect(thumbsDownButton).toBeVisible({ timeout: 5000 });

    // Before clicking, the button should have default gray styling
    const classesBefore = await thumbsDownButton.getAttribute('class');
    expect(classesBefore).not.toContain('bg-red-100');

    // Click thumbs down
    await thumbsDownButton.click();
    await page.waitForTimeout(500);

    // After clicking, the button class should include red styles
    const classesAfter = await thumbsDownButton.getAttribute('class');
    expect(classesAfter).toContain('bg-red-100');
    expect(classesAfter).toContain('text-red-600');
  });

  test('UI-32: Feedback persists - thumbs up stays green after clicking', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    await sendChatMessage(page, 'Share wisdom about gratitude from the scriptures');

    const thumbsUpButton = page.locator('button[title="Helpful"]').first();
    await expect(thumbsUpButton).toBeVisible({ timeout: 5000 });

    // Click thumbs up
    await thumbsUpButton.click();
    await page.waitForTimeout(500);

    // Verify it is green
    let classes = await thumbsUpButton.getAttribute('class');
    expect(classes).toContain('bg-green-100');
    expect(classes).toContain('text-green-600');

    // Wait a moment and verify it remains green (state persists)
    await page.waitForTimeout(1000);
    classes = await thumbsUpButton.getAttribute('class');
    expect(classes).toContain('bg-green-100');
    expect(classes).toContain('text-green-600');

    // Also verify that clicking thumbs up again does not toggle it off
    // (the handleFeedback function returns early if same type is clicked)
    await thumbsUpButton.click();
    await page.waitForTimeout(300);
    classes = await thumbsUpButton.getAttribute('class');
    expect(classes).toContain('bg-green-100');
    expect(classes).toContain('text-green-600');
  });
});
