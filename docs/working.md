# Working Log

## Changelog

### 2026-10-29
- Accepted English public skill + CLI design with LVSKIHP-only verified support.
- Scaffolded documentation before implementation; default branch is master.
- Implementing bounded read-only transport, source timestamps, SQLite and a continuous collector.

## Implementation Checklist
- [ ] Offline tests and lint
- [ ] Opt-in live hardware checks
- [ ] Independent code and privacy reviews
- [ ] CI, protected master, pull request and merge
- [ ] Private host integration and monitored continuous service

## Lessons Learned
- LVSKIHP is a model; the manufacturer is Wistron NeWeb Corporation.
- BLE.log contains radio observations despite the UI category name.
- A successful HTTP response may contain an application error or stale log rows.
- Client Watch banner persistence does not establish repeated disconnection events.

## Open Validation
- Authentication session lifetime under continuous polling.
- Log rotation and bounded pagination coverage over extended operation.
- Which radio/anchor the firmware labels 5GSignal and 5GARFCN describe.
