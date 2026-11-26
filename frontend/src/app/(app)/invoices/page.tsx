"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePlus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ErrorBanner } from "@/components/error-banner";
import { PageHeader } from "@/components/page-header";
import { InvoiceStatusBadge, PaymentStatusBadge } from "@/components/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { invoicesApi } from "@/lib/api/endpoints";
import type { Invoice } from "@/lib/api/types";
import { useActiveCompany, useCompany } from "@/lib/company";
import { formatDate, formatRwf } from "@/lib/format";

export default function InvoicesPage() {
  const company = useActiveCompany();
  const { canEdit } = useCompany();
  const [status, setStatus] = useState("");

  const { data, error, isPending } = useQuery({
    queryKey: ["invoices", company.id, status],
    queryFn: () => invoicesApi.list(company.id, status || undefined),
  });

  return (
    <>
      <PageHeader
        title="Invoices"
        description="Totals and VAT are calculated by the server from each invoice's lines."
        actions={
          canEdit && (
            <Link href="/invoices/new" className={buttonVariants()}>
              <FilePlus /> New invoice
            </Link>
          )
        }
      />

      <label className="flex w-fit items-center gap-2 text-sm">
        <span className="text-muted-foreground">Status</span>
        <NativeSelect value={status} onChange={(e) => setStatus(e.target.value)} className="w-40">
          <option value="">All</option>
          <option value="draft">Draft</option>
          <option value="issued">Issued</option>
          <option value="cancelled">Cancelled</option>
        </NativeSelect>
      </label>

      <ErrorBanner message={error?.message} />
      <Card className="p-0">
        {isPending ? (
          <Skeleton className="m-4 h-32" />
        ) : data && data.results.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">
            No invoices yet{status && " with this status"}.
          </p>
        ) : (
          data && <InvoiceTable invoices={data.results} canEdit={canEdit} />
        )}
      </Card>
      {data && data.count > data.results.length && (
        // TODO: pagination controls.
        <p className="text-xs text-muted-foreground">
          Showing the latest {data.results.length} of {data.count}.
        </p>
      )}
    </>
  );
}

function InvoiceTable({ invoices, canEdit }: { invoices: Invoice[]; canEdit: boolean }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Number</TableHead>
          <TableHead>Customer</TableHead>
          <TableHead>Date</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">VAT</TableHead>
          <TableHead className="text-right">Total</TableHead>
          <TableHead className="text-right">Balance</TableHead>
          {canEdit && <TableHead className="sr-only">Actions</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {invoices.map((invoice) => (
          <TableRow key={invoice.id}>
            <TableCell className="font-medium">{invoice.invoice_number}</TableCell>
            <TableCell>{invoice.customer_name}</TableCell>
            <TableCell>{formatDate(invoice.issue_date)}</TableCell>
            <TableCell className="space-x-1">
              <InvoiceStatusBadge status={invoice.status} />
              {invoice.status === "issued" && (
                <PaymentStatusBadge status={invoice.payment_status} />
              )}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatRwf(invoice.vat_amount)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatRwf(invoice.total_amount)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {invoice.status === "issued" ? formatRwf(invoice.balance_due) : "—"}
            </TableCell>
            {canEdit && (
              <TableCell className="text-right">
                {invoice.status === "draft" && <IssueButton invoice={invoice} />}
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function IssueButton({ invoice }: { invoice: Invoice }) {
  const queryClient = useQueryClient();
  const company = useActiveCompany();
  const issue = useMutation({
    mutationFn: () => invoicesApi.issue(company.id, invoice.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices", company.id] });
      queryClient.invalidateQueries({ queryKey: ["vat-summary", company.id] });
    },
  });
  return (
    <span className="inline-flex items-center gap-2">
      {issue.error && <span className="text-xs text-destructive">{issue.error.message}</span>}
      <Button
        size="sm"
        variant="outline"
        disabled={issue.isPending}
        onClick={() => {
          if (window.confirm(`Issue ${invoice.invoice_number}? It can't be edited afterwards.`)) {
            issue.mutate();
          }
        }}
      >
        {issue.isPending ? "Issuing…" : "Issue"}
      </Button>
    </span>
  );
}
