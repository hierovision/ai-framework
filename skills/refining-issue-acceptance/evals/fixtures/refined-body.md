## Add guest checkout to the cart

Let guests complete a purchase without creating an account. Today the cart
forces sign-in at checkout, which drops roughly a third of intended purchases.
This adds a guest path: browse -> checkout -> place order -> confirm by email,
with the same validation and persistence guarantees as signed-in users.

### Acceptance Criteria

**AC1 — [e2e]** A visitor reaches the checkout page and places an order without
ever signing in, then sees an order-confirmation screen. Verify: an e2e test
drives the browse -> checkout -> place-order flow as a guest and asserts the
confirmation screen appears.

**AC2 — [integration]** A guest's cart survives a page reload and a new browser
tab within the same session, and the placed order is persisted with a
guest flag and no linked user account. Verify: an integration test reloads the
session store and reads the order back, asserting it exists with guest=true and
no user_id.

**AC3 — [integration]** Submitting checkout with an invalid or missing email is
rejected and no order is created; an audit event recording the rejected
attempt is emitted. Verify: an integration test posts an invalid email and
asserts a 422 response, zero orders written, and one rejection event emitted.

**AC4 — [unit]** Given an empty or malformed email, the checkout email
validation reports an invalid-email error and does not proceed. Verify: a unit
test calls the validation with empty/malformed input and asserts an
invalid-email result and no downstream call.

**AC5 — [e2e]** After a successful guest order, a confirmation email is received
at the guest's address and the cart is emptied. Verify: an e2e test asserts the
confirmation email arrives and the cart container shows no items.

### Notes
Guest orders should be linkable to an account if the user signs up later
(out of scope for this issue).
