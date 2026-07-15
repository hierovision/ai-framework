## Add guest checkout to the cart

We should let guests buy things.

### Acceptance Criteria

**AC1 — [e2e]** Add a `handleGuestCheckout()` function in `src/cart/checkout.ts`
that renders the checkout page for anonymous users.

**AC2 — [integration]** Update the `orders` table migration to add a `guest`
boolean column and persist the cart via the `CartStore.save` method.

**AC3 — [unit]** Refactor `validateEmail()` to reject empty input.
