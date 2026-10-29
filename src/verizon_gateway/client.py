"""Strict read-only LVSKIHP transport and in-memory session lifecycle."""

import json
import time

import httpx

from .auth import login
from .config import Config, GatewayError

STATUS_PATH = "/cgi-bin/luci/verizon/network/getStatus"
DATA_PATH = "/cgi-bin/luci/cgi"
LOG_PATH = "/cgi-bin/luci/verizon/system_settings/log"
OBJECTS = {
    "Device.Cellular.Interface.1.": (
        "Status", "CurrentAccessTechnology", "SupportedAccessTechnologies", "RSSI", "Name"),
    "Device.DeviceInfo.": ("ModelNumber", "SoftwareVersion", "UpTime"),
    "Device.DeviceInfo.TemperatureStatus.TemperatureSensor.1.": ("Value",),
    "Device.DeviceInfo.ProcessStatus.": ("CPUUsage",),
}


class GatewayClient:
    def __init__(self, config: Config, *, transport=None, authenticator=login, clock=time.monotonic):
        self.config = config
        self.authenticator = authenticator
        self.clock = clock
        self.authenticated = False
        self.last_failed_login = float("-inf")
        self.http = httpx.Client(
            base_url=config.url, timeout=15, follow_redirects=False, trust_env=False,
            transport=transport,
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json",
                     "Referer": config.url + "/cgi-bin/luci/"},
        )

    def close(self):
        self.http.close()

    def authenticate(self):
        if self.clock() - self.last_failed_login < 300:
            raise GatewayError("authentication_backoff")
        try:
            cookies = self.authenticator(self.config)
        except GatewayError:
            self.last_failed_login = self.clock()
            raise
        self.http.cookies.clear()
        self.http.cookies.update(cookies)
        self.authenticated = True

    def get(self, path, params=None):
        params = params or {}
        if path == STATUS_PATH:
            valid = not params
        elif path == DATA_PATH:
            try:
                obj = json.loads(params.get("data", ""))
                name = obj.get("ObjName")
                valid = (set(params) == {"api", "data"} and params["api"] == "get"
                         and name in OBJECTS and set(obj) == {"ObjName", "Param"}
                         and obj["Param"] == {field: "" for field in OBJECTS[name]})
            except (ValueError, TypeError, AttributeError):
                valid = False
        elif path == LOG_PATH:
            valid = (set(params) == {"action", "category", "startIdx", "logCount", "sortOrder"}
                     and params["action"] == "getlog" and params["category"] == "BLE.log"
                     and type(params["startIdx"]) is int and 1 <= params["startIdx"] <= 1001
                     and type(params["logCount"]) is int and 1 <= params["logCount"] <= 200
                     and params["sortOrder"] == -1)
        else:
            valid = False
        if not valid:
            raise GatewayError("read_not_allowed")
        if not self.authenticated:
            self.authenticate()
        for attempt in range(2):
            try:
                return self._request(path, params)
            except GatewayError as error:
                if error.code != "authentication_expired":
                    raise
                self.authenticated = False
                if attempt:
                    self.last_failed_login = self.clock()
                    raise
                self.authenticate()

    def _request(self, path, params):
        try:
            with self.http.stream("GET", path, params=params) as response:
                if response.status_code in (301, 302, 303, 307, 308, 401, 403):
                    raise GatewayError("authentication_expired")
                if response.status_code >= 400:
                    raise GatewayError("gateway_http_error")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 2_000_000:
                        raise GatewayError("response_too_large")
                if bytes(body).lstrip().startswith(b"<"):
                    raise GatewayError("authentication_expired")
                data = json.loads(body)
            if not isinstance(data, dict) or data.get("status") not in (None, "success"):
                raise GatewayError("invalid_gateway_response")
            if path == STATUS_PATH and not {"modemtype", "internetStatus"} <= data.keys():
                raise GatewayError("invalid_status_response")
            return data
        except GatewayError:
            raise
        except httpx.TimeoutException:
            raise GatewayError("gateway_timeout") from None
        except httpx.HTTPError:
            raise GatewayError("gateway_unreachable") from None
        except (ValueError, UnicodeError):
            raise GatewayError("invalid_gateway_response") from None

    def object(self, name):
        if name not in OBJECTS:
            raise GatewayError("read_not_allowed")
        data = self.get(DATA_PATH, {
            "api": "get", "data": json.dumps({"ObjName": name,
                "Param": {field: "" for field in OBJECTS[name]}}, separators=(",", ":")),
        })
        for value in data.values():
            if isinstance(value, dict) and value.get("ObjName") == name:
                return {field: value.get(field) for field in OBJECTS[name]}
        raise GatewayError("missing_telemetry_object")

    def log_rows(self, limit=200):
        if not 1 <= limit <= 1000:
            raise GatewayError("invalid_log_limit")
        rows, more = [], True
        while more and len(rows) < limit:
            count = min(200, limit - len(rows))
            data = self.get(LOG_PATH, {"action": "getlog", "category": "BLE.log",
                "startIdx": len(rows) + 1, "logCount": count, "sortOrder": -1})
            page = data.get("LogData")
            if not isinstance(page, list):
                raise GatewayError("invalid_log_response")
            rows.extend(page[:count])
            more = data.get("MoreData") in (True, "true", 1)
            if not page:
                break
        return rows, more
