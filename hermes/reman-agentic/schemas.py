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
                "maxProperties": 64,
                "additionalProperties": True,
                "description": "Business input only; never include user, team, agent, mode, or execution context.",
            },
        },
        "required": ["tool_name", "input"],
        "additionalProperties": False,
    },
}

ACCOUNTING_TOOL_CONTRACT = {
    "name": "reman_accounting_tool_contract",
    "description": (
        "Return the versioned business input contract for one granted Accounting tool. "
        "Call this before invoking a tool when its required or optional fields are not already known."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "pattern": "^accounting\\.[a-z0-9_.]+$",
                "description": "Exact tool name returned by reman_available_tools.",
            },
        },
        "required": ["tool_name"],
        "additionalProperties": False,
    },
}

PREPARE_ACCOUNTING_ACTION = {
    "name": "reman_accounting_prepare_action",
    "description": (
        "Prepare one granted Accounting action for mandatory confirmation by the delegated user in REmanager. "
        "This tool always uses draft_with_confirmation and can never approve or execute direct actions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "pattern": "^accounting\\.[a-z0-9_.]+$",
                "description": "Exact draft_with_confirmation Accounting tool returned by discovery, excluding the dedicated file tool.",
            },
            "input": {
                "type": "object",
                "maxProperties": 64,
                "additionalProperties": True,
                "description": "CamelCase business input only; never include identity, team, agent, grant, scope, or mode fields.",
            },
            "operation_id": {
                "type": "string",
                "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
                "description": "Stable unique identifier for this intended business action; reuse it only for an equivalent retry.",
            },
        },
        "required": ["tool_name", "input", "operation_id"],
        "additionalProperties": False,
    },
}

PREPARE_ACCOUNTING_FILE_ACTION = {
    "name": "reman_accounting_prepare_file_action",
    "description": (
        "Upload one to five allowlisted local PDFs and prepare a granted Accounting file action for mandatory "
        "confirmation in REmanager. Supports generic document creation and adding attachments to an existing resource. "
        "The tool waits for malware scanning and never approves the action."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "enum": [
                    "accounting.documents.create_with_attachments",
                    "accounting.attachments.add",
                    "accounting.non_electronic_invoices.create",
                ],
                "description": "Exact file action returned by reman_available_tools.",
            },
            "input": {
                "type": "object",
                "maxProperties": 64,
                "additionalProperties": True,
                "description": "CamelCase business input only. Do not include uploadSessionId or any execution context.",
            },
            "pdf_paths": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {"type": "string"},
                "description": "Absolute PDF paths below REMAN_AGENT_ALLOWED_PDF_DIRS; symlinks and traversal are denied.",
            },
            "operation_id": {
                "type": "string",
                "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
                "description": "Stable unique identifier; reuse only for an equivalent retry.",
            },
        },
        "required": ["tool_name", "input", "pdf_paths", "operation_id"],
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
        "Upload one to five allowlisted local PDFs and prepare a non-electronic incoming invoice for mandatory "
        "confirmation by the delegated user in REmanager. The tool waits for REman malware scanning and never approves the action."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "company_id": {"type": "integer", "minimum": 1},
            "accounting_contact_id": {"type": "integer", "minimum": 1},
            "partner_name": {"type": "string", "maxLength": 180},
            "partner_tax_code": {"type": "string", "maxLength": 32},
            "partner_vat_number": {"type": "string", "maxLength": 32},
            "document_number": {"type": "string", "minLength": 1, "maxLength": 255},
            "document_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "due_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "due_dates": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "properties": {
                        "dueDate": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "amount": {"type": "number", "minimum": 0},
                        "paymentMethod": {"type": "string", "maxLength": 80},
                        "verificationStatus": {"type": "string", "enum": ["stand_by", "verified"]},
                        "markedToPay": {"type": "boolean"},
                        "notes": {"type": "string", "maxLength": 255},
                    },
                    "required": ["dueDate"],
                    "additionalProperties": False,
                },
            },
            "payment_allocations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "paymentId": {"type": "integer", "minimum": 1},
                        "allocatedAmount": {"type": "number", "exclusiveMinimum": 0},
                    },
                    "required": ["paymentId", "allocatedAmount"],
                    "additionalProperties": False,
                },
            },
            "net_amount": {"type": "number", "minimum": 0},
            "vat_amount": {"type": "number", "minimum": 0},
            "gross_amount": {"type": "number", "minimum": 0},
            "withholding_amount": {"type": "number", "minimum": 0},
            "original_currency": {
                "type": "string", "minLength": 3, "maxLength": 8,
                "description": "ISO currency printed on a non-EUR document; REmanager derives the EUR accounting amounts.",
            },
            "original_net_amount": {
                "type": "number", "minimum": 0,
                "description": "Net amount printed on the document in original_currency.",
            },
            "original_vat_amount": {
                "type": "number", "minimum": 0,
                "description": "VAT or tax amount printed on the document in original_currency.",
            },
            "original_gross_amount": {
                "type": "number", "minimum": 0,
                "description": "Gross total printed on the document in original_currency.",
            },
            "fx_rate_to_eur": {"type": "number", "exclusiveMinimum": 0},
            "fx_rate_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "fx_rate_source": {"type": "string", "maxLength": 64},
            "fx_conversion_note": {"type": "string", "maxLength": 255},
            "description": {"type": "string", "maxLength": 255},
            "notes": {"type": "string", "maxLength": 5000},
            "pdf_paths": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {"type": "string"},
                "description": "Absolute PDF paths below REMAN_AGENT_ALLOWED_PDF_DIRS; symlinks and traversal are denied.",
            },
            "operation_id": {
                "type": "string",
                "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
                "description": "Stable unique identifier; reuse only for an equivalent retry.",
            },
        },
        "required": [
            "company_id", "document_number", "document_date", "net_amount", "vat_amount",
            "gross_amount", "pdf_paths", "operation_id"
        ],
        "additionalProperties": False,
    },
}
