"""Schemas exposed to the Hermes model."""

AVAILABLE_TOOLS = {
    "name": "reman_available_tools",
    "description": (
        "List only the REman tools and execution modes currently granted to this connected agent. "
        "For Accounting workflows, first load the plugin skill reman-agentic:reman-accounting when skill_view is available."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

INVOKE_ACCOUNTING_READ = {
    "name": "reman_accounting_read",
    "description": (
        "Invoke one exact read-only accounting.* tool returned by reman_available_tools. "
        "Use the camelCase input contract documented in the reman-accounting skill."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "pattern": "^accounting\\.[a-z0-9_.]+$",
                "description": "Exact Accounting tool name returned by discovery.",
            },
            "input": {
                "type": "object",
                "maxProperties": 32,
                "additionalProperties": True,
                "description": "Business input only; never include user, team, agent, mode, or execution context.",
            },
        },
        "required": ["tool_name", "input"],
        "additionalProperties": False,
    },
}

LIST_COMPANIES = {
    "name": "reman_accounting_list_companies",
    "description": "List Accounting companies currently accessible to the delegated REman user and granted to this agent.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Optional company name filter."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 25},
        },
        "additionalProperties": False,
    },
}

SEARCH_PARTNERS = {
    "name": "reman_accounting_search_partners",
    "description": "Search suppliers or other Accounting contacts in one granted REman company before registering an invoice.",
    "parameters": {
        "type": "object",
        "properties": {
            "company_id": {"type": "integer", "minimum": 1},
            "query": {"type": "string"},
            "vat_number": {"type": "string"},
            "tax_code": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 25},
        },
        "required": ["company_id"],
        "additionalProperties": False,
    },
}

SEARCH_INVOICES = {
    "name": "reman_accounting_search_non_electronic_invoices",
    "description": "Search existing non-electronic incoming invoices in one granted REman company, including duplicate checks.",
    "parameters": {
        "type": "object",
        "properties": {
            "company_id": {"type": "integer", "minimum": 1},
            "query": {"type": "string"},
            "document_number": {"type": "string"},
            "partner_name": {"type": "string"},
            "date_from": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "date_to": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 25},
        },
        "required": ["company_id"],
        "additionalProperties": False,
    },
}

CREATE_INVOICE = {
    "name": "reman_accounting_create_non_electronic_invoice",
    "description": (
        "Register a non-electronic incoming invoice in REman with one to five local PDF attachments. "
        "The current security rollout permits draft_with_confirmation only. "
        "A draft can only be approved by the user in REman; this tool never approves it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["draft_with_confirmation"], "default": "draft_with_confirmation"},
            "company_id": {"type": "integer", "minimum": 1},
            "accounting_contact_id": {"type": "integer", "minimum": 1},
            "partner_name": {"type": "string"},
            "partner_tax_code": {"type": "string"},
            "partner_vat_number": {"type": "string"},
            "document_number": {"type": "string"},
            "document_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "due_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "net_amount": {"type": "number", "minimum": 0},
            "vat_amount": {"type": "number", "minimum": 0},
            "gross_amount": {"type": "number", "minimum": 0},
            "withholding_amount": {"type": "number", "minimum": 0},
            "description": {"type": "string"},
            "notes": {"type": "string"},
            "pdf_paths": {"type": "array", "minItems": 1, "maxItems": 5, "items": {"type": "string"}},
            "operation_id": {"type": "string", "description": "Optional stable caller identifier for this business operation."},
        },
        "required": ["company_id", "document_number", "document_date", "net_amount", "vat_amount", "gross_amount", "pdf_paths"],
        "additionalProperties": False,
    },
}
