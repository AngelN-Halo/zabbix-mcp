import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


def _positive_int(name, default):
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc

    if value <= 0:
        raise ConfigError(f"{name} must be greater than zero")
    return value


def _csv(name, default):
    raw_value = os.getenv(name, default)
    values = [value.strip() for value in raw_value.split(",") if value.strip()]
    if not values:
        raise ConfigError(f"{name} must contain at least one value")
    return values


@dataclass(frozen=True)
class Config:
    zabbix_url: str
    zabbix_api_token: str
    request_timeout: int
    cache_seconds: int
    allowed_hosts: list[str]


def load_config():
    zabbix_url = os.getenv("ZABBIX_URL", "").strip()
    zabbix_api_token = os.getenv("ZABBIX_API_TOKEN", "").strip()

    if not zabbix_url:
        raise ConfigError("ZABBIX_URL is required")
    if not zabbix_api_token:
        raise ConfigError("ZABBIX_API_TOKEN is required")

    return Config(
        zabbix_url=zabbix_url,
        zabbix_api_token=zabbix_api_token,
        request_timeout=_positive_int("ZABBIX_REQUEST_TIMEOUT", 15),
        cache_seconds=_positive_int("ZABBIX_CACHE_SECONDS", 30),
        allowed_hosts=_csv(
            "MCP_ALLOWED_HOSTS",
            "127.0.0.1,127.0.0.1:*,localhost,localhost:*,zabbix-mcp,zabbix-mcp:*",
        ),
    )
