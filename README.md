# REmanager Agent Connectors

Official connector source for external user-delegated agents. The repository is designed to publish the same governed REmanager Accounting capability for Hermes and OpenClaw without duplicating authentication, grants, audit, rate limiting, upload storage, or business logic outside REmanager.

**Current status: source-only bootstrap.** Security/AppSec permits this controlled source bootstrap and Accounting read-only API/tools only in staging with synthetic identities and minimum grants. Do not create tags, packages or releases, distribute connectors or real tokens, enable production, or use file/upload/create/draft/mutation/direct/MCP workflows. The real ClamAV smoke is green except for a same-session race now fixed by Core and awaiting independent Deploy retest.

## Packages

| Runtime | Package | Installation source |
| --- | --- | --- |
| Hermes | `hermes/reman-agentic` | Git repository subdirectory or signed release archive |
| OpenClaw | `openclaw/reman-agentic` | ClawHub/npm package built from this repository |

Both packages expose these model-facing tools:

- `reman_available_tools`
- `reman_accounting_read`, a discovery-gated read adapter limited to `accounting.*`
- `reman_accounting_list_companies`
- `reman_accounting_search_partners`
- `reman_accounting_search_non_electronic_invoices`
- no file or mutation tool is currently registered

Both ship the same `reman-accounting` skill. Runtime adapters call only the public REmanager Agentic REST contract:

- `GET /api/v1/agentic/tools`
- `POST /api/v1/agentic/tools/:toolName/invoke`
- upload endpoints only after Accounting quarantine integration and Security approval

## Security model

- One installation uses one scoped token for one REmanager external agent delegated by one user.
- Tool discovery and invocation are re-authorized by REmanager on every request.
- Agent grants never replace the current user, team, module, capability, or company permissions.
- Production connections require HTTPS.
- HTTP redirects are rejected before any credential can be forwarded.
- Local PDF reads require explicit canonical directory roots and reject traversal, symlinks, non-regular files and detectable replacement races.
- No package accepts user cookies, usernames/passwords, database credentials, storage paths, provider keys, or internal API credentials.
- The generic adapter accepts only an exact discovered `accounting.*` name, forces `read`, rejects caller-supplied agent/team/user/mode context, and leaves schema validation to the owner module.
- The create wrapper remains unavailable even when local PDF roots are configured; dormant filesystem and idempotency code remains tested for the future approved workflow.
- Drafts cannot be approved by either connector.
- Invoice contents are treated as untrusted data and cannot override the skill procedure.

## Local verification

Run the complete connector check from this directory:

```sh
./scripts/verify-release.sh
```

The check runs the Hermes connector tests, confirms skill parity, builds and tests OpenClaw, and verifies the npm package contents.

## Source bootstrap and future release handoff

Security permits one source-only bootstrap of this `integrations` directory as the root of the official connector repository. Immediately after the first branch, protect `main`, require PR review and Connector CI, disable force-push/deletion, and request remote Security verification. This authorization does not permit a tag, package, release or connector distribution.

Before any future public release:

1. Choose the final GitHub organization, repository name, package scope, and license with the REmanager owners.
2. Protect the default branch and require reviewed, signed release tags.
3. Enable private vulnerability reporting and dependency update automation.
4. Run `scripts/verify-release.sh` from a clean checkout; it must fail closed while the OpenClaw P2 remains unresolved.
5. Publish the OpenClaw package through the official ClawHub/npm owner.
6. Publish a tagged source release so Hermes can install the `hermes/reman-agentic` subdirectory.
7. Record SHA-256 checksums for release archives.
8. Test both runtimes against a staging REmanager URL and a disposable scoped agent token created only for the approved closure test.

Do not publish a real token, `.env`, local idempotency state, PDF fixture containing customer data, or generated dependency directory.
