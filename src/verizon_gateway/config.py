"""Local configuration and secret-manager-neutral command hooks."""

from dataclasses import dataclass, field
import json
import os
import subprocess
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class GatewayError(Exception):
    """Only stable, safe codes cross the CLI/logging boundary."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def resolve(value: str, command: str) -> str:
    if not command:
        return value
    try:
        argv = json.loads(command)
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise ValueError
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=True)
        return result.stdout.strip()
    except (ValueError, OSError, subprocess.SubprocessError):
        raise GatewayError("credential_command_failed") from None


@dataclass(repr=False)
class Config:
    url: str = ""
    password: str = field(default="", repr=False)
    username: str = "admin"
    timezone: str = "UTC"
    browser_channel: str = "chrome"
    password_command: str = field(default="", repr=False)

    @classmethod
    def from_env(cls):
        prefix = "VERIZON_GATEWAY_"
        url = resolve(os.getenv(prefix + "URL", ""), os.getenv(prefix + "URL_COMMAND", ""))
        parsed = urlsplit(url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise GatewayError("invalid_gateway_url")
        timezone = os.getenv(prefix + "TIMEZONE", "UTC")
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise GatewayError("invalid_timezone") from None
        return cls(
            url=f"{parsed.scheme}://{parsed.netloc}",
            password=os.getenv(prefix + "PASSWORD", ""),
            username=os.getenv(prefix + "USERNAME", "admin"),
            timezone=timezone,
            browser_channel=os.getenv(prefix + "BROWSER_CHANNEL", "chrome"),
            password_command=os.getenv(prefix + "PASSWORD_COMMAND", ""),
        )

    def secret(self):
        password = resolve(self.password, self.password_command)
        if not password:
            raise GatewayError("missing_password")
        return password
