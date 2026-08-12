import axios from "axios";

import { useAuthStore } from "../stores/auth";

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8085/api",
  timeout: 15000,
});

http.interceptors.request.use((config) => {
  const token = useAuthStore().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (["post", "put", "patch", "delete"].includes(String(config.method).toLowerCase()) && !config.headers["Idempotency-Key"]) {
    config.headers["Idempotency-Key"] = typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => {
    if (response.data?.code === 401) {
      useAuthStore().logout();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return response;
  },
  async (error) => {
    if (error.response?.status === 401) {
      useAuthStore().logout();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);
