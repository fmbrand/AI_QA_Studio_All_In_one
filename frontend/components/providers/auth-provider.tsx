"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, refreshSession, setAccessToken, setSessionExpiredHandler } from "@/lib/api";
import type { TokenResponse, User } from "@/lib/types";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: Status;
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  register: (name: string, email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// A non-sensitive hint that a refresh cookie may exist. Without it we skip the startup refresh call,
// so anonymous visitors do not trigger a 401. The cookie itself stays httpOnly and is never read here.
const SESSION_HINT = "aiqa-session-hint";

function readHint(): boolean {
  try {
    return window.localStorage.getItem(SESSION_HINT) === "1";
  } catch {
    return true; // Storage unavailable: try the refresh anyway.
  }
}

function writeHint(on: boolean) {
  try {
    if (on) window.localStorage.setItem(SESSION_HINT, "1");
    else window.localStorage.removeItem(SESSION_HINT);
  } catch {
    // Ignore: the hint only avoids one request.
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUserState] = useState<User | null>(null);
  const queryClient = useQueryClient();

  const accept = useCallback((data: TokenResponse) => {
    setAccessToken(data.access_token);
    setUserState(data.user);
    setStatus("authenticated");
    writeHint(true);
    return data.user;
  }, []);

  const clear = useCallback(() => {
    setAccessToken(null);
    setUserState(null);
    setStatus("anonymous");
    writeHint(false);
    queryClient.clear();
  }, [queryClient]);

  // Restore the session from the refresh cookie on first load.
  useEffect(() => {
    let cancelled = false;
    if (!readHint()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStatus("anonymous");
      return;
    }
    refreshSession().then((data) => {
      if (cancelled) return;
      if (data) accept(data);
      else {
        writeHint(false);
        setStatus("anonymous");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [accept]);

  useEffect(() => {
    setSessionExpiredHandler(clear);
    return () => setSessionExpiredHandler(null);
  }, [clear]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      login: async (email, password) => accept(await api.post<TokenResponse>("/auth/login", { email, password })),
      register: async (name, email, password) =>
        accept(await api.post<TokenResponse>("/auth/register", { name, email, password })),
      logout: async () => {
        try {
          await api.post("/auth/logout");
        } finally {
          clear();
        }
      },
      setUser: setUserState,
    }),
    [status, user, accept, clear],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
