import { test, expect } from '@playwright/test';
import { loginViaAPI, sendChatMessage } from './helpers/auth';

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
