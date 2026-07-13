import { defineConfig } from '@playwright/test'

// Trace on failure is enabled — do not override to 'off'. A failing e2e
// is a perception problem; the trace (DOM snapshots, network log,
// console errors) is the discriminating evidence for
// debugging-test-failures.
export default defineConfig({
  testDir: './e2e',
  trace: 'retain-on-failure',
  use: {
    baseURL: 'http://localhost:5173',
  },
})
