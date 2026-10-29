# Technical RFC: verizon-gateway-skill

- **Status:** Accepted implementation design
- **Verified Target:** Verizon Home Gateway model **LVSKIHP** (manufactured by Wistron NeWeb Corporation, WNC)

## 1. Configuration and Secret Resolution

- `VERIZON_GATEWAY_URL` or optional `VERIZON_GATEWAY_URL_COMMAND` (JSON argv array executed with `shell=False`).
- `VERIZON_GATEWAY_PASSWORD` or optional `VERIZON_GATEWAY_PASSWORD_COMMAND` (JSON argv array, `shell=False`; generic local command hook, no mandatory 1Password or built-in secret provider).
- `VERIZON_GATEWAY_USERNAME` (`admin`), `VERIZON_GATEWAY_TIMEZONE` (`UTC`, IANA timezone), `VERIZON_GATEWAY_BROWSER_CHANNEL` (`chrome`).

## 2. Authentication and Read-Only Transport

1. **Login:** Playwright opens `VERIZON_GATEWAY_BROWSER_CHANNEL` for standard login only, captures cookies into memory, and closes the browser immediately.
2. **Reads:** Ordinary HTTP `GET` requests carry in-memory cookies and mandatory `X-Requested-With: XMLHttpRequest`.
3. **LVSKIHP GET Allowlist:**
   - `/cgi-bin/luci/verizon/network/getStatus`
   - `/cgi-bin/luci/cgi` (`api=get` with strictly enumerated objects/fields)
   - `/cgi-bin/luci/verizon/system_settings/log` (`action=getlog`, `category=BLE.log`, bounded pagination)

Settings writes, reboots, speed tests, firmware updates, shell enablement, and engineering credential bypasses are prohibited.

## 3. Telemetry Normalization and Time Model

- **Status & System:** `modemtype`, `networkType` (`"Ethernet"` does not establish cellular absence), `RSRP`, uninterpreted `signal`, internet status, cellular status and access technology, model, firmware, `uptime` (s), temperature (°C), CPU (%).
- **BLE Log (`5GSignal`):** Normalize key whitespace (including `MCS`) and parse `RSRP`, `RSRQ`, `SINR`, `PCI`, `SSBI`, `MO`, `MCS`, `5GARFCN`. `PCI` is not globally unique; do not infer current mmWave carrier from `5GARFCN` until verified.
- **Time & Missingness:** Store `collected_at` (UTC), `source_observed_at` (UTC), and original local timestamp converted via `VERIZON_GATEWAY_TIMEZONE`. Future or DST-ambiguous timestamps never count as fresh. Distinguish `null` (missing) from `0`. Radio rows `>180s` old are stale and never carried into current measurements.
- **Ordering, Truncation & Banners:** Read bounded recent pages, ignore response ordering (sort by parsed timestamp), and expose truncation flags. Expose only a recognized Client Watch kickout interface identifier—never raw banner text; a persistent identical banner is one ongoing state, not repeated events.

## 4. SQLite Storage and Monitor Lifecycle

- **Database:** Stored outside `src/` in a gitignored directory; `schema_version = 1`, WAL mode, indexes, transactional writes.
  - `samples`: start/completion timestamps, `success`/`partial`/`error`, structured JSON, safe error code.
  - `events`: Client Watch banner changes, access-tech transitions, uptime resets, internet outage/recovery.
  - `radio_observations`: deduplicated by `(source_observed_at, normalized_payload_hash)`, never mutable log file index.
- **Retention & Export:** 90-day default retention with infrequent bounded pruning; JSONL output via `export`.
- **Collector (`monitor`):** Adjacent single-writer lock fails fast on duplicates. Monotonic cadence skips missed ticks without overlap or catch-up storms. `SIGINT`/`SIGTERM` stop gracefully. Transient network failures persist safe error codes with bounded exponential backoff instead of exiting. Cookies persist across ticks, expiring/re-logging in via Playwright only on auth failure with rate limiting. Supervision remains host-specific; no REST server or dashboard is included.
- **Redaction:** Never log credentials, response bodies, request URLs, or raw exceptions.

## 5. Open Validation

Extended live runs are still needed to validate LVSKIHP authentication session TTL and `BLE.log` rotation behavior.
