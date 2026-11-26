"use client";

import { Building2, LogOut, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { CompanyProvider, useCompany } from "@/lib/company";
import { ROLE_LABELS } from "@/lib/format";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/invoices", label: "Invoices" },
  { href: "/expenses", label: "Expenses" },
] as const;

/** Pages that work without an active company (so a new user can create one). */
const NO_COMPANY_NEEDED = ["/companies/new"];

function Loading() {
  return (
    <div className="mx-auto grid w-full max-w-6xl gap-4 p-6" aria-busy="true">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

/** Every logged-in page is wrapped in this. Logged-out visitors are sent to /login. */
export function AppShell({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  if (status !== "authenticated") return <Loading />;
  return (
    <CompanyProvider>
      <Shell>{children}</Shell>
    </CompanyProvider>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { companies, active, isLoading } = useCompany();
  const needsCompany = !NO_COMPANY_NEEDED.includes(pathname);

  let content = children;
  if (isLoading) content = <Loading />;
  else if (companies.length === 0 && needsCompany) content = <NoCompanyYet />;
  else if (!active && needsCompany) content = <Loading />;

  return (
    <>
      <Header />
      <main className="mx-auto grid w-full max-w-6xl gap-6 p-6">{content}</main>
    </>
  );
}

function Header() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { companies, active, setActive } = useCompany();

  return (
    <header className="border-b bg-background">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-6 py-3">
        <Link href="/dashboard" className="text-lg font-semibold tracking-tight">
          tRax
        </Link>
        <nav className="flex gap-1" aria-label="Main">
          {NAV.map((item) => {
            const current = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={current ? "page" : undefined}
                className={buttonVariants({ variant: current ? "secondary" : "ghost", size: "sm" })}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {companies.length > 0 && (
            <label className="flex items-center gap-2 text-sm">
              <Building2 className="size-4 text-muted-foreground" aria-hidden />
              <span className="sr-only">Active company</span>
              <NativeSelect
                className="w-56"
                value={active?.id ?? ""}
                onChange={(event) => setActive(event.target.value)}
              >
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.legal_name} · {ROLE_LABELS[company.my_role]}
                  </option>
                ))}
              </NativeSelect>
            </label>
          )}
          <Link
            href="/companies/new"
            className={buttonVariants({ variant: "outline", size: "sm" })}
            title="Add a company"
          >
            <Plus /> Company
          </Link>
          <span className="hidden text-sm text-muted-foreground md:inline">{user?.email}</span>
          <Button variant="ghost" size="sm" onClick={logout}>
            <LogOut /> Log out
          </Button>
        </div>
      </div>
    </header>
  );
}

function NoCompanyYet() {
  return (
    <Card className="mx-auto w-full max-w-lg">
      <CardHeader>
        <CardTitle>Add your first company</CardTitle>
        <CardDescription>
          tRax keeps each company&apos;s records separate. Add the company you file taxes for — or
          ask its owner to invite you.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Link href="/companies/new" className={buttonVariants()}>
          <Plus /> Add a company
        </Link>
      </CardContent>
    </Card>
  );
}
