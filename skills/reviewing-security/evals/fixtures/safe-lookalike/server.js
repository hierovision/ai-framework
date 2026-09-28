const express = require("express");
const { requireAuth } = require("./auth");
const { findTask } = require("./tasks");

const app = express();
app.use(express.json());

app.get("/api/tasks/:id", requireAuth, async (req, res) => {
  const task = await findTask(req.app.locals.pool, req.params.id, req.user.id);
  if (!task) {
    return res.status(404).json({ error: "not found" });
  }
  res.json(task);
});

app.listen(3000);
