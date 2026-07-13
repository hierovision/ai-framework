import { test as base, expect, type Page } from '@playwright/test'

// Authenticated-session fixture: grants a logged-in supabase session by
// seeding the auth token via context.addInitScript — NOT by replaying
// the login UI in every test. Replaying login per test is slow and
// couples every journey to the auth flow; this fixture grants an
// authenticated page directly.
type AuthFixtures = { authedPage: Page }

export const test = base.extend<AuthFixtures>({
  authedPage: async ({ page, context }, use) => {
    await context.addInitScript((token) => {
      window.localStorage.setItem('supabase.auth.token', token)
    }, 'seeded-test-jwt-user-a')
    await use(page)
  },
})

export { expect }
