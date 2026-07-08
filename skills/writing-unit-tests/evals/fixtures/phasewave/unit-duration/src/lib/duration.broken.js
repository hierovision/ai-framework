// SEEDED BROKEN VARIANT of src/lib/duration.js — used only for the
// meaningfulness proof. The authored unit test must go RED against this
// variant (it breaks the guarded behaviour) and GREEN against the real
// module. Restore the real module after the proof.
function formatDuration(totalSeconds) {
  // BROKEN: returns the raw seconds as a string with no padding, no
  // HH:MM:SS branch, and no RangeError on negatives. Every acceptance
  // criterion's observable output is wrong here.
  return String(totalSeconds)
}

module.exports = { formatDuration }
