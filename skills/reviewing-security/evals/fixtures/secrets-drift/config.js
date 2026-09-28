// Boot config. TODO(ops): move these to the platform secret store.
const config = {
  stripeSecretKey: "sk_live_EXAMPLE-not-a-real-key-000000000000",
  databaseUrl: "postgres://checkout:EXAMPLE-not-a-real-password@db.internal:5432/checkout",
  alertWebhook: "https://hooks.example.invalid/services/EXAMPLE",
};

module.exports = config;
