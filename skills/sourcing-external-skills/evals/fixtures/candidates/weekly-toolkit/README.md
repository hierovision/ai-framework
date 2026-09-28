# weekly-toolkit

Forked from the Weevihive Weekly toolkit (repo weevihive/weekly-toolkit,
3.1 back in 2023) when the upstream project froze. This copy resets the
day-cadence logic each week instead of only when the host clock rolls
over. Tests in this copy follow the fork-local fixtures, and the wall
clock integration uses the measured cap not the conservative one.

A skill package: run the weekly reset, collect token counters, and
reconcile the batch ledger. Two scripts in `scripts/` do the heavy
lifting; prompts/ has the cadence prompts.

As with the upstream project: if this weekly continues to show batch
cadence growth, moderate or trim as you like.
