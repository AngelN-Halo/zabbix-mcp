# Contributor guidance

- Keep upstream API access read-only and bounded; no arbitrary JSON-RPC or management actions.
- Never commit `.env`, `.env.upstream`, API tokens, certificates, exported status, or real host inventories.
- Keep examples on a local network and loopback; deployment-specific gateway configuration remains private.
- Preserve input validation and host-header protection. Use synthetic host names in tests.
