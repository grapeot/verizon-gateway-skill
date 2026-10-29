from datetime import timedelta
import json
import threading

import pytest

from verizon_gateway.cli import main
from verizon_gateway.config import GatewayError
from verizon_gateway.monitor import next_tick, run
from verizon_gateway.storage import Store, writer_lock
from verizon_gateway.telemetry import snapshot, utcnow


def test_transactional_history_radio_dedup_events_and_lock(tmp_path, fake_gateway):
    client, state = fake_gateway
    path = tmp_path / "history.sqlite"
    store = Store(path)
    store.save(snapshot(client, radio_log=True))
    store.save(snapshot(client, radio_log=True))
    assert store.db.execute("SELECT count(*) FROM radio_observations").fetchone()[0] == 1
    assert store.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
    state.update(modem="LTE", uptime="2", banner="")
    store.save(snapshot(client))
    kinds = {row[0] for row in store.db.execute("SELECT kind FROM events")}
    assert kinds == {"access_technology_changed", "uptime_reset", "banner_changed"}
    assert store.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert store.db.execute("PRAGMA user_version").fetchone()[0] == 1
    assert len(list(store.export((utcnow() - timedelta(days=1)).isoformat()))) == 7
    store.close()
    with writer_lock(path):
        with pytest.raises(GatewayError, match="monitor_already_running"):
            with writer_lock(path):
                pass


def test_monitor_error_and_recovery_keeps_same_session(tmp_path, fake_gateway):
    client, state = fake_gateway
    outputs = []
    stop = threading.Event()

    class FastStop:
        def is_set(self):
            return stop.is_set()

        def wait(self, _):
            if len(outputs) == 1:
                state["fail"] = 500
            elif len(outputs) == 2:
                state["fail"] = None

    path = tmp_path / "monitor.sqlite"
    assert run(client, path, interval=60, count=3, stop=FastStop(), emit=outputs.append) == 3
    assert [o["status"] for o in outputs] == ["success", "error", "success"]
    assert state["auth_calls"] == 1
    store = Store(path, readonly=True)
    assert {row[0] for row in store.db.execute("SELECT kind FROM events")} == {
        "collection_failed", "collection_recovered"}
    store.close()


def test_skip_missed_ticks():
    assert next_tick(100, 105, 60) == 160
    assert next_tick(100, 280, 60) == 340


def test_prune_and_offline_cli(tmp_path, fake_gateway, capsys):
    client, _ = fake_gateway
    path = tmp_path / "history.sqlite"
    store = Store(path)
    store.save(snapshot(client, radio_log=True))
    assert main(["health", "--database", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["healthy"] is True
    assert main(["export", "--database", str(path), "--since", "24h"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert {json.loads(line)["kind"] for line in lines} == {"samples", "radio_observations"}
    with store.db:
        store.db.execute("UPDATE samples SET collected_at='2000-01-01T00:00:00+00:00'")
    store.prune(90)
    assert store.latest() is None
    store.close()


def test_empty_and_missing_database_health(tmp_path, capsys):
    path = tmp_path / "empty.sqlite"
    assert main(["health", "--database", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "database_not_found"
    store = Store(path)
    store.close()
    assert main(["health", "--database", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["healthy"] is False
