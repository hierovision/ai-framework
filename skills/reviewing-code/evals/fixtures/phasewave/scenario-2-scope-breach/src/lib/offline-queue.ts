// Offline outbox for focus-session mutations. Queued entries persist to
// localStorage (not in memory) so a started session survives a reload while
// offline. Replay-on-reconnect is a separate feature (feat-offline-replay)
// and is intentionally NOT wired here (see plan Excluded).
const STORAGE_KEY = 'phasewave:offline-queue'

export interface QueueEntry {
  id: string
  table: string
  op: 'insert' | 'update' | 'delete'
  row: Record<string, unknown>
}

function readQueue(): QueueEntry[] {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw ? (JSON.parse(raw) as QueueEntry[]) : []
}

function writeQueue(q: QueueEntry[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(q))
}

export function queueSession(
  payload: Omit<QueueEntry, 'id'> & { id?: string }
): QueueEntry {
  const entry: QueueEntry = {
    id: payload.id ?? `q-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    table: payload.table,
    op: payload.op,
    row: payload.row,
  }
  const q = readQueue()
  q.push(entry)
  writeQueue(q)
  return entry
}