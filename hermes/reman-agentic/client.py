"""Small stdlib-only client for the governed REman Agentic REST surface."""

import base64
import http.client
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_REMAN_BASE_URL = "https://app.remanager.it"


ACCOUNTING_TOOL_NAME = re.compile(r"^accounting\.[a-z0-9_.]+$")
APPROVED_ACCOUNTING_READ_TOOLS = frozenset({
    "accounting.accounts.get",
    "accounting.accounts.search",
    "accounting.attachments.create_download_url",
    "accounting.attachments.get",
    "accounting.attachments.search",
    "accounting.companies.list",
    "accounting.contact_people.get",
    "accounting.contact_people.search",
    "accounting.credit_note_applications.get",
    "accounting.credit_note_applications.search",
    "accounting.delivery_note_lines.search",
    "accounting.delivery_notes.get",
    "accounting.delivery_notes.search",
    "accounting.document_due_dates.get",
    "accounting.document_due_dates.search",
    "accounting.documents.get",
    "accounting.documents.search",
    "accounting.insurance_policies.get",
    "accounting.insurance_policies.search",
    "accounting.loan_installments.get",
    "accounting.loan_installments.search",
    "accounting.loans.get",
    "accounting.loans.search",
    "accounting.non_electronic_invoices.search",
    "accounting.partners.get",
    "accounting.partners.search",
    "accounting.payment_components.get",
    "accounting.payment_components.search",
    "accounting.payment_links.search",
    "accounting.payments.get",
    "accounting.payments.search",
    "accounting.summary.read",
    "accounting.tax_commitments.get",
    "accounting.tax_commitments.search",
    "accounting.tax_installments.get",
    "accounting.tax_installments.search",
})
APPROVED_ACCOUNTING_DRAFT_TOOLS = frozenset({
    "accounting.accounts.create",
    "accounting.accounts.update",
    "accounting.attachments.add",
    "accounting.bank_movements.import",
    "accounting.contact_people.create",
    "accounting.contact_people.update",
    "accounting.credit_note_applications.apply",
    "accounting.credit_note_applications.unapply",
    "accounting.delivery_notes.create",
    "accounting.delivery_notes.mark_seen",
    "accounting.delivery_notes.mark_unseen",
    "accounting.document_competence.update",
    "accounting.document_due_dates.create",
    "accounting.document_due_dates.mark_paid",
    "accounting.document_due_dates.unmark_paid",
    "accounting.document_due_dates.update",
    "accounting.document_precursor_links.apply",
    "accounting.document_precursor_links.unapply",
    "accounting.documents.create",
    "accounting.documents.create_with_attachments",
    "accounting.documents.duplicate",
    "accounting.documents.mark_paid",
    "accounting.documents.mark_seen",
    "accounting.documents.unmark_paid",
    "accounting.documents.mark_unseen",
    "accounting.documents.update",
    "accounting.insurance_policies.create",
    "accounting.insurance_policies.renew",
    "accounting.insurance_policies.status",
    "accounting.insurance_policies.update",
    "accounting.loan_installments.create",
    "accounting.loan_installments.status",
    "accounting.loan_installments.update",
    "accounting.loans.create",
    "accounting.loans.status",
    "accounting.loans.update",
    "accounting.non_electronic_invoices.create",
    "accounting.partners.create",
    "accounting.partners.update",
    "accounting.payment_links.create",
    "accounting.payment_links.remove",
    "accounting.payments.create",
    "accounting.payments.duplicate",
    "accounting.payments.mark_seen",
    "accounting.payments.mark_unseen",
    "accounting.payments.split_components",
    "accounting.payments.update",
    "accounting.tax_commitments.create",
    "accounting.tax_commitments.update",
    "accounting.tax_installments.create",
    "accounting.tax_installments.mark_paid",
    "accounting.tax_installments.unmark_paid",
    "accounting.tax_installments.update",
})
FILE_CREATE_TOOL = "accounting.non_electronic_invoices.create"
FILE_ACTION_TOOLS = frozenset({
    FILE_CREATE_TOOL,
    "accounting.documents.create_with_attachments",
    "accounting.attachments.add",
})
APPROVED_ACCOUNTING_TOOLS = APPROVED_ACCOUNTING_READ_TOOLS | APPROVED_ACCOUNTING_DRAFT_TOOLS
REMOTE_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
APPROVED_REMOTE_ERROR_CODES = frozenset({
    "accounting_contact_not_found",
    "accounting_delivery_note_not_found",
    "accounting_document_ai_search_failed",
    "accounting_document_not_found",
    "accounting_document_type_not_agentic",
    "accounting_due_date_ai_search_failed",
    "accounting_due_date_not_found",
    "accounting_insurance_policy_not_found",
    "accounting_loan_not_found",
    "accounting_partner_ai_search_failed",
    "accounting_partner_not_found",
    "accounting_payment_ai_search_failed",
    "accounting_payment_not_found",
    "accounting_summary_ai_read_failed",
    "accounting_tax_commitment_not_found",
    "accounting_tax_installment_not_found",
    "accounting_agentic_attachment_create_failed",
    "accounting_agentic_company_constraint_denied",
    "accounting_agentic_empty_update",
    "accounting_agentic_file_count_invalid",
    "accounting_agentic_file_empty",
    "accounting_agentic_file_extension_denied",
    "accounting_agentic_file_mime_denied",
    "accounting_agentic_file_too_large",
    "accounting_agentic_mutation_kind_unsupported",
    "accounting_agentic_pdf_invalid",
    "accounting_agentic_prepared_state_invalid",
    "accounting_agentic_stale_state",
    "accounting_agentic_total_size_exceeded",
    "accounting_invoice_duplicate",
    "agentic_action_revalidation_denied",
    "agentic_idempotency_conflict",
    "agentic_idempotency_key_required",
    "agentic_internal_error",
    "agentic_upload_base64_invalid",
    "agentic_upload_concurrency_exceeded",
    "agentic_upload_item_quota_exceeded",
    "agentic_upload_quota_exceeded",
    "agentic_upload_session_not_found",
    "agentic_upload_session_quota_exceeded",
    "agentic_upload_session_unavailable",
    "agentic_upload_too_large",
    "agent_token_invalid",
    "agentic_admin_forbidden",
    "agentic_attachment_download_https_required",
    "agentic_attachment_download_not_available",
    "agentic_direct_disabled",
    "agentic_disabled",
    "agentic_execution_mode_denied",
    "agentic_execution_mode_unsupported",
    "agentic_grant_denied",
    "agentic_grant_expired",
    "agentic_input_invalid",
    "agentic_invoke_failed",
    "agentic_module_disabled",
    "agentic_rate_limit_exceeded",
    "agentic_resource_denied",
    "agentic_result_too_large",
    "agentic_scope_denied",
    "agentic_tool_not_found",
    "agentic_tool_output_invalid",
    "agentic_user_capability_denied",
    "agentic_user_permission_denied",
    "agentic_user_resource_denied",
    "not_found",
})


def _normalize_remote_error_code(value):
    if not isinstance(value, str) or not REMOTE_ERROR_CODE.fullmatch(value):
        return "reman_http_error"
    return value if value in APPROVED_REMOTE_ERROR_CODES else "reman_http_error"


class RemanError(Exception):
    def __init__(self, code, status=None, request_id=None, retryable=False):
        super().__init__(code)
        self.code = str(code)
        self.status = status
        self.request_id = request_id
        self.retryable = bool(retryable)

    def public(self):
        result = {"error": self.code, "retryable": self.retryable}
        if self.status is not None:
            result["status"] = self.status
        if self.request_id:
            result["requestId"] = self.request_id
        return result


class RemanTransportError(RemanError):
    def __init__(self, code):
        super().__init__(code, retryable=True)


class _DenyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RemanClient:
    def __init__(self, base_url=None, token=None, timeout=None):
        self.base_url = (
            base_url or os.environ.get("REMAN_AGENT_BASE_URL", "") or DEFAULT_REMAN_BASE_URL
        ).strip().rstrip("/")
        self.token = (token or os.environ.get("REMAN_AGENT_TOKEN", "")).strip()
        self.timeout = float(timeout or os.environ.get("REMAN_AGENT_TIMEOUT_SECONDS", "30"))
        self._validate_configuration()

    def _validate_configuration(self):
        if not self.base_url or not self.token:
            raise RemanError("reman_connector_not_configured")
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise RemanError("reman_base_url_invalid")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RemanError("reman_base_url_invalid")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise RemanError("reman_https_required")

    def _request(self, method, path, payload=None, idempotency_key=None):
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "User-Agent": "Hermes-REman-Agentic/1.2.0",
            "X-REman-Agent-Token": self.token,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["X-REman-Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.build_opener(_DenyRedirects()).open(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            try:
                if 300 <= error.code < 400:
                    raise RemanError("reman_redirect_denied", error.code) from None
                try:
                    failure = json.loads(error.read().decode("utf-8"))
                except Exception:
                    failure = {}
                if not isinstance(failure, dict):
                    failure = {}
                raise RemanError(_normalize_remote_error_code(failure.get("error")), error.code) from None
            finally:
                error.close()
        except (
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            http.client.RemoteDisconnected,
            http.client.IncompleteRead,
            ConnectionResetError,
        ):
            raise RemanTransportError("reman_transport_timeout_or_unreachable") from None
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            raise RemanError("reman_response_invalid") from None

    def discover(self):
        discovery = self._request("GET", "/api/v1/agentic/tools")
        if not isinstance(discovery, dict):
            raise RemanError("reman_response_invalid")
        sanitized = dict(discovery)
        items = []
        for item in discovery.get("items", []):
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            name = item["name"]
            supported = item.get("supportedModes")
            if not ACCOUNTING_TOOL_NAME.fullmatch(name) or name not in APPROVED_ACCOUNTING_TOOLS or not isinstance(supported, list):
                continue
            modes = []
            if name in APPROVED_ACCOUNTING_READ_TOOLS and "read" in supported:
                modes.append("read")
            if name in APPROVED_ACCOUNTING_DRAFT_TOOLS and "draft_with_confirmation" in supported:
                modes.append("draft_with_confirmation")
            if modes:
                items.append({**item, "supportedModes": modes})
        sanitized["items"] = items
        return sanitized

    def require_tool(self, tool_name, mode):
        if mode == "read":
            approved = APPROVED_ACCOUNTING_READ_TOOLS
        elif mode == "draft_with_confirmation":
            approved = APPROVED_ACCOUNTING_DRAFT_TOOLS
        else:
            raise RemanError("reman_direct_mode_disabled" if mode == "direct" else "reman_execution_mode_invalid")
        if tool_name not in approved:
            raise RemanError("reman_tool_not_approved_by_connector")
        discovery = self.discover()
        tool = next((item for item in discovery.get("items", []) if item.get("name") == tool_name), None)
        if not tool:
            raise RemanError("reman_tool_not_granted_or_unavailable")
        if mode not in tool.get("supportedModes", []):
            raise RemanError("reman_tool_mode_not_granted")
        return tool

    def invoke(self, tool_name, mode, input_data, idempotency_key=None):
        self.require_tool(tool_name, mode)
        if mode == "draft_with_confirmation" and not idempotency_key:
            raise RemanError("reman_idempotency_key_required")
        return self._request(
            "POST",
            "/api/v1/agentic/tools/{}/invoke".format(urllib.parse.quote(tool_name, safe="")),
            {"mode": mode, "input": input_data},
            idempotency_key,
        )

    def create_upload_session(self, tool_name):
        self.require_tool(tool_name, "draft_with_confirmation")
        if tool_name not in FILE_ACTION_TOOLS:
            raise RemanError("reman_upload_tool_not_approved")
        return self._request("POST", "/api/v1/agentic/uploads/sessions", {"toolName": tool_name})

    def upload_pdf(self, session_id, file_name, content):
        return self._request(
            "POST",
            "/api/v1/agentic/uploads/sessions/{}/items".format(urllib.parse.quote(session_id, safe="")),
            {
                "fileName": file_name,
                "mimeType": "application/pdf",
                "contentBase64": base64.b64encode(content).decode("ascii"),
            },
        )

    def get_upload_session(self, session_id):
        return self._request(
            "GET",
            "/api/v1/agentic/uploads/sessions/{}".format(urllib.parse.quote(session_id, safe="")),
        )
