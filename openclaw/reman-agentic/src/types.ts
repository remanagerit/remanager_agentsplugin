export type JsonObject = Record<string, unknown>;

export type RemanPluginConfig = {
  baseUrl?: string;
  token?: unknown;
  timeoutSeconds?: number;
};

export type ToolDescriptor = {
  name?: string;
  supportedModes?: string[];
  filePolicy?: {
    maxFiles?: number;
    maxFileBytes?: number;
    maxTotalBytes?: number;
  };
};

export type AccountingReadInput = {
  tool_name: string;
  input: JsonObject;
};

export type InvoiceInput = {
  mode?: "draft_with_confirmation";
  company_id?: number;
  accounting_contact_id?: number;
  partner_name?: string;
  partner_tax_code?: string;
  partner_vat_number?: string;
  document_number?: string;
  document_date?: string;
  due_date?: string;
  net_amount?: number;
  vat_amount?: number;
  gross_amount?: number;
  withholding_amount?: number;
  description?: string;
  notes?: string;
  pdf_paths?: string[];
  operation_id?: string;
};
