import { AppShell } from "@/components/app-shell";

/**
 * Logged-in pages are rendered in the browser: they need the login token
 * (kept in the browser) before they can show anything, so the server
 * pre-render is just a loading shell. Tell Next.js not to validate these
 * routes for "instant navigation" — they're expected to wait for the session.
 * TODO: revisit if the session moves to an httpOnly cookie (then the server
 * could render these pages).
 */
export const instant = false;

// Layout for every logged-in page: header, navigation, company switcher.
export default function AppLayout({ children }: LayoutProps<"/">) {
  return <AppShell>{children}</AppShell>;
}
