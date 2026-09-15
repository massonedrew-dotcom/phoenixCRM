import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { refreshAccessToken, request, session } from "../api/client";
import type { LoginResponse, User } from "../api/types";

type AuthState =
  | { status: "loading"; user: null }
  | { status: "anonymous"; user: null }
  | { status: "authenticated"; user: User };

interface AuthContextValue {
  state: AuthState;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({ status: "loading", user: null });

  const becomeAnonymous = useCallback(() => {
    session.clear();
    queryClient.clear();
    setState({ status: "anonymous", user: null });
  }, [queryClient]);

  useEffect(() => {
    session.onAuthLost(becomeAnonymous);
    let cancelled = false;
    (async () => {
      if (!session.hasRefreshToken() || !(await refreshAccessToken())) {
        if (!cancelled) becomeAnonymous();
        return;
      }
      try {
        const user = await request<User>("/auth/me");
        if (!cancelled) setState({ status: "authenticated", user });
      } catch {
        if (!cancelled) becomeAnonymous();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [becomeAnonymous]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await request<LoginResponse>("/auth/login", {
      method: "POST",
      json: { username, password },
    });
    session.start(response.access_token, response.refresh_token);
    setState({ status: "authenticated", user: response.user });
  }, []);

  const logout = useCallback(async () => {
    try {
      await request<void>("/auth/logout", { method: "POST" });
    } catch {
      // The session is dropped locally even if the server cannot be reached.
    }
    becomeAnonymous();
  }, [becomeAnonymous]);

  const value = useMemo(() => ({ state, login, logout }), [state, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}

/** The signed-in user; only call inside routes guarded by RequireAuth. */
export function useCurrentUser(): User {
  const { state } = useAuth();
  if (state.status !== "authenticated") {
    throw new Error("useCurrentUser requires an authenticated session");
  }
  return state.user;
}
