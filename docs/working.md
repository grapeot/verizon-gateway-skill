# Working Log

## Changelog

### 2026-10-29
- Accepted English public skill + CLI design with LVSKIHP-only verified support.
- Scaffolded documentation before implementation; default branch is master.
- Implementing bounded read-only transport, source timestamps, SQLite and a continuous collector.
- Implemented allowlisted reads, one-read auth-expiry recovery, failed-login cooldown, locale-independent log dates, freshness, SQLite/WAL/dedup/events/retention and single-writer locking.
- Offline verification: 21 passed, 1 live test deselected; Ruff passed. Synthetic wheel/sdist exclusion and rebuild checks passed.
- Opt-in hardware verification: 1 passed. Host-supervised bounded acceptance: 2 successful persisted samples, exit 0, explicit diagnosis opt-out in process metadata.
- Independent code review and privacy review: PASS after resolving session retry, locale parsing and package selection findings.
- Host integration uses a continuous 60-second collector. Declaration is persisted; initial bootstrap uses a one-off process launch until the operator's next supervisor restart.
- Continuous hardware acceptance: three successful samples at approximately 60-second spacing; 110 deduplicated radio observations; stored-history health and latest radio freshness passed.
- Public CI passed. Protected master requires the test check and pull requests, zero mandatory approving reviews, and administrator enforcement.

## Implementation Checklist
- [x] Offline tests and lint
- [x] Opt-in live hardware checks
- [x] Independent code and privacy reviews
- [x] CI, protected master and reviewed pull request ready for authorized merge
- [x] Private host integration and monitored continuous collector (bootstrap until next supervisor restart)

## Lessons Learned
- LVSKIHP is a model; the manufacturer is Wistron NeWeb Corporation.
- BLE.log contains radio observations despite the UI category name.
- A successful HTTP response may contain an application error or stale log rows.
- Client Watch banner persistence does not establish repeated disconnection events.

## Open Validation
- Authentication session lifetime under continuous polling.
- Log rotation and bounded pagination coverage over extended operation.
- Which radio/anchor the firmware labels 5GSignal and 5GARFCN describe.
