# Read-only Zabbix MCP example

A monitoring MCP service with a small example group list. It reads status and problems but does not acknowledge events or change monitoring configuration. Edit the illustrative groups for your environment **outside this public source tree**; never publish a host inventory.

## Configuration

Copy `.env.example` to ignored `.env`, replace placeholders, and copy `.env.upstream.example` to ignored `.env.upstream` for the upstream API endpoint and token. Keep both local and protected. Never include production hosts, network addresses, monitoring data, or tokens in Git.

Compose publishes example listeners on host loopback only. It uses a project-local Docker network; no reverse proxy, organization hostname, or remote tunnel is configured here. Configure authentication, authorization, TLS, Host allowlists, and an access-controlled gateway before any client access. Loopback binding does not make a remote-facing proxy safe by itself.

## Check

Validate with `docker compose config` after creating local environment files. Build and use synthetic monitoring data to test health, status aggregation, and read-only behavior. Review exported status and logs for infrastructure and personal information. Do not expose the MCP or OpenAPI listener directly to the internet.
