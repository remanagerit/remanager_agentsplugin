"""Hermes registration entry point for the REman Agentic connector."""

import os
from pathlib import Path

from . import schemas, tools
from .file_access import has_configured_pdf_roots


def _configured():
    return bool(os.environ.get("REMAN_AGENT_TOKEN", "").strip())


def _configured_for_files():
    return _configured() and has_configured_pdf_roots()


def register(ctx):
    ctx.register_skill(
        name="reman-accounting",
        path=Path(__file__).resolve().parent / "skills" / "reman-accounting" / "SKILL.md",
        description="Governed REmanager Accounting read and user-confirmed action workflows.",
    )
    definitions = (
        (schemas.AVAILABLE_TOOLS, tools.available_tools, _configured, ["REMAN_AGENT_TOKEN"]),
        (schemas.ACCOUNTING_TOOL_CONTRACT, tools.tool_contract, _configured, ["REMAN_AGENT_TOKEN"]),
        (schemas.INVOKE_ACCOUNTING_READ, tools.invoke_accounting_read, _configured, ["REMAN_AGENT_TOKEN"]),
        (schemas.PREPARE_ACCOUNTING_ACTION, tools.prepare_accounting_action, _configured, ["REMAN_AGENT_TOKEN"]),
        (
            schemas.PREPARE_ACCOUNTING_FILE_ACTION,
            tools.prepare_accounting_file_action,
            _configured_for_files,
            ["REMAN_AGENT_TOKEN", "REMAN_AGENT_ALLOWED_PDF_DIRS"],
        ),
        (schemas.LIST_COMPANIES, tools.list_companies, _configured, ["REMAN_AGENT_TOKEN"]),
        (schemas.SEARCH_PARTNERS, tools.search_partners, _configured, ["REMAN_AGENT_TOKEN"]),
        (schemas.SEARCH_INVOICES, tools.search_invoices, _configured, ["REMAN_AGENT_TOKEN"]),
        (
            schemas.CREATE_INVOICE,
            tools.create_invoice,
            _configured_for_files,
            ["REMAN_AGENT_TOKEN", "REMAN_AGENT_ALLOWED_PDF_DIRS"],
        ),
    )
    for schema, handler, check_fn, required_env in definitions:
        ctx.register_tool(
            name=schema["name"],
            toolset="reman_agentic",
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=required_env,
            description=schema["description"],
        )
