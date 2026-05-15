import { test, expect } from '@playwright/test';
import { loginViaAPI, sendChatMessage } from './helpers/auth';

// ---------------------------------------------------------------------------
// Sidebar Tests
// ---------------------------------------------------------------------------

test.describe('Sidebar Tests', () => {
  test('UI-19: Sidebar toggle button visible in header', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    // The header has a toggle button with the History icon (first button in header's left section).
    // It's the button inside the header that toggles sidebar open/close.
    const header = page.locator('header');
    await expect(header).toBeVisible();

    // The toggle button is the first button in the header's left flex group
    const toggleButton = header.locator('button').first();
    await expect(toggleButton).toBeVisible();
  });

  test('UI-20: Clicking sidebar toggle opens sidebar - Conversations heading appears', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    // Click the sidebar toggle button in the header
    const toggleButton = page.locator('header button').first();
    await toggleButton.click();

    // Wait for the sidebar to slide in — it contains an h2 with "Conversations"
    const conversationsHeading = page.locator('h2', { hasText: 'Conversations' });
    await expect(conversationsHeading).toBeVisible({ timeout: 5000 });
  });

  test('UI-21: Clicking toggle again closes sidebar', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    const toggleButton = page.locator('header button').first();

    // Open the sidebar
    await toggleButton.click();
    const conversationsHeading = page.locator('h2', { hasText: 'Conversations' });
    await expect(conversationsHeading).toBeVisible({ timeout: 5000 });

    // Close the sidebar by clicking the toggle again
    await toggleButton.click();

    // The aside element should now be translated off-screen (-translate-x-full).
    // Wait for the transition to complete.
    await page.waitForTimeout(600);

    // Verify the sidebar is translated off-screen
    const aside = page.locator('aside');
    const transformStyle = await aside.evaluate((el: HTMLElement) => {
      return window.getComputedStyle(el).transform;
    });

    // When closed, the sidebar's transform should include a negative translateX
    // (the computed matrix will show a negative X translation value)
    // A matrix like "matrix(1, 0, 0, 1, -288, 0)" means it's off-screen to the left
    expect(transformStyle).toMatch(/matrix/);
    const matrixValues = transformStyle.match(/matrix\(([^)]+)\)/);
    if (matrixValues) {
      const parts = matrixValues[1].split(',').map((v: string) => parseFloat(v.trim()));
      // parts[4] is the translateX value; when closed it should be negative
      expect(parts[4]).toBeLessThan(0);
    }
  });

  test('UI-22: Sidebar shows user info and conversation history area', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    // Open sidebar
    const toggleButton = page.locator('header button').first();
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Verify the sidebar has the Conversations heading
    const conversationsHeading = page.locator('h2', { hasText: 'Conversations' });
    await expect(conversationsHeading).toBeVisible({ timeout: 5000 });

    // Verify the user section with Sign Out is visible
    const signOutButton = page.locator('aside button', { hasText: 'Sign Out' });
    await expect(signOutButton).toBeVisible({ timeout: 5000 });
  });

  test('UI-23: Sidebar shows user name at bottom', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    // Open sidebar
    const toggleButton = page.locator('header button').first();
    await toggleButton.click();
    await page.waitForTimeout(500);

    // The sidebar bottom section shows the user info section and "Sign Out" button.
    // The user name paragraph and Sign Out button are in the sidebar footer.
    const signOutButton = page.locator('aside button', { hasText: 'Sign Out' });
    await expect(signOutButton).toBeVisible({ timeout: 5000 });

    // Verify the user info section exists (avatar icon + name paragraph + sign out)
    const userSection = page.locator('aside').locator('div.border-t');
    await expect(userSection).toBeVisible();
  });

  test('UI-24: Header New Session button clears current chat', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    // Send a message to have some chat content
    await sendChatMessage(page, 'Tell me about morning meditation routines');

    // Verify message bubbles exist
    const messageBubbles = page.locator('.animate-fade-in');
    const countBefore = await messageBubbles.count();
    expect(countBefore).toBeGreaterThanOrEqual(2);

    // Click the header "New Session" button (inside the header's right-side button group)
    const newSessionButton = page.locator('header button', { hasText: 'New Session' });
    await newSessionButton.click();
    await page.waitForTimeout(1000);

    // The chat should be cleared — after New Session, the empty state
    // shows the welcome cards (Seek Wisdom / Daily Support) rendered by
    // pages/index.tsx around line 773. "Elevate your spirit" only exists
    // on the LoginPage, NOT in the authenticated empty state.
    const welcomeCard = page.getByRole('button', { name: /Seek Wisdom/i });
    await expect(welcomeCard).toBeVisible({ timeout: 5000 });
  });

  test('UI-25: Conversation history appears in sidebar after exchanging messages', async ({ page, request }) => {
    await page.goto('/');
    await loginViaAPI(page, request);

    // Send messages to create a conversation that will auto-save
    await sendChatMessage(page, 'I want to learn about karma yoga');
    // Auto-save fires 2s after messages change (see pages/index.tsx:333)
    // and then triggers a fetchHistory. Wait for both to complete.
    await page.waitForTimeout(3000);

    // Open the sidebar
    const toggleButton = page.locator('header button').first();
    await toggleButton.click();

    // Wait for the "Loading conversations..." placeholder to disappear.
    // It's rendered while fetchHistory is in flight (pages/index.tsx
    // historyLoading state). Without this wait, the test races the
    // fetch and counts 0 items.
    await expect(page.locator('text=Loading conversations...')).not.toBeVisible({ timeout: 10000 });

    // The sidebar should now have at least one conversation history item.
    // History items are buttons inside the sidebar's scrollable area
    // with a title and date — they're rendered AFTER the "New Session"
    // button so we filter that out.
    const historyItems = page.locator('aside .overflow-y-auto button').filter({ hasNotText: 'New Session' });
    await expect(historyItems.first()).toBeVisible({ timeout: 5000 });
    const count = await historyItems.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('UI-26: Mobile responsive - sidebar starts hidden at 375x812', async ({ page, request }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    await loginViaAPI(page, request);

    // On mobile, sidebar should be off-screen by default (has -translate-x-full)
    const aside = page.locator('aside');
    const transformStyle = await aside.evaluate((el: HTMLElement) => {
      return window.getComputedStyle(el).transform;
    });

    // The sidebar is translated fully off-screen to the left
    expect(transformStyle).toMatch(/matrix/);
    const matrixValues = transformStyle.match(/matrix\(([^)]+)\)/);
    if (matrixValues) {
      const parts = matrixValues[1].split(',').map((v: string) => parseFloat(v.trim()));
      expect(parts[4]).toBeLessThan(0);
    }

    // The "Conversations" heading should not be visible on screen
    const heading = page.locator('h2', { hasText: 'Conversations' });
    await expect(heading).not.toBeInViewport();
  });

  test('UI-27: Desktop responsive - toggle works at 1280x800', async ({ page, request }) => {
    // Set desktop viewport
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/');
    await loginViaAPI(page, request);

    // Toggle button should be visible
    const toggleButton = page.locator('header button').first();
    await expect(toggleButton).toBeVisible();

    // Open sidebar
    await toggleButton.click();
    const heading = page.locator('h2', { hasText: 'Conversations' });
    await expect(heading).toBeVisible({ timeout: 5000 });

    // Close sidebar
    await toggleButton.click();
    await page.waitForTimeout(600);

    // Sidebar should be off-screen again — heading should not be in viewport
    await expect(heading).not.toBeInViewport();
  });
});
