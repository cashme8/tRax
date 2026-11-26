/**
 * Display helpers. Money is formatted as a string → string transformation,
 * so an amount is never converted to a JavaScript number (a float).
 */

import type { Money } from "@/lib/api/types";

/** "1234567.5" → "1,234,567.50" ; "-72000.00" → "-72,000.00" */
export function formatMoney(amount: Money | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return "—";
  const negative = amount.startsWith("-");
  const [whole = "0", fraction = ""] = amount.replace(/^[-+]/, "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const cents = (fraction + "00").slice(0, 2);
  return `${negative ? "-" : ""}${grouped}.${cents}`;
}

/** "RWF 1,234,567.50" */
export function formatRwf(amount: Money | null | undefined): string {
  const formatted = formatMoney(amount);
  return formatted === "—" ? formatted : `RWF ${formatted}`;
}

/** "2026-03-10" → "10 Mar 2026" (dates are calendar dates: no time-zone shifting). */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [year, month, day] = iso.slice(0, 10).split("-");
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${Number(day)} ${months[Number(month) - 1]} ${year}`;
}

/** Today's date in Kigali as "YYYY-MM-DD". */
export function todayISO(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Kigali" }).format(new Date());
}

/** First and last day of the month containing `iso`. */
export function monthBounds(iso: string): { start: string; end: string } {
  const [year, month] = iso.split("-").map(Number);
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const mm = String(month).padStart(2, "0");
  return { start: `${year}-${mm}-01`, end: `${year}-${mm}-${String(lastDay).padStart(2, "0")}` };
}

export const TREATMENT_LABELS = {
  standard: "Standard-rated",
  zero_rated: "Zero-rated",
  exempt: "Exempt",
  non_taxable: "Non-taxable",
} as const;

export const ROLE_LABELS = { owner: "Owner", accountant: "Accountant", viewer: "Viewer" } as const;
