"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ErrorBanner } from "@/components/error-banner";
import { FormField, invalidProps } from "@/components/form-field";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { companiesApi } from "@/lib/api/endpoints";
import { useCompany } from "@/lib/company";
import { todayISO } from "@/lib/format";
import { applyApiErrors, zodResolver } from "@/lib/forms";

const schema = z.object({
  legal_name: z.string().trim().min(1, "Enter the registered company name."),
  tin: z.string().regex(/^\d{9}$/, "A TIN is exactly 9 digits."),
  business_type: z.enum([
    "sole_proprietor",
    "limited_company",
    "partnership",
    "cooperative",
    "ngo",
    "other",
  ]),
  industry: z.string(),
  tax_profile: z.object({
    tax_regime: z.enum(["real", "lump_sum", "flat"]),
    vat_registered: z.boolean(),
    filing_frequency: z.enum(["monthly", "quarterly"]),
    effective_from: z.iso.date("Pick a date."),
  }),
});
type Values = z.infer<typeof schema>;

export default function NewCompanyPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { setActive } = useCompany();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      legal_name: "",
      tin: "",
      business_type: "limited_company",
      industry: "",
      tax_profile: {
        tax_regime: "real",
        vat_registered: true,
        filing_frequency: "monthly",
        effective_from: todayISO(),
      },
    },
  });

  async function onSubmit(values: Values) {
    setFormError(null);
    try {
      const company = await companiesApi.create(values);
      await queryClient.invalidateQueries({ queryKey: ["companies"] });
      setActive(company.id);
      router.push("/dashboard");
    } catch (error) {
      const message = applyApiErrors(error, setError, Object.keys(schema.shape));
      if (message !== "Please fix the highlighted fields.") setFormError(message);
    }
  }

  const tp = errors.tax_profile;
  return (
    <>
      <PageHeader
        title="Add a company"
        description="You'll be its owner and can invite your accountant or team."
      />
      <form onSubmit={handleSubmit(onSubmit)} className="grid max-w-2xl gap-6" noValidate>
        <ErrorBanner message={formError} />
        <Card>
          <CardHeader>
            <CardTitle>Company</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <FormField id="legal_name" label="Legal name" error={errors.legal_name?.message}>
                <Input
                  id="legal_name"
                  {...invalidProps("legal_name", errors.legal_name?.message)}
                  {...register("legal_name")}
                />
              </FormField>
            </div>
            <FormField id="tin" label="TIN" error={errors.tin?.message} hint="9 digits, from RRA.">
              <Input
                id="tin"
                inputMode="numeric"
                maxLength={9}
                {...invalidProps("tin", errors.tin?.message)}
                {...register("tin")}
              />
            </FormField>
            <FormField id="business_type" label="Business type">
              <NativeSelect id="business_type" {...register("business_type")}>
                <option value="limited_company">Limited company</option>
                <option value="sole_proprietor">Sole proprietor</option>
                <option value="partnership">Partnership</option>
                <option value="cooperative">Cooperative</option>
                <option value="ngo">NGO / non-profit</option>
                <option value="other">Other</option>
              </NativeSelect>
            </FormField>
            <div className="sm:col-span-2">
              <FormField id="industry" label="Industry (optional)">
                <Input
                  id="industry"
                  placeholder="e.g. Retail, Hospitality"
                  {...register("industry")}
                />
              </FormField>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tax profile</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <FormField id="tax_regime" label="Tax regime">
              <NativeSelect id="tax_regime" {...register("tax_profile.tax_regime")}>
                <option value="real">Real regime</option>
                <option value="lump_sum">Lump-sum regime</option>
                <option value="flat">Flat tax regime</option>
              </NativeSelect>
            </FormField>
            <FormField id="filing_frequency" label="VAT filing">
              <NativeSelect id="filing_frequency" {...register("tax_profile.filing_frequency")}>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
              </NativeSelect>
            </FormField>
            <FormField
              id="effective_from"
              label="Profile applies from"
              error={tp?.effective_from?.message}
              hint="Invoices dated before this can't be priced."
            >
              <Input
                id="effective_from"
                type="date"
                {...invalidProps("effective_from", tp?.effective_from?.message)}
                {...register("tax_profile.effective_from")}
              />
            </FormField>
            <label className="flex items-center gap-2 self-end pb-1.5 text-sm">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                {...register("tax_profile.vat_registered")}
              />
              Registered for VAT
            </label>
          </CardContent>
        </Card>

        <div className="flex gap-2">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Create company"}
          </Button>
          <Button type="button" variant="ghost" onClick={() => router.back()}>
            Cancel
          </Button>
        </div>
      </form>
    </>
  );
}
