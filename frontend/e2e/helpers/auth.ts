/**
 * Centralized e2e test helpers — single source of truth.
 *
 * Why this exists
 * ---------------
 * Five spec files used to declare their own copies of `loginViaAPI` and
 * `sendChatMessage`. Four of them shipped with a broken selector
 * (`input[placeholder="Share your spiritual journey..."]`) — but the chat
 * input is a `<textarea>`, so `input[...]` never matched. That single bug,
 * duplicated across 5 files, caused 26 of 29 e2e failures in the prior
 * test run.
 *
 * The durable fix: ONE module, used by every spec file.
 *
 * Selector contract
 * -----------------
 * Tests MUST use `[data-testid="chat-input"]` to find the chat input.
 * Do NOT query by placeholder text — that string is UX copy and changes
 * with the next redesign. Do NOT query by tag name (`textarea` today,
 * could become a contenteditable div tomorrow). The data-testid is an
 * explicit, intentional contract between the markup and the tests.
 */
import { Page, APIRequestContext, expect } from '@playwright/test';

export const API_BASE = process.env.API_URL || 'http://localhost:8080';

/**
 * Generate a fresh email so tests don't collide on the unique-email
 * constraint of the auth backend.
 */
export function uniqueEmail(prefix: string = 'e2etest'): string {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 10000)}@test.com`;
}

export interface TestUser {
  name: string;
  email: string;
  password: string;
  phone: string;
  gender: string;
  dob: string;
  profession: string;
}

/**
 * Build a fresh test user with a unique email. Override any field by
 * passing a partial object.
 */
export function uniqueUser(overrides: Partial<TestUser> = {}): TestUser {
  return {
    name: 'E2E Tester',
    email: uniqueEmail(),
    password: 'TestPass123',
    phone: '9876543210',
    gender: 'Male',
    dob: '1995-06-15',
    profession: 'Working Professional',
    ...overrides,
  };
}

/**
 * Register a user via the backend's /api/auth/register endpoint and
 * return the parsed JSON response. Throws if the request fails so the
 * test surfaces the error early instead of cascading.
 */
export async function registerUserViaAPI(
  request: APIRequestContext,
  user: TestUser,
): Promise<{ token: string; user: any }> {
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
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(
      `registerUserViaAPI failed (${response.status()}): ${body}`,
    );
  }
  return response.json();
}

/**
 * Register a fresh test user, plant the auth token + user object in
 * localStorage, reload the page so the React app picks them up, and
 * wait for the authenticated chat surface to be ready.
 *
 * "Ready" is defined by the `[data-testid="chat-input"]` element being
 * visible — that is the canonical signal that the user can start
 * conversing. The previous helpers waited on either a placeholder string
 * (broken: chat is a textarea, not an input) or the page header (works
 * but doesn't prove the chat is interactive).
 *
 * Returns the test user that was created so tests can reference its
 * email/name afterwards.
 */
export async function loginViaAPI(
  page: Page,
  request: APIRequestContext,
  overrides: Partial<TestUser> = {},
): Promise<TestUser> {
  const user = uniqueUser(overrides);
  const data = await registerUserViaAPI(request, user);

  // Stringify the user object before passing into page.evaluate. Doing
  // this on the Node side avoids any object-serialization quirks across
  // the Playwright IPC boundary and lets us pass two strings instead of
  // a nested object.
  const userJson = JSON.stringify(data.user);
  await page.evaluate(
    (args: { token: string; userJson: string }) => {
      localStorage.setItem('auth_token', args.token);
      localStorage.setItem('auth_user', args.userJson);
      // Drop any session_id left over from a previous test. If we don't,
      // useSession's mount-time restore will reuse the stale ID, the next
      // request will return the same session_id from the backend, React
      // won't re-render (same value), useEffect won't fire, and the
      // localStorage assertion in tests like SES-11 silently fails.
      localStorage.removeItem('spiritual_session_id');
    },
    { token: data.token, userJson },
  );

  await page.reload();
  await waitForChatReady(page);
  return user;
}

/**
 * Wait for the authenticated chat interface to be ready for input.
 *
 * Uses the stable `[data-testid="chat-input"]` contract — see the
 * file-level comment for why placeholder/tag selectors are forbidden.
 */
export async function waitForChatReady(
  page: Page,
  timeout: number = 10000,
): Promise<void> {
  await page.locator('[data-testid="chat-input"]').waitFor({
    state: 'visible',
    timeout,
  });
}

/**
 * Get a Playwright locator for the chat input. Use this in tests
 * instead of building your own selector.
 */
export function chatInput(page: Page) {
  return page.locator('[data-testid="chat-input"]');
}

/**
 * Send a chat message and wait for the assistant's reply to fully
 * render.
 *
 * "Fully rendered" means: the input has been re-enabled (which only
 * happens after the streaming `done` event has fired and the message,
 * products, citations, and session metadata have all been committed to
 * state). Waiting for `isProcessing` to become false is the most
 * reliable signal because it's set/unset by the same code path that
 * controls every downstream UI element.
 *
 * Why not wait for "bubble has > 10 chars": that only proves SOME text
 * has streamed in, not that the response is complete. Tests that look
 * for products, TTS buttons, feedback buttons, or persisted session
 * IDs need the FULL lifecycle to have finished — not just the first
 * few tokens.
 */
export async function sendChatMessage(
  page: Page,
  text: string,
  options: { timeout?: number } = {},
): Promise<void> {
  const timeout = options.timeout ?? 60000;
  const input = chatInput(page);
  await input.fill(text);
  // Use the testid instead of `form button[type="submit"]` to avoid
  // matching any submit button that might exist elsewhere on the page
  // (e.g., in the sidebar search form).
  await page.locator('[data-testid="send-button"]').click();

  // Wait for the request to complete: the input is disabled while
  // isProcessing=true and re-enabled when the `done` event fires.
  // This is the canonical "response complete" signal — the same flag
  // gates the assistant message rendering, products, citations, and
  // session-id persistence.
  //
  // NOTE: page.waitForFunction signature is `(fn, arg, options)`. The
  // `arg` slot is the value passed to the page function — NOT options.
  // Passing `{timeout}` as the second arg silently drops the timeout
  // override and falls back to playwright.config.ts `actionTimeout`
  // (15s by default). Always pass `undefined` for arg before options.
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="chat-input"]') as HTMLTextAreaElement | null;
      return el !== null && !el.disabled;
    },
    undefined,
    { timeout },
  );
  // Brief settle time for any post-done effects (e.g. localStorage
  // useEffects, animation start) before the next assertion runs.
  await page.waitForTimeout(300);
}

/**
 * Self-test: assert that the chat input is reachable via the canonical
 * data-testid. Used by `helpers/auth.spec.ts` to lock down the contract.
 */
export async function assertChatInputUsesDataTestId(page: Page): Promise<void> {
  // Both must succeed: the testid must resolve AND it must be visible.
  const locator = page.locator('[data-testid="chat-input"]');
  await expect(locator).toBeVisible();
}
