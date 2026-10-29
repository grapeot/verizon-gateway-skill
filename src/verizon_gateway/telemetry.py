"""Typed-value normalization with explicit source age and conservative semantics."""

from datetime import datetime, timezone
import hashlib
import json
import math
import re
from zoneinfo import ZoneInfo

from .client import STATUS_PATH
from .config import GatewayError

UTC = timezone.utc
RADIO_FIELDS = {"RSRP": "rsrp_dbm", "RSRQ": "rsrq_db", "SINR": "sinr_db",
                "PCI": "pci", "SSBI": "ssbi", "MCS": "mcs", "5GARFCN": "arfcn_reported"}
MONTHS = {name: index for index, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def utcnow():
    return datetime.now(UTC)


def number(value):
    try:
        if value is None or isinstance(value, bool) or value == "":
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def enum(value, choices):
    return value if value in choices else None


def banner(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(
        r"\s*Router: Client Watch kickout by AP Router on (wifi[0-9]{1,2})\s*", value)
    return {"kind": "client_watch_kickout", "interface": match.group(1)} if match else None


def parse_local_time(local):
    match = re.fullmatch(r"([A-Za-z]{3}) (\d{1,2}), (\d{4}) (\d{2}):(\d{2}):(\d{2})", local)
    if not match or match[1] not in MONTHS:
        raise ValueError("invalid_log_time")
    return datetime(int(match[3]), MONTHS[match[1]], int(match[2]),
                    int(match[4]), int(match[5]), int(match[6]))


def source_time(local, zone):
    naive = parse_local_time(local)
    tz = ZoneInfo(zone)
    first, second = naive.replace(tzinfo=tz, fold=0), naive.replace(tzinfo=tz, fold=1)
    if first.utcoffset() != second.utcoffset():
        return None
    converted = first.astimezone(UTC)
    if converted.astimezone(tz).replace(tzinfo=None) != naive:
        return None
    return converted


def parse_radio(rows, zone, now=None):
    now = now or utcnow()
    observations = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = row.get("str", "")
        if not isinstance(text, str) or "{" not in text:
            continue
        try:
            signal = json.loads(text[text.index("{"):]).get("5GSignal")
            if not isinstance(signal, dict):
                continue
            signal = {key.strip(): value for key, value in signal.items()}
            local = row.get("Date", "") + " " + row.get("Time", "")
            observed = source_time(local, zone)
            # Re-format parsed time to avoid retaining arbitrary date strings.
            local = parse_local_time(local).isoformat()
        except (ValueError, TypeError, AttributeError):
            continue
        values = {target: number(signal.get(key)) for key, target in RADIO_FIELDS.items()}
        values["modulation"] = enum(signal.get("MO"),
            ("QPSK", "16_QAM", "64_QAM", "256_QAM", "1024_QAM"))
        age = (now - observed).total_seconds() if observed else None
        freshness = ("invalid_time" if age is None else "future" if age < 0
                     else "stale" if age > 180 else "fresh")
        payload = json.dumps(values, sort_keys=True)
        digest = hashlib.sha256((local + payload).encode()).hexdigest()
        observations[digest] = {
            "source": "BLE.log:5GSignal", "source_observed_at":
                observed.isoformat() if observed else None,
            "source_local_time": local, "source_timezone": zone,
            "age_seconds": age, "freshness": freshness, "values": values,
            "observation_id": digest,
        }
    return sorted(observations.values(), key=lambda r: r["source_local_time"])


def snapshot(client, *, radio_log=False, log_limit=200):
    started = utcnow()
    result = {"schema_version": 1, "collected_at": started.isoformat(), "status": "success",
              "errors": {}, "gateway": {}, "cellular": {}, "system": {}}

    def read(name, callback):
        try:
            return callback()
        except GatewayError as error:
            result["errors"][name] = error.code
            return None

    raw = read("gateway", lambda: client.get(STATUS_PATH))
    if raw is not None:
        result["gateway"] = {
            "modem_type": enum(raw.get("modemtype"), ("5G", "LTE", "4G", "")),
            "network_type": enum(raw.get("networkType"),
                ("Ethernet", "5G", "LTE", "4G LTE", "No Service", "")),
            "rsrp_dbm": number(raw.get("rsrp")), "signal_uninterpreted": number(raw.get("signal")),
            "internet_status": enum(raw.get("internetStatus"),
                ("internetAllow", "internetDeny", "internetBlock", "internetDisconnect", "")),
            "banner": banner(raw.get("alertMSG")),
        }
    cell = read("cellular", lambda: client.object("Device.Cellular.Interface.1."))
    if cell:
        result["cellular"] = {
            "status": enum(cell.get("Status"), ("Up", "Down", "Dormant", "Unknown", "Error")),
            "access_technology": enum(cell.get("CurrentAccessTechnology"),
                ("5G", "LTE", "4G", "5G NSA", "5G SA", "No Service", "")),
            "rssi_reported": number(cell.get("RSSI")),
        }
    info = read("device", lambda: client.object("Device.DeviceInfo."))
    if info:
        if info.get("ModelNumber") != "LVSKIHP":
            result["errors"]["model"] = "unsupported_model"
        version = info.get("SoftwareVersion")
        result["system"].update({"model": "LVSKIHP" if info.get("ModelNumber") == "LVSKIHP"
            else "unsupported", "manufacturer": "Wistron NeWeb Corporation",
            "firmware": version if isinstance(version, str)
                and re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,5}", version) else None,
            "uptime_seconds": number(info.get("UpTime"))})
    temp = read("temperature", lambda: client.object(
        "Device.DeviceInfo.TemperatureStatus.TemperatureSensor.1."))
    cpu = read("cpu", lambda: client.object("Device.DeviceInfo.ProcessStatus."))
    result["system"]["temperature_c"] = number(temp.get("Value")) if temp else None
    result["system"]["cpu_percent"] = number(cpu.get("CPUUsage")) if cpu else None
    if radio_log:
        logs = read("radio_log", lambda: client.log_rows(log_limit))
        observations = parse_radio(logs[0], client.config.timezone) if logs else []
        result["radio_observations"] = observations
        result["radio_log_truncated"] = logs[1] if logs else None
        # Historical observations remain available, but stale values never fill current metrics.
        fresh = [r for r in observations if r["freshness"] == "fresh"]
        result["current_radio"] = fresh[-1] if fresh else None
    result["completed_at"] = utcnow().isoformat()
    if result["errors"]:
        result["status"] = "partial" if raw is not None else "error"
    return result
