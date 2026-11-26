"use client";

/**
 * Who is logged in. On first load in the browser, a saved refresh token is
 * exchanged for an access token and the user is fetched; until then the
 * status is "loading" (also what the server pre-render shows).
 */

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { refreshAccessToken } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";
import type { User } from "@/lib/api/types";
import { session } from "@/lib/session";

type Status = "loading" | "anonymous" | "authenticated";

type AuthContextValue = {
  status: Status;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; full_name: string; password: string }) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    // Any API call that finds the session dead (refresh failed) logs us out here.
    const unsubscribe = session.onLogout(() => {
      setUser(null);
      setStatus("anonymous");
      queryClient.clear();
    });

    let cancelled = false;
    (async () => {
      try {
        if (await refreshAccessToken()) {
          const me = await authApi.me();
          if (!cancelled) {
            setUser(me);
            setStatus("authenticated");
          }
          return;
        }
      } catch {
        // fall through to anonymous
      }
      if (!cancelled) setStatus("anonymous");
    })();

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [queryClient]);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await authApi.login(email, password);
    session.setTokens(tokens.access, tokens.refresh);
    setUser(await authApi.me());
    setStatus("authenticated");
  }, []);

  const register = useCallback(
    async (data: { email: string; full_name: string; password: string }) => {
      const result = await authApi.register(data);
      session.setTokens(result.access, result.refresh);
      setUser(result.user);
      setStatus("authenticated");
    },
    [],
  );

  const logout = useCallback(() => session.clear(), []);

  const value = useMemo(
    () => ({ status, user, login, register, logout }),
    [status, user, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
