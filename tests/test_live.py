import os

import pytest

from verizon_gateway.client import GatewayClient
from verizon_gateway.config import Config
from verizon_gateway.telemetry import snapshot


@pytest.mark.live
@pytest.mark.skipif(os.getenv("VERIZON_GATEWAY_LIVE_TEST") != "1", reason="hardware opt-in")
def test_live_read_only_snapshot():
    client = GatewayClient(Config.from_env())
    try:
        result = snapshot(client, radio_log=True)
        assert result["status"] == "success"
        assert result["system"]["model"] == "LVSKIHP"
        assert result["radio_observations"]
    finally:
        client.close()
