"""Local SQLite history, transition events, and single-writer process locking."""

from contextlib import contextmanager
from datetime import timedelta
import fcntl
import json
import os
from pathlib import Path
import sqlite3

from .config import GatewayError
from .telemetry import utcnow


@contextmanager
def writer_lock(path):
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.with_suffix(path.suffix + ".lock").open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise GatewayError("monitor_already_running") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Store:
    def __init__(self, path, *, readonly=False):
        self.path = Path(path).expanduser().resolve()
        if readonly:
            if not self.path.is_file():
                raise GatewayError("database_not_found")
            self.db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.db = sqlite3.connect(self.path, timeout=5)
            os.chmod(self.path, 0o600)
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                self.db.close()
                raise GatewayError("unsupported_database_version")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY, collected_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS samples_time ON samples(collected_at);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, collected_at TEXT NOT NULL,
                    kind TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS events_time ON events(collected_at);
                CREATE TABLE IF NOT EXISTS radio_observations (
                    observation_id TEXT PRIMARY KEY, first_seen_at TEXT NOT NULL,
                    source_observed_at TEXT, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS radio_seen ON radio_observations(first_seen_at);
                PRAGMA user_version=1;
            """)
        self.db.row_factory = sqlite3.Row

    def close(self):
        self.db.close()

    def latest(self, successful=False):
        condition = "WHERE status='success'" if successful else ""
        row = self.db.execute(f"SELECT payload FROM samples {condition} ORDER BY id DESC LIMIT 1")
        value = row.fetchone()
        return json.loads(value[0]) if value else None

    def save(self, sample):
        previous = self.latest()
        # Compare device-state transitions against the last complete sample,
        # not an intervening error or partially missing subsystem.
        baseline = self.latest(successful=True)
        events = []
        if previous and (previous["status"] == "error") != (sample["status"] == "error"):
            events.append(("collection_recovered" if sample["status"] != "error"
                           else "collection_failed", {"status": sample["status"]}))
        if baseline and sample["status"] == "success":
            comparisons = [
                ("banner_changed", "gateway", "banner"),
                ("access_technology_changed", "cellular", "access_technology"),
                ("internet_status_changed", "gateway", "internet_status"),
            ]
            for kind, section, key in comparisons:
                old, new = baseline.get(section, {}).get(key), sample.get(section, {}).get(key)
                if old != new and (kind == "banner_changed" or (old is not None and new is not None)):
                    events.append((kind, {"old": old, "new": new}))
            old = baseline.get("system", {}).get("uptime_seconds")
            new = sample.get("system", {}).get("uptime_seconds")
            if old is not None and new is not None and new < old:
                events.append(("uptime_reset", {"previous_seconds": old, "current_seconds": new}))
        persisted = {k: v for k, v in sample.items() if k != "radio_observations"}
        with self.db:
            self.db.execute(
                "INSERT INTO samples(collected_at,completed_at,status,payload) VALUES (?,?,?,?)",
                (sample["collected_at"], sample["completed_at"], sample["status"], encode(persisted)))
            for kind, payload in events:
                self.db.execute("INSERT INTO events(collected_at,kind,payload) VALUES (?,?,?)",
                                (sample["collected_at"], kind, encode(payload)))
            for observation in sample.get("radio_observations", []):
                self.db.execute("""INSERT OR IGNORE INTO radio_observations
                    (observation_id,first_seen_at,source_observed_at,payload) VALUES (?,?,?,?)""",
                    (observation["observation_id"], sample["collected_at"],
                     observation["source_observed_at"], encode(observation)))

    def prune(self, days=90):
        cutoff = (utcnow() - timedelta(days=days)).isoformat()
        with self.db:
            for table, column in (("samples", "collected_at"), ("events", "collected_at"),
                                  ("radio_observations", "first_seen_at")):
                self.db.execute(f"DELETE FROM {table} WHERE rowid IN "
                                f"(SELECT rowid FROM {table} WHERE {column} < ? LIMIT 10000)",
                                (cutoff,))

    def export(self, since):
        for table, column in (("samples", "collected_at"), ("events", "collected_at"),
                              ("radio_observations", "first_seen_at")):
            for row in self.db.execute(f"SELECT * FROM {table} WHERE {column} >= ? "
                                       f"ORDER BY {column}", (since,)):
                yield {"kind": table, "record": dict(row) | {"payload": json.loads(row["payload"])}}
