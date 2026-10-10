<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ArrowRight, Refresh } from "@element-plus/icons-vue";

import { createSliderCaptcha, verifySliderCaptcha, type SliderCaptchaChallenge } from "../api/auth";

withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false });
const modelValue = defineModel<string>({ default: "" });

type CaptchaStatus = "loading" | "ready" | "dragging" | "verifying" | "success" | "error";

const challenge = ref<SliderCaptchaChallenge | null>(null);
const status = ref<CaptchaStatus>("loading");
const offsetX = ref(0);
const errorText = ref("");
const sliderTrack = ref<HTMLDivElement | null>(null);
const pointerStartX = ref(0);
const offsetStart = ref(0);

const maxOffset = computed(() => challenge.value
  ? challenge.value.board_width - challenge.value.piece_size
  : 0);
const progress = computed(() => maxOffset.value ? offsetX.value / maxOffset.value : 0);
const pieceStyle = computed(() => {
  if (!challenge.value) return {};
  const item = challenge.value;
  return {
    left: `${offsetX.value / item.board_width * 100}%`,
    top: `${item.piece_top / item.board_height * 100}%`,
    width: `${item.piece_size / item.board_width * 100}%`,
    height: `${item.piece_size / item.board_height * 100}%`,
  };
});
const handleStyle = computed(() => ({
  left: `calc(${progress.value * 100}% - ${progress.value * 48}px)`,
}));
const statusLabel = computed(() => {
  if (status.value === "loading") return "正在加载验证";
  if (status.value === "dragging") return "请将滑块拖至拼图缺口";
  if (status.value === "verifying") return "正在验证…";
  if (status.value === "success") return "验证通过";
  if (status.value === "error") return errorText.value || "验证失败，请刷新后重试";
  return "拖动滑块完成验证";
});

async function loadChallenge() {
  modelValue.value = "";
  challenge.value = null;
  offsetX.value = 0;
  errorText.value = "";
  status.value = "loading";
  try {
    challenge.value = await createSliderCaptcha();
    status.value = "ready";
  } catch {
    errorText.value = "验证加载失败，请刷新重试";
    status.value = "error";
  }
}

function moveDrag(event: PointerEvent) {
  if (status.value !== "dragging" || !challenge.value || !sliderTrack.value) return;
  const width = sliderTrack.value.getBoundingClientRect().width;
  if (!width) return;
  const delta = (event.clientX - pointerStartX.value) / width * challenge.value.board_width;
  offsetX.value = Math.max(0, Math.min(maxOffset.value, offsetStart.value + delta));
}

async function verify() {
  if (!challenge.value || status.value !== "ready") return;
  status.value = "verifying";
  try {
    modelValue.value = await verifySliderCaptcha(challenge.value.challenge_id, offsetX.value);
    status.value = "success";
  } catch (error) {
    const message = error as { message?: string };
    errorText.value = message.message || "滑块位置不正确，请刷新后重试";
    status.value = "error";
  }
}

function stopDrag() {
  if (status.value !== "dragging") return;
  window.removeEventListener("pointermove", moveDrag);
  window.removeEventListener("pointerup", stopDrag);
  window.removeEventListener("pointercancel", cancelDrag);
  status.value = "ready";
  void verify();
}

function cancelDrag() {
  if (status.value !== "dragging") return;
  window.removeEventListener("pointermove", moveDrag);
  window.removeEventListener("pointerup", stopDrag);
  window.removeEventListener("pointercancel", cancelDrag);
  status.value = "ready";
}

function startDrag(event: PointerEvent) {
  if (status.value !== "ready" || !sliderTrack.value) return;
  event.preventDefault();
  pointerStartX.value = event.clientX;
  offsetStart.value = offsetX.value;
  status.value = "dragging";
  window.addEventListener("pointermove", moveDrag);
  window.addEventListener("pointerup", stopDrag, { once: true });
  window.addEventListener("pointercancel", cancelDrag, { once: true });
}

function moveByKeyboard(event: KeyboardEvent) {
  if (status.value !== "ready") return;
  if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
    event.preventDefault();
    const step = event.shiftKey ? 10 : 3;
    offsetX.value = Math.max(0, Math.min(maxOffset.value, offsetX.value + (event.key === "ArrowRight" ? step : -step)));
  } else if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    void verify();
  }
}

onMounted(() => { void loadChallenge(); });
onBeforeUnmount(() => {
  window.removeEventListener("pointermove", moveDrag);
  window.removeEventListener("pointerup", stopDrag);
  window.removeEventListener("pointercancel", cancelDrag);
});

defineExpose({ reset: loadChallenge });
</script>

<template>
  <div class="slider-captcha" :aria-busy="status === 'loading' || status === 'verifying'">
    <div class="captcha-title"><strong>滑块验证</strong><span>拖动黄色拼图块，对准蓝色缺口</span></div>
    <div class="captcha-board" :style="{ aspectRatio: `${challenge?.board_width || 320} / ${challenge?.board_height || 144}` }">
      <img v-if="challenge" class="captcha-background" :src="challenge.background_image" alt="滑块拼图验证图" draggable="false" />
      <img
        v-if="challenge"
        class="captcha-piece"
        :class="{ 'is-moving': status === 'dragging', 'is-verified': status === 'success' }"
        :src="challenge.piece_image"
        :style="pieceStyle"
        alt="待移动拼图块"
        draggable="false"
      />
      <div v-if="status === 'loading'" class="captcha-loading">正在准备安全验证…</div>
      <button
        class="captcha-refresh"
        type="button"
        aria-label="刷新滑块验证"
        :disabled="status === 'loading' || status === 'verifying' || disabled"
        @click="loadChallenge"
      ><el-icon><Refresh /></el-icon></button>
    </div>
    <div ref="sliderTrack" class="slider-track">
      <div class="slider-rail" :class="{ 'is-success': status === 'success' }" :style="{ width: `${status === 'success' ? 100 : progress * 100}%` }"></div>
      <button
        class="slider-handle"
        :class="{ 'is-dragging': status === 'dragging', 'is-success': status === 'success' }"
        type="button"
        role="slider"
        aria-label="滑块验证"
        aria-valuemin="0"
        :aria-valuemax="maxOffset"
        :aria-valuenow="Math.round(offsetX)"
        :aria-valuetext="statusLabel"
        :disabled="status === 'loading' || status === 'verifying' || status === 'success' || status === 'error' || disabled"
        :style="handleStyle"
        @pointerdown="startDrag"
        @keydown="moveByKeyboard"
      ><el-icon><ArrowRight /></el-icon></button>
      <span class="slider-hint" :class="{ 'is-success': status === 'success', 'is-error': status === 'error' }" aria-live="polite">{{ statusLabel }}</span>
    </div>
  </div>
</template>

<style scoped>
.slider-captcha { width: 100%; max-width: 320px; margin: 0 0 19px; }
.captcha-title { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.captcha-title strong { color: #5a4034; font-size: 12px; font-weight: 750; }
.captcha-title span { color: #8b6a59; font-size: 11px; }
.captcha-board { position: relative; width: 100%; overflow: hidden; border: 2px solid #557b91; border-radius: 11px; background: #d8e6ed; box-shadow: 0 4px 12px rgba(55, 86, 105, .2); }
.captcha-background { display: block; width: 100%; height: 100%; object-fit: fill; user-select: none; }
.captcha-piece { position: absolute; z-index: 2; filter: drop-shadow(0 3px 5px rgba(22, 34, 48, .5)); pointer-events: none; user-select: none; }
.captcha-piece.is-moving { filter: drop-shadow(0 5px 8px rgba(22, 34, 48, .65)); }
.captcha-piece.is-verified { filter: drop-shadow(0 2px 4px rgba(45, 130, 103, .48)); }
.captcha-loading { position: absolute; inset: 0; display: grid; place-items: center; background: rgba(248, 247, 244, .86); color: #82776e; font-size: 12px; }
.captcha-refresh { position: absolute; z-index: 2; top: 8px; right: 8px; display: grid; width: 32px; height: 32px; place-items: center; border: 1px solid rgba(255,255,255,.88); border-radius: 8px; background: #fffaf4; box-shadow: 0 2px 6px rgba(35, 30, 27, .18); color: #744b39; cursor: pointer; }
.captcha-refresh:disabled { cursor: not-allowed; opacity: .55; }
.slider-track { position: relative; height: 48px; margin-top: 10px; overflow: hidden; border: 1px solid #ddc6b8; border-radius: 10px; background: #f6eee8; touch-action: none; user-select: none; }
.slider-rail { position: absolute; inset: 0 auto 0 0; border-radius: 9px; background: #df946f; transition: width .08s linear; }
.slider-rail.is-success { background: #b4d8c5; }
.slider-handle { position: absolute; top: -1px; z-index: 1; display: grid; width: 48px; height: 48px; place-items: center; border: 2px solid #fff8f1; border-radius: 10px; background: #b95639; box-shadow: 0 3px 8px rgba(115, 55, 34, .34); color: #fff; cursor: grab; touch-action: none; }
.slider-handle:disabled { cursor: default; }
.slider-handle.is-dragging { cursor: grabbing; }
.slider-handle.is-success { border-color: #f5fff9; background: #32866b; color: #fff; }
.slider-hint { position: absolute; inset: 0; display: grid; place-items: center; padding: 0 52px; color: #624d41; font-size: 12px; font-weight: 650; pointer-events: none; }
.slider-hint.is-success { color: #25644f; }
.slider-hint.is-error { color: #a8442f; }
.slider-handle:focus-visible, .captcha-refresh:focus-visible { outline: 3px solid rgba(198, 109, 75, .48); outline-offset: 2px; }
</style>
