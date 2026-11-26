/**
 * Small bridge between react-hook-form and zod (instead of adding the
 * @hookform/resolvers package), plus a helper that shows the API's
 * field errors next to the right inputs.
 */

import type { FieldErrors, FieldValues, Path, Resolver, UseFormSetError } from "react-hook-form";
import type { z } from "zod";

import { ApiError } from "@/lib/api/client";

export function zodResolver<T extends FieldValues>(schema: z.ZodType<T>): Resolver<T> {
  return async (values) => {
    const result = schema.safeParse(values);
    if (result.success) return { values: result.data, errors: {} };

    // Build the nested shape react-hook-form expects, e.g. { items: [{ quantity: {...} }] }.
    const errors: Record<string, unknown> = {};
    for (const issue of result.error.issues) {
      let node: Record<string, unknown> = errors;
      issue.path.forEach((key, index) => {
        const k = String(key);
        if (index === issue.path.length - 1) {
          node[k] ??= { type: issue.code, message: issue.message };
        } else {
          node[k] ??= typeof issue.path[index + 1] === "number" ? [] : {};
          node = node[k] as Record<string, unknown>;
        }
      });
      if (issue.path.length === 0) errors.root = { type: issue.code, message: issue.message };
    }
    return { values: {}, errors: errors as FieldErrors<T> };
  };
}

/**
 * Put API field errors on the form fields; return the general message (if any)
 * for a banner. Unknown fields are folded into the general message.
 */
export function applyApiErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  knownFields: readonly string[],
): string {
  if (!(error instanceof ApiError)) return "Something went wrong. Please try again.";
  const extra: string[] = [];
  for (const [field, messages] of Object.entries(error.fieldErrors)) {
    const root = field.split(".")[0];
    if (knownFields.includes(root)) {
      setError(field as Path<T>, { type: "server", message: messages.join(" ") });
    } else {
      extra.push(...messages);
    }
  }
  return [error.message, ...extra].join(" ");
}

/** A decimal amount typed as text, e.g. "1500" or "1500.50" (never parsed to a float). */
export const DECIMAL_PATTERN = /^\d+(\.\d{1,2})?$/;
export const QUANTITY_PATTERN = /^\d+(\.\d{1,3})?$/;
