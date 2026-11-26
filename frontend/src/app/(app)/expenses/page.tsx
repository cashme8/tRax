"use client";

import { useQuery } from "@tanstack/react-query";
import { Receipt } from "lucide-react";
import Link from "next/link";

import { ErrorBanner } from "@/components/error-banner";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { expensesApi } from "@/lib/api/endpoints";
import { useActiveCompany, useCompany } from "@/lib/company";
import { formatDate, formatRwf, TREATMENT_LABELS } from "@/lib/format";

import { EXPENSE_CATEGORIES } from "./categories";

export default function ExpensesPage() {
  const company = useActiveCompany();
  const { canEdit } = useCompany();
  const { data, error, isPending } = useQuery({
    queryKey: ["expenses", company.id],
    queryFn: () => expensesApi.list(company.id),
  });

  return (
    <>
      <PageHeader
        title="Expenses"
        description="Running costs. Input VAT is calculated by the server from the amount and treatment."
        actions={
          canEdit && (
            <Link href="/expenses/new" className={buttonVariants()}>
              <Receipt /> New expense
            </Link>
          )
        }
      />
      <ErrorBanner message={error?.message} />
      <Card className="p-0">
        {isPending ? (
          <Skeleton className="m-4 h-32" />
        ) : data && data.results.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">No expenses recorded yet.</p>
        ) : (
          data && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>VAT treatment</TableHead>
                  <TableHead className="text-right">Amount excl. VAT</TableHead>
                  <TableHead className="text-right">VAT</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((expense) => (
                  <TableRow key={expense.id}>
                    <TableCell>{formatDate(expense.expense_date)}</TableCell>
                    <TableCell>{EXPENSE_CATEGORIES[expense.category]}</TableCell>
                    <TableCell>
                      {expense.description || "—"}
                      {expense.supplier_name && (
                        <span className="block text-xs text-muted-foreground">
                          {expense.supplier_name}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{TREATMENT_LABELS[expense.tax_treatment]}</Badge>
                      {!expense.ebm_receipt_number && expense.vat_amount !== "0.00" && (
                        <span className="block text-xs text-muted-foreground">No EBM receipt</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatRwf(expense.amount_excl_vat)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatRwf(expense.vat_amount)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatRwf(expense.total_amount)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )
        )}
      </Card>
    </>
  );
}
