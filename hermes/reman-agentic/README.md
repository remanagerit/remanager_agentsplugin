# REman Agentic plugin for Hermes

This Hermes directory plugin exposes only the REmanager Accounting read tools granted to one user-delegated external agent. Discovery is authoritative: model-facing calls can invoke only discovered `accounting.*` tools in mode `read`.

The plugin contains no create, upload, mutation, `direct`, MCP, browser automation, user-session, database, storage, or provider-key integration. User, team and agent identity always come from the REmanager token context and cannot be supplied by the model.

> Security status: this source is a release candidate for an independent Hermes closure. Do not publish or distribute it, configure real tokens, or enable Agentic in production until Security/AppSec explicitly approves the exact candidate checksum and provenance.

## Format and installation

The archive uses Hermes' supported directory-plugin format: one `reman-agentic/` directory containing `plugin.yaml`, `__init__.py`, handlers, schemas and the bundled skill. General plugins are opt-in.

After an approved release:

1. Verify the archive SHA-256 and file manifest.
2. Extract the `reman-agentic/` directory from the official artifact.
3. Run `./install.sh` from that verified directory, or place it at `~/.hermes/plugins/reman-agentic`.
4. Configure `REMAN_AGENT_BASE_URL` and `REMAN_AGENT_TOKEN` in the trusted Hermes process environment.
5. Run `hermes plugins enable reman-agentic` and restart Hermes.

Use `hermes plugins remove reman-agentic` for the official CLI removal path. The packaged `uninstall.sh` is tested as a local, exact-path fallback.

Production endpoints must use HTTPS. Plain HTTP is accepted only for `localhost`, `127.0.0.1` or `::1` synthetic tests. Environment variables are visible to trusted code in the same process, so the REmanager token must not share a Hermes process with unreviewed plugins or tools.

## Grants and behavior

Grant only the Accounting read scopes needed by the user and explicit company resources. `resourceIds=[]` is never unrestricted. The delegating user must retain current Accounting permissions, company access and capabilities; changing or revoking any of them takes effect independently of Hermes.

The plugin registers:

- `reman_available_tools`;
- `reman_accounting_read`;
- `reman_accounting_list_companies`;
- `reman_accounting_search_partners`;
- `reman_accounting_search_non_electronic_invoices`.

Discovery is intersected with the exact 22 Accounting read tools approved for this candidate, then filters out every tool without `read`. The static set is only an upper bound and never grants access: the tool must still be returned by REmanager discovery. The generic adapter forces mode `read`, limits input size and rejects caller-supplied user, team, agent, scope or execution context at any nesting level.

Transport failures return `retryable: true`. Policy, authorization, validation and connector-boundary failures return `retryable: false`, including `agentic_disabled` and `agentic_direct_disabled`. HTTP error codes are exposed only from a bounded read-only allowlist; arbitrary remote error text and remote request IDs are never returned to the model.

The bundled skill is available as `reman-agentic:reman-accounting`.
