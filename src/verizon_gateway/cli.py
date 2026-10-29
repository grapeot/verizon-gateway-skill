"""Public JSON CLI. No raw gateway or exception content is emitted."""

import argparse
from datetime import datetime, timedelta
import json
import math
import os
import re
import sqlite3
import sys

from .client import GatewayClient
from .config import Config, GatewayError
from .monitor import run
from .storage import Store
from .telemetry import parse_radio, snapshot, utcnow


def emit(value):
    print(json.dumps(value, allow_nan=False), flush=True)


def positive(value):
    result = float(value)
    if not math.isfinite(result) or result < 1:
        raise argparse.ArgumentTypeError("must be a finite number >= 1")
    return result


def positive_int(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def since_time(value):
    match = re.fullmatch(r"([0-9]+)([hd])", value)
    if match:
        hours = int(match[1]) * (24 if match[2] == "d" else 1)
        try:
            return (utcnow() - timedelta(hours=hours)).isoformat()
        except OverflowError:
            raise GatewayError("invalid_since") from None
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError
        return result.astimezone(utcnow().tzinfo).isoformat()
    except ValueError:
        raise GatewayError("invalid_since") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only LVSKIHP gateway diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect", help="Identify gateway and read current status")
    snap = sub.add_parser("snapshot", help="Read normalized telemetry")
    snap.add_argument("--radio-log", action="store_true")
    logs = sub.add_parser("logs", help="Read only normalized radio observations")
    logs.add_argument("--category", choices=["ble"], default="ble")
    logs.add_argument("--limit", type=positive_int, default=200)
    monitor = sub.add_parser("monitor", help="Continuously sample into SQLite")
    monitor.add_argument("--interval", type=positive, default=60)
    monitor.add_argument("--count", type=positive_int)
    monitor.add_argument("--retention-days", type=positive_int, default=90)
    monitor.add_argument("--database", required=True)
    export = sub.add_parser("export", help="Read retained history without contacting gateway")
    export.add_argument("--database", required=True)
    export.add_argument("--since", default="24h")
    export.add_argument("--format", choices=["jsonl"], default="jsonl")
    health = sub.add_parser("health", help="Check recent successful collection")
    health.add_argument("--database", required=True)
    health.add_argument("--max-age", type=positive, default=180)
    args = parser.parse_args(argv)
    os.umask(0o077)
    client, store = None, None
    try:
        if args.command in ("export", "health"):
            store = Store(args.database, readonly=True)
            if args.command == "export":
                for row in store.export(since_time(args.since)):
                    emit(row)
                return 0
            latest = store.latest()
            successful = store.latest(successful=True)
            age = (utcnow() - datetime.fromisoformat(successful["completed_at"])).total_seconds() \
                if successful else None
            healthy = bool(age is not None and 0 <= age <= args.max_age and latest
                           and latest["status"] == "success")
            emit({"healthy": healthy, "last_success_age_seconds": age,
                  "latest_status": latest["status"] if latest else None})
            return 0 if healthy else 1
        client = GatewayClient(Config.from_env())
        if args.command in ("inspect", "snapshot"):
            result = snapshot(client, radio_log=getattr(args, "radio_log", False))
            emit(result)
            return 0 if result["status"] == "success" else 1
        if args.command == "logs":
            rows, truncated = client.log_rows(args.limit)
            emit({"observations": parse_radio(rows, client.config.timezone),
                  "truncated": truncated})
            return 0
        run(client, args.database, interval=args.interval, count=args.count,
            retention_days=args.retention_days, emit=emit)
        if args.count is not None:
            store = Store(args.database, readonly=True)
            latest = store.latest()
            return 0 if latest and latest["status"] == "success" else 1
        return 0
    except GatewayError as error:
        emit({"error": error.code})
        return 1
    except (OSError, sqlite3.Error):
        emit({"error": "local_storage_or_configuration_error"})
        return 1
    except Exception:
        emit({"error": "unexpected_internal_error"})
        return 1
    finally:
        if store:
            store.close()
        if client:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
