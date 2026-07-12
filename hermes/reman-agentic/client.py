"""Small stdlib-only client for the governed REman Agentic REST surface."""

import base64
import http.client
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request


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

    def _request(self, method, path, payload=None, idempotency_key=None):
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "User-Agent": "Hermes-REman-Agentic/1.0",
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
                raise RemanError(failure.get("error", "reman_http_error"), error.code, failure.get("requestId")) from None
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
            {**item, "supportedModes": [mode for mode in item.get("supportedModes", []) if mode != "direct"]}
            for item in discovery.get("items", [])
            if isinstance(item, dict)
        ]
        return sanitized

    def require_tool(self, tool_name, mode):
        discovery = self.discover()
        tool = next((item for item in discovery.get("items", []) if item.get("name") == tool_name), None)
        if not tool:
            raise RemanError("reman_tool_not_granted_or_unavailable")
        if mode not in tool.get("supportedModes", []):
            raise RemanError("reman_tool_mode_not_granted")
        return tool

    def invoke(self, tool_name, mode, input_data, idempotency_key=None):
        self.require_tool(tool_name, mode)
        return self._request(
            "POST",
            "/api/v1/agentic/tools/{}/invoke".format(urllib.parse.quote(tool_name, safe="")),
            {"mode": mode, "input": input_data},
            idempotency_key,
        )

    def create_upload_session(self, tool_name):
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
