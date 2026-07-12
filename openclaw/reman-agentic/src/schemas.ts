import { Type } from "typebox";

const optionalShortText = Type.Optional(Type.String({ maxLength: 255 }));
const optionalDate = Type.Optional(Type.String({ pattern: "^\\d{4}-\\d{2}-\\d{2}$" }));
const optionalAmount = Type.Optional(Type.Number({ minimum: 0 }));

export const availableToolsSchema = Type.Object({}, { additionalProperties: false });

export const accountingReadSchema = Type.Object(
  {
    tool_name: Type.String({ pattern: "^accounting\\.[a-z0-9_.]+$" }),
    input: Type.Record(Type.String(), Type.Unknown(), { maxProperties: 32 }),
  },
  { additionalProperties: false },
);

export const listCompaniesSchema = Type.Object(
  {
    query: optionalShortText,
    limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 50, default: 25 })),
  },
  { additionalProperties: false },
);

export const searchPartnersSchema = Type.Object(
  {
    company_id: Type.Integer({ minimum: 1 }),
    query: optionalShortText,
    vat_number: Type.Optional(Type.String({ maxLength: 32 })),
    tax_code: Type.Optional(Type.String({ maxLength: 32 })),
    limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 25, default: 25 })),
  },
  { additionalProperties: false },
);

export const searchInvoicesSchema = Type.Object(
  {
    company_id: Type.Integer({ minimum: 1 }),
    query: optionalShortText,
    document_number: optionalShortText,
    partner_name: Type.Optional(Type.String({ maxLength: 180 })),
    date_from: optionalDate,
    date_to: optionalDate,
    limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 25, default: 25 })),
  },
  { additionalProperties: false },
);

export const createInvoiceSchema = Type.Object(
  {
    mode: Type.Optional(
      Type.Literal("draft_with_confirmation", { default: "draft_with_confirmation" }),
    ),
    company_id: Type.Integer({ minimum: 1 }),
    accounting_contact_id: Type.Optional(Type.Integer({ minimum: 1 })),
    partner_name: Type.Optional(Type.String({ maxLength: 180 })),
    partner_tax_code: Type.Optional(Type.String({ maxLength: 32 })),
    partner_vat_number: Type.Optional(Type.String({ maxLength: 32 })),
    document_number: Type.String({ minLength: 1, maxLength: 255 }),
    document_date: Type.String({ pattern: "^\\d{4}-\\d{2}-\\d{2}$" }),
    due_date: optionalDate,
    net_amount: Type.Number({ minimum: 0 }),
    vat_amount: Type.Number({ minimum: 0 }),
    gross_amount: Type.Number({ minimum: 0 }),
    withholding_amount: optionalAmount,
    description: optionalShortText,
    notes: Type.Optional(Type.String({ maxLength: 5000 })),
    pdf_paths: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 5 }),
    operation_id: Type.Optional(
      Type.String({
        minLength: 1,
        maxLength: 255,
        description: "Stable caller identifier for retries of this exact business operation.",
      }),
    ),
  },
  { additionalProperties: false },
);
