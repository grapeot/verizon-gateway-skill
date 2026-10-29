from datetime import datetime, timedelta, timezone
import json

from conftest import radio_row
from verizon_gateway.telemetry import banner, number, parse_radio, snapshot

NOW = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)


def test_live_shape_and_privacy_projection(fake_gateway):
    client, state = fake_gateway
    result = snapshot(client, radio_log=True)
    assert result["status"] == "success"
    assert result["gateway"]["network_type"] == "Ethernet"
    assert result["cellular"]["access_technology"] == "5G"
    assert result["system"]["cpu_percent"] == 0
    assert result["cellular"]["rssi_reported"] is None
    assert result["current_radio"]["values"]["sinr_db"] == 0
    assert "example-sensitive-value" not in json.dumps(result)
    assert len(state["calls"]) == 6
    snapshot(client)
    assert state["auth_calls"] == 1


def test_time_ordering_and_no_stale_carry_forward(fake_gateway):
    client, state = fake_gateway
    state["rows"] = [radio_row(NOW), radio_row(NOW - timedelta(seconds=300))]
    rows = parse_radio(state["rows"], "UTC", NOW)
    assert [r["freshness"] for r in rows] == ["stale", "fresh"]
    assert rows[-1]["values"]["mcs"] == 9
    result = snapshot(client, radio_log=True)
    assert result["current_radio"] is None
    assert result["radio_observations"]


def test_ambiguous_nonexistent_future_time():
    ambiguous = datetime(2026, 11, 1, 1, 30)
    nonexistent = datetime(2026, 3, 8, 2, 30)
    for date in (ambiguous, nonexistent):
        result = parse_radio([radio_row(date)], "America/Los_Angeles", NOW)[0]
        assert result["freshness"] == "invalid_time"
        assert result["source_observed_at"] is None
    future = parse_radio([radio_row(NOW + timedelta(seconds=1))], "UTC", NOW)[0]
    assert future["freshness"] == "future"


def test_missing_zero_and_unknown_banner():
    assert number("0") == 0
    for value in (None, "", "N/A", "nan", True):
        assert number(value) is None
    assert banner("example-sensitive-value") is None
    assert banner("Router: Client Watch kickout by AP Router on wifi1\n") == {
        "kind": "client_watch_kickout", "interface": "wifi1"}


def test_malformed_rows_and_deduplication():
    row = radio_row(NOW)
    rows = parse_radio([None, {"str": "malformed"}, {"str": "{bad"}, row, row], "UTC", NOW)
    assert len(rows) == 1


def test_english_log_months_ignore_process_locale(monkeypatch):
    from verizon_gateway import telemetry

    class NoStrptime(datetime):
        @classmethod
        def strptime(cls, *_):
            raise AssertionError("locale-dependent parser used")

    monkeypatch.setattr(telemetry, "datetime", NoStrptime)
    result = parse_radio([{"Date": "Oct 29, 2026", "Time": "12:00:00",
                         "str": '{"5GSignal":{"SINR":"0"}}'}], "UTC",
                        datetime(2026, 10, 29, 12, tzinfo=timezone.utc))
    assert result[0]["freshness"] == "fresh"
