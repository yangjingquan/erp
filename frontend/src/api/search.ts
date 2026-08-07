import { http } from "./http";

export function globalSearch(keyword: string) {
  return http.get("/search", { params: { q: keyword } });
}
