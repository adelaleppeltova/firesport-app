import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export const setAuthToken = (token) => {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common["Authorization"];
  }
};

// separátní klient bez interceptoru pro refresh
const refreshApi = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

let isRefreshing = false;
let pending = [];

const subscribe = (cb) => pending.push(cb);
const notifyAll = (token) => {
  pending.forEach((cb) => cb(token));
  pending = [];
};

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const url = original?.url || "";

    if (status !== 401) return Promise.reject(error);

    // Nezkoušej refresh na auth endpointy a pokud už byl retry proveden
    const isAuthEndpoint =
      url.includes("/auth/login") ||
      url.includes("/auth/register") ||
      url.includes("/auth/refresh");

    if (isAuthEndpoint || original._retry) {
      return Promise.reject(error);
    }

    original._retry = true;

    if (isRefreshing) {
      // počkat na probíhající refresh
      return new Promise((resolve, reject) => {
        subscribe((newToken) => {
          if (newToken) {
            if (original.headers)
              original.headers["Authorization"] = `Bearer ${newToken}`;
            resolve(api(original));
          } else {
            reject(error);
          }
        });
      });
    }

    isRefreshing = true;
    try {
      const r = await refreshApi.post("/auth/refresh");
      const access = r.data?.access_token;
      setAuthToken(access);
      notifyAll(access);
      return api(original);
    } catch (e) {
      setAuthToken(null);
      notifyAll(null);
      return Promise.reject(e);
    } finally {
      isRefreshing = false;
    }
  }
);

export default api;
