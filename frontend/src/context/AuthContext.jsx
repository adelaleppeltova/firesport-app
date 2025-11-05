import { createContext, useContext, useEffect, useState } from "react";
import api, { setAuthToken } from "../api/axios";

const AuthContext = createContext(null);

// Modulový guard proti duplicitnímu refreshi ve StrictMode
let BOOTSTRAPPED = false;

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (BOOTSTRAPPED) {
      setLoading(false);
      return;
    }
    BOOTSTRAPPED = true;

    (async () => {
      try {
        const r = await api.post("/auth/refresh");
        const access = r.data?.access_token;
        if (access) {
          setAuthToken(access);
          setIsAuthenticated(true);
        } else {
          setAuthToken(null);
          setIsAuthenticated(false);
        }
      } catch {
        // 401 je OK, pokud nejste přihlášen/a
        setAuthToken(null);
        setIsAuthenticated(false);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    const access = r.data?.access_token;
    if (access) {
      setAuthToken(access);
      setIsAuthenticated(true);
    }
    return r;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setAuthToken(null);
      setIsAuthenticated(false);
    }
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
