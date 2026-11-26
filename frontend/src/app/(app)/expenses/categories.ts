import type { ExpenseCategory } from "@/lib/api/types";

export const EXPENSE_CATEGORIES: Record<ExpenseCategory, string> = {
  rent: "Rent",
  utilities: "Utilities",
  transport: "Transport",
  office: "Office supplies",
  professional_fees: "Professional fees",
  communication: "Phone and internet",
  maintenance: "Repairs and maintenance",
  bank_charges: "Bank charges",
  other: "Other",
};
