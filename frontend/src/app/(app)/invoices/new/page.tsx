"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { ErrorBanner } from "@/components/error-banner";
import { FormField, invalidProps } from "@/components/form-field";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { customersApi, invoicesApi } from "@/lib/api/endpoints";
import { useActiveCompany } from "@/lib/company";
import { todayISO, TREATMENT_LABELS } from "@/lib/format";
import { applyApiErrors, DECIMAL_PATTERN, QUANTITY_PATTERN, zodResolver } from "@/lib/forms";

const NEW_CUSTOMER = "__new__";
const TREATMENTS = ["standard", "zero_rated", "exempt", "non_taxable"] as const;

const lineSchema = z.object({
  description: z.string().trim().min(1, "Describe the item."),
  quantity: z
    .string()
    .regex(QUANTITY_PATTERN, "A number, e.g. 2 or 1.5")
    .refine((v) => !/^0+(\.0*)?$/.test(v), "Must be more than 0."),
  unit_price: z.string().regex(DECIMAL_PATTERN, "An amount, e.g. 25000 or 999.50"),
  tax_treatment: z.enum(TREATMENTS),
});

const schema = z
  .object({
    invoice_number: z.string().trim().min(1, "Give the invoice a number."),
    customer: z.string(),
    new_customer_name: z.string(),
    issue_date: z.iso.date("Pick a date."),
    due_date: z.union([z.literal(""), z.iso.date()]),
    notes: z.string(),
    items: z.array(lineSchema).min(1, "Add at least one line."),
  })
  .superRefine((values, ctx) => {
    if (!values.customer) {
      ctx.addIssue({ code: "custom", path: ["customer"], message: "Choose a customer." });
    }
    if (values.customer === NEW_CUSTOMER && !values.new_customer_name.trim()) {
      ctx.addIssue({ code: "custom", path: ["new_customer_name"], message: "Enter a name." });
    }
  });
type Values = z.infer<typeof schema>;

const emptyLine = {
  description: "",
  quantity: "1",
  unit_price: "",
  tax_treatment: "standard",
} as const;

export default function NewInvoicePage() {
  const company = useActiveCompany();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);

  const customers = useQuery({
    queryKey: ["customers", company.id],
    queryFn: () => customersApi.list(company.id),
  });

  const {
    register,
    control,
    handleSubmit,
    setError,

    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      invoice_number: "",
      customer: "",
      new_customer_name: "",
      issue_date: todayISO(),
      due_date: "",
      notes: "",
      items: [{ ...emptyLine }],
    },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "items" });
  const isNewCustomer = useWatch({ control, name: "customer" }) === NEW_CUSTOMER;

  async function onSubmit(values: Values) {
    setFormError(null);
    try {
      let customerId = values.customer;
      if (customerId === NEW_CUSTOMER) {
        const created = await customersApi.create(company.id, {
          name: values.new_customer_name.trim(),
        });
        customerId = created.id;
        queryClient.invalidateQueries({ queryKey: ["customers", company.id] });
      }
      await invoicesApi.create(company.id, {
        invoice_number: values.invoice_number,
        customer: customerId,
        issue_date: values.issue_date,
        due_date: values.due_date || null,
        notes: values.notes,
        items: values.items,
      });
      await queryClient.invalidateQueries({ queryKey: ["invoices", company.id] });
      router.push("/invoices");
    } catch (error) {
      const message = applyApiErrors(error, setError, [
        "invoice_number",
        "customer",
        "issue_date",
        "due_date",
        "items",
      ]);
      if (message !== "Please fix the highlighted fields.") setFormError(message);
    }
  }

  return (
    <>
      <PageHeader
        title="New invoice"
        description="Saved as a draft. Issue it from the invoice list when it's final."
      />
      <form onSubmit={handleSubmit(onSubmit)} className="grid gap-6" noValidate>
        <ErrorBanner message={formError} />

        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-4">
            <FormField
              id="invoice_number"
              label="Invoice number"
              error={errors.invoice_number?.message}
            >
              <Input
                id="invoice_number"
                placeholder="INV-0001"
                {...invalidProps("invoice_number", errors.invoice_number?.message)}
                {...register("invoice_number")}
              />
            </FormField>
            <FormField id="customer" label="Customer" error={errors.customer?.message}>
              <NativeSelect
                id="customer"
                {...invalidProps("customer", errors.customer?.message)}
                {...register("customer")}
              >
                <option value="">{customers.isPending ? "Loading…" : "Choose…"}</option>
                {customers.data?.results.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                  </option>
                ))}
                <option value={NEW_CUSTOMER}>+ New customer…</option>
              </NativeSelect>
            </FormField>
            <FormField id="issue_date" label="Issue date" error={errors.issue_date?.message}>
              <Input
                id="issue_date"
                type="date"
                {...invalidProps("issue_date", errors.issue_date?.message)}
                {...register("issue_date")}
              />
            </FormField>
            <FormField id="due_date" label="Due date (optional)" error={errors.due_date?.message}>
              <Input
                id="due_date"
                type="date"
                {...invalidProps("due_date", errors.due_date?.message)}
                {...register("due_date")}
              />
            </FormField>
            {isNewCustomer && (
              <div className="md:col-span-2">
                <FormField
                  id="new_customer_name"
                  label="New customer name"
                  error={errors.new_customer_name?.message}
                >
                  <Input
                    id="new_customer_name"
                    {...invalidProps("new_customer_name", errors.new_customer_name?.message)}
                    {...register("new_customer_name")}
                  />
                </FormField>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Lines</CardTitle>
            <CardDescription>
              Unit prices exclude VAT. tRax calculates VAT and totals when you save.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {errors.items?.root?.message && (
              <p className="text-sm text-destructive">{errors.items.root.message}</p>
            )}
            {fields.map((field, index) => {
              const e = errors.items?.[index];
              const id = (name: string) => `items-${index}-${name}`;
              return (
                <fieldset
                  key={field.id}
                  className="grid items-start gap-3 rounded-lg border p-3 md:grid-cols-[2fr_0.7fr_1fr_1fr_auto]"
                >
                  <legend className="sr-only">Line {index + 1}</legend>
                  <FormField
                    id={id("description")}
                    label="Description"
                    error={e?.description?.message}
                  >
                    <Input
                      id={id("description")}
                      {...invalidProps(id("description"), e?.description?.message)}
                      {...register(`items.${index}.description`)}
                    />
                  </FormField>
                  <FormField id={id("quantity")} label="Qty" error={e?.quantity?.message}>
                    <Input
                      id={id("quantity")}
                      inputMode="decimal"
                      {...invalidProps(id("quantity"), e?.quantity?.message)}
                      {...register(`items.${index}.quantity`)}
                    />
                  </FormField>
                  <FormField
                    id={id("unit_price")}
                    label="Unit price (RWF)"
                    error={e?.unit_price?.message}
                  >
                    <Input
                      id={id("unit_price")}
                      inputMode="decimal"
                      {...invalidProps(id("unit_price"), e?.unit_price?.message)}
                      {...register(`items.${index}.unit_price`)}
                    />
                  </FormField>
                  <FormField
                    id={id("tax_treatment")}
                    label="VAT treatment"
                    error={e?.tax_treatment?.message}
                  >
                    <NativeSelect
                      id={id("tax_treatment")}
                      {...register(`items.${index}.tax_treatment`)}
                    >
                      {TREATMENTS.map((t) => (
                        <option key={t} value={t}>
                          {TREATMENT_LABELS[t]}
                        </option>
                      ))}
                    </NativeSelect>
                  </FormField>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="md:mt-6"
                    disabled={fields.length === 1}
                    onClick={() => remove(index)}
                    aria-label={`Remove line ${index + 1}`}
                  >
                    <Trash2 />
                  </Button>
                </fieldset>
              );
            })}
            <Button
              type="button"
              variant="outline"
              className="w-fit"
              onClick={() => append({ ...emptyLine })}
            >
              <Plus /> Add line
            </Button>
          </CardContent>
        </Card>

        <FormField id="notes" label="Notes (optional)">
          <Input id="notes" {...register("notes")} />
        </FormField>

        <div className="flex gap-2">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Save draft"}
          </Button>
          <Button type="button" variant="ghost" onClick={() => router.back()}>
            Cancel
          </Button>
        </div>
      </form>
    </>
  );
}
