// Formats a duration in seconds as a zero-padded timer string.
// MM:SS under one hour; HH:MM:SS at one hour and above.
// Pure function: no I/O, no store, no DOM, no clock, no collaborators.
function formatDuration(totalSeconds) {
  if (typeof totalSeconds !== 'number' || !Number.isFinite(totalSeconds)) {
    throw new RangeError('formatDuration requires a finite number of seconds')
  }
  if (totalSeconds < 0) {
    throw new RangeError('formatDuration requires a non-negative number of seconds')
  }
  const s = Math.floor(totalSeconds)
  const hours = Math.floor(s / 3600)
  const minutes = Math.floor((s % 3600) / 60)
  const seconds = s % 60
  const pad = (n) => String(n).padStart(2, '0')
  if (hours > 0) return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
  return `${pad(minutes)}:${pad(seconds)}`
}

module.exports = { formatDuration }
