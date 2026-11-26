/**
 * Where the login tokens and the active company live in the browser.
 *
 * - Access token: in memory only (gone on page reload; short-lived anyway).
 * - Refresh token: localStorage, so a reload keeps you logged in.
 *   TODO(before production): move the refresh token to an httpOnly cookie
 *   (set by the backend) so page scripts can't read it.
 * - Active company id: localStorage, sent as the X-Company-ID header.
 */

const REFRESH_KEY = "trax.refresh";
const COMPANY_KEY = "trax.company";

let accessToken: string | null = null;
const logoutListeners = new Set<() => void>();

function storage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export const session = {
  getAccess: () => accessToken,
  getRefresh: () => storage()?.getItem(REFRESH_KEY) ?? null,

  setTokens(access: string, refresh?: string) {
    accessToken = access;
    if (refresh) storage()?.setItem(REFRESH_KEY, refresh);
  },

  /** Forget everything and tell listeners (the auth provider) we're logged out. */
  clear() {
    accessToken = null;
    storage()?.removeItem(REFRESH_KEY);
    storage()?.removeItem(COMPANY_KEY);
    logoutListeners.forEach((listener) => listener());
  },

  onLogout(listener: () => void) {
    logoutListeners.add(listener);
    return () => logoutListeners.delete(listener);
  },

  getCompanyId: () => storage()?.getItem(COMPANY_KEY) ?? null,
  setCompanyId(id: string) {
    storage()?.setItem(COMPANY_KEY, id);
  },
};
