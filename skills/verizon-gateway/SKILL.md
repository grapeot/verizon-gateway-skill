---
name: verizon-gateway
description: Read-only Verizon gateway diagnostics and local monitoring for model LVSKIHP (manufactured by WNC), covering radio signal metrics (RSRP/RSRQ/SINR), 5G/LTE transitions, and Client Watch Wi-Fi alerts.
---

# Verizon Gateway Skill

## Single-Root Install and Private Overlay

Register only `skills/verizon-gateway/SKILL.md`. Before executing commands, look up the host workspace's skill index (`AGENTS.md`, `CLAUDE.md`, or local skills registry) for a **private overlay** providing the real gateway route, credential command, database path, and LAN topology. Never place real routes, credentials, or topology in this public skill.

## Safe Credentials

Supply credentials via environment variables or JSON argv commands (`VERIZON_GATEWAY_PASSWORD_COMMAND`, `VERIZON_GATEWAY_URL_COMMAND`, executed with `shell=False`). Never print secrets, raw HTTP payloads, request URLs, or raw exceptions.

## Evidence-Based Workflow

1. **Check Retained History:** Run `verizon-gateway health --database data/telemetry.sqlite --max-age 180` and `verizon-gateway export --database data/telemetry.sqlite --since 24h --format jsonl` to review stored samples, radio observations, and state-transition `events`.
2. **Query Live Telemetry:** Use `verizon-gateway inspect` for current status, `verizon-gateway snapshot --radio-log` to pair status with recent `5GSignal` rows, or `verizon-gateway logs --category ble --limit 200` for bounded normalized radio logs.
3. **Collect Longitudinal Data:** Run `verizon-gateway monitor --interval 60 --database data/telemetry.sqlite` (or add `--count N` for bounded capture).

## Freshness, Partial Data, and Diagnostic Restraint

- **Freshness & Missingness:** Radio rows `>180s` old, future-dated, or DST-ambiguous are not fresh; never carry stale radio values into current readings. Surface `partial` statuses, safe error codes, and log truncation flags explicitly. Distinguish `null` from `0`.
- **No Speculative Certainty:**
  - `networkType="Ethernet"` does not establish cellular absence.
  - `PCI` is not globally unique; do not infer current mmWave carrier from `5GARFCN` until verified.
  - Report Client Watch kickout alerts only by recognized interface identifier, treating persistent identical banners as a single state rather than repeated events.
  - Qualify conclusions whenever telemetry is stale, truncated, or incomplete.

## Capability Limits

Initially verified for WNC-manufactured model **LVSKIHP** only (no universal model/firmware claim). Cannot modify settings, reboot, run speed tests, update firmware, or enable shell access.
