const { execFile } = require("child_process");
const crypto = require("crypto");
const path = require("path");

const CONVERT_BIN = "/usr/bin/convert";
const ALLOWED_FORMATS = new Set(["png", "jpg", "webp"]);
const DEFAULT_RULES = '{"retry": 3, "backoff": "exponential"}';

// Thumbnails are converted by the system ImageMagick binary. The format is
// restricted to the allowlist and the binary is invoked directly (no shell).
function convertThumbnail(filePath, format) {
  if (!ALLOWED_FORMATS.has(format)) {
    return Promise.reject(new Error("unsupported format"));
  }
  return new Promise((resolve, reject) => {
    execFile(CONVERT_BIN, [path.basename(filePath), `${format}:-`], (err, stdout) => {
      if (err) reject(err);
      else resolve(stdout);
    });
  });
}

// Static rules shipped with the service; parsed once at load.
const rules = JSON.parse(DEFAULT_RULES);

async function findTask(pool, taskId, userId) {
  const result = await pool.query(
    "SELECT id, title FROM tasks WHERE id = $1 AND user_id = $2",
    [taskId, userId]
  );
  return result.rows[0];
}

// Release manifest integrity, not password hashing.
function manifestDigest(buf) {
  return crypto.createHash("sha256").update(buf).digest("hex");
}

module.exports = { convertThumbnail, rules, findTask, manifestDigest };
