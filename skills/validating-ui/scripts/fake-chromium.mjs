// Fake chromium for the objective self-check (mirrors the
// capturing-ui-evidence fake-chromium precedent). The REAL browser path
// is deferred in the eval harness; this canned browser emits
// deterministic console/pageerror/screenshot/aria behavior per state so
// verify-smoke.js can assert smoke.mjs's net + artifact logic without a
// chromium runtime.

const EMIT = {
  green: { console: [], pageErrors: [] },
  allowlisted: { console: [["warning", "Benign library hint"]], pageErrors: [] },
  error: { console: [["error", "Failed to fetch dynamically imported module"]], pageErrors: [] },
  warning: { console: [["warning", "Unhandled error during execution of component event handler"]], pageErrors: [] },
  pageerror: { console: [], pageErrors: ["TypeError: phaseFormEditRef.value?.stopPreview is not a function"] },
};

export function createFakeBrowser(state) {
  const emit = EMIT[state] || EMIT.green;
  return {
    async createBrowserContext() {
      return {
        async newPage() {
          const handlers = { console: [], pageerror: [] };
          return {
            on(type, cb) {
              (handlers[type] ||= []).push(cb);
            },
            async goto() {},
            async screenshot() {
              return Buffer.from("fake-full-page-png");
            },
            getByRole() {
              return {
                async click() {},
                async waitFor() {},
                async screenshot() {
                  return Buffer.from("fake-clip-png");
                },
              };
            },
            getByTestId() {
              return {
                async screenshot() {
                  return Buffer.from("fake-clip-png");
                },
              };
            },
            locator() {
              return {
                async ariaSnapshot() {
                  return "dialog\n  button \"Open dialog\"\n  button \"Save\"";
                },
                async screenshot() {
                  return Buffer.from("fake-png");
                },
              };
            },
            _flush() {
              for (const [type, text] of emit.console) {
                for (const cb of handlers.console) cb({ type: () => type, text: () => text });
              }
              for (const text of emit.pageErrors) {
                for (const cb of handlers.pageerror) cb(new Error(text));
              }
            },
          };
        },
      };
    },
    async close() {},
  };
}
