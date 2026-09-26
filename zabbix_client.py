import requests


class ZabbixError(RuntimeError):
    pass


class ZabbixRequestError(ZabbixError):
    pass


class ZabbixAPIError(ZabbixError):
    pass


def build_zabbix_url(base_url):
    cleaned = str(base_url or "").strip()
    if not cleaned:
        raise ValueError("Zabbix base URL is required")
    return cleaned.rstrip("/") + "/api_jsonrpc.php"


class ZabbixClient:
    def __init__(self, base_url, api_token, timeout=15):
        self.url = build_zabbix_url(base_url)
        self.timeout = timeout
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json-rpc",
            }
        )

    def rpc(self, method, params=None, authenticated=True):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1,
        }

        try:
            headers = None
            if authenticated:
                headers = {"Authorization": f"Bearer {self.api_token}"}
            response = self.session.post(
                self.url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ZabbixRequestError(
                f"Zabbix request failed for {method}: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ZabbixAPIError(
                f"Invalid JSON response from Zabbix for {method}"
            ) from exc

        error = data.get("error") or {}
        if error:
            code = error.get("code", "unknown")
            message = error.get("message", "Unknown API error")
            details = error.get("data")
            suffix = f" ({details})" if details else ""
            raise ZabbixAPIError(
                f"Zabbix API error for {method} [{code}]: {message}{suffix}"
            )

        return data.get("result", [])
