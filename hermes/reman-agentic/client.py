"""Small stdlib-only client for the governed REman Agentic REST surface."""

import http.client
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request


ACCOUNTING_TOOL_NAME = re.compile(r"^accounting\.[a-z0-9_.]+$")
APPROVED_ACCOUNTING_READ_TOOLS = frozenset({
    "accounting.companies.list",
    "accounting.partners.search",
    "accounting.partners.get",
    "accounting.non_electronic_invoices.search",
    "accounting.documents.search",
    "accounting.documents.get",
    "accounting.document_due_dates.search",
    "accounting.document_due_dates.get",
    "accounting.delivery_notes.search",
    "accounting.delivery_notes.get",
    "accounting.payments.search",
    "accounting.payments.get",
    "accounting.payment_links.search",
    "accounting.tax_commitments.search",
    "accounting.tax_commitments.get",
    "accounting.tax_installments.search",
    "accounting.tax_installments.get",
    "accounting.loans.search",
    "accounting.loans.get",
    "accounting.insurance_policies.search",
    "accounting.insurance_policies.get",
    "accounting.summary.read",
})
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
    "agent_token_invalid",
    "agentic_admin_forbidden",
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
        self.base_url = (base_url or os.environ.get("REMAN_AGENT_BASE_URL", "")).strip().rstrip("/")
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

    def _request(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "User-Agent": "Hermes-REman-Agentic/1.0",
            "X-REman-Agent-Token": self.token,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
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
        sanitized["items"] = [
            {**item, "supportedModes": ["read"]}
            for item in discovery.get("items", [])
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and ACCOUNTING_TOOL_NAME.fullmatch(item["name"])
            and item["name"] in APPROVED_ACCOUNTING_READ_TOOLS
            and isinstance(item.get("supportedModes"), list)
            and "read" in item["supportedModes"]
        ]
        return sanitized

    def require_tool(self, tool_name, mode):
        if mode != "read":
            raise RemanError("reman_read_only_connector")
        discovery = self.discover()
        tool = next((item for item in discovery.get("items", []) if item.get("name") == tool_name), None)
        if not tool:
            raise RemanError("reman_tool_not_granted_or_unavailable")
        if mode not in tool.get("supportedModes", []):
            raise RemanError("reman_tool_mode_not_granted")
        return tool

    def invoke(self, tool_name, mode, input_data):
        self.require_tool(tool_name, mode)
        return self._request(
            "POST",
            "/api/v1/agentic/tools/{}/invoke".format(urllib.parse.quote(tool_name, safe="")),
            {"mode": mode, "input": input_data},
        )
