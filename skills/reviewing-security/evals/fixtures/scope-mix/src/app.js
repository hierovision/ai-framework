const express = require("express");
const { exec } = require("child_process");

const app = express();

app.get("/api/ping", (req, res) => {
  exec(`ping -c 1 ${req.query.host}`, (err, stdout) => {
    if (err) {
      return res.status(500).send("ping failed");
    }
    res.type("text/plain").send(stdout);
  });
});

app.listen(3000);
