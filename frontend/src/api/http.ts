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
  return config;
});

http.interceptors.response.use(
  (response) => response,
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
