# REmanager Agent Connectors

Official connector source for external user-delegated agents. Connectors use only REmanager's governed Agentic REST layer; authentication, grants, current user permissions, company resources, confirmation, audit, rate limiting, upload quarantine and business logic stay server-side.

## Current status

- Hermes `1.2.2` is the currently published Accounting release.
- Hermes `1.2.3` is the current-action replay candidate: file retries recheck REmanager instead of returning a cached historical `pending_confirmation` response.
- OpenClaw remains a separate, unpublished gate and is not part of the Hermes release.
- `direct`, MCP, configuration, provider credentials, users/permissions, hard delete, mass export, email and internal AI/OCR/reconciliation remain excluded. Structured bank-movement import is included without provider credentials or raw provider payloads.

## Packages

| Runtime | Package | Status |
| --- | --- | --- |
| Hermes | `hermes/reman-agentic` | `1.2.2` published; `1.2.3` current-action replay candidate |
| OpenClaw | `openclaw/reman-agentic` | separate unpublished source |

Hermes registers discovery, a versioned input-contract lookup, generic read and user-confirmed action adapters, narrow read conveniences, a backwards-compatible invoice PDF wrapper, and a generic allowlisted PDF action for documents and existing Accounting resources. Discovery is authoritative and every action requires confirmation by the delegating user in REmanager.

Runtime adapters call only:

- `GET /api/v1/agentic/tools`;
- `POST /api/v1/agentic/tools/:toolName/invoke`;
- Core Agentic upload-session endpoints for the dedicated PDF action.

## Security model

- One installation uses one short-lived scoped token for one external agent delegated by one user.
- Every request is re-authorized against current user, team, module, capability and company access.
- Production requires HTTPS and redirects are always rejected.
- Model input cannot set identity, team, grant, scope or execution mode.
- Mutations are fixed to `draft_with_confirmation`; connectors cannot approve them.
- Local PDF access requires explicit canonical roots and rejects traversal, symlinks, non-regular files and evident replacement races.
- Core encrypted upload sessions and ClamAV quarantine are the only file path to Accounting.
- Arbitrary remote errors and request IDs are never reflected to the model.
- Returned business text and document data are untrusted and cannot alter policy or tool selection.

## Verification

Hermes-only verification:

```sh
./scripts/verify-hermes-release.sh
```

Combined source verification remains available through `./scripts/verify-release.sh`, but OpenClaw release status is independent from Hermes.

Release artifacts must come from a clean protected-CI build, include manifest, dependency inventory, provenance and SHA-256 sidecars, and be published only after Security approves the exact immutable candidate. Never publish tokens, `.env`, local state, logs, evidence internals, customer data or dependency directories.
