// Layout for the logged-out pages (login, register): a centred card.
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 p-6">
      <div className="text-center">
        <p className="text-3xl font-semibold tracking-tight">tRax</p>
        <p className="text-sm text-muted-foreground">
          Rwanda tax compliance for companies and their accountants
        </p>
      </div>
      <div className="w-full max-w-sm">{children}</div>
    </main>
  );
}
