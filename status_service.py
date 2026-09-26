import threading
import time
from datetime import datetime, timezone

from groups import SERVICE_GROUPS, get_group, host_matches_group
from zabbix_client import ZabbixClient


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_id(value):
    if value is None:
        return ""
    return str(value).strip()


def iso_timestamp(value):
    epoch = safe_int(value, -1)
    if epoch < 0:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


class StatusService:
    def __init__(self, config, client=None):
        self.config = config
        self.client = client or ZabbixClient(
            config.zabbix_url,
            config.zabbix_api_token,
            timeout=config.request_timeout,
        )
        self._lock = threading.RLock()
        self._snapshot = None
        self._snapshot_deadline = 0.0

    def connection_test(self):
        started = time.monotonic()
        version = self.client.rpc("apiinfo.version", authenticated=False)
        return {
            "ok": True,
            "zabbix_version": version,
            "latency_ms": round((time.monotonic() - started) * 1000),
        }

    def _fetch_snapshot(self):
        problems = self.client.rpc(
            "problem.get",
            {
                "output": [
                    "eventid",
                    "objectid",
                    "name",
                    "severity",
                    "clock",
                    "acknowledged",
                    "suppressed",
                ],
                "source": 0,
                "object": 0,
                "sortfield": ["eventid"],
                "sortorder": "DESC",
            },
        )
        triggers = self.client.rpc(
            "trigger.get",
            {
                "output": ["triggerid", "description", "priority", "lastchange"],
                "filter": {"value": 1},
                "selectHosts": ["hostid", "host", "name"],
                "sortfield": "priority",
                "sortorder": "DESC",
            },
        )
        hosts = self.client.rpc(
            "host.get",
            {
                "output": ["hostid", "host", "name", "status"],
                "sortfield": "name",
            },
        )

        problems_by_trigger = {}
        for problem in problems or []:
            trigger_id = normalize_id(
                problem.get("objectid") or problem.get("triggerid")
            )
            if trigger_id and trigger_id not in problems_by_trigger:
                problems_by_trigger[trigger_id] = problem

        issues_by_host = {}
        active_problems = []
        seen_problem_keys = set()

        for trigger in triggers or []:
            trigger_id = normalize_id(trigger.get("triggerid"))
            problem = problems_by_trigger.get(trigger_id, {})
            severity = safe_int(problem.get("severity"), safe_int(trigger.get("priority")))
            name = problem.get("name") or trigger.get("description") or "Unknown problem"
            trigger_hosts = trigger.get("hosts", []) or []
            affected_hosts = []

            for host in trigger_hosts:
                host_id = normalize_id(host.get("hostid"))
                host_name = host.get("name") or host.get("host") or "Unknown host"
                affected_hosts.append(host_name)
                if host_id:
                    issues_by_host.setdefault(host_id, []).append(
                        {
                            "trigger_id": trigger_id,
                            "name": name,
                            "severity": severity,
                        }
                    )

            problem_key = normalize_id(problem.get("eventid")) or f"trigger:{trigger_id}"
            if problem_key in seen_problem_keys:
                continue
            seen_problem_keys.add(problem_key)
            active_problems.append(
                {
                    "event_id": normalize_id(problem.get("eventid")) or None,
                    "trigger_id": trigger_id or None,
                    "name": name,
                    "severity": severity,
                    "started_at": iso_timestamp(
                        problem.get("clock") or trigger.get("lastchange")
                    ),
                    "acknowledged": normalize_id(problem.get("acknowledged")) == "1",
                    "suppressed": normalize_id(problem.get("suppressed")) == "1",
                    "affected_hosts": sorted(set(affected_hosts)),
                }
            )

        groups = []
        for group in SERVICE_GROUPS:
            group_hosts = []
            unhealthy = 0
            critical = 0

            for host in hosts or []:
                if not host_matches_group(host, group):
                    continue

                host_id = normalize_id(host.get("hostid"))
                host_issues = issues_by_host.get(host_id, [])
                disabled = normalize_id(host.get("status")) == "1"
                worst_severity = max(
                    [safe_int(issue.get("severity")) for issue in host_issues],
                    default=0,
                )

                if disabled or worst_severity >= 4:
                    status = "offline"
                    unhealthy += 1
                    critical += 1
                elif worst_severity >= 1:
                    status = "warning"
                    unhealthy += 1
                else:
                    status = "online"

                group_hosts.append(
                    {
                        "id": host_id,
                        "label": host.get("name") or host.get("host") or "Unknown host",
                        "status": status,
                        "problem_count": len(host_issues),
                        "problems": host_issues,
                    }
                )

            if not group_hosts:
                group_status = "warning"
            elif critical:
                group_status = "offline"
            elif unhealthy:
                group_status = "warning"
            else:
                group_status = "online"

            groups.append(
                {
                    "id": group["id"],
                    "label": group["label"],
                    "status": group_status,
                    "host_count": len(group_hosts),
                    "problem_host_count": unhealthy,
                    "hosts": group_hosts,
                }
            )

        return {
            "source": "zabbix",
            "observed_at": datetime.now(tz=timezone.utc).isoformat(),
            "groups": groups,
            "active_problems": active_problems,
        }

    def snapshot(self, force_refresh=False):
        now = time.monotonic()
        with self._lock:
            if (
                not force_refresh
                and self._snapshot is not None
                and now < self._snapshot_deadline
            ):
                return self._snapshot

            self._snapshot = self._fetch_snapshot()
            self._snapshot_deadline = time.monotonic() + self.config.cache_seconds
            return self._snapshot

    def system_summary(self, force_refresh=False):
        snapshot = self.snapshot(force_refresh=force_refresh)
        counts = {"online": 0, "warning": 0, "offline": 0}
        for group in snapshot["groups"]:
            counts[group["status"]] = counts.get(group["status"], 0) + 1

        if counts["offline"]:
            overall_status = "offline"
        elif counts["warning"]:
            overall_status = "warning"
        else:
            overall_status = "online"

        return {
            "source": snapshot["source"],
            "observed_at": snapshot["observed_at"],
            "cache_seconds": self.config.cache_seconds,
            "overall_status": overall_status,
            "group_counts": counts,
            "active_problem_count": len(snapshot["active_problems"]),
        }

    def list_groups(self):
        snapshot = self.snapshot()
        return {
            "observed_at": snapshot["observed_at"],
            "groups": [
                {key: value for key, value in group.items() if key != "hosts"}
                for group in snapshot["groups"]
            ],
        }

    def group_health(self, group_id, include_hosts=False):
        if get_group(group_id) is None:
            valid_ids = [group["id"] for group in SERVICE_GROUPS]
            raise ValueError(
                f"Unknown group_id '{group_id}'. Valid values: {', '.join(valid_ids)}"
            )

        snapshot = self.snapshot()
        for group in snapshot["groups"]:
            if group["id"] != group_id:
                continue
            result = dict(group)
            result["observed_at"] = snapshot["observed_at"]
            if not include_hosts:
                result.pop("hosts", None)
            return result

        raise ValueError(f"Group '{group_id}' is not present in the current snapshot")

    def active_problems(self, minimum_severity=1, limit=50):
        minimum_severity = safe_int(minimum_severity, 1)
        limit = max(1, min(safe_int(limit, 50), 100))
        if minimum_severity < 0 or minimum_severity > 5:
            raise ValueError("minimum_severity must be between 0 and 5")

        snapshot = self.snapshot()
        problems = [
            problem
            for problem in snapshot["active_problems"]
            if safe_int(problem.get("severity")) >= minimum_severity
        ]
        problems.sort(
            key=lambda problem: (
                safe_int(problem.get("severity")),
                problem.get("started_at") or "",
            ),
            reverse=True,
        )
        return {
            "observed_at": snapshot["observed_at"],
            "minimum_severity": minimum_severity,
            "returned": min(len(problems), limit),
            "problems": problems[:limit],
        }

    def recent_events(self, hours=24, group_id=None, limit=50):
        hours = max(1, min(safe_int(hours, 24), 168))
        limit = max(1, min(safe_int(limit, 50), 100))
        params = {
            "output": [
                "eventid",
                "objectid",
                "name",
                "severity",
                "clock",
                "value",
                "acknowledged",
            ],
            "source": 0,
            "object": 0,
            "time_from": int(time.time()) - (hours * 3600),
            "sortfield": ["clock", "eventid"],
            "sortorder": "DESC",
            "selectHosts": ["hostid", "host", "name"],
            "limit": limit,
        }

        if group_id:
            group = self.group_health(group_id, include_hosts=True)
            host_ids = [host["id"] for host in group.get("hosts", []) if host.get("id")]
            if not host_ids:
                return {"hours": hours, "group_id": group_id, "returned": 0, "events": []}
            params["hostids"] = host_ids

        events = self.client.rpc("event.get", params)
        normalized = []
        for event in events or []:
            normalized.append(
                {
                    "event_id": normalize_id(event.get("eventid")),
                    "trigger_id": normalize_id(event.get("objectid")),
                    "name": event.get("name") or "Unknown event",
                    "severity": safe_int(event.get("severity")),
                    "occurred_at": iso_timestamp(event.get("clock")),
                    "state": "problem" if normalize_id(event.get("value")) == "1" else "recovery",
                    "acknowledged": normalize_id(event.get("acknowledged")) == "1",
                    "affected_hosts": sorted(
                        {
                            host.get("name") or host.get("host") or "Unknown host"
                            for host in event.get("hosts", []) or []
                        }
                    ),
                }
            )

        return {
            "hours": hours,
            "group_id": group_id,
            "returned": len(normalized),
            "events": normalized,
        }
