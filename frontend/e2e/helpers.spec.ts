/**
 * Smoke test for the centralized e2e helpers.
 *
 * Why this exists
 * ---------------
 * The helpers in `e2e/helpers/auth.ts` are now the single source of
 * truth for authenticating a Playwright test session against the
 * 3ioNetra backend. If those helpers regress (wrong selector, wrong
 * endpoint, wrong storage key), every spec file that imports them
 * fails. This file gives us one canonical health-check that surfaces
 * the regression with a clear message instead of a wall of timeout
 * failures.
 */
import { test, expect } from '@playwright/test';
import {
  loginViaAPI,
  uniqueUser,
  registerUserViaAPI,
  waitForChatReady,
  chatInput,
  assertChatInputUsesDataTestId,
} from './helpers/auth';

test.describe('Helpers self-test', () => {
  test('HELPER-01: registerUserViaAPI returns a token', async ({ request }) => {
    const user = uniqueUser();
    const data = await registerUserViaAPI(request, user);
    expect(data.token).toBeTruthy();
    expect(data.token.length).toBeGreaterThan(20);
    expect(data.user).toBeTruthy();
    expect(data.user.email).toBe(user.email);
  });

  test('HELPER-02: loginViaAPI lands on the chat surface', async ({
    page,
    request,
  }) => {
    await page.goto('/');
    await loginViaAPI(page, request);
    // After loginViaAPI returns, the chat input must be visible.
    await assertChatInputUsesDataTestId(page);
  });

  test('HELPER-03: chatInput resolves via data-testid (no placeholder coupling)', async ({
    page,
    request,
  }) => {
    await page.goto('/');
    await loginViaAPI(page, request);
    const input = chatInput(page);
    await expect(input).toBeVisible();
    // The element MUST be a textarea (today). If the markup ever changes
    // to a contenteditable div, this test still passes because we query
    // by data-testid, not tag name. We assert the tag here only as
    // documentation of the current shape.
    const tagName = await input.evaluate((el) => el.tagName.toLowerCase());
    expect(['textarea', 'div', 'input']).toContain(tagName);
  });

  test('HELPER-04: waitForChatReady is idempotent', async ({
    page,
    request,
  }) => {
    await page.goto('/');
    await loginViaAPI(page, request);
    // Calling it a second time must not fail or hang — it just returns.
    await waitForChatReady(page);
    await waitForChatReady(page);
  });
});
