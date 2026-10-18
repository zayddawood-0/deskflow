"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  AUTH_LOGOUT_EVENT,
  refreshSession,
  setAccessToken,
} from "@/lib/api-client";
import { AuthContext, type AuthContextValue } from "@/hooks/use-auth";
import type { AuthResponse, User } from "@/types/api";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");

  useEffect(() => {
    let active = true;
    void refreshSession().then((session) => {
      if (!active) {
        return;
      }
      setAccessToken(session?.access_token ?? null);
      setUser(session?.user ?? null);
      setStatus(session ? "authenticated" : "unauthenticated");
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const handleLogout = () => {
      setAccessToken(null);
      setUser(null);
      setStatus("unauthenticated");
    };
    window.addEventListener(AUTH_LOGOUT_EVENT, handleLogout);
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, handleLogout);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api<AuthResponse>("/auth/login", {
      method: "POST",
      json: { email, password },
    });
    setAccessToken(data.access_token);
    setUser(data.user);
    setStatus("authenticated");
    return data.user;
  }, []);

  const register = useCallback(
    async (fullName: string, email: string, password: string) => {
      await api<User>("/auth/register", {
        method: "POST",
        json: { email, full_name: fullName, password },
      });
      const data = await api<AuthResponse>("/auth/login", {
        method: "POST",
        json: { email, password },
      });
      setAccessToken(data.access_token);
      setUser(data.user);
      setStatus("authenticated");
      return data.user;
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await api<void>("/auth/logout", { method: "POST" });
    } finally {
      setAccessToken(null);
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, status, login, register, logout }),
    [user, status, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
