import { createContext, useContext, useState, useEffect } from "react";
import api, { setAuthToken } from "../api/axios";
import { hashPassword } from "../utils/passwordHash";

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      setAuthToken(token);
      api
        .get("/v1/auth/me")
        .then(({ data }) => setUser(data))
        .catch(() => {
          localStorage.removeItem("token");
          setAuthToken(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email, password) => {
    const passwordHash = await hashPassword(password);
    const { data } = await api.post("/v1/auth/login", {
      email,
      password_hash: passwordHash,
    });
    localStorage.setItem("token", data.access_token);
    setAuthToken(data.access_token);
    setUser(data.user);
    window.location.href = "/domu";
  };

  const logout = () => {
    localStorage.removeItem("token");
    setAuthToken(null);
    setUser(null);
    window.location.href = "/prihlaseni";
  };

  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider
      value={{ user, login, logout, loading, isAuthenticated }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
