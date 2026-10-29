# verizon-gateway-skill

Read-only telemetry CLI and agent skill for Verizon home internet gateways. Initial hardware support targets model **LVSKIHP**, manufactured by **Wistron NeWeb Corporation (WNC)**. Compatibility with other gateway models or firmware revisions is not assumed.

Initial support is limited to the verified LVSKIHP interface. See `docs/rfc.md` for field semantics and open validation.

## Scope and Limitations

- **Read-only:** Performs standard browser login, closes the browser immediately, and queries allowlisted HTTP `GET` endpoints.
- **No device mutation:** Never changes settings, reboots hardware, runs speed tests, updates firmware, enables shell access, or uses engineering credentials.
- **Local CLI and SQLite:** Persists normalized telemetry locally; includes no REST server or dashboard.

## Setup

Create a virtual environment with `uv`, install the package, and set up Chrome for Playwright authentication:

```bash
cd /path/to/project
uv venv
source .venv/bin/activate
uv pip install -e .
playwright install chrome
```

## Configuration

```bash
export VERIZON_GATEWAY_URL="http://gateway.example"
export VERIZON_GATEWAY_USERNAME="admin"          # default: admin
export VERIZON_GATEWAY_TIMEZONE="UTC"            # default: UTC (IANA timezone)
export VERIZON_GATEWAY_BROWSER_CHANNEL="chrome"  # default: chrome
export VERIZON_GATEWAY_PASSWORD="example-password"

# Optional JSON argv command hooks (shell=False; any local command works, 1Password not required):
export VERIZON_GATEWAY_PASSWORD_COMMAND='["op", "read", "op://your-vault/your-item/your-field"]'
export VERIZON_GATEWAY_URL_COMMAND='["printf", "%s", "http://gateway.example"]'
```

## CLI Usage

```bash
verizon-gateway inspect
verizon-gateway snapshot --radio-log
verizon-gateway logs --category ble --limit 200
verizon-gateway monitor --interval 60 --database data/telemetry.sqlite
verizon-gateway monitor --interval 60 --database data/telemetry.sqlite --count 5
verizon-gateway export --database data/telemetry.sqlite --since 24h --format jsonl
verizon-gateway health --database data/telemetry.sqlite --max-age 180
```

- `inspect`: One-shot gateway, cellular, and system status.
- `snapshot --radio-log`: Status paired with recent normalized radio log observations.
- `logs --category ble --limit 200`: Bounded allowlisted `BLE.log` radio rows (no raw arbitrary log export).
- `monitor`: Continuous local collector (`--count` optional for bounded acceptance runs).
- `export` / `health`: Export retained rows as JSONL or verify collector freshness against `--max-age` seconds.

## Data Retention and Supervision

`monitor` stores data in a local SQLite database outside `src/` (e.g., `data/telemetry.sqlite`) with WAL mode, an adjacent single-writer lock, and 90-day default retention. Supervise long-running collection with your host service manager (`launchd`, `systemd`, etc.); the collector handles `SIGINT`/`SIGTERM` cleanly and records transient failures rather than exiting.

## Installing as an Agent Skill

Hand this repository's GitHub URL to Codex, Claude Code, Cursor, or OpenCode to install. The agent reads your host `AGENTS.md` or `CLAUDE.md` and skill routing index, registers one root skill (`skills/verizon-gateway/SKILL.md`), and stores private aliases, routes, and credential references in a host-owned overlay.

## Repository Layout

```text
AGENTS.md
LICENSE                          # MIT
.env.example
.github/workflows/ci.yml
docs/
  prd.md
  rfc.md
  working.md
  test.md
skills/
  verizon-gateway/SKILL.md
src/
  verizon_gateway/
    py.typed
tests/
```
