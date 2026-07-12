"""Hermes handlers. Every handler returns JSON and fails closed."""

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path

from .client import RemanClient, RemanError
from .file_access import allowed_pdf_roots, read_allowed_pdf

CREATE_TOOL = "accounting.non_electronic_invoices.create"
STATE_TTL_SECONDS = 7 * 24 * 60 * 60
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


def _state_root():
    root = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))) / "reman-agentic-state"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


def _atomic_json(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix=".reman-", dir=str(path.parent), text=True)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _load_state(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(value.get("updatedAt", 0)) <= STATE_TTL_SECONDS:
            return value
    except Exception:
        pass
    return None


def _positive_limit(value, fallback):
    return int(value) if isinstance(value, (int, float)) and int(value) > 0 else fallback


def _read_pdfs(paths, policy, roots, before_open=None):
    if not isinstance(paths, list) or not 1 <= len(paths) <= 5:
        raise RemanError("reman_pdf_count_invalid")
    max_files = min(5, _positive_limit(policy.get("maxFiles"), 5))
    max_file_bytes = min(20 * 1024 * 1024, _positive_limit(policy.get("maxFileBytes"), 20 * 1024 * 1024))
    max_total_bytes = min(100 * 1024 * 1024, _positive_limit(policy.get("maxTotalBytes"), 100 * 1024 * 1024))
    if len(paths) > max_files:
        raise RemanError("reman_pdf_count_exceeds_grant")
    metadata = []
    total = 0
    for raw_path in paths:
        path, content, size = read_allowed_pdf(
            str(raw_path), roots, max_bytes=max_file_bytes, before_open=before_open
        )
        total += size
        if total > max_total_bytes:
            raise RemanError("reman_pdf_total_exceeds_grant_limit")
        if len(content) != size or not content.startswith(b"%PDF-"):
            raise RemanError("reman_pdf_invalid_or_missing")
        metadata.append({"name": path.name, "content": content, "sha256": hashlib.sha256(content).hexdigest()})
    return metadata


def _fingerprint(input_data, files, operation_id):
    canonical = {
        "input": input_data,
        "files": [{"name": item["name"], "sha256": item["sha256"], "size": len(item["content"])} for item in files],
        "operationId": operation_id or None,
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _safe_response(response):
    source = response.get("result") if isinstance(response, dict) and isinstance(response.get("result"), dict) else {}
    allowed = {
        "status", "entryId", "draftId", "companyId", "attachmentIds", "attachmentCount", "documentNumber",
        "documentDate", "warnings", "createdVia", "expiresAt", "confirmationUrl"
    }
    result = {key: value for key, value in source.items() if key in allowed}
    return _compact({
        "result": result,
        "idempotentReplay": response.get("idempotentReplay") if isinstance(response, dict) else None,
        "requestId": response.get("requestId") if isinstance(response, dict) else None,
    })


def available_tools(args, **kwargs):
    return _ok(lambda: RemanClient().discover())


def _invoke_accounting_read(args):
    tool_name = args.get("tool_name")
    input_data = args.get("input")
    if not isinstance(tool_name, str) or not ACCOUNTING_READ_TOOL.fullmatch(tool_name):
        raise RemanError("reman_accounting_tool_name_invalid")
    if not isinstance(input_data, dict) or len(input_data) > 32:
        raise RemanError("reman_accounting_input_invalid")
    if RESERVED_AGENT_INPUT_KEYS.intersection(input_data):
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


def _create_invoice(args):
    mode = args.get("mode", "draft_with_confirmation")
    if mode == "direct":
        raise RemanError("reman_direct_mode_disabled")
    if mode != "draft_with_confirmation":
        raise RemanError("reman_execution_mode_invalid")
    roots = allowed_pdf_roots()
    client = RemanClient()
    tool = client.require_tool(CREATE_TOOL, mode)
    policy = tool.get("filePolicy") or {}
    files = _read_pdfs(args.get("pdf_paths"), policy, roots)
    input_data = _compact({
        "companyId": args.get("company_id"), "accountingContactId": args.get("accounting_contact_id"),
        "partnerName": args.get("partner_name"), "partnerTaxCode": args.get("partner_tax_code"),
        "partnerVatNumber": args.get("partner_vat_number"), "documentNumber": args.get("document_number"),
        "documentDate": args.get("document_date"), "dueDate": args.get("due_date"),
        "netAmount": args.get("net_amount"), "vatAmount": args.get("vat_amount"), "grossAmount": args.get("gross_amount"),
        "withholdingAmount": args.get("withholding_amount"), "description": args.get("description"), "notes": args.get("notes"),
    })
    fingerprint = _fingerprint({"mode": mode, **input_data}, files, args.get("operation_id"))
    state_path = _state_root() / (fingerprint + ".json")
    lock_path = _state_root() / (fingerprint + ".lock")
    try:
        lock_path.mkdir(mode=0o700)
    except FileExistsError:
        raise RemanError("reman_operation_already_in_progress")
    try:
        state = _load_state(state_path) or {
            "idempotencyKey": "hermes-reman-" + fingerprint,
            "uploadedHashes": [],
            "updatedAt": time.time(),
        }
        if state.get("status") == "succeeded" and "response" in state:
            return state["response"]
        if not state.get("uploadSessionId"):
            state["uploadSessionId"] = client.create_upload_session(CREATE_TOOL)["sessionId"]
            state["updatedAt"] = time.time()
            _atomic_json(state_path, state)
        uploaded = set(state.get("uploadedItems", []))
        for index, item in enumerate(files):
            item_key = "{}:{}".format(index, item["sha256"])
            if item_key in uploaded:
                continue
            client.upload_pdf(state["uploadSessionId"], item["name"], item["content"])
            uploaded.add(item_key)
            state["uploadedItems"] = sorted(uploaded)
            state["updatedAt"] = time.time()
            _atomic_json(state_path, state)
        response = client.invoke(
            CREATE_TOOL,
            mode,
            {**input_data, "uploadSessionId": state["uploadSessionId"]},
            state["idempotencyKey"],
        )
        state.update({"status": "succeeded", "response": _safe_response(response), "updatedAt": time.time()})
        _atomic_json(state_path, state)
        return response
    finally:
        try:
            lock_path.rmdir()
        except OSError:
            pass


def create_invoice(args, **kwargs):
    return _ok(lambda: _create_invoice(args))
