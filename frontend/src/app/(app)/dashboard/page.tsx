"use client";

import { useQuery } from "@tanstack/react-query";
import { FilePlus, Receipt, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ErrorBanner } from "@/components/error-banner";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { taxApi } from "@/lib/api/endpoints";
import type { Money, VatSummary } from "@/lib/api/types";
import { useActiveCompany, useCompany } from "@/lib/company";
import { formatDate, formatRwf, monthBounds, todayISO, TREATMENT_LABELS } from "@/lib/format";

export default function DashboardPage() {
  const company = useActiveCompany();
  const { canEdit } = useCompany();
  const [month, setMonth] = useState(() => todayISO().slice(0, 7)); // "2026-11"
  const { start, end } = monthBounds(`${month}-01`);

  const { data, error, isPending } = useQuery({
    queryKey: ["vat-summary", company.id, start, end],
    queryFn: () => taxApi.vatSummary(company.id, start, end),
  });

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={`${company.legal_name} · TIN ${company.tin}`}
        actions={
          canEdit && (
            <>
              <Link href="/invoices/new" className={buttonVariants()}>
                <FilePlus /> New invoice
              </Link>
              <Link href="/expenses/new" className={buttonVariants({ variant: "outline" })}>
                <Receipt /> New expense
              </Link>
            </>
          )
        }
      />

      <section className="grid gap-4" aria-labelledby="vat-heading">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="vat-heading" className="text-lg font-semibold">
              VAT for the period
            </h2>
            <p className="text-sm text-muted-foreground">
              {formatDate(start)} – {formatDate(end)}. Only issued invoices count.
            </p>
          </div>
          <label className="grid gap-1 text-sm">
            <span className="text-muted-foreground">Month</span>
            <Input
              type="month"
              value={month}
              onChange={(event) => event.target.value && setMonth(event.target.value)}
              className="w-44"
            />
          </label>
        </div>

        {company.current_tax_profile && !company.current_tax_profile.vat_registered && (
          <Alert>
            <AlertTitle>Not registered for VAT</AlertTitle>
            <AlertDescription>
              This company&apos;s tax profile says it isn&apos;t VAT-registered, so its invoices
              carry no VAT and it can&apos;t claim input VAT.
            </AlertDescription>
          </Alert>
        )}

        <ErrorBanner message={error?.message} />
        {isPending ? <SummarySkeleton /> : data && <Summary summary={data} />}
      </section>
    </>
  );
}

function StatCard({ label, amount, note }: { label: string; amount: Money; note: string }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl tabular-nums">{formatRwf(amount)}</CardTitle>
      </CardHeader>
      <CardContent className="text-xs text-muted-foreground">{note}</CardContent>
    </Card>
  );
}

function Summary({ summary }: { summary: VatSummary }) {
  const inCredit = summary.credit !== "0.00";
  return (
    <>
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Output VAT"
          amount={summary.output_vat}
          note={`On ${summary.output_by_treatment.standard.count} standard-rated sales lines`}
        />
        <StatCard
          label="Input VAT (claimable)"
          amount={summary.input_vat}
          note="From purchases and expenses"
        />
        {inCredit ? (
          <StatCard label="VAT credit" amount={summary.credit} note="More input than output VAT" />
        ) : (
          <StatCard label="Net VAT payable" amount={summary.net_payable} note="Output − input" />
        )}
      </div>

      {summary.warnings.length > 0 && (
        <Alert>
          <TriangleAlert />
          <AlertTitle>Check before filing</AlertTitle>
          <AlertDescription>
            <ul className="mt-1 list-disc space-y-1 pl-4">
              {summary.warnings.map((warning) => (
                <li key={warning.code}>
                  {warning.message}
                  {warning.count > 0 && warning.code !== "unverified_tax_rules" && (
                    <span className="text-muted-foreground"> ({warning.count})</span>
                  )}
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Sales by tax treatment</CardTitle>
          <CardDescription>Amounts excluding VAT, from issued invoices.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
            {(Object.keys(TREATMENT_LABELS) as (keyof typeof TREATMENT_LABELS)[]).map((key) => (
              <div key={key} className="flex justify-between border-b py-1">
                <dt className="text-muted-foreground">{TREATMENT_LABELS[key]}</dt>
                <dd className="tabular-nums">{formatRwf(summary.output_by_treatment[key].net)}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Calculated by tRax from your records
        {summary.rule_versions.length > 0 && ` (tax rules: ${summary.rule_versions.join(", ")})`}.
        tRax prepares figures; review them before filing on RRA e-Tax.
      </p>
    </>
  );
}

function SummarySkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-3" aria-busy="true">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-28" />
      ))}
    </div>
  );
}
