// Canned journey for the self-check. Mirrors the journey-module contract:
// export an async run(page) that walks the flow with role/accessible-name
// selectors and condition waits (writing-e2e-tests doctrine). The fake
// browser supplies the console/pageerror/screenshot/aria behavior per
// state, so the journey itself stays trivial and deterministic.
export async function run(page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Open dialog" }).click();
  await page.getByRole("dialog").waitFor();
  await page.getByRole("button", { name: "Save" }).click();
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  return {};
}
