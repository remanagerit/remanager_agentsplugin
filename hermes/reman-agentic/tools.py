"""Governed Hermes handlers. Every handler returns bounded JSON and fails closed."""

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path

from .catalog import TOOL_CONTRACTS, contract_for
from .client import (
    APPROVED_ACCOUNTING_DRAFT_TOOLS,
    APPROVED_ACCOUNTING_READ_TOOLS,
    FILE_ACTION_TOOLS,
    FILE_CREATE_TOOL,
    RemanClient,
    RemanError,
    RemanTransportError,
)
from .file_access import allowed_pdf_roots, read_allowed_pdf
from .schemas import UPLOAD_FILE


ACCOUNTING_TOOL = re.compile(r"^accounting\.[a-z0-9_.]+$")
OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ACTION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
STATE_TTL_SECONDS = 7 * 24 * 60 * 60
STALE_UPLOAD_SESSION_ERRORS = {"agentic_upload_session_not_found", "agentic_upload_session_unavailable"}
RESERVED_AGENT_INPUT_KEYS = {
    "agentId", "delegatingUserId", "executionMode", "grantVersion", "isExternalAgent",
    "isSystemAdmin", "mode", "scopes", "teamId", "uploadSessionId", "userId",
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


def _validate_business_input(tool_name, input_data, approved):
    if not isinstance(tool_name, str) or not ACCOUNTING_TOOL.fullmatch(tool_name):
        raise RemanError("reman_accounting_tool_name_invalid")
    if tool_name not in approved:
        raise RemanError("reman_tool_not_approved_by_connector")
    if not isinstance(input_data, dict) or len(input_data) > 64:
        raise RemanError("reman_accounting_input_invalid")
    if _contains_reserved_key(input_data):
        raise RemanError("reman_agent_context_input_forbidden")
    if len(json.dumps(input_data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")) > 64 * 1024:
        raise RemanError("reman_accounting_input_too_large")
    return input_data


def _operation_id(value):
    if not isinstance(value, str) or not OPERATION_ID.fullmatch(value):
        raise RemanError("reman_operation_id_invalid")
    return value


def _idempotency_key(tool_name, input_data, operation_id):
    canonical = json.dumps(
        {"toolName": tool_name, "input": input_data, "operationId": operation_id},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "hermes-reman-" + hashlib.sha256(canonical).hexdigest()


def _safe_action_response(response):
    source = response.get("result") if isinstance(response, dict) and isinstance(response.get("result"), dict) else {}
    allowed = {
        "status", "actionId", "expiresAt", "confirmationRequired", "preview", "inputSummary",
        "resourceSummary", "entryId", "companyId", "attachmentIds", "attachmentCount",
        "documentNumber", "documentDate", "warnings", "createdVia", "errorCode",
        "documentId", "fiscalDocumentType", "settledByOrigin", "paidAmount", "residualAmount", "paymentsCreated",
    }
    return _compact({
        "result": {key: value for key, value in source.items() if key in allowed},
        "idempotentReplay": response.get("idempotentReplay") if isinstance(response, dict) else None,
    })


def _minimal_state_response(response):
    result = response.get("result") if isinstance(response, dict) and isinstance(response.get("result"), dict) else {}
    return {"result": {key: result[key] for key in ("status", "actionId", "expiresAt", "confirmationRequired", "errorCode") if key in result}}


def available_tools(args, **kwargs):
    return _ok(lambda: RemanClient().discover())


def _tool_contract(args):
    tool_name = args.get("tool_name")
    if not isinstance(tool_name, str) or tool_name not in TOOL_CONTRACTS:
        raise RemanError("reman_tool_not_approved_by_connector")
    contract = contract_for(tool_name)
    RemanClient().require_tool(tool_name, contract["mode"])
    return contract


def tool_contract(args, **kwargs):
    return _ok(lambda: _tool_contract(args))


def _invoke_accounting_read(args):
    tool_name = args.get("tool_name")
    input_data = _validate_business_input(tool_name, args.get("input"), APPROVED_ACCOUNTING_READ_TOOLS)
    return RemanClient().invoke(tool_name, "read", input_data)


def invoke_accounting_read(args, **kwargs):
    return _ok(lambda: _invoke_accounting_read(args))


def _prepare_accounting_action(args):
    tool_name = args.get("tool_name")
    if tool_name in FILE_ACTION_TOOLS and tool_name != "accounting.attachments.add":
        raise RemanError("reman_file_tool_requires_dedicated_handler")
    supplied = args.get("input")
    if tool_name == "accounting.attachments.add" and isinstance(supplied, dict):
        session_id = supplied.get("uploadSessionId")
        if not isinstance(session_id, str) or not ACTION_ID.fullmatch(session_id):
            raise RemanError("reman_upload_input_invalid")
        # Only this top-level business reference is permitted; recursive context checks stay intact.
        business = {key: value for key, value in supplied.items() if key != "uploadSessionId"}
        input_data = {**_validate_business_input(tool_name, business, APPROVED_ACCOUNTING_DRAFT_TOOLS), "uploadSessionId": session_id}
    else:
        input_data = _validate_business_input(tool_name, supplied, APPROVED_ACCOUNTING_DRAFT_TOOLS)
    operation_id = _operation_id(args.get("operation_id"))
    response = RemanClient().invoke(
        tool_name,
        "draft_with_confirmation",
        input_data,
        _idempotency_key(tool_name, input_data, operation_id),
    )
    return _safe_action_response(response)


def prepare_accounting_action(args, **kwargs):
    return _ok(lambda: _prepare_accounting_action(args))


def accounting_action(args, **kwargs):
    return prepare_accounting_action(args, **kwargs)


def upload_session_create(args, **kwargs):
    return _ok(lambda: RemanClient().create_upload_session("accounting.attachments.add"))


def upload_file_base64(args, **kwargs):
    def run():
        for name, definition in UPLOAD_FILE["parameters"]["properties"].items():
            value = args.get(name)
            if not isinstance(value, str) or not value or len(value) > definition.get("maxLength", 255):
                raise RemanError("reman_upload_input_invalid")
            if "enum" in definition and value not in definition["enum"]:
                raise RemanError("reman_upload_input_invalid")
        if not ACTION_ID.fullmatch(args["sessionId"]):
            raise RemanError("reman_upload_input_invalid")
        client = RemanClient()
        client.require_tool("accounting.attachments.add", "draft_with_confirmation")
        return client.upload_file_base64(args["sessionId"], args["fileName"], args["mimeType"], args["contentBase64"])
    return _ok(run)


def upload_session_release(args, **kwargs):
    def run():
        session_id = args.get("sessionId")
        if not isinstance(session_id, str) or not ACTION_ID.fullmatch(session_id):
            raise RemanError("reman_upload_input_invalid")
        return RemanClient().release_upload_session(session_id)
    return _ok(run)


def _cancel_agentic_action(args):
    action_id = args.get("action_id")
    if not isinstance(action_id, str) or not ACTION_ID.fullmatch(action_id):
        raise RemanError("reman_action_id_invalid")
    reason = args.get("reason")
    if reason is not None:
        if not isinstance(reason, str) or len(reason.strip()) > 500:
            raise RemanError("reman_cancel_reason_invalid")
        reason = reason.strip()
    response = RemanClient().cancel_action(action_id, reason)
    item = response.get("item") if isinstance(response, dict) and isinstance(response.get("item"), dict) else {}
    return _compact({
        "item": {key: item.get(key) for key in ("actionId", "status", "createdAt", "cancelledAt", "updatedAt") if key in item},
        "requestId": response.get("requestId") if isinstance(response, dict) else None,
    })


def cancel_agentic_action(args, **kwargs):
    return _ok(lambda: _cancel_agentic_action(args))


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


def _state_root():
    root = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))) / "reman-agentic-state"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise RemanError("reman_state_directory_invalid")
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


def _clear_upload_session_state(state, state_path):
    state.pop("uploadSessionId", None)
    state.pop("uploadedItems", None)
    state["updatedAt"] = time.time()
    _atomic_json(state_path, state)


def _release_upload_session(client, state, state_path):
    session_id = state.get("uploadSessionId")
    if not session_id:
        return
    released = True
    try:
        client.release_upload_session(session_id)
    except RemanError as error:
        released = error.code in {"not_found", "agentic_upload_session_not_found", "agentic_upload_session_unavailable"}
    if released:
        _clear_upload_session_state(state, state_path)


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
        path, content, size = read_allowed_pdf(str(raw_path), roots, max_bytes=max_file_bytes, before_open=before_open)
        total += size
        if total > max_total_bytes:
            raise RemanError("reman_pdf_total_exceeds_grant_limit")
        if len(content) != size or not content.startswith(b"%PDF-"):
            raise RemanError("reman_pdf_invalid_or_missing")
        metadata.append({"name": path.name, "content": content, "sha256": hashlib.sha256(content).hexdigest()})
    return metadata


def _file_fingerprint(tool_name, input_data, files, operation_id):
    canonical = {
        "toolName": tool_name,
        "input": input_data,
        "files": [{"name": item["name"], "sha256": item["sha256"], "size": len(item["content"])} for item in files],
        "operationId": operation_id,
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _wait_for_ready(client, session_id):
    wait_seconds = min(120, max(1, int(os.environ.get("REMAN_AGENT_SCAN_WAIT_SECONDS", "45"))))
    deadline = time.monotonic() + wait_seconds
    while True:
        session = client.get_upload_session(session_id)
        status = session.get("status") if isinstance(session, dict) else None
        if status == "ready":
            return True
        if status in {"rejected", "quarantined", "consumed"}:
            raise RemanError("reman_upload_rejected")
        if status not in {"uploaded", "pending_scan", "clean", "processing"}:
            raise RemanError("reman_upload_status_invalid")
        if time.monotonic() >= deadline:
            return False
        time.sleep(1)


def _prepare_file_action(tool_name, input_data, pdf_paths, operation_id):
    if tool_name not in FILE_ACTION_TOOLS:
        raise RemanError("reman_file_tool_not_approved")
    operation_id = _operation_id(operation_id)
    input_data = _validate_business_input(tool_name, input_data, APPROVED_ACCOUNTING_DRAFT_TOOLS)
    roots = allowed_pdf_roots()
    client = RemanClient()
    tool = client.require_tool(tool_name, "draft_with_confirmation")
    policy = tool.get("filePolicy") or {}
    files = _read_pdfs(pdf_paths, policy, roots)
    fingerprint = _file_fingerprint(tool_name, input_data, files, operation_id)
    state_path = _state_root() / (fingerprint + ".json")
    lock_path = _state_root() / (fingerprint + ".lock")
    try:
        lock_path.mkdir(mode=0o700)
    except FileExistsError:
        raise RemanError("reman_operation_already_in_progress")
    try:
        state = _load_state(state_path) or {
            "idempotencyKey": "hermes-reman-" + fingerprint,
            "uploadedItems": [],
            "updatedAt": time.time(),
        }
        prepared_action = state.get("status") == "succeeded" and isinstance(state.get("response"), dict)
        attempts = 0
        while True:
            attempts += 1
            if not prepared_action and not state.get("uploadSessionId"):
                session = client.create_upload_session(tool_name)
                state["uploadSessionId"] = session.get("sessionId")
                if not isinstance(state["uploadSessionId"], str):
                    raise RemanError("reman_response_invalid")
                state["updatedAt"] = time.time()
                _atomic_json(state_path, state)
            try:
                if not prepared_action:
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
                    if not _wait_for_ready(client, state["uploadSessionId"]):
                        state["updatedAt"] = time.time()
                        _atomic_json(state_path, state)
                        return {"result": {"status": "pending_scan", "operationId": operation_id, "retryAfterSeconds": 5}}
                response = client.invoke(
                    tool_name,
                    "draft_with_confirmation",
                    {**input_data, "uploadSessionId": state["uploadSessionId"]},
                    state["idempotencyKey"],
                )
                break
            except RemanTransportError:
                raise
            except RemanError as error:
                _release_upload_session(client, state, state_path)
                if attempts == 1 and error.code in STALE_UPLOAD_SESSION_ERRORS:
                    continue
                raise
        safe = _safe_action_response(response)
        state.update({"status": "succeeded", "response": _minimal_state_response(safe), "updatedAt": time.time()})
        _atomic_json(state_path, state)
        return safe
    finally:
        try:
            lock_path.rmdir()
        except OSError:
            pass


def _prepare_accounting_file_action(args):
    return _prepare_file_action(
        args.get("tool_name"),
        args.get("input"),
        args.get("pdf_paths"),
        args.get("operation_id"),
    )


def prepare_accounting_file_action(args, **kwargs):
    return _ok(lambda: _prepare_accounting_file_action(args))


def _create_invoice(args):
    input_data = _compact({
        "companyId": args.get("company_id"), "accountingContactId": args.get("accounting_contact_id"),
        "partnerName": args.get("partner_name"), "partnerTaxCode": args.get("partner_tax_code"),
        "partnerVatNumber": args.get("partner_vat_number"), "documentNumber": args.get("document_number"),
        "documentDate": args.get("document_date"), "dueDate": args.get("due_date"),
        "dueDates": args.get("due_dates"), "paymentAllocations": args.get("payment_allocations"),
        "netAmount": args.get("net_amount"), "vatAmount": args.get("vat_amount"), "grossAmount": args.get("gross_amount"),
        "withholdingAmount": args.get("withholding_amount"), "originalCurrency": args.get("original_currency"),
        "originalNetAmount": args.get("original_net_amount"), "originalVatAmount": args.get("original_vat_amount"),
        "originalGrossAmount": args.get("original_gross_amount"), "fxRateToEur": args.get("fx_rate_to_eur"),
        "fxRateDate": args.get("fx_rate_date"), "fxRateSource": args.get("fx_rate_source"),
        "fxConversionNote": args.get("fx_conversion_note"), "description": args.get("description"),
        "notes": args.get("notes"),
    })
    return _prepare_file_action(
        FILE_CREATE_TOOL,
        input_data,
        args.get("pdf_paths"),
        args.get("operation_id"),
    )


def create_invoice(args, **kwargs):
    return _ok(lambda: _create_invoice(args))
