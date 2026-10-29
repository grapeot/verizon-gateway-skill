# Test Plan: verizon-gateway-skill

- **Status:** Acceptance plan; execution evidence belongs in `working.md`.

## 1. Offline Automated Suite (CI)

CI runs offline tests exclusively using synthetic fixtures with placeholder hosts (`http://gateway.example`) and zero live hardware or credentials.

- **Configuration & Subprocess Safety:** Verify env parsing, JSON argv validation (`shell=False`) for `VERIZON_GATEWAY_PASSWORD_COMMAND` and `VERIZON_GATEWAY_URL_COMMAND`, and secret redaction on command failures.
- **Transport Guardrails:** Assert requests reject non-allowlisted paths/methods, enforce `X-Requested-With: XMLHttpRequest`, and never log URLs, bodies, credentials, or raw exceptions.
- **Normalization & Domain Rules:**
  - Preserve `null` vs `0` across all status, system, and radio metrics.
  - Normalize whitespace in `BLE.log` `5GSignal` keys (including `MCS`).
  - Keep cellular metrics intact when `networkType` reports `"Ethernet"`.
  - Expose `5GARFCN` and `PCI` without carrier inference or global-uniqueness assumptions.
  - Sort unordered `BLE.log` rows and set truncation metadata when hitting `--limit` or page bounds.
  - Emit only allowlisted Client Watch kickout interface identifiers, rejecting arbitrary raw banner strings.
- **Time & Freshness:** Test IANA timezone conversion, `>180s` staleness classification, non-carry-forward of stale radio values, and rejection of future or DST-ambiguous timestamps from fresh status.
- **SQLite & Monitor Loop:** Verify WAL schema v1 setup, `(source_observed_at, payload_hash)` deduplication across simulated log shifts, single-state banner/outage/access-tech/uptime-reset event edge detection, adjacent lock-file fail-fast, monotonic missed-tick skipping, auth-failure-only rate-limited re-login, bounded backoff, 90-day pruning, `export --format jsonl`, and `health --max-age`.

## 2. Opt-In Live Hardware Smoke Check

Run manually outside CI when an `LVSKIHP` gateway is configured locally: validate Playwright login + browser teardown, `inspect`, `snapshot --radio-log`, `logs --category ble --limit 200`, and `monitor --count 3`.
