# checkout-api (fixture)

Small Express service backing the storefront checkout. Routes:

- `GET /api/orders/:id` — return one order for the signed-in customer.
- `POST /api/orders/:id/cancel` — cancel an order.
- `POST /api/admin/refund` — issue a refund (staff only).

The service sits behind `auth.js`; `db.js` owns the Postgres access.

(Fixture for eval use — the code is intentionally flawed for review.)
