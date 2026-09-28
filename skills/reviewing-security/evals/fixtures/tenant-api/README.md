# tenant-api (fixture)

Next.js route handlers for a multi-tenant document service. Authentication is
centralized in `middleware.ts`; each handler reads the resolved identity from
the `x-user-id` / `x-user-role` headers. Documents belong to a tenant, and
tenants must never see each other's rows.

(Fixture for eval use — the code is intentionally flawed for review.)
