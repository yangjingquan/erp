import { http } from "./http";

export interface SliderCaptchaChallenge {
  challenge_id: string;
  background_image: string;
  piece_image: string;
  piece_top: number;
  board_width: number;
  board_height: number;
  piece_size: number;
}

function requireSuccess(response: { data: { code?: number; msg?: string } }) {
  if (response.data.code !== 0) {
    throw new Error(response.data.msg || "请求失败，请重试");
  }
}

export async function createSliderCaptcha() {
  const response = await http.get("/auth/captcha/challenge");
  requireSuccess(response);
  return response.data.data as SliderCaptchaChallenge;
}

export async function verifySliderCaptcha(challengeId: string, offsetX: number) {
  const response = await http.post("/auth/captcha/verify", {
    challenge_id: challengeId,
    offset_x: offsetX,
  });
  requireSuccess(response);
  return response.data.data.captcha_token as string;
}

export function changePassword(old_password: string, new_password: string) {
  return http.post("/auth/change-password", { old_password, new_password });
}
export async function register(username: string, password: string, captchaToken: string) {
  const response = await http.post("/auth/register", {
    username,
    password,
    captcha_token: captchaToken,
  });
  requireSuccess(response);
  return response;
}
export function listOrganizations() { return http.get("/auth/organizations"); }
export function switchOrganization(orgId: string) { return http.post(`/auth/switch-organization/${orgId}`); }
