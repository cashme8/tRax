import { Badge } from "@/components/ui/badge";
import type { InvoiceStatus, PaymentStatus } from "@/lib/api/types";

const STATUS = {
  draft: { label: "Draft", variant: "outline" },
  issued: { label: "Issued", variant: "default" },
  cancelled: { label: "Cancelled", variant: "destructive" },
} as const;

const PAYMENT = {
  unpaid: { label: "Unpaid", variant: "outline" },
  partially_paid: { label: "Part paid", variant: "secondary" },
  paid: { label: "Paid", variant: "secondary" },
} as const;

export function InvoiceStatusBadge({ status }: { status: InvoiceStatus }) {
  const { label, variant } = STATUS[status];
  return <Badge variant={variant}>{label}</Badge>;
}

export function PaymentStatusBadge({ status }: { status: PaymentStatus }) {
  const { label, variant } = PAYMENT[status];
  return <Badge variant={variant}>{label}</Badge>;
}
