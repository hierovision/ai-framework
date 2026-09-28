const express = require("express");
const { requireAuth } = require("./auth");
const db = require("./db");

const app = express();
app.use(express.json());

app.get("/api/orders/:id", requireAuth, async (req, res) => {
  const order = await db.getOrder(req.params.id);
  if (!order) {
    return res.status(404).json({ error: "not found" });
  }
  res.json(order);
});

app.post("/api/orders/:id/cancel", requireAuth, async (req, res) => {
  const cancelled = await db.cancelOrder(req.params.id, req.body.reason);
  if (!cancelled) {
    return res.status(404).json({ error: "not found" });
  }
  res.json({ ok: true });
});

app.post("/api/admin/refund", requireAuth, async (req, res) => {
  await db.refund(req.body.orderId, req.body.amountCents);
  res.json({ ok: true });
});

app.listen(3000);
