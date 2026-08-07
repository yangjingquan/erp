import { http } from "./http";

export function changePassword(old_password: string, new_password: string) {
  return http.post("/auth/change-password", { old_password, new_password });
}
