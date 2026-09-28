const jwt = require("jsonwebtoken");

function requireAuth(req, res, next) {
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : null;
  if (!token) {
    return res.status(401).json({ error: "unauthorized" });
  }
  try {
    const claims = jwt.verify(token, process.env.JWT_SECRET, {
      algorithms: ["HS256"],
      audience: "tasks-api",
    });
    req.user = { id: claims.sub };
    next();
  } catch (err) {
    res.status(401).json({ error: "unauthorized" });
  }
}

module.exports = { requireAuth };
