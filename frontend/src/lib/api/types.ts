/**
 * TypeScript shapes of the Django API's JSON. Keep in sync with the DRF
 * serializers in backend/ (accounts, companies, accounting, tax_engine).
 *
 * Money and rates are `Money` strings like "1180.00" — never numbers — so
 * JavaScript can't introduce floating-point rounding errors.
 */

export type Money = string;
export type Rate = string; // fraction, e.g. "0.1800"
export type ISODate = string; // "2026-03-10"
export type UUID = string;

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

// --- accounts ---------------------------------------------------------------

export type User = {
  id: UUID;
  email: string;
  full_name: string;
  created_at: string;
};

export type Tokens = { access: string; refresh: string };
export type RegisterResponse = Tokens & { user: User };

// --- companies --------------------------------------------------------------

export type Role = "owner" | "accountant" | "viewer";
export type BusinessType =
  "sole_proprietor" | "limited_company" | "partnership" | "cooperative" | "ngo" | "other";
export type TaxRegime = "real" | "lump_sum" | "flat";
export type FilingFrequency = "monthly" | "quarterly";

export type TaxProfile = {
  id: UUID;
  tax_regime: TaxRegime;
  vat_registered: boolean;
  filing_frequency: FilingFrequency;
  effective_from: ISODate;
  created_at: string;
};

export type Company = {
  id: UUID;
  legal_name: string;
  tin: string;
  business_type: BusinessType;
  industry: string;
  my_role: Role;
  current_tax_profile: TaxProfile | null;
  created_at: string;
};

export type NewCompany = {
  legal_name: string;
  tin: string;
  business_type: BusinessType;
  industry: string;
  tax_profile: Omit<TaxProfile, "id" | "created_at">;
};

// --- accounting -------------------------------------------------------------

export type TaxTreatment = "standard" | "zero_rated" | "exempt" | "non_taxable";

export type Party = {
  id: UUID;
  name: string;
  tin: string;
  email: string;
  phone: string;
  address: string;
  created_at: string;
};
export type Customer = Party;
export type Supplier = Party & { vat_registered: boolean };

export type InvoiceStatus = "draft" | "issued" | "cancelled";
export type PaymentStatus = "unpaid" | "partially_paid" | "paid";

export type InvoiceItem = {
  id: UUID;
  description: string;
  quantity: string;
  unit_price: Money;
  tax_treatment: TaxTreatment;
  // computed by the server
  line_subtotal: Money;
  vat_rate: Rate;
  vat_amount: Money;
  line_total: Money;
  rule_version: string | null;
};

export type Invoice = {
  id: UUID;
  invoice_number: string;
  customer: UUID;
  customer_name: string;
  issue_date: ISODate;
  due_date: ISODate | null;
  status: InvoiceStatus;
  ebm_receipt_number: string | null;
  notes: string;
  items: InvoiceItem[];
  subtotal: Money;
  vat_amount: Money;
  total_amount: Money;
  amount_paid: Money;
  balance_due: Money;
  payment_status: PaymentStatus;
  created_at: string;
  updated_at: string;
};

/** What the client sends: inputs only. The server computes every total. */
export type NewInvoice = {
  invoice_number: string;
  customer: UUID;
  issue_date: ISODate;
  due_date: ISODate | null;
  notes: string;
  items: Pick<InvoiceItem, "description" | "quantity" | "unit_price" | "tax_treatment">[];
};

export type ExpenseCategory =
  | "rent"
  | "utilities"
  | "transport"
  | "office"
  | "professional_fees"
  | "communication"
  | "maintenance"
  | "bank_charges"
  | "other";

export type Expense = {
  id: UUID;
  expense_date: ISODate;
  category: ExpenseCategory;
  description: string;
  supplier: UUID | null;
  supplier_name: string | null;
  ebm_receipt_number: string | null;
  tax_treatment: TaxTreatment;
  amount_excl_vat: Money;
  // computed by the server
  vat_rate: Rate;
  vat_amount: Money;
  total_amount: Money;
  rule_version: string | null;
  created_at: string;
};

export type NewExpense = Pick<
  Expense,
  | "expense_date"
  | "category"
  | "description"
  | "supplier"
  | "ebm_receipt_number"
  | "tax_treatment"
  | "amount_excl_vat"
>;

// --- tax_engine -------------------------------------------------------------

export type Totals = { net: Money; vat: Money; count: number };
export type ByTreatment = Record<TaxTreatment, Totals>;

export type VatWarningCode =
  | "draft_invoices_excluded"
  | "sales_missing_ebm_receipt"
  | "input_vat_missing_ebm_receipt"
  | "input_vat_not_registered"
  | "unverified_tax_rules";

export type VatSummary = {
  company_id: UUID;
  period_start: ISODate;
  period_end: ISODate;
  output_vat: Money;
  input_vat: Money;
  input_vat_not_claimable: Money;
  net_vat: Money;
  net_payable: Money;
  credit: Money;
  output_by_treatment: ByTreatment;
  purchases_by_treatment: ByTreatment;
  expenses_by_treatment: ByTreatment;
  rule_versions: string[];
  warnings: { code: VatWarningCode; message: string; count: number }[];
};
