# REman Agentic plugin for Hermes

This plugin exposes the REmanager Accounting read tools granted to a connected Hermes agent through the Core Agentic REST gateway. Discovery is authoritative: the generic read adapter can invoke only discovered `accounting.*` tools in mode `read`. It does not use browser automation, user cookies, passwords, database access, storage paths, or provider API keys.

> Security status: source-only repository bootstrap is authorized, but connector distribution, releases and real tokens are not. Only Accounting read-only staging tests with synthetic identities and minimum grants are approved. File-based invoice creation remains unavailable pending the Core race retest and a separate Security gate.

## Install

1. In REman, open **Account > Agenti collegati**, create an agent with provider `hermes`, configure its grants and create a token.
2. Install the official Git release subdirectory with `hermes plugins install <official-owner>/<official-repository>/hermes/reman-agentic`, or run `./install.sh` from a verified local checkout.
3. Put these values in the Hermes environment (normally `~/.hermes/.env`):

   ```dotenv
   REMAN_AGENT_BASE_URL=https://reman.example.com
   REMAN_AGENT_TOKEN=<one-time token shown by REman>
   ```

4. Enable the opt-in plugin with `hermes plugins enable reman-agentic` and restart the Hermes process.

The plugin also registers the governed Accounting workflow as `reman-agentic:reman-accounting`. Hermes can load it with `skill_view("reman-agentic:reman-accounting")`; the discovery tool description directs the model to it before complex Accounting work.

Production endpoints must use HTTPS. Plain HTTP is accepted only for `localhost`, `127.0.0.1` or `::1` development targets.

`REMAN_AGENT_ALLOWED_PDF_DIRS` remains a dormant compatibility setting. Even when configured, the create tool stays unavailable until a real scanner and the remaining closure tests are approved. Its filesystem boundary tests remain part of release verification.

Hermes environment variables are visible to trusted code running in the same process. Do not enable unreviewed plugins or tools in a Hermes process that holds a REman token; use a dedicated OS account/profile with least-privilege filesystem permissions.

## Grants

Grant only the read tools needed by the user, restricted to explicit company IDs. `resourceIds=[]` is never unrestricted; unrestricted access must be an explicit Core grant.

| REman tool | Required scope | Suggested access |
| --- | --- | --- |
| `accounting.companies.list` | `accounting.companies.read` | `read` |
| `accounting.partners.search/get` | `accounting.partners.read` | `read` |
| `accounting.non_electronic_invoices.search` | `accounting.non_electronic_invoices.read` | `read` |
| `accounting.documents.search/get` | `accounting.documents.read` | `read` |
| `accounting.document_due_dates.search/get` | `accounting.document_due_dates.read` | `read` |
| `accounting.delivery_notes.search/get` | `accounting.delivery_notes.read` | `read` |
| `accounting.payments.search/get` | `accounting.payments.read` | `read` |
| `accounting.payment_links.search` | `accounting.payment_links.read` | `read` |
| `accounting.tax_commitments.search/get` | `accounting.tax_commitments.read` | `read` |
| `accounting.tax_installments.search/get` | `accounting.tax_installments.read` | `read` |
| `accounting.loans.search/get` | `accounting.loans.read` | `read` |
| `accounting.insurance_policies.search/get` | `accounting.insurance_policies.read` | `read` |
| `accounting.summary.read` | `accounting.summary.read` | `read` |

The delegating user must still have the current Accounting permissions, company resource access and required capabilities. Changing or revoking a grant in REman takes effect independently of Hermes.

The model calls `reman_available_tools`, then `reman_accounting_read` with the exact discovered tool and the camelCase input documented by the bundled skill. Dedicated wrappers remain convenience aliases, not a static authority. `direct` is filtered and rejected.

## Error behavior

Transport failures are returned with `retryable: true`. Core policy, authorization, validation, quarantine, and connector boundary failures return `retryable: false`; in particular, do not retry `agentic_disabled`, `agentic_direct_disabled`, or `agentic_file_quarantine_unavailable` as a workaround.
