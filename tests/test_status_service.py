from types import SimpleNamespace

import pytest

from groups import SERVICE_GROUPS, host_matches_group
from status_service import StatusService
from zabbix_client import build_zabbix_url


class FakeClient:
    def rpc(self, method, params=None, authenticated=True):
        if method == "problem.get":
            return [
                {
                    "eventid": "9001",
                    "objectid": "7001",
                    "name": "Directory service unavailable",
                    "severity": "5",
                    "clock": "100",
                    "acknowledged": "0",
                    "suppressed": "0",
                }
            ]
        if method == "trigger.get":
            return [
                {
                    "triggerid": "7001",
                    "description": "Directory service unavailable",
                    "priority": "5",
                    "lastchange": "100",
                    "hosts": [{"hostid": "1", "host": "example-dc01", "name": "example-dc01"}],
                }
            ]
        if method == "host.get":
            return [{"hostid": "1", "host": "example-dc01", "name": "example-dc01", "status": "0"}]
        if method == "apiinfo.version":
            return "7.4.0"
        if method == "event.get":
            return []
        raise AssertionError(f"Unexpected method: {method}")


def make_service():
    config = SimpleNamespace(
        zabbix_url="https://example/zabbix",
        zabbix_api_token="token",
        request_timeout=5,
        cache_seconds=30,
    )
    return StatusService(config, client=FakeClient())


def test_build_zabbix_url():
    assert build_zabbix_url("https://example/zabbix/") == "https://example/zabbix/api_jsonrpc.php"


def test_host_group_matching():
    group = next(group for group in SERVICE_GROUPS if group["id"] == "active_directory")
    assert host_matches_group({"name": "Production example-dc01"}, group)


def test_critical_problem_sets_group_offline():
    group = make_service().group_health("active_directory", include_hosts=True)
    assert group["status"] == "offline"
    assert group["hosts"][0]["problem_count"] == 1


def test_invalid_group_is_rejected():
    with pytest.raises(ValueError, match="Unknown group_id"):
        make_service().group_health("not-a-group")
