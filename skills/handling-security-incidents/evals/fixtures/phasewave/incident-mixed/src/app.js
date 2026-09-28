const express = require("express");
const { exec } = require("child_process");
const app = express();

app.get("/diag", (req, res) => {
  exec("traceroute " + req.query.host, (err, stdout) => res.send(stdout));
});

app.listen(8080);
