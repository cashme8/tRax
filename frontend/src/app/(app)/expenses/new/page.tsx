"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ErrorBanner } from "@/components/error-banner";
import { FormField, invalidProps } from "@/components/form-field";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { expensesApi, suppliersApi } from "@/lib/api/endpoints";
import type { ExpenseCategory } from "@/lib/api/types";
import { useActiveCompany } from "@/lib/company";
import { todayISO, TREATMENT_LABELS } from "@/lib/format";
import { applyApiErrors, DECIMAL_PATTERN, zodResolver } from "@/lib/forms";

import { EXPENSE_CATEGORIES } from "../categories";

const TREATMENTS = ["standard", "zero_rated", "exempt", "non_taxable"] as const;
const CATEGORIES = Object.keys(EXPENSE_CATEGORIES) as [ExpenseCategory, ...ExpenseCategory[]];

const schema = z.object({
  expense_date: z.iso.date("Pick a date."),
  category: z.enum(CATEGORIES),
  description: z.string(),
  supplier: z.string(),
  ebm_receipt_number: z.string(),
  tax_treatment: z.enum(TREATMENTS),
  amount_excl_vat: z.string().regex(DECIMAL_PATTERN, "An amount, e.g. 150000 or 999.50"),
});
type Values = z.infer<typeof schema>;

export default function NewExpensePage() {
  const company = useActiveCompany();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const suppliers = useQuery({
    queryKey: ["suppliers", company.id],
    queryFn: () => suppliersApi.list(company.id),
  });

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      expense_date: todayISO(),
      category: "rent",
      description: "",
      supplier: "",
      ebm_receipt_number: "",
      tax_treatment: "standard",
      amount_excl_vat: "",
    },
  });

  async function onSubmit(values: Values) {
    setFormError(null);
    try {
      await expensesApi.create(company.id, {
        ...values,
        supplier: values.supplier || null,
        ebm_receipt_number: values.ebm_receipt_number.trim() || null,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["expenses", company.id] }),
        queryClient.invalidateQueries({ queryKey: ["vat-summary", company.id] }),
      ]);
      router.push("/expenses");
    } catch (error) {
      const message = applyApiErrors(error, setError, Object.keys(schema.shape));
      if (message !== "Please fix the highlighted fields.") setFormError(message);
    }
  }

  return (
    <>
      <PageHeader title="New expense" />
      <form onSubmit={handleSubmit(onSubmit)} className="grid max-w-2xl gap-6" noValidate>
        <ErrorBanner message={formError} />
        <Card>
          <CardHeader>
            <CardTitle>Expense</CardTitle>
            <CardDescription>
              Enter the amount excluding VAT. tRax calculates the input VAT when you save.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <FormField id="expense_date" label="Date" error={errors.expense_date?.message}>
              <Input
                id="expense_date"
                type="date"
                {...invalidProps("expense_date", errors.expense_date?.message)}
                {...register("expense_date")}
              />
            </FormField>
            <FormField id="category" label="Category">
              <NativeSelect id="category" {...register("category")}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {EXPENSE_CATEGORIES[c]}
                  </option>
                ))}
              </NativeSelect>
            </FormField>
            <div className="sm:col-span-2">
              <FormField id="description" label="Description (optional)">
                <Input id="description" {...register("description")} />
              </FormField>
            </div>
            <FormField
              id="amount_excl_vat"
              label="Amount excl. VAT (RWF)"
              error={errors.amount_excl_vat?.message}
            >
              <Input
                id="amount_excl_vat"
                inputMode="decimal"
                {...invalidProps("amount_excl_vat", errors.amount_excl_vat?.message)}
                {...register("amount_excl_vat")}
              />
            </FormField>
            <FormField id="tax_treatment" label="VAT treatment">
              <NativeSelect id="tax_treatment" {...register("tax_treatment")}>
                {TREATMENTS.map((t) => (
                  <option key={t} value={t}>
                    {TREATMENT_LABELS[t]}
                  </option>
                ))}
              </NativeSelect>
            </FormField>
            <FormField
              id="supplier"
              label="Supplier (optional)"
              error={errors.supplier?.message}
              hint="An unregistered supplier's bills carry no VAT."
            >
              <NativeSelect id="supplier" {...register("supplier")}>
                <option value="">None</option>
                {suppliers.data?.results.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.name}
                    {!supplier.vat_registered && " (not VAT-registered)"}
                  </option>
                ))}
              </NativeSelect>
            </FormField>
            <FormField
              id="ebm_receipt_number"
              label="Supplier EBM receipt no."
              hint="Needed to claim the input VAT."
            >
              <Input id="ebm_receipt_number" {...register("ebm_receipt_number")} />
            </FormField>
          </CardContent>
        </Card>
        <div className="flex gap-2">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Save expense"}
          </Button>
          <Button type="button" variant="ghost" onClick={() => router.back()}>
            Cancel
          </Button>
        </div>
      </form>
    </>
  );
}
