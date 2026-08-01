# REmanager Agentic plugin for Hermes

This Hermes directory plugin exposes the approved REmanager Accounting Agentic surface for one user-delegated external agent: bounded reads and business actions that always require confirmation by that user in REmanager.

The connector upper bound is 90 tools: 37 reads, 50 generic `draft_with_confirmation` actions and three file actions. It exposes zero `direct` tools and cannot approve an action. Discovery, current user permissions, grants, capabilities, company resources, rate limits and audit remain authoritative on the REmanager server.

Configuration, provider/API keys, users/permissions, hard delete, mass export, email, AI/OCR/reconciliation, browser automation and MCP are excluded. Structured bank-movement import is included without provider credentials or raw provider payloads.

## Format and installation

The archive uses Hermes' supported directory-plugin format: one `reman-agentic/` directory containing `plugin.yaml`, Python handlers, schemas, the versioned catalog and the bundled skill.

After an approved release:

1. Download only from the official `remanagerit/remanager_agentsplugin` GitHub Release.
2. Verify the archive SHA-256 and complete manifest.
3. Extract the `reman-agentic/` directory.
4. Run `./install.sh` from that verified directory, or place it at `~/.hermes/plugins/reman-agentic`.
5. Configure a distinct `REMAN_AGENT_TOKEN` in the dedicated trusted Hermes process. The official production URL is built in.
6. For any PDF workflow, ask the user which local directories Hermes may access and configure those roots through `REMAN_AGENT_ALLOWED_PDF_DIRS`.
7. Run `hermes plugins enable reman-agentic` and restart Hermes.

Use `hermes plugins remove reman-agentic` for the official CLI removal path. The packaged `uninstall.sh` is an exact-path fallback.

Production endpoints require HTTPS. Plain HTTP is accepted only for local synthetic tests. The token must not share a process with unreviewed plugins or tools.

## Production connection and local PDF folders

The plugin uses the official REmanager production origin by default, so a standard installation needs only the token:

```sh
REMAN_AGENT_TOKEN=<token-created-in-REmanager>
```

The built-in base URL is `https://app.remanager.it`. Do not derive or alter it. `REMAN_AGENT_BASE_URL` is an optional override only when the user explicitly provides an approved REmanager staging or self-hosted deployment. When overriding it, do not append `/api`, `/api/v1` or `/api/v1/agentic`; the connector appends the governed API paths itself.

`REMAN_AGENT_ALLOWED_PDF_DIRS` is optional and is required for all PDF workflows. Its entries are absolute directories on the machine where the Hermes process runs, not directories on the REmanager server. The user decides which directories are allowed; the agent must not invent roots or widen the configured boundary.

Use the operating-system path separator between multiple roots:

```sh
# macOS/Linux
REMAN_AGENT_ALLOWED_PDF_DIRS=/data/invoices:/data/scans

# Windows
REMAN_AGENT_ALLOWED_PDF_DIRS=C:\Invoices;D:\Scans
```

When Hermes runs in a container, configure paths visible inside that container and mount only the user-approved host directories, preferably read-only. Without `REMAN_AGENT_ALLOWED_PDF_DIRS`, all read tools and non-file draft actions remain available, while PDF upload fails closed.

## Grants and behavior

Create one token per installation with a short bounded TTL. In REmanager, grant the Administration module at `read` or `draft_with_confirmation` level and select the allowed companies. Revocation, permission loss, capability loss and company-access loss take effect independently of Hermes.

The plugin registers:

- `reman_available_tools` for server-authoritative discovery;
- `reman_accounting_tool_contract` for the versioned input contract of one discovered tool;
- `reman_accounting_read` for exact Accounting reads;
- `reman_accounting_prepare_action` for non-file actions fixed to `draft_with_confirmation`;
- `reman_accounting_prepare_file_action` for generic document PDFs and attachments on existing resources;
- three narrow read convenience wrappers;
- `reman_accounting_create_non_electronic_invoice` for allowlisted PDFs, Core upload sessions and mandatory confirmation.

The static 90-tool catalog is only an upper bound and never grants access. A tool must also be returned by REmanager discovery with the expected mode. Inputs cannot contain user, team, agent, scope, grant or execution-mode context at any nesting level.

Document creation supports up to 12 structured due dates and up to 20 allocations to existing payments. REmanager derives the residual and paid/partial/open status from payment links; the plugin deliberately exposes no manually editable residual field. Generic file actions support `other_expense` and other document types, and can attach clean PDFs to existing Accounting resources.

Attachment metadata is available through bounded read tools. A download request returns a short-lived, single-use HTTPS capability URL after REmanager authorization checks. That URL must be consumed without the Agentic token, cookies or redirects and must never be persisted in a ledger or log.

For a complete Accounting document, call `accounting.documents.create_access_urls` through `reman_accounting_read` with `companyId`, `documentId`, and optional `ttlSeconds`. The default and maximum TTL are three hours (`10800` seconds). REmanager returns a single-use `viewUrl` and, when an original attachment is available, a separate single-use `originalDownloadUrl`:

- XML invoices open as REmanager's AssoSoftware HTML rendering through `viewUrl`; `originalDownloadUrl` downloads the original XML;
- PDF documents open inline through `viewUrl`; `originalDownloadUrl` downloads the original PDF;
- documents without a primary XML/PDF attachment use a printable HTML view and may omit `originalDownloadUrl`.

Each URL is an opaque bearer capability. Open it only for the user's current request, never append the agent token, cookies, query data or custom authorization headers, never follow redirects, and never persist or log it. Because each link is single-use, generate a fresh pair instead of replaying a consumed URL.

Mutations require a stable `operation_id`; the connector derives the idempotency key. The model cannot provide raw headers or select `direct`. File access is fail-closed when PDF roots are absent and rejects traversal, symlinks, non-regular files and evident TOCTOU changes. Uploaded files are not consumed until the Core scanner reports the entire session `ready`.

Transport failures alone are retryable. Policy, authorization, validation, quarantine and stale-state failures are non-retryable. HTTP error codes are exposed only from a bounded allowlist; arbitrary remote error text and request IDs are never returned to the model.

The bundled skill is available as `reman-agentic:reman-accounting`.
