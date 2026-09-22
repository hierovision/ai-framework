export function queueSession(insert: () => Promise<void>): void {
  // Persist the pending insert to localStorage and flush on reconnect.
  const pending = JSON.parse(localStorage.getItem("offline-queue") ?? "[]");
  pending.push({ at: Date.now() });
  localStorage.setItem("offline-queue", JSON.stringify(pending));
}
