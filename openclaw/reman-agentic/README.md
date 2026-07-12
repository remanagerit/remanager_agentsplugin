# REmanager Agentic plugin for OpenClaw

This native OpenClaw plugin exposes only the REmanager Accounting read tools granted to one user-delegated external agent. Discovery is authoritative: `reman_accounting_read` can invoke only discovered `accounting.*` tools in mode `read`. It uses the public Agentic Gateway and never uses browser automation, user sessions, passwords, database access, storage paths, provider credentials, or internal endpoints.

> Security status: source-only repository bootstrap is authorized, but package distribution, releases and real tokens are not. Only Accounting read-only staging tests with synthetic identities and minimum grants are approved. File-based invoice creation remains unavailable pending the Core race retest and a separate Security gate.

## Requirements

- OpenClaw `2026.6.11` or newer on a supported Node.js release.
- A public HTTPS REmanager deployment with the Agentic Foundation and Accounting tools deployed.
- One scoped agent token created under **Account > Connected agents**.

## Local package installation

```sh
npm ci
npm run build
openclaw plugins install .
openclaw plugins enable reman-agentic
```

After the official package is published, install the pinned official ClawHub or Git release specified by REmanager instead of an arbitrary package with a similar name.

## Configuration

Configure the public URL and token in `plugins.entries.reman-agentic.config`. Prefer a SecretRef for the token:

```json5
{
  plugins: {
    entries: {
      "reman-agentic": {
        enabled: true,
        config: {
          baseUrl: "https://app.example.com",
          token: { source: "env", provider: "default", id: "REMAN_AGENT_TOKEN" },
        },
      },
    },
  },
  tools: {
    allow: ["reman-agentic"],
  },
}
```

`REMAN_AGENT_BASE_URL`, `REMAN_AGENT_TOKEN` and an OS path-separator list in `REMAN_AGENT_ALLOWED_PDF_DIRS` are supported as an alternative. Prefer a SecretRef for the token. Production URLs must use HTTPS; HTTP is accepted only for loopback development.

The create-invoice tool is not registered in the package contract, even when PDF directories are configured. It will remain absent until real ClamAV end-to-end smoke and Security approval are available. REmanager grants remain authoritative and are rechecked through discovery for every invocation.

## Skill

The plugin ships the `reman-accounting` skill. It documents the exact inputs for the current company, partner, document, due-date, DDT, payment, payment-link, tax, loan, policy, and summary tools. Dedicated wrappers remain convenience aliases, not a static authority.

## Execution and errors

- The connector invokes only `read` for the generic Accounting adapter.
- `direct` is disabled even if an older server discovery advertises it.
- Transport failures are marked `retryable: true`; policy, permission, validation, quarantine, and connector boundary failures are `retryable: false`.

Do not retry `agentic_disabled`, `agentic_direct_disabled`, or `agentic_file_quarantine_unavailable` as a fallback.
