# feat-offline-queue

## Acceptance Criteria

| AC | Description | Verification |
|----|-------------|--------------|
| AC1 | Timer sessions queued while offline | `npm run test` |

## Files to Modify

| Path | Change |
|------|--------|
| `src/lib/offline-queue.ts` | new queue helper |
| `src/stores/focus-timer.ts` | route start() through the queue |

## Verification

```bash
npm run type-check && npm run lint && npm run test
```
