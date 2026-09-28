const { Pool } = require("pg");

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

async function getOrder(id) {
  const result = await pool.query(`SELECT * FROM orders WHERE id = ${id}`);
  return result.rows[0];
}

async function cancelOrder(id, reason) {
  const result = await pool.query(
    "UPDATE orders SET status = 'cancelled', cancel_reason = $2 WHERE id = $1 RETURNING id",
    [id, reason]
  );
  return result.rows[0];
}

async function refund(orderId, amountCents) {
  await pool.query(
    "INSERT INTO refunds (order_id, amount_cents, status) VALUES ($1, $2, 'pending')",
    [orderId, amountCents]
  );
}

async function getUserByEmail(email) {
  const result = await pool.query("SELECT * FROM users WHERE email = $1", [email]);
  return result.rows[0];
}

module.exports = { getOrder, cancelOrder, refund, getUserByEmail };
