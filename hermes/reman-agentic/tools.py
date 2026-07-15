"""Read-only Hermes handlers. Every handler returns redacted JSON."""

import json
import re

from .client import RemanClient, RemanError


ACCOUNTING_READ_TOOL = re.compile(r"^accounting\.[a-z0-9_.]+$")
RESERVED_AGENT_INPUT_KEYS = {
    "agentId", "delegatingUserId", "executionMode", "grantVersion", "isExternalAgent",
    "isSystemAdmin", "mode", "scopes", "teamId", "userId",
}


def _ok(action):
    try:
        return json.dumps(action(), ensure_ascii=False)
    except RemanError as error:
        return json.dumps(error.public(), ensure_ascii=False)
    except Exception:
        return json.dumps({"error": "reman_connector_internal_error", "retryable": False})


def _compact(values):
    return {key: value for key, value in values.items() if value is not None and value != ""}


def _contains_reserved_key(value):
    if isinstance(value, dict):
        return bool(RESERVED_AGENT_INPUT_KEYS.intersection(value)) or any(
            _contains_reserved_key(child) for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_reserved_key(child) for child in value)
    return False


def available_tools(args, **kwargs):
    return _ok(lambda: RemanClient().discover())


def _invoke_accounting_read(args):
    tool_name = args.get("tool_name")
    input_data = args.get("input")
    if not isinstance(tool_name, str) or not ACCOUNTING_READ_TOOL.fullmatch(tool_name):
        raise RemanError("reman_accounting_tool_name_invalid")
    if not isinstance(input_data, dict) or len(input_data) > 32:
        raise RemanError("reman_accounting_input_invalid")
    if _contains_reserved_key(input_data):
        raise RemanError("reman_agent_context_input_forbidden")
    if len(json.dumps(input_data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")) > 32 * 1024:
        raise RemanError("reman_accounting_input_too_large")
    return RemanClient().invoke(tool_name, "read", input_data)


def invoke_accounting_read(args, **kwargs):
    return _ok(lambda: _invoke_accounting_read(args))


def list_companies(args, **kwargs):
    return _ok(lambda: RemanClient().invoke("accounting.companies.list", "read", _compact({
        "query": args.get("query"), "limit": args.get("limit", 25)
    })))


def search_partners(args, **kwargs):
    return _ok(lambda: RemanClient().invoke("accounting.partners.search", "read", _compact({
        "companyId": args.get("company_id"), "query": args.get("query"), "vatNumber": args.get("vat_number"),
        "taxCode": args.get("tax_code"), "limit": args.get("limit", 25)
    })))


def search_invoices(args, **kwargs):
    return _ok(lambda: RemanClient().invoke("accounting.non_electronic_invoices.search", "read", _compact({
        "companyId": args.get("company_id"), "query": args.get("query"), "documentNumber": args.get("document_number"),
        "partnerName": args.get("partner_name"), "dateFrom": args.get("date_from"), "dateTo": args.get("date_to"),
        "limit": args.get("limit", 25)
    })))
