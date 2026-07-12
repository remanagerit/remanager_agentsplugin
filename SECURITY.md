# Security Policy

## Supported releases

No connector release is currently authorized or supported. The repository is source-only until Security/AppSec approves a later signed release line. Connector permissions remain controlled server-side by the REmanager Agentic Gateway.

## Reporting

Report vulnerabilities privately through GitHub Private Vulnerability Reporting on the official REmanager connector repository. Do not open a public issue containing tokens, customer data, invoice contents, internal URLs, exploit details, or audit records.

## Credential handling

- Create tokens only from **Account > Connected agents**.
- Store tokens in the runtime secret mechanism or environment, never in prompts, skill files, source control, logs, support tickets, or command history.
- Rotate a token after suspected exposure and revoke the connected agent when the installation is no longer trusted.
- Use a distinct REmanager agent and token for each Hermes or OpenClaw installation.

## Trust boundary

These connectors are convenience adapters, not authorization authorities. REmanager owns authentication, scopes, resource constraints, current user permissions, rate limits, upload validation, idempotency, audit, and business validation. A modified connector cannot grant itself additional REmanager access.

The approved runtime gate is limited to Accounting read-only in controlled staging with synthetic identities and minimum grants. Connector code rejects `direct`; the file-based `draft_with_confirmation` wrapper remains unavailable until the scanner race retest and an independent Security approval.

Do not add generic arbitrary endpoint invocation, browser automation fallbacks, direct storage access, direct database access, draft approval, or collection of REmanager user credentials. The model-facing generic read adapter is not an arbitrary endpoint client: it is restricted to discovered `accounting.*` tool names, always forces `read`, and is authorized and schema-validated again by REmanager.
