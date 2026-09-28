const express = require("express");
const { exec } = require("child_process");
const app = express();

app.get("/ping", (req, res) => {
  exec("ping -c 1 " + req.query.host, (err, stdout) => {
    res.send(stdout || String(err));
  });
});

app.listen(3000);
