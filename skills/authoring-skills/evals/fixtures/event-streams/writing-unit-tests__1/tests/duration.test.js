const assert = require("node:assert");
const { formatDuration } = require("../src/lib/duration");

// AC1: formatDuration(0) === '00:00'
assert.strictEqual(formatDuration(0), "00:00");
// AC2: formatDuration(65) === '01:05'
assert.strictEqual(formatDuration(65), "01:05");
// AC3: formatDuration(3661) === '01:01:01'
assert.strictEqual(formatDuration(3661), "01:01:01");
// AC4: formatDuration(-5) throws RangeError
assert.throws(() => formatDuration(-5), RangeError);
