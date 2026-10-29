import httpx
import pytest

from verizon_gateway.client import GatewayClient, DATA_PATH, STATUS_PATH
from verizon_gateway.config import Config, GatewayError, resolve
from verizon_gateway.telemetry import snapshot


def test_read_allowlist_rejects_before_login(fake_gateway):
    client, state = fake_gateway
    for path, params in (("/control/reboot", {}), (DATA_PATH, {"api": "set"}),
                         (STATUS_PATH, {"closeMeshAlertMSG": ""})):
        with pytest.raises(GatewayError, match="read_not_allowed"):
            client.get(path, params)
    assert state["auth_calls"] == 0
    assert not state["calls"]


def test_auth_expiry_throttles_relogin(fake_gateway):
    client, state = fake_gateway
    snapshot(client)
    state["fail"] = 403
    result = snapshot(client)
    assert result["status"] == "error"
    assert state["auth_calls"] == 2
    snapshot(client)
    assert state["auth_calls"] == 2
    client.last_failed_login -= 301
    state["fail"] = None
    assert snapshot(client)["status"] == "success"
    assert state["auth_calls"] == 3


def test_expired_request_is_retried_after_successful_login():
    state = {"login": 0}

    def authenticate(_):
        state["login"] += 1
        return {"session": str(state["login"])}

    def respond(request):
        if state["login"] == 1:
            return httpx.Response(401)
        return httpx.Response(200, json={"modemtype": "5G", "internetStatus": "internetAllow"})

    client = GatewayClient(Config(url="http://gateway.example"),
        transport=httpx.MockTransport(respond), authenticator=authenticate)
    try:
        assert client.get(STATUS_PATH)["modemtype"] == "5G"
        assert state["login"] == 2
    finally:
        client.close()


def test_recovered_session_does_not_poison_the_snapshot(fake_gateway):
    client, state = fake_gateway
    assert snapshot(client)["status"] == "success"
    original_authenticate = client.authenticator

    def recover(config):
        state["fail"] = None
        return original_authenticate(config)

    client.authenticator = recover
    state["fail"] = 401
    result = snapshot(client)
    assert result["status"] == "success"
    assert result["errors"] == {}
    assert state["auth_calls"] == 2


def test_incomplete_status_is_not_a_success():
    client = GatewayClient(Config(url="http://gateway.example"),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
        authenticator=lambda _: {"session": "example"})
    try:
        with pytest.raises(GatewayError, match="invalid_status_response"):
            client.get(STATUS_PATH)
    finally:
        client.close()


def test_network_error_is_safe():
    def fail(request):
        raise httpx.ConnectError("example-sensitive-value", request=request)
    client = GatewayClient(Config(url="http://gateway.example"),
        transport=httpx.MockTransport(fail), authenticator=lambda _: {"session": "example"})
    result = snapshot(client)
    client.close()
    assert result["status"] == "error"
    assert set(result["errors"].values()) == {"gateway_unreachable"}
    assert "example-sensitive-value" not in str(result)


def test_command_failure_does_not_echo_secret():
    with pytest.raises(GatewayError, match="credential_command_failed") as error:
        resolve("", '["/nonexistent-example-command", "example-sensitive-value"]')
    assert "example-sensitive-value" not in str(error.value)
    for value in ('"not-an-array"', "[]", '[1]'):
        with pytest.raises(GatewayError):
            resolve("", value)


def test_config_rejects_url_credentials_and_bad_timezone(monkeypatch):
    monkeypatch.setenv("VERIZON_GATEWAY_URL", "http://alice:example@gateway.example")
    with pytest.raises(GatewayError, match="invalid_gateway_url"):
        Config.from_env()
    monkeypatch.setenv("VERIZON_GATEWAY_URL", "http://gateway.example")
    monkeypatch.setenv("VERIZON_GATEWAY_TIMEZONE", "Invalid/Example")
    with pytest.raises(GatewayError, match="invalid_timezone"):
        Config.from_env()


def test_log_limit_and_pagination(fake_gateway):
    client, state = fake_gateway
    state["rows"] *= 250
    rows, more = client.log_rows(230)
    assert len(rows) == 230 and more is True
    assert len(state["calls"]) == 2
    with pytest.raises(GatewayError, match="invalid_log_limit"):
        client.log_rows(1001)
