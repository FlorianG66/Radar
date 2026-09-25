"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, clearTokens, errorMessage, getToken, setTokens } from "@/lib/api";
import type { User } from "@/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  refreshUser: () => Promise<void>;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
    organization_name?: string;
  }) => Promise<User>;
  logout: () => void;
  error: string | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshUser = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me);
    } catch (e) {
      clearTokens();
      setUser(null);
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve()
      .then(refreshUser)
      .catch(() => undefined);
  }, [refreshUser]);

  const resolve = useCallback(
    async (promise: Promise<User>) => {
      setError(null);
      try {
        const me = await promise;
        setUser(me);
        return me;
      } catch (e) {
        setError(errorMessage(e));
        throw e;
      }
    },
    [],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await api.post<{
        access_token: string;
        refresh_token?: string;
      }>("/auth/login", { email, password });
      setTokens(tokens);
      return resolve(api.get<User>("/auth/me"));
    },
    [resolve],
  );

  const register = useCallback(
    async (payload: {
      email: string;
      password: string;
      first_name?: string;
      last_name?: string;
      organization_name?: string;
    }) => {
      const tokens = await api.post<{ access_token: string; refresh_token?: string }>(
        "/auth/register",
        payload,
      );
      setTokens(tokens);
      return resolve(api.get<User>("/auth/me"));
    },
    [resolve],
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, refreshUser, login, register, logout, error }),
    [user, loading, refreshUser, login, register, logout, error],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans <AuthProvider>");
  return ctx;
}