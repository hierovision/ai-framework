// Request logging used by every handler.
function logRequest(req) {
  console.log(
    `[req] ${req.method} ${req.url} auth=${req.headers.authorization || "-"} ip=${req.ip}`
  );
}

module.exports = { logRequest };
