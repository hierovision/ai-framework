// Auth-fixture for capture (app mode). Grants an authenticated Supabase
// session by seeding the JWT via context.addInitScript — the e2e
// auth-fixture pattern, applied to capture rather than replaying the
// login UI before capture. capture.mjs (app mode) imports the default
// export of the --auth-fixture path and calls setup(context) before
// navigating to the route.
export default async function setupAuth(context) {
  await context.addInitScript((token) => {
    window.localStorage.setItem('supabase.auth.token', token)
  }, 'seeded-test-jwt-user-a')
}