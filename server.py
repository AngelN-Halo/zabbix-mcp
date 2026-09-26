from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import load_config
from status_service import StatusService


config = load_config()
service = StatusService(config)
mcp = MCPServer("zabbix-readonly")


@mcp.tool()
def zabbix_connection_test() -> dict:
    """Verify read-only connectivity to Zabbix and return its API version."""
    return service.connection_test()


@mcp.tool()
def zabbix_get_system_summary(force_refresh: bool = False) -> dict:
    """Return overall health counts for the allowlisted service groups."""
    return service.system_summary(force_refresh=force_refresh)


@mcp.tool()
def zabbix_list_service_groups() -> dict:
    """List allowlisted service groups and their current aggregate health."""
    return service.list_groups()


@mcp.tool()
def zabbix_get_group_health(group_id: str, include_hosts: bool = False) -> dict:
    """Return health for one allowlisted group; host details are opt-in."""
    return service.group_health(group_id, include_hosts=include_hosts)


@mcp.tool()
def zabbix_list_active_problems(
    minimum_severity: int = 1,
    limit: int = 50,
) -> dict:
    """List active Zabbix problems, bounded to 100 results and severity 0-5."""
    return service.active_problems(minimum_severity=minimum_severity, limit=limit)


@mcp.tool()
def zabbix_get_recent_events(
    hours: int = 24,
    group_id: str | None = None,
    limit: int = 50,
) -> dict:
    """Return up to 100 trigger events from the last 1-168 hours."""
    return service.recent_events(hours=hours, group_id=group_id, limit=limit)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request):
    return JSONResponse({"status": "ok", "service": "zabbix-readonly-mcp"})


transport_security = TransportSecuritySettings(
    allowed_hosts=config.allowed_hosts,
    allowed_origins=[],
)
app = mcp.streamable_http_app(transport_security=transport_security)


if __name__ == "__main__":
    mcp.run(transport="stdio")
