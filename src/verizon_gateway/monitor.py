"""One long-lived process, monotonic cadence, graceful stop, no catch-up storm."""

import signal
import threading
import time

from .storage import Store, writer_lock
from .telemetry import snapshot


def next_tick(due, now, interval):
    return due + max(1, int((now - due) // interval) + 1) * interval


def run(client, database, *, interval=60, count=None, retention_days=90,
        stop=None, clock=time.monotonic, emit=print):
    stop = stop or threading.Event()
    original = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, signal.SIGTERM):
            original[sig] = signal.signal(sig, lambda *_: stop.set())
    try:
        with writer_lock(database):
            store = Store(database)
            try:
                due, failures, iterations, last_prune = clock(), 0, 0, float("-inf")
                while not stop.is_set() and (count is None or iterations < count):
                    sample = snapshot(client, radio_log=True)
                    store.save(sample)
                    iterations += 1
                    emit({"event": "sample", "collected_at": sample["collected_at"],
                          "status": sample["status"], "errors": sample["errors"]})
                    if clock() - last_prune >= 3600:
                        store.prune(retention_days)
                        last_prune = clock()
                    if count is not None and iterations >= count:
                        break
                    failures = min(failures + 1, 4) if sample["status"] == "error" else 0
                    now = clock()
                    due = next_tick(due, now, interval)
                    if failures:
                        due = max(due, now + min(300, interval * 2 ** (failures - 1)))
                    stop.wait(max(0, due - clock()))
                return iterations
            finally:
                store.close()
    finally:
        for sig, handler in original.items():
            signal.signal(sig, handler)
