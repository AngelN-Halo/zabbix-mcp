import asyncio
import json
import os

from mcp import Client


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return None


async def main():
    url = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")
    async with Client(url) as client:
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools.tools]
        result = await client.call_tool("zabbix_connection_test", {})
        summary = await client.call_tool("zabbix_get_system_summary", {})
        groups = await client.call_tool("zabbix_list_service_groups", {})
        recent = await client.call_tool(
            "zabbix_get_recent_events", {"hours": 1, "limit": 5}
        )
        print(
            json.dumps(
                {
                    "tools": tool_names,
                    "connection_test": payload(result),
                    "connection_test_ok": not result.is_error,
                    "summary_ok": not summary.is_error,
                    "summary": payload(summary),
                    "group_count": len((payload(groups) or {}).get("groups", [])),
                    "recent_events_ok": not recent.is_error,
                    "recent_event_count": (payload(recent) or {}).get("returned"),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
