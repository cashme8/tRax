/**
 * Typed functions for each API endpoint the frontend uses.
 * Company-scoped calls take the company id first; it becomes the X-Company-ID header.
 */

import { apiRequest } from "@/lib/api/client";
import type {
  Company,
  Customer,
  Expense,
  Invoice,
  NewCompany,
  NewExpense,
  NewInvoice,
  Paginated,
  RegisterResponse,
  Supplier,
  Tokens,
  User,
  VatSummary,
} from "@/lib/api/types";

export const authApi = {
  login: (email: string, password: string) =>
    apiRequest<Tokens>("/api/auth/login/", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  register: (data: { email: string; full_name: string; password: string }) =>
    apiRequest<RegisterResponse>("/api/auth/register/", {
      method: "POST",
      body: data,
      auth: false,
    }),
  me: () => apiRequest<User>("/api/auth/me/"),
};

export const companiesApi = {
  list: () => apiRequest<Paginated<Company>>("/api/companies/"),
  create: (data: NewCompany) =>
    apiRequest<Company>("/api/companies/", { method: "POST", body: data }),
};

export const customersApi = {
  list: (companyId: string) => apiRequest<Paginated<Customer>>("/api/customers/", { companyId }),
  create: (companyId: string, data: { name: string; tin?: string }) =>
    apiRequest<Customer>("/api/customers/", { method: "POST", body: data, companyId }),
};

export const suppliersApi = {
  list: (companyId: string) => apiRequest<Paginated<Supplier>>("/api/suppliers/", { companyId }),
};

export const invoicesApi = {
  list: (companyId: string, status?: string) =>
    apiRequest<Paginated<Invoice>>("/api/invoices/", { query: { status }, companyId }),
  create: (companyId: string, data: NewInvoice) =>
    apiRequest<Invoice>("/api/invoices/", { method: "POST", body: data, companyId }),
  issue: (companyId: string, id: string) =>
    apiRequest<Invoice>(`/api/invoices/${id}/issue/`, { method: "POST", companyId }),
};

export const expensesApi = {
  list: (companyId: string) => apiRequest<Paginated<Expense>>("/api/expenses/", { companyId }),
  create: (companyId: string, data: NewExpense) =>
    apiRequest<Expense>("/api/expenses/", { method: "POST", body: data, companyId }),
};

export const taxApi = {
  vatSummary: (companyId: string, start: string, end: string) =>
    apiRequest<VatSummary>("/api/tax/vat-summary/", { query: { start, end }, companyId }),
};
