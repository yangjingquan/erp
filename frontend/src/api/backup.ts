import { http } from "./http";

export function createBackup() {
  return http.post("/system/backup");
}

export function validateRestore(path: string, confirmationToken: string) {
  return http.post("/system/restore/validate", undefined, {
    params: { path, confirmation_token: confirmationToken },
  });
}

export function restoreBackup(path: string, confirmationToken: string) {
  return http.post("/system/restore", undefined, {
    params: { path, confirmation_token: confirmationToken },
  });
}
