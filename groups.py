"""Example service groups. Replace search terms with your own host/group naming conventions."""

SERVICE_GROUPS = [
    {"id": "active_directory", "label": "Directory Services", "search": ["example-dc"]},
    {"id": "virtualization", "label": "Virtualization", "search": ["example-hv"]},
    {"id": "file_services", "label": "File Services", "search": ["example-file"]},
]


def get_group(group_id):
    for group in SERVICE_GROUPS:
        if group["id"] == group_id:
            return group
    return None


def host_matches_group(host, group):
    names = [str(host.get("host") or "").lower(), str(host.get("name") or "").lower()]
    return any(
        term.lower() in candidate
        for term in group.get("search", [])
        for candidate in names
    )
