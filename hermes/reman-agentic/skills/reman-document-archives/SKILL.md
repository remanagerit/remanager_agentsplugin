---
name: reman-document-archives
description: Attach original files to REmanager company, project, property or unit archive folders through the scoped document tools. Not for Accounting invoice attachments or imports.
---

# Document archives

Call reman_available_tools first. Only these explicit archive tools are supported:

| Tool | Context | Resource |
| --- | --- | --- |
| documents.administration.attachments.add | administration | company |
| documents.projects.attachments.add | projects | project |
| documents.real_estate.attachments.add | real_estate | property or unit |

They are not accounting.attachments.add (which attaches to Accounting records).
Use a verified existing folderId within the exact resource. If available read tools
or explicit user context do not provide that ID, ask; do not guess, use root/0,
create folders or call cookie-authenticated Web endpoints. Unit authorization uses
its parent property, but the business input still names the unit.

## Transfer and invoke

1. Call reman_agentic_upload_session_create with toolName set to the exact scoped
   tool. Omitting it creates an Accounting session, not an archive session.
2. Upload authorized original bytes with reman_agentic_upload_file_base64 using
   the same toolName, sessionId, fileName, mimeType and contentBase64. The helper
   does not read local files or URLs. Use only a user-authorized runtime transfer.
3. Poll reman_agentic_upload_session_status with backoff (2s,4s,then8s; stop after
   60s and report pending; respect Retry-After). Require session ready AND every
   expected item clean. Not-found may mean expired/terminal/nonowned, not success;
   do not blindly reupload or use mutation as polling. Respect discovery and
   session policy. Archive caps: 5 files, 20 MiB/file, 20 MiB total, concurrency 1;
   tighter limits win. Group only one destination context/folder in a session.
4. Call reman_document_archive_action with tool_name, stable operation_id and
   input {contextModuleCode,resourceType,resourceId,folderId,uploadSessionId,
   description?}. IDs are positive, uploadSessionId is UUID; description max1000.
   No team/user/agent/grant fields. No Web proxy, local storage path or DB access.
5. mode defaults to auto: Core decides draft or direct from live grants. Explicit
   direct requires discovery authorization. A direct denial is non-retryable;
   never silently replace it with a draft. Accounting handlers remain draft-only;
   this direct support is limited to the three archive tools above.
6. Check executionMode and result: pending_confirmation needs user approval;
   created with linkIds/attachmentIds means applied. Upload alone is not a link.

Reuse operation_id, business input and session after uncertain invoke/timeout.
Never reupload or generate a second key blindly. Core owns transactional receipt
and replay; transport success alone is not proof of exactly-once recovery after
every crash. Release only abandoned unheld sessions before ambiguous invocation.
For your own pending proposal use reman_agentic_action_cancel, not session deletion.

## Original formats

Only use formats in live filePolicy and the current session allowlist. New
formats require a new session. Canonical additions: TXT text/plain, XML
application/xml, P7M application/pkcs7-mime. Existing PDF/EML/Office/iWork/JPEG/PNG
remain policy-governed. Never use generic ZIP/octet-stream or rename extensions.
TXT/XML are UTF-8 or BOM-marked UTF-16; XML DTD/ENTITY is denied. P7M acceptance
identifies a CMS envelope, not a verified signature or extracted document.
When live policy includes them, DWG=image/vnd.dwg (AC1012/14/15/18/21/24/27/32),
text DXF=image/vnd.dxf (binary DXF denied), PSD/PSB=image/vnd.adobe.photoshop
(8BPS version1/2). These are bounded header/container identification, not drawing
integrity or pixel validation. Do not claim support for PLN/PLA/INDD/AI/FIG or
other native formats absent from discovery; a PDF or ZIP renamed is not native.
IFC uses application/x-step (SPF envelope/approved schema); IDML uses
application/vnd.adobe.indesign-idml-package (package/manifest validation).
Neither implies geometry/layout validation or preview. PLN/PLA/INDD/AI/FIG remain
unsupported in this candidate, not automatically converted or substituted.
Storage/download only: no preview, conversion, macro execution, import or cloud
project access is implied. Do not split a native project to evade 20 MiB limits.

## Errors

- document_archive_forbidden: verify authorization, no retry workaround.
- document_archive_upload_not_ready: inspect governed session/scanner state.
- document_archive_replay_conflict: stop and reconcile conflicting operation.
- document_archive_invalid_file: inspect format/policy, do not rename to bypass.
- agentic_direct_not_authorized: stop; permissions must be changed by an authorized user.
- 429: preserve diagnostic code and respect Retry-After; no aggressive retry.

Never log token, base64, file content, private paths or storage keys.
