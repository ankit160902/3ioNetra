import { test, expect } from '@playwright/test';
import { loginViaAPI } from './helpers/auth';

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3000';

test.describe('Chat Interface UI Tests', () => {
  test.beforeEach(async ({ page, request }) => {
    await page.goto(FRONTEND_URL);
    await loginViaAPI(page, request);
    // Wait for the authenticated chat interface to load
    await page.waitForSelector('header', { timeout: 10000 });
  });

  test('UI-06: Chat interface loads after authentication', async ({ page }) => {
    // Verify header with logo text "3ioNetra"
    const headerLogo = page.getByText('3ioNetra', { exact: true });
    await expect(headerLogo).toBeVisible();

    // Verify chat input is visible
    const chatInput = page.locator('#chat-input');
    await expect(chatInput).toBeVisible();

    // Verify send button is visible
    const sendButton = page.locator('form button[type="submit"]');
    await expect(sendButton).toBeVisible();
  });

  test('UI-07: Empty state shows welcome cards', async ({ page }) => {
    // Verify "Seek Wisdom" card is visible
    const seekWisdom = page.getByText('Seek Wisdom');
    await expect(seekWisdom).toBeVisible();

    // Verify "Daily Support" card is visible
    const dailySupport = page.getByText('Daily Support');
    await expect(dailySupport).toBeVisible();
  });

  test('UI-08: Chat input accepts text', async ({ page }) => {
    const chatInput = page.locator('#chat-input');
    await chatInput.fill('Hello, I need guidance');
    await expect(chatInput).toHaveValue('Hello, I need guidance');
  });

  test('UI-09: Send button disabled when input is empty', async ({ page }) => {
    const chatInput = page.locator('#chat-input');

    // Ensure the input is empty
    await expect(chatInput).toHaveValue('');

    // Verify the send button is disabled
    const sendButton = page.locator('form button[type="submit"]');
    await expect(sendButton).toBeDisabled();
  });

  test('UI-10: Send message and get response', async ({ page }) => {
    const chatInput = page.locator('#chat-input');
    const sendButton = page.locator('form button[type="submit"]');

    // Type a message
    await chatInput.fill('Namaste');
    await sendButton.click();

    // Verify user message appears in the chat
    const userMessage = page.locator('text=Namaste').first();
    await expect(userMessage).toBeVisible({ timeout: 5000 });

    // Wait for assistant response to appear (allow up to 30s for LLM)
    const assistantBubble = page.locator('.justify-start .bg-white').first();
    await expect(assistantBubble).toBeVisible({ timeout: 30000 });

    // Verify assistant message has some text content
    const assistantText = await assistantBubble.textContent();
    expect(assistantText!.length).toBeGreaterThan(0);
  });

  test('UI-11: User message styled correctly (right-aligned with orange gradient)', async ({ page }) => {
    const chatInput = page.locator('#chat-input');
    const sendButton = page.locator('form button[type="submit"]');

    await chatInput.fill('Namaste');
    await sendButton.click();

    // Wait for the user message bubble to appear
    const userBubbleContainer = page.locator('.justify-end').first();
    await expect(userBubbleContainer).toBeVisible({ timeout: 5000 });

    // Verify the user message bubble has the orange gradient class
    const userBubble = userBubbleContainer.locator('.from-orange-500.to-amber-600');
    await expect(userBubble).toBeVisible();
  });

  test('UI-12: Assistant message styled correctly (left-aligned with white bg)', async ({ page }) => {
    const chatInput = page.locator('#chat-input');
    const sendButton = page.locator('form button[type="submit"]');

    await chatInput.fill('Namaste');
    await sendButton.click();

    // Wait for the assistant response
    const assistantContainer = page.locator('.justify-start .rounded-tl-sm').first();
    await expect(assistantContainer).toBeVisible({ timeout: 30000 });

    // Verify the assistant bubble has white background class
    await expect(assistantContainer).toHaveClass(/bg-white/);
  });

  test('UI-13: New Session button clears chat', async ({ page }) => {
    const chatInput = page.locator('#chat-input');
    const sendButton = page.locator('form button[type="submit"]');

    // Send a message first
    await chatInput.fill('Namaste');
    await sendButton.click();

    // Wait for the user message to appear in chat
    const userMessage = page.locator('.justify-end').first();
    await expect(userMessage).toBeVisible({ timeout: 5000 });

    // Click the "New Session" button in the header
    const newSessionButton = page.locator('header').getByText('New Session');
    await newSessionButton.click();

    // Verify messages are cleared — the welcome empty state should reappear
    const seekWisdom = page.getByText('Seek Wisdom');
    await expect(seekWisdom).toBeVisible({ timeout: 5000 });
  });

  test('UI-15: Chat input disabled while processing', async ({ page }) => {
    const chatInput = page.locator('#chat-input');
    const sendButton = page.locator('form button[type="submit"]');

    await chatInput.fill('Namaste');
    await sendButton.click();

    // Immediately after sending, the input should be disabled while processing
    await expect(chatInput).toBeDisabled({ timeout: 3000 });

    // Wait for response to complete, then input should be enabled again
    const assistantBubble = page.locator('.justify-start .bg-white').first();
    await expect(assistantBubble).toBeVisible({ timeout: 30000 });
    await expect(chatInput).toBeEnabled({ timeout: 5000 });
  });
});
