"""Hermes registration entry point for the REman Agentic connector."""

import os
from pathlib import Path

from . import schemas, tools


def _configured():
    return bool(os.environ.get("REMAN_AGENT_BASE_URL", "").strip() and os.environ.get("REMAN_AGENT_TOKEN", "").strip())


def register(ctx):
    ctx.register_skill(
        name="reman-accounting",
        path=Path(__file__).resolve().parent / "skills" / "reman-accounting" / "SKILL.md",
        description="Governed read-only REman Accounting workflows.",
    )
    definitions = (
        (schemas.AVAILABLE_TOOLS, tools.available_tools, _configured, ["REMAN_AGENT_BASE_URL", "REMAN_AGENT_TOKEN"]),
        (schemas.INVOKE_ACCOUNTING_READ, tools.invoke_accounting_read, _configured, ["REMAN_AGENT_BASE_URL", "REMAN_AGENT_TOKEN"]),
        (schemas.LIST_COMPANIES, tools.list_companies, _configured, ["REMAN_AGENT_BASE_URL", "REMAN_AGENT_TOKEN"]),
        (schemas.SEARCH_PARTNERS, tools.search_partners, _configured, ["REMAN_AGENT_BASE_URL", "REMAN_AGENT_TOKEN"]),
        (schemas.SEARCH_INVOICES, tools.search_invoices, _configured, ["REMAN_AGENT_BASE_URL", "REMAN_AGENT_TOKEN"]),
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
