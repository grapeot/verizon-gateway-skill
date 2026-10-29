from datetime import timedelta
import json

import httpx
import pytest

from verizon_gateway.client import GatewayClient, STATUS_PATH, DATA_PATH, LOG_PATH
from verizon_gateway.config import Config
from verizon_gateway.telemetry import utcnow


def radio_row(at=None, **values):
    at = at or utcnow()
    fields = {"RSRP": "-90", "RSRQ": "-12", "SINR": "0", "PCI": "123",
              "SSBI": "1", "MCS ": "9", "MO": "16_QAM", "5GARFCN": "123456"}
    fields.update(values)
    return {"Date": at.strftime("%b %d, %Y"), "Time": at.strftime("%H:%M:%S"),
            "str": "source: " + json.dumps({"5GSignal": fields})}


@pytest.fixture
def fake_gateway():
    state = {"calls": [], "auth_calls": 0, "modem": "5G", "uptime": "9000",
             "banner": "Router: Client Watch kickout by AP Router on wifi1\n",
             "rows": [radio_row(utcnow() - timedelta(seconds=10))], "fail": None}

    def authenticate(_):
        state["auth_calls"] += 1
        return {"session": "example-session"}

    def respond(request):
        state["calls"].append(request)
        assert request.method == "GET"
        assert request.headers["X-Requested-With"] == "XMLHttpRequest"
        if state["fail"]:
            return httpx.Response(state["fail"], text="example-sensitive-value")
        if request.url.path == STATUS_PATH:
            return httpx.Response(200, json={"modemtype": state["modem"],
                "networkType": "Ethernet", "rsrp": "-90", "signal": "-55",
                "internetStatus": "internetAllow", "alertMSG": state["banner"],
                "unexpected_private_field": "example-sensitive-value"})
        if request.url.path == LOG_PATH:
            start = int(request.url.params["startIdx"]) - 1
            count = int(request.url.params["logCount"])
            rows = state["rows"][start:start + count]
            return httpx.Response(200, json={"LogData": rows,
                "MoreData": len(state["rows"]) > start + count})
        assert request.url.path == DATA_PATH
        obj = json.loads(request.url.params["data"])["ObjName"]
        values = {
            "Device.Cellular.Interface.1.": {"Status": "Up", "CurrentAccessTechnology":
                state["modem"], "RSSI": "", "IMEI": "example-sensitive-value"},
            "Device.DeviceInfo.": {"ModelNumber": "LVSKIHP", "SoftwareVersion": "1.2.3",
                "UpTime": state["uptime"], "SerialNumber": "example-sensitive-value"},
            "Device.DeviceInfo.ProcessStatus.": {"CPUUsage": "0"},
            "Device.DeviceInfo.TemperatureStatus.TemperatureSensor.1.": {"Value": "30"},
        }[obj]
        return httpx.Response(200, json={"1": {"ObjName": obj, **values}, "status": "success"})

    client = GatewayClient(Config(url="http://gateway.example"),
        transport=httpx.MockTransport(respond), authenticator=authenticate)
    yield client, state
    client.close()
