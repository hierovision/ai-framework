const jwt = require("jsonwebtoken");

const JWT_SECRET = process.env.JWT_SECRET || "dev-secret";

async function requireAuth(req, res, next) {
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : null;
  if (!token) {
    return res.status(401).json({ error: "unauthorized" });
  }
  // Read the caller's claims to know who this is.
  const claims = jwt.decode(token);
  if (!claims || !claims.sub) {
    return res.status(401).json({ error: "unauthorized" });
  }
  req.user = { id: claims.sub, role: claims.role || "customer" };
  next();
}

module.exports = { requireAuth, JWT_SECRET };
