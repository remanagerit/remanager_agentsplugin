# REmanager Agentic plugin for Hermes

This Hermes directory plugin exposes the approved REmanager Accounting Agentic surface for one user-delegated external agent: bounded reads and business actions that always require confirmation by that user in REmanager.

The connector upper bound is 83 tools: 33 reads, 49 generic `draft_with_confirmation` actions and the file-based non-electronic invoice action. It exposes zero `direct` tools and cannot approve an action. Discovery, current user permissions, grants, capabilities, company resources, rate limits and audit remain authoritative on the REmanager server.

Configuration, provider/API keys, users/permissions, hard delete, mass export, email, bank movement import, AI/OCR/reconciliation, browser automation and MCP are excluded.

> Release status: version 1.1.0 must not be published or configured with real tokens until Security/AppSec approves the exact candidate commit, tree, archive checksum and provenance, and the separate REmanager production gate is approved.

## Format and installation

The archive uses Hermes' supported directory-plugin format: one `reman-agentic/` directory containing `plugin.yaml`, Python handlers, schemas, the versioned catalog and the bundled skill.

After an approved release:

1. Download only from the official `remanagerit/remanager_agentsplugin` GitHub Release.
2. Verify the archive SHA-256 and complete manifest.
3. Extract the `reman-agentic/` directory.
4. Run `./install.sh` from that verified directory, or place it at `~/.hermes/plugins/reman-agentic`.
5. Configure `REMAN_AGENT_BASE_URL` and a distinct `REMAN_AGENT_TOKEN` in the dedicated trusted Hermes process.
6. For PDF invoice upload, configure `REMAN_AGENT_ALLOWED_PDF_DIRS` as an OS-path-separator-delimited allowlist of absolute directories.
7. Run `hermes plugins enable reman-agentic` and restart Hermes.

Use `hermes plugins remove reman-agentic` for the official CLI removal path. The packaged `uninstall.sh` is an exact-path fallback.

Production endpoints require HTTPS. Plain HTTP is accepted only for local synthetic tests. The token must not share a process with unreviewed plugins or tools.

## Grants and behavior

Create one token per installation with a short bounded TTL. Grant only needed Accounting tool scopes and explicit companies. `resourceIds=[]` is never unrestricted. Revocation, permission loss, capability loss and company-access loss take effect independently of Hermes.

The plugin registers:

- `reman_available_tools` for server-authoritative discovery;
- `reman_accounting_tool_contract` for the versioned input contract of one discovered tool;
- `reman_accounting_read` for exact Accounting reads;
- `reman_accounting_prepare_action` for non-file actions fixed to `draft_with_confirmation`;
- three narrow read convenience wrappers;
- `reman_accounting_create_non_electronic_invoice` for allowlisted PDFs, Core upload sessions and mandatory confirmation.

The static 83-tool catalog is only an upper bound and never grants access. A tool must also be returned by REmanager discovery with the expected mode. Inputs cannot contain user, team, agent, scope, grant or execution-mode context at any nesting level.

Mutations require a stable `operation_id`; the connector derives the idempotency key. The model cannot provide raw headers or select `direct`. File access is fail-closed when PDF roots are absent and rejects traversal, symlinks, non-regular files and evident TOCTOU changes. Uploaded files are not consumed until the Core scanner reports the entire session `ready`.

Transport failures alone are retryable. Policy, authorization, validation, quarantine and stale-state failures are non-retryable. HTTP error codes are exposed only from a bounded allowlist; arbitrary remote error text and request IDs are never returned to the model.

The bundled skill is available as `reman-agentic:reman-accounting`.
