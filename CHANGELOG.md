# Changelog

## 2026-10-20

- Trade aggregation now reports the complete amount of a closed 60-second series,
  rather than only the amount at its first alert-threshold crossing. Actual cash,
  shares and weighted prices remain consistent across downstream consumers.
- Pending trade series survive restarts. Incomplete API polls and callback pressure
  retain pending work instead of silently discarding it.
- Insider signals are recorded as published only after Telegram confirms delivery.
  Confirmed receipts can recover local bookkeeping without sending again; uncertain
  network outcomes require reconciliation rather than blind retries.
- Telegram formatting errors have a bounded plain-text fallback. Public pages escape
  external text while keeping existing routes and access controls.
- Existing user filters, category selections and saved preferences are preserved.

Fresh trade aggregation can add up to 60 seconds plus the next successful poll,
in addition to source/API latency. A series is a time-based grouping, not a proven
exchange order ID. Exactly-once external delivery is not guaranteed.

Validation included 104 isolated automated checks, owner-only test-bot delivery,
and ordinary production-alert delivery after rollout. Insider failure/recovery cases
used synthetic integrated tests; a naturally occurring insider publication has not
yet validated the new delivery path.

The public repository remains a demonstration shell with core implementations
removed. It is not a runnable copy of the production service.
