"""Versioned model-facing catalog for the approved Accounting Agentic surface."""


def _contract(mode, required, optional=(), notes=None):
    result = {
        "mode": mode,
        "required": list(required),
        "optional": list(optional),
        "inputStyle": "camelCase",
    }
    if notes:
        result["notes"] = notes
    return result


READ_CONTRACTS = {
    "accounting.accounts.get": _contract("read", ("companyId", "accountId")),
    "accounting.accounts.search": _contract("read", ("companyId",), ("accountType", "query", "limit", "cursor"), "accountType: bank|cash|card|wallet|other"),
    "accounting.attachments.create_download_url": _contract(
        "read",
        ("companyId", "targetType", "targetId", "attachmentId"),
        ("ttlSeconds",),
        "Returns a short-lived, bounded-use HTTPS URL after resource and capability checks; never attach the agent token to that URL",
    ),
    "accounting.attachments.get": _contract("read", ("companyId", "targetType", "targetId", "attachmentId")),
    "accounting.attachments.search": _contract("read", ("companyId", "targetType", "targetId"), ("limit", "cursor")),
    "accounting.companies.list": _contract("read", (), ("query", "limit")),
    "accounting.contact_people.get": _contract("read", ("companyId", "contactPersonId")),
    "accounting.contact_people.search": _contract("read", ("companyId",), ("partnerId", "query", "limit", "cursor")),
    "accounting.credit_note_applications.get": _contract("read", ("companyId", "applicationId")),
    "accounting.credit_note_applications.search": _contract("read", ("companyId",), ("creditNoteId", "invoiceId", "limit", "cursor")),
    "accounting.delivery_note_lines.search": _contract("read", ("companyId", "deliveryNoteId"), ("limit", "cursor")),
    "accounting.delivery_notes.get": _contract("read", ("companyId", "deliveryNoteId")),
    "accounting.delivery_notes.search": _contract("read", ("companyId",), ("query", "limit", "cursor")),
    "accounting.document_due_dates.get": _contract("read", ("companyId", "dueDateId")),
    "accounting.document_due_dates.search": _contract("read", ("companyId",), ("documentId", "limit", "cursor")),
    "accounting.documents.create_access_urls": _contract(
        "read",
        ("companyId", "documentId"),
        ("ttlSeconds",),
        "Returns a single-use view URL and, when available, a distinct single-use original-file URL. Default and maximum TTL are 10800 seconds. XML invoice views use AssoSoftware HTML, PDF views are inline, and documents without a primary attachment use printable HTML. Consume capability URLs without the agent token, cookies, custom authorization headers or redirects",
    ),
    "accounting.documents.get": _contract("read", ("companyId", "documentId")),
    "accounting.documents.search": _contract("read", ("companyId", "types"), ("query", "limit", "cursor"), "types: 1..6 values among invoice_in, invoice_out, invoice_non_electronic_in, invoice_notice_in, credit_note, other_expense"),
    "accounting.insurance_policies.get": _contract("read", ("companyId", "policyId")),
    "accounting.insurance_policies.search": _contract("read", ("companyId",), ("limit", "cursor")),
    "accounting.loan_installments.get": _contract("read", ("companyId", "installmentId")),
    "accounting.loan_installments.search": _contract("read", ("companyId",), ("loanId", "status", "limit", "cursor"), "status: open|paid|cancelled"),
    "accounting.loans.get": _contract("read", ("companyId", "loanId")),
    "accounting.loans.search": _contract("read", ("companyId",), ("limit", "cursor")),
    "accounting.non_electronic_invoices.search": _contract("read", ("companyId",), ("query", "documentNumber", "partnerName", "dateFrom", "dateTo", "limit")),
    "accounting.partners.get": _contract("read", ("companyId", "partnerId")),
    "accounting.partners.search": _contract("read", ("companyId",), ("query", "vatNumber", "taxCode", "limit")),
    "accounting.payment_components.get": _contract("read", ("companyId", "componentImportId")),
    "accounting.payment_components.search": _contract("read", ("companyId",), ("paymentId", "status", "limit", "cursor"), "status: uploaded|parsed|applied|error"),
    "accounting.payment_links.search": _contract("read", ("companyId",), ("paymentId", "documentId", "limit", "cursor")),
    "accounting.payments.get": _contract("read", ("companyId", "paymentId")),
    "accounting.payments.search": _contract("read", ("companyId",), ("direction", "query", "limit", "cursor"), "direction: in|out"),
    "accounting.summary.read": _contract("read", ("companyId", "dateFrom", "dateTo")),
    "accounting.tax_commitments.get": _contract("read", ("companyId", "commitmentId")),
    "accounting.tax_commitments.search": _contract("read", ("companyId",), ("limit", "cursor")),
    "accounting.tax_installments.get": _contract("read", ("companyId", "installmentId")),
    "accounting.tax_installments.search": _contract("read", ("companyId",), ("commitmentId", "limit", "cursor")),
}


PARTNER_FIELDS = ("kind", "name", "vatNumber", "taxCode", "email", "pecEmail", "sdiCode", "addressLine", "postalCode", "city", "province", "referencePersonName")
DOCUMENT_FIELDS = ("documentNumber", "documentDate", "dueDate", "netAmount", "vatAmount", "grossAmount", "withholdingAmount", "originalCurrency", "originalNetAmount", "originalVatAmount", "originalGrossAmount", "fxRateToEur", "fxRateDate", "fxRateSource", "fxConversionNote", "accountingContactId", "partnerName", "partnerTaxCode", "partnerVatNumber", "description", "notes", "status", "paymentDirection")
PAYMENT_FIELDS = ("accountingEntryId", "accountingContactId", "accountId", "direction", "paymentDate", "amount", "excludeFromAccountBalance", "isAccountingCost", "costCategory", "costCompetenceMode", "costCompetenceFiscalYear", "costCompetenceStartDate", "costCompetenceEndDate", "costCompetenceAllocations", "description", "referenceNumber", "notes")
TAX_INSTALLMENT_FIELDS = ("installmentNo", "dueDate", "amount", "paidAmount", "paymentDate", "paymentMethod", "paymentNoticeCode", "creditorTaxCode", "status", "notes")
LOAN_INSTALLMENT_FIELDS = ("installmentNo", "dueDate", "principalAmount", "interestAmount", "amount", "paidAmount", "paymentDate", "status", "notes")
INSURANCE_FIELDS = ("object", "policyNumber", "insurerName", "agencyName", "agencyIban", "effectiveDate", "expiryDate", "premiumAmount", "premiumFrequency", "status", "notes")


DRAFT_CONTRACTS = {
    "accounting.partners.create": _contract("draft_with_confirmation", ("companyId", "kind", "name"), PARTNER_FIELDS[2:], "kind: own_company|customer|supplier|generic"),
    "accounting.partners.update": _contract("draft_with_confirmation", ("companyId", "partnerId"), PARTNER_FIELDS),
    "accounting.contact_people.create": _contract("draft_with_confirmation", ("companyId", "accountingContactId", "name"), ("phone", "email")),
    "accounting.contact_people.update": _contract("draft_with_confirmation", ("companyId", "contactPersonId"), ("name", "phone", "email")),
    "accounting.accounts.create": _contract("draft_with_confirmation", ("companyId", "accountType", "description", "initialBalance"), ("coordinates",), "accountType: bank|cash|card|wallet|other"),
    "accounting.accounts.update": _contract("draft_with_confirmation", ("companyId", "accountId"), ("accountType", "description", "coordinates", "initialBalance")),
    "accounting.documents.create": _contract(
        "draft_with_confirmation",
        ("companyId", "type"),
        ("projectId", "crmContactId") + DOCUMENT_FIELDS + ("dueDates", "paymentAllocations"),
        "type: invoice_in|invoice_out|invoice_notice_in|invoice_non_electronic_in|other_expense|credit_note|debit_note|other; dueDates: 1..12 structured rows; paymentAllocations: 1..20 existing paymentId/allocatedAmount rows; residual and status are derived server-side",
    ),
    "accounting.documents.create_with_attachments": {
        "mode": "draft_with_confirmation",
        "connectorTool": "reman_accounting_prepare_file_action",
        "inputStyle": "camelCase",
        "required": ["companyId", "type", "pdf_paths", "operation_id"],
        "optional": list(("projectId", "crmContactId") + DOCUMENT_FIELDS + ("dueDates", "paymentAllocations")),
        "notes": "Use tool_name accounting.documents.create_with_attachments; pdf_paths must contain 1..5 regular PDFs below configured roots; supports other_expense and other document types; the agent cannot approve",
    },
    "accounting.documents.update": _contract("draft_with_confirmation", ("companyId", "entryId"), DOCUMENT_FIELDS),
    "accounting.documents.duplicate": _contract("draft_with_confirmation", ("companyId", "entryId")),
    "accounting.documents.mark_paid": _contract("draft_with_confirmation", ("companyId", "entryId"), ("excludeFromAccountBalance",)),
    "accounting.documents.unmark_paid": _contract("draft_with_confirmation", ("companyId", "entryId")),
    "accounting.documents.mark_seen": _contract("draft_with_confirmation", ("companyId", "entryId")),
    "accounting.documents.mark_unseen": _contract("draft_with_confirmation", ("companyId", "entryId")),
    "accounting.document_due_dates.create": _contract("draft_with_confirmation", ("companyId", "entryId", "dueDate"), ("amount", "paymentMethod", "verificationStatus", "markedToPay", "notes")),
    "accounting.document_due_dates.update": _contract("draft_with_confirmation", ("companyId", "dueDateId"), ("dueDate", "amount", "paymentMethod", "verificationStatus", "markedToPay", "notes")),
    "accounting.document_due_dates.mark_paid": _contract("draft_with_confirmation", ("companyId", "dueDateId"), ("excludeFromAccountBalance",)),
    "accounting.document_due_dates.unmark_paid": _contract("draft_with_confirmation", ("companyId", "dueDateId")),
    "accounting.credit_note_applications.apply": _contract("draft_with_confirmation", ("companyId", "creditNoteEntryId", "invoiceEntryId", "appliedGrossAmount"), ("appliedNetAmount", "notes")),
    "accounting.credit_note_applications.unapply": _contract("draft_with_confirmation", ("companyId", "creditNoteEntryId", "invoiceEntryId")),
    "accounting.document_competence.update": _contract("draft_with_confirmation", ("companyId", "entryId", "mode"), ("fiscalYear", "competenceStartDate", "competenceEndDate", "allocations"), "mode: fiscal_year|date_range|split; allocations: 1..24 objects with netAmount and optional fiscalYear/date range/notes"),
    "accounting.document_precursor_links.apply": _contract("draft_with_confirmation", ("companyId", "precursorEntryId", "invoiceEntryId")),
    "accounting.document_precursor_links.unapply": _contract("draft_with_confirmation", ("companyId", "precursorEntryId", "invoiceEntryId")),
    "accounting.delivery_notes.create": _contract("draft_with_confirmation", ("companyId", "documentDate", "documentNumber", "recipientName", "lines"), ("accountingContactId", "numberingSeries", "status", "senderName", "senderVatNumber", "senderTaxCode", "senderAddressLine", "senderPostalCode", "senderCity", "senderProvince", "recipientVatNumber", "recipientTaxCode", "recipientAddressLine", "recipientPostalCode", "recipientCity", "recipientProvince", "destinationAddressLine", "destinationPostalCode", "destinationCity", "destinationProvince", "transportReason", "carrierName", "notes"), "lines: 1..200 objects with description, quantity and optional unitOfMeasure"),
    "accounting.delivery_notes.mark_seen": _contract("draft_with_confirmation", ("companyId", "deliveryNoteId")),
    "accounting.delivery_notes.mark_unseen": _contract("draft_with_confirmation", ("companyId", "deliveryNoteId")),
    "accounting.payments.create": _contract("draft_with_confirmation", ("companyId", "direction", "paymentDate", "amount"), tuple(field for field in PAYMENT_FIELDS if field not in {"direction", "paymentDate", "amount"}), "direction: in|out"),
    "accounting.payments.update": _contract("draft_with_confirmation", ("companyId", "paymentId"), PAYMENT_FIELDS),
    "accounting.payments.duplicate": _contract("draft_with_confirmation", ("companyId", "paymentId")),
    "accounting.payments.split_components": _contract("draft_with_confirmation", ("companyId", "paymentId", "components"), (), "components: 1..200 objects with amount and optional accountingEntryId, accountingContactId, description, referenceNumber, notes"),
    "accounting.payments.mark_seen": _contract("draft_with_confirmation", ("companyId", "paymentId")),
    "accounting.payments.mark_unseen": _contract("draft_with_confirmation", ("companyId", "paymentId")),
    "accounting.bank_movements.import": _contract(
        "draft_with_confirmation",
        ("companyId", "movements"),
        ("sourceRunId",),
        "movements: 1..200 structured bank movements; provider is fixed server-side; no raw provider payload, credentials, OCR or AI reconciliation",
    ),
    "accounting.payment_links.create": _contract("draft_with_confirmation", ("companyId", "paymentId", "entryId", "allocatedAmount")),
    "accounting.payment_links.remove": _contract("draft_with_confirmation", ("companyId", "paymentId", "entryId")),
    "accounting.tax_commitments.create": _contract("draft_with_confirmation", ("companyId", "title", "commitmentType", "totalAmount", "installmentCount"), ("taxCode", "compensable", "status", "notes", "dueDates"), "commitmentType: f24|f23|pagopa|bollettino|avviso_bonario|cartella|other; dueDates creates the bounded installment schedule atomically"),
    "accounting.tax_commitments.update": _contract("draft_with_confirmation", ("companyId", "taxCommitmentId"), ("title", "taxCode", "commitmentType", "totalAmount", "installmentCount", "compensable", "status", "notes")),
    "accounting.tax_installments.create": _contract("draft_with_confirmation", ("companyId", "taxCommitmentId", "installmentNo", "dueDate", "amount"), TAX_INSTALLMENT_FIELDS[3:]),
    "accounting.tax_installments.update": _contract("draft_with_confirmation", ("companyId", "taxInstallmentId"), TAX_INSTALLMENT_FIELDS),
    "accounting.tax_installments.mark_paid": _contract("draft_with_confirmation", ("companyId", "taxInstallmentId", "paymentDate"), ("paidAmount", "paymentMethod")),
    "accounting.tax_installments.unmark_paid": _contract("draft_with_confirmation", ("companyId", "taxInstallmentId")),
    "accounting.loans.create": _contract("draft_with_confirmation", ("companyId", "accountId", "name", "lenderName"), ("principalAmount", "startDate", "endDate", "status", "notes", "installments"), "installments: up to 240 objects using loan installment fields"),
    "accounting.loans.update": _contract("draft_with_confirmation", ("companyId", "loanId"), ("accountId", "name", "lenderName", "principalAmount", "startDate", "endDate", "notes")),
    "accounting.loans.status": _contract("draft_with_confirmation", ("companyId", "loanId", "status"), (), "status: active|closed|cancelled|archived"),
    "accounting.loan_installments.create": _contract("draft_with_confirmation", ("companyId", "loanId", "installmentNo", "dueDate", "amount"), tuple(field for field in LOAN_INSTALLMENT_FIELDS if field not in {"installmentNo", "dueDate", "amount"})),
    "accounting.loan_installments.update": _contract("draft_with_confirmation", ("companyId", "loanInstallmentId"), LOAN_INSTALLMENT_FIELDS),
    "accounting.loan_installments.status": _contract("draft_with_confirmation", ("companyId", "loanInstallmentId", "status"), ("paidAmount", "paymentDate"), "status: open|paid|cancelled"),
    "accounting.insurance_policies.create": _contract("draft_with_confirmation", ("companyId", "object", "policyNumber", "insurerName", "effectiveDate", "expiryDate", "premiumAmount", "premiumFrequency"), ("agencyName", "agencyIban", "status", "notes")),
    "accounting.insurance_policies.update": _contract("draft_with_confirmation", ("companyId", "policyId"), INSURANCE_FIELDS),
    "accounting.insurance_policies.status": _contract("draft_with_confirmation", ("companyId", "policyId", "status"), (), "status: active|expired|cancelled|archived"),
    "accounting.insurance_policies.renew": _contract("draft_with_confirmation", ("companyId", "policyId", "policyNumber", "effectiveDate", "expiryDate", "premiumAmount"), ("premiumFrequency",)),
    "accounting.non_electronic_invoices.create": {
        "mode": "draft_with_confirmation",
        "connectorTool": "reman_accounting_create_non_electronic_invoice",
        "inputStyle": "snake_case",
        "required": ["company_id", "document_number", "document_date", "net_amount", "vat_amount", "gross_amount", "pdf_paths", "operation_id"],
        "optional": ["accounting_contact_id", "partner_name", "partner_tax_code", "partner_vat_number", "due_date", "due_dates", "payment_allocations", "withholding_amount", "original_currency", "original_net_amount", "original_vat_amount", "original_gross_amount", "fx_rate_to_eur", "fx_rate_date", "fx_rate_source", "fx_conversion_note", "description", "notes"],
        "notes": "pdf_paths must contain 1..5 regular PDF files below configured allowlisted roots; the agent cannot approve the resulting action",
    },
    "accounting.attachments.add": {
        "mode": "draft_with_confirmation",
        "connectorTool": "reman_accounting_prepare_file_action",
        "inputStyle": "camelCase",
        "required": ["companyId", "targetType", "targetId", "pdf_paths", "operation_id"],
        "optional": ["description"],
        "notes": "Use tool_name accounting.attachments.add; targetType: document|payment|delivery_note|tax_commitment|tax_installment|loan|loan_installment|insurance_policy; attaches 1..5 clean PDFs after user confirmation",
    },
}


TOOL_CONTRACTS = {**READ_CONTRACTS, **DRAFT_CONTRACTS}


def contract_for(tool_name):
    contract = TOOL_CONTRACTS.get(tool_name)
    return {"toolName": tool_name, **contract} if contract else None
