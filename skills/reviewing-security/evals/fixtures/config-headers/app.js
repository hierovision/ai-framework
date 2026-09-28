const express = require("express");
const cors = require("cors");
const jwt = require("jsonwebtoken");

const app = express();
app.use(express.json());
app.use(cors({ origin: true, credentials: true }));

app.post("/api/login", (req, res) => {
  const user = { id: "u_1", email: req.body.email };
  const token = jwt.sign({ sub: user.id }, process.env.SESSION_SECRET || "dev-secret");
  res.cookie("session", token, { httpOnly: true });
  res.json(user);
});

app.get("/api/me", (req, res) => {
  res.json({ ok: true });
});

app.listen(3000);
