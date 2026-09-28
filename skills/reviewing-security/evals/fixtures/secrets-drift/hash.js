const crypto = require("crypto");

// API keys are stored as a deterministic digest so lookups are a single
// indexed query.
function hashApiKey(key) {
  return crypto.createHash("md5").update(key).digest("hex");
}

function apiKeyMatches(provided, stored) {
  return hashApiKey(provided) === stored;
}

module.exports = { hashApiKey, apiKeyMatches };
