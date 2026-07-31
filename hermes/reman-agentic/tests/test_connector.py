import importlib.util
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reman_agentic_test_plugin",
    PLUGIN_DIR / "__init__.py",
    submodule_search_locations=[str(PLUGIN_DIR)],
)
PLUGIN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PLUGIN
SPEC.loader.exec_module(PLUGIN)
CATALOG = importlib.import_module("reman_agentic_test_plugin.catalog")
CLIENT = importlib.import_module("reman_agentic_test_plugin.client")
FILES = importlib.import_module("reman_agentic_test_plugin.file_access")
TOOLS = importlib.import_module("reman_agentic_test_plugin.tools")


class State:
    requests = []
    adversary_requests = []
    base_url = ""
    adversary_url = ""
    upload_status = "ready"


def discovered_items():
    read = [
        {"name": name, "supportedModes": ["read"], "description": "read"}
        for name in sorted(CLIENT.APPROVED_ACCOUNTING_READ_TOOLS)
    ]
    drafts = [
        {
            "name": name,
            "supportedModes": ["draft_with_confirmation", "direct"],
            "description": "draft",
            **({"filePolicy": {"maxFiles": 5, "maxFileBytes": 20 * 1024 * 1024, "maxTotalBytes": 100 * 1024 * 1024}} if name == CLIENT.FILE_CREATE_TOOL else {}),
        }
        for name in sorted(CLIENT.APPROVED_ACCOUNTING_DRAFT_TOOLS)
    ]
    return read + drafts + [
        {"name": "accounting.settings.update", "supportedModes": ["direct"]},
        {"name": "accounting.bank_movements.import", "supportedModes": ["draft_with_confirmation"]},
        {"name": "tasks.search", "supportedModes": ["read"]},
    ]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self):
        length = int(self.headers.get("content-length", "0"))
        return json.loads(self.rfile.read(length)) if length else None

    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("location", location)
        self.end_headers()

    def do_GET(self):
        State.requests.append(("GET", self.path, None, dict(self.headers)))
        if self.path.startswith("/redirect-same/"):
            self._redirect(State.base_url + "/api/v1/agentic/tools")
            return
        if self.path.startswith("/redirect-cross/"):
            self._redirect(State.adversary_url + "/collect")
            return
        if self.path.startswith("/api/v1/agentic/uploads/sessions/"):
            self._send(200, {
                "sessionId": "session-1",
                "toolName": CLIENT.FILE_CREATE_TOOL,
                "status": State.upload_status,
                "items": [{"itemId": "item-1", "status": "clean" if State.upload_status == "ready" else State.upload_status}],
            })
            return
        self._send(200, {"grantVersion": 3, "items": discovered_items()})

    def do_POST(self):
        payload = self._json()
        State.requests.append(("POST", self.path, payload, dict(self.headers)))
        if self.path == "/api/v1/agentic/uploads/sessions":
            self._send(201, {"sessionId": "session-1", "status": "uploaded"})
        elif self.path.endswith("/items"):
            self._send(201, {"itemId": "item-1", "status": "pending_scan"})
        elif self.path.endswith("/accounting.payments.search/invoke"):
            self._send(200, {"result": {"items": [{"id": 41, "amount": 120}], "nextCursor": None}})
        elif self.path.endswith("/accounting.documents.search/invoke"):
            adversarial = payload.get("input", {}).get("adversarial")
            if adversarial == "error":
                self._send(500, {
                    "error": "agentic_disabled\n/private/tmp/customer.pdf secret-agent-token payload={sensitive}",
                    "requestId": "req-valid\n/private/tmp/secret-agent-token",
                    "message": "payload={customer-data}",
                    "debug": {"path": "/private/tmp/customer.pdf", "token": "secret-agent-token"},
                })
            else:
                self._send(503, {"error": "agentic_disabled", "requestId": "req-policy-1"})
        elif self.path.endswith("/accounting.payments.create/invoke"):
            self._send(200, {"result": {
                "status": "pending_confirmation",
                "actionId": "action-payment-1",
                "expiresAt": "2026-07-20T12:00:00Z",
                "confirmationRequired": True,
                "preview": {"kind": "payments.create"},
                "inputSummary": {"companyId": 7},
                "resourceSummary": {"resourceType": "company", "resourceId": 7},
            }, "idempotentReplay": False, "requestId": "req-safe"})
        elif self.path.endswith("/accounting.non_electronic_invoices.create/invoke"):
            self._send(200, {"result": {
                "status": "pending_confirmation",
                "actionId": "action-invoice-1",
                "expiresAt": "2026-07-20T12:00:00Z",
                "confirmationRequired": True,
                "preview": {"attachmentUploadSessionPrepared": True},
                "inputSummary": {"companyId": 7},
                "resourceSummary": {"resourceType": "company", "resourceId": 7},
            }, "idempotentReplay": False, "requestId": "req-safe"})
        else:
            self._send(404, {"error": "not_found"})


class AdversaryHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        State.adversary_requests.append((self.path, dict(self.headers)))
        self.send_response(200)
        self.end_headers()


class ConnectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adversary = ThreadingHTTPServer(("127.0.0.1", 0), AdversaryHandler)
        cls.adversary_thread = threading.Thread(target=cls.adversary.serve_forever, daemon=True)
        cls.adversary_thread.start()
        State.adversary_url = "http://127.0.0.1:{}".format(cls.adversary.server_port)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        State.base_url = "http://127.0.0.1:{}".format(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()
        cls.adversary.shutdown()
        cls.adversary_thread.join()
        cls.adversary.server_close()

    def setUp(self):
        State.requests = []
        State.adversary_requests = []
        State.upload_status = "ready"
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.allowed = self.root / "allowed"
        self.allowed.mkdir()
        self.pdf = self.allowed / "invoice.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        os.environ["HERMES_HOME"] = self.temp.name
        os.environ["REMAN_AGENT_BASE_URL"] = State.base_url
        os.environ["REMAN_AGENT_TOKEN"] = "secret-agent-token"
        os.environ["REMAN_AGENT_ALLOWED_PDF_DIRS"] = str(self.allowed)
        os.environ["REMAN_AGENT_SCAN_WAIT_SECONDS"] = "1"

    def tearDown(self):
        for key in (
            "HERMES_HOME", "REMAN_AGENT_BASE_URL", "REMAN_AGENT_TOKEN",
            "REMAN_AGENT_ALLOWED_PDF_DIRS", "REMAN_AGENT_SCAN_WAIT_SECONDS",
        ):
            os.environ.pop(key, None)
        self.temp.cleanup()

    def invoice_args(self):
        return {
            "company_id": 7,
            "document_number": "INV-42",
            "document_date": "2026-07-20",
            "net_amount": 100,
            "vat_amount": 22,
            "gross_amount": 122,
            "notes": "never persist me",
            "pdf_paths": [str(self.pdf)],
            "operation_id": "invoice-42-v1",
        }

    def assert_file_error(self, path, code, before_open=None):
        with self.assertRaises(CLIENT.RemanError) as raised:
            FILES.read_allowed_pdf(path, FILES.allowed_pdf_roots(), max_bytes=1024 * 1024, before_open=before_open)
        self.assertEqual(raised.exception.code, code)

    def test_catalog_has_exact_83_tool_membership(self):
        self.assertEqual(len(CLIENT.APPROVED_ACCOUNTING_READ_TOOLS), 33)
        self.assertEqual(len(CLIENT.APPROVED_ACCOUNTING_DRAFT_TOOLS), 50)
        self.assertEqual(set(CATALOG.TOOL_CONTRACTS), CLIENT.APPROVED_ACCOUNTING_TOOLS)
        self.assertEqual(len(CATALOG.TOOL_CONTRACTS), 83)
        self.assertNotIn("accounting.bank_movements.import", CATALOG.TOOL_CONTRACTS)

    def test_operator_instructions_are_self_contained(self):
        readme = (PLUGIN_DIR / "README.md").read_text(encoding="utf-8")
        skill = (PLUGIN_DIR / "skills" / "reman-accounting" / "SKILL.md").read_text(encoding="utf-8")
        plugin_manifest = (PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8")
        installer = (PLUGIN_DIR / "install.sh").read_text(encoding="utf-8")

        for content in (readme, skill, plugin_manifest, installer):
            self.assertIn("https://app.remanager.it", content)

        self.assertIn("official REmanager production origin by default", readme)
        self.assertIn("optional override", readme)
        self.assertIn("directories on the machine where the Hermes process runs", readme)
        self.assertIn("The user decides which directories are allowed", readme)
        self.assertIn("Separate multiple roots with `:` on macOS/Linux and `;` on Windows", skill)
        self.assertIn("preferably read-only", skill)
        self.assertIn("Without it, reads and non-file drafts remain usable", skill)

    def test_official_production_url_is_the_default(self):
        os.environ.pop("REMAN_AGENT_BASE_URL", None)
        client = CLIENT.RemanClient(token="synthetic-token")
        self.assertEqual(client.base_url, "https://app.remanager.it")
        self.assertTrue(PLUGIN._configured())

    def test_discovery_exposes_exact_approved_modes_and_hides_direct(self):
        discovery = CLIENT.RemanClient().discover()
        self.assertEqual({item["name"] for item in discovery["items"]}, CLIENT.APPROVED_ACCOUNTING_TOOLS)
        for item in discovery["items"]:
            expected = ["read"] if item["name"] in CLIENT.APPROVED_ACCOUNTING_READ_TOOLS else ["draft_with_confirmation"]
            self.assertEqual(item["supportedModes"], expected)
        output = TOOLS.available_tools({})
        self.assertNotIn("secret-agent-token", output)
        self.assertNotIn("tasks.search", output)
        self.assertNotIn("accounting.settings.update", output)
        self.assertNotIn("accounting.bank_movements.import", output)
        self.assertNotIn('"direct"', output)

    def test_contract_requires_current_discovery_and_returns_bounded_fields(self):
        contract = json.loads(TOOLS.tool_contract({"tool_name": "accounting.payments.create"}))
        self.assertEqual(contract["mode"], "draft_with_confirmation")
        self.assertIn("companyId", contract["required"])
        denied = json.loads(TOOLS.tool_contract({"tool_name": "accounting.bank_movements.import"}))
        self.assertEqual(denied["error"], "reman_tool_not_approved_by_connector")

    def test_generic_accounting_read_uses_discovery_and_forces_read(self):
        result = json.loads(TOOLS.invoke_accounting_read({
            "tool_name": "accounting.payments.search",
            "input": {"companyId": 7, "limit": 25, "cursor": 0},
        }))
        self.assertEqual(result["result"]["items"][0]["id"], 41)
        invoke = next(item for item in State.requests if item[1].endswith("/accounting.payments.search/invoke"))
        self.assertEqual(invoke[2], {"mode": "read", "input": {"companyId": 7, "limit": 25, "cursor": 0}})

    def test_generic_action_forces_draft_and_derives_stable_idempotency(self):
        args = {
            "tool_name": "accounting.payments.create",
            "input": {"companyId": 7, "direction": "out", "paymentDate": "2026-07-20", "amount": 122},
            "operation_id": "payment-42-v1",
        }
        first = json.loads(TOOLS.prepare_accounting_action(args))
        second = json.loads(TOOLS.prepare_accounting_action(args))
        self.assertEqual(first["result"]["status"], "pending_confirmation")
        self.assertTrue(first["result"]["confirmationRequired"])
        invokes = [item for item in State.requests if item[1].endswith("/accounting.payments.create/invoke")]
        self.assertEqual(len(invokes), 2)
        self.assertTrue(all(item[2]["mode"] == "draft_with_confirmation" for item in invokes))
        headers = [{key.lower(): value for key, value in item[3].items()} for item in invokes]
        self.assertEqual(headers[0]["x-reman-idempotency-key"], headers[1]["x-reman-idempotency-key"])
        self.assertNotIn("requestId", json.dumps(first))

    def test_generic_handlers_block_context_unapproved_file_and_large_input(self):
        forbidden = json.loads(TOOLS.prepare_accounting_action({
            "tool_name": "accounting.payments.create",
            "input": {"companyId": 7, "nested": {"teamId": 99}},
            "operation_id": "forbidden-1",
        }))
        self.assertEqual(forbidden["error"], "reman_agent_context_input_forbidden")
        outside = json.loads(TOOLS.invoke_accounting_read({"tool_name": "tasks.search", "input": {}}))
        self.assertEqual(outside["error"], "reman_accounting_tool_name_invalid")
        file_generic = json.loads(TOOLS.prepare_accounting_action({
            "tool_name": CLIENT.FILE_CREATE_TOOL, "input": {"companyId": 7}, "operation_id": "file-1"
        }))
        self.assertEqual(file_generic["error"], "reman_file_tool_requires_dedicated_handler")
        oversized = json.loads(TOOLS.invoke_accounting_read({
            "tool_name": "accounting.payments.search", "input": {"query": "x" * (65 * 1024)}
        }))
        self.assertEqual(oversized["error"], "reman_accounting_input_too_large")

    def test_file_invoice_upload_waits_for_clean_and_prepares_only_draft(self):
        output = TOOLS.create_invoice(self.invoice_args())
        result = json.loads(output)
        self.assertEqual(result["result"]["status"], "pending_confirmation")
        self.assertTrue(result["result"]["confirmationRequired"])
        upload_session = next(item for item in State.requests if item[1] == "/api/v1/agentic/uploads/sessions")
        self.assertEqual(upload_session[2], {"toolName": CLIENT.FILE_CREATE_TOOL})
        upload = next(item for item in State.requests if item[1].endswith("/items"))
        self.assertEqual(upload[2]["mimeType"], "application/pdf")
        invoke = next(item for item in State.requests if item[1].endswith("/accounting.non_electronic_invoices.create/invoke"))
        self.assertEqual(invoke[2]["mode"], "draft_with_confirmation")
        self.assertEqual(invoke[2]["input"]["uploadSessionId"], "session-1")
        headers = {key.lower(): value for key, value in invoke[3].items()}
        self.assertTrue(headers["x-reman-idempotency-key"].startswith("hermes-reman-"))
        ledger = "".join(path.read_text() for path in Path(self.temp.name, "reman-agentic-state").glob("*.json"))
        combined = output + ledger
        for forbidden in ("secret-agent-token", "never persist me", "INV-42", str(self.pdf), "%PDF-", "contentBase64"):
            self.assertNotIn(forbidden, combined)

    def test_pending_scan_returns_continuation_without_invoking_business_tool(self):
        State.upload_status = "pending_scan"
        result = json.loads(TOOLS.create_invoice(self.invoice_args()))
        self.assertEqual(result["result"], {"status": "pending_scan", "operationId": "invoice-42-v1", "retryAfterSeconds": 5})
        self.assertFalse(any(item[1].endswith("/accounting.non_electronic_invoices.create/invoke") for item in State.requests))

    def test_file_retry_reuses_session_upload_and_idempotency_state(self):
        State.upload_status = "pending_scan"
        first = json.loads(TOOLS.create_invoice(self.invoice_args()))
        self.assertEqual(first["result"]["status"], "pending_scan")
        State.upload_status = "ready"
        second = json.loads(TOOLS.create_invoice(self.invoice_args()))
        self.assertEqual(second["result"]["status"], "pending_confirmation")
        self.assertEqual(len([item for item in State.requests if item[1] == "/api/v1/agentic/uploads/sessions"]), 1)
        self.assertEqual(len([item for item in State.requests if item[1].endswith("/items")]), 1)
        self.assertEqual(len([item for item in State.requests if item[1].endswith("/accounting.non_electronic_invoices.create/invoke")]), 1)

    def test_quarantined_file_is_terminal(self):
        State.upload_status = "quarantined"
        result = json.loads(TOOLS.create_invoice(self.invoice_args()))
        self.assertEqual(result, {"error": "reman_upload_rejected", "retryable": False})
        self.assertFalse(any(item[1].endswith("/accounting.non_electronic_invoices.create/invoke") for item in State.requests))

    def test_pdf_root_boundary_rejects_outside_traversal_symlink_and_non_regular(self):
        path, content, _ = FILES.read_allowed_pdf(str(self.pdf), FILES.allowed_pdf_roots(), max_bytes=1024 * 1024)
        self.assertEqual(path, self.pdf.resolve())
        self.assertTrue(content.startswith(b"%PDF-"))
        outside = self.root / "outside.pdf"
        outside.write_bytes(b"%PDF-1.4\noutside\n")
        self.assert_file_error(str(outside), "reman_pdf_path_denied")
        self.assert_file_error(str(self.allowed / ".." / "outside.pdf"), "reman_pdf_path_denied")
        direct_link = self.allowed / "direct-link.pdf"
        direct_link.symlink_to(self.pdf)
        self.assert_file_error(str(direct_link), "reman_pdf_symlink_denied")
        outside_dir = self.root / "outside-dir"
        outside_dir.mkdir()
        (outside_dir / "escaped.pdf").write_bytes(b"%PDF-1.4\nescaped\n")
        escape_dir = self.allowed / "escape"
        escape_dir.symlink_to(outside_dir, target_is_directory=True)
        self.assert_file_error(str(escape_dir / "escaped.pdf"), "reman_pdf_symlink_denied")
        non_regular = self.allowed / "folder.pdf"
        non_regular.mkdir()
        self.assert_file_error(str(non_regular), "reman_pdf_not_regular")

    def test_pdf_change_between_validation_and_open_is_rejected(self):
        def replace(path):
            path.unlink()
            path.write_bytes(b"%PDF-1.4\nreplaced\n")

        self.assert_file_error(str(self.pdf), "reman_pdf_changed_during_read", before_open=replace)

    def test_policy_error_and_adversarial_payload_are_non_retryable_and_redacted(self):
        normal = json.loads(TOOLS.invoke_accounting_read({
            "tool_name": "accounting.documents.search", "input": {"companyId": 7, "types": ["invoice_in"]}
        }))
        self.assertEqual(normal, {"error": "agentic_disabled", "retryable": False, "status": 503})
        output = TOOLS.invoke_accounting_read({
            "tool_name": "accounting.documents.search",
            "input": {"companyId": 7, "types": ["invoice_in"], "adversarial": "error"},
        })
        self.assertEqual(json.loads(output), {"error": "reman_http_error", "retryable": False, "status": 500})
        for forbidden in ("/private/tmp", "secret-agent-token", "payload={", "requestId", "\n"):
            self.assertNotIn(forbidden, output)

    def test_only_transport_errors_are_retryable(self):
        self.assertFalse(CLIENT.RemanError("agentic_disabled").public()["retryable"])
        self.assertFalse(CLIENT.RemanError("reman_upload_rejected").public()["retryable"])
        self.assertTrue(CLIENT.RemanTransportError("reman_transport_timeout_or_unreachable").public()["retryable"])

    def test_redirects_are_denied_without_forwarding_token(self):
        for route in ("redirect-same", "redirect-cross"):
            client = CLIENT.RemanClient(base_url=State.base_url + "/" + route, token="redirect-secret")
            with self.assertRaises(CLIENT.RemanError) as raised:
                client.discover()
            self.assertEqual(raised.exception.code, "reman_redirect_denied")
        self.assertEqual(State.adversary_requests, [])

    def test_direct_and_model_controlled_mode_are_absent(self):
        with self.assertRaises(CLIENT.RemanError) as raised:
            CLIENT.RemanClient().invoke("accounting.payments.create", "direct", {}, "key")
        self.assertEqual(raised.exception.code, "reman_direct_mode_disabled")
        self.assertNotIn("mode", PLUGIN.schemas.PREPARE_ACCOUNTING_ACTION["parameters"]["properties"])
        self.assertNotIn("mode", PLUGIN.schemas.CREATE_INVOICE["parameters"]["properties"])

    def test_remote_plain_http_is_rejected(self):
        with self.assertRaises(CLIENT.RemanError) as raised:
            CLIENT.RemanClient(base_url="http://example.com", token="token")
        self.assertEqual(raised.exception.code, "reman_https_required")

    def test_plugin_registers_declared_tools_skill_and_file_gate(self):
        registered = []
        skills = []

        class Context:
            def register_tool(self, **definition):
                registered.append(definition)

            def register_skill(self, **definition):
                skills.append(definition)

        PLUGIN.register(Context())
        names = {item["name"] for item in registered}
        expected = {
            "reman_available_tools", "reman_accounting_tool_contract", "reman_accounting_read",
            "reman_accounting_prepare_action", "reman_accounting_list_companies",
            "reman_accounting_search_partners", "reman_accounting_search_non_electronic_invoices",
            "reman_accounting_create_non_electronic_invoice",
        }
        self.assertEqual(names, expected)
        file_tool = next(item for item in registered if item["name"] == "reman_accounting_create_non_electronic_invoice")
        self.assertTrue(file_tool["check_fn"]())
        os.environ.pop("REMAN_AGENT_ALLOWED_PDF_DIRS")
        self.assertFalse(file_tool["check_fn"]())
        self.assertEqual([item["name"] for item in skills], ["reman-accounting"])
        self.assertTrue(skills[0]["path"].is_file())


if __name__ == "__main__":
    unittest.main()
