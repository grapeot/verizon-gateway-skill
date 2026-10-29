# Product Requirements Document: verizon-gateway-skill

- **Status:** Accepted implementation scope
- **Target Hardware:** Verizon Home Internet Gateway model **LVSKIHP** (manufactured by Wistron NeWeb Corporation, WNC)

## Problem Statement

Diagnosing intermittent cellular drops, 5G/LTE transitions, and Wi-Fi Client Watch events on Verizon home gateways is difficult when relying solely on point-in-time web UI checks. Operators and AI coding agents need structured, read-only local telemetry with clear freshness guarantees and durable history, without risking configuration changes or leaking sensitive router payloads.

## Goals

1. **Read-Only Inspection & Monitoring:** Provide a CLI (`verizon-gateway`) for live status (`inspect`), radio-enriched snapshots (`snapshot --radio-log`), bounded `BLE.log` queries (`logs`), continuous SQLite collection (`monitor`), JSONL export (`export`), and freshness checks (`health`).
2. **Evidence-Grade Semantics:** Distinguish missing values from `0`, mark radio rows older than 180 seconds as stale without carrying stale metrics forward, preserve UTC and router-local timestamps separately, and avoid unsupported inferences (such as treating `networkType="Ethernet"` as missing cellular, treating `PCI` as globally unique, or inferring mmWave carriers from `5GARFCN` before firmware verification).
3. **Safe Local Operation:** Redact sensitive data from logs, support secret-manager-agnostic command hooks (`shell=False`), expose only recognized Client Watch interface identifiers rather than raw banner text, and tolerate transient network failures gracefully.
4. **Agent Skill Integration:** Ship one root `SKILL.md` guiding agents through evidence-based diagnostics while delegating local routes and credentials to a private host overlay.

## Non-Goals

- Supporting unverified Verizon gateway models or firmware universally.
- Modifying settings, rebooting hardware, running speed tests, updating firmware, enabling shell access, or bypassing normal login.
- Providing an HTTP server, remote API, or web dashboard.
