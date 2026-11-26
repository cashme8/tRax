"use client";

/**
 * The active company: which of the user's companies the app is showing.
 * The choice is remembered in the browser. Pages pass `active.id` to every
 * API call (it becomes X-Company-ID) and include it in every query key, so
 * switching company refetches everything for the new company.
 */

import { useQuery } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { companiesApi } from "@/lib/api/endpoints";
import type { Company } from "@/lib/api/types";
import { session } from "@/lib/session";

type CompanyContextValue = {
  companies: Company[];
  active: Company | null;
  setActive: (id: string) => void;
  isLoading: boolean;
  /** Owners and accountants can create and edit; viewers only read. */
  canEdit: boolean;
};

const CompanyContext = createContext<CompanyContextValue | null>(null);

export function CompanyProvider({ children }: { children: React.ReactNode }) {
  const { data, isLoading } = useQuery({
    queryKey: ["companies"],
    queryFn: companiesApi.list,
  });
  const companies = useMemo(() => data?.results ?? [], [data]);
  // Only rendered in the browser after login, so reading localStorage here is safe.
  const [chosenId, setChosenId] = useState<string | null>(() => session.getCompanyId());

  // The chosen company if it's still one of ours, otherwise the first one.
  const active = companies.find((c) => c.id === chosenId) ?? companies[0] ?? null;

  const setActive = useCallback((id: string) => {
    session.setCompanyId(id);
    setChosenId(id);
  }, []);

  const value = useMemo(
    () => ({
      companies,
      active,
      setActive,
      isLoading,
      canEdit: active !== null && active.my_role !== "viewer",
    }),
    [companies, active, setActive, isLoading],
  );
  return <CompanyContext.Provider value={value}>{children}</CompanyContext.Provider>;
}

export function useCompany(): CompanyContextValue {
  const context = useContext(CompanyContext);
  if (!context) throw new Error("useCompany must be used inside <CompanyProvider>");
  return context;
}

/** The active company, for pages that only render once one exists. */
export function useActiveCompany(): Company {
  const { active } = useCompany();
  if (!active) throw new Error("No active company");
  return active;
}
