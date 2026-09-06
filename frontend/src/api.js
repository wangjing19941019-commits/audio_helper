import axios from "axios";

export const API_BASE = "http://localhost:8003";

export const TIMEOUTS = {
  health: 8_000,
  upload: 15_000,
  asr: 25_000,
  extract: 20_000,
  search: 22_000,
  finalize: 38_000,
  audio: 15_000,
};

export const api = axios.create({
  baseURL: API_BASE,
});

export function isCanceled(error) {
  return error?.code === "ERR_CANCELED" || error?.name === "CanceledError";
}

export function isTimeoutError(error) {
  return error?.code === "ECONNABORTED" || String(error?.message || "").toLowerCase().includes("timeout");
}

export function isNetworkError(error) {
  return !error?.response && !isTimeoutError(error) && !isCanceled(error);
}

export function readApiError(error, fallbackStage) {
  const body = error?.response?.data;
  if (body && typeof body === "object" && body.error?.message) {
    return {
      message: body.error.message,
      code: body.error.code,
      stage: body.error.stage || fallbackStage,
    };
  }
  if (isTimeoutError(error)) {
    return { message: "请求超时，请稍后重试。", code: "TIMEOUT", stage: fallbackStage };
  }
  if (isNetworkError(error)) {
    return { message: "网络连接失败，请检查网络后重试。", code: "NETWORK", stage: fallbackStage };
  }
  return { message: "请求失败，请稍后重试。", code: "REQUEST_FAILED", stage: fallbackStage };
}

function businessData(response) {
  return response.data.data;
}

export async function getHealth(config = {}) {
  const response = await api.get("/health", { timeout: TIMEOUTS.health, ...config });
  return businessData(response);
}

export async function uploadAudio(file, config = {}) {
  const form = new FormData();
  form.append("file", file, file.name || "meetup-recording.webm");
  const response = await api.post("/upload", form, {
    timeout: TIMEOUTS.upload,
    ...config,
  });
  return businessData(response);
}

export async function recognizeAudio(audioId, config = {}) {
  const response = await api.post(
    "/asr",
    { audio_id: audioId },
    { timeout: TIMEOUTS.asr, ...config },
  );
  return businessData(response);
}

export async function extractMeetup(text, city, config = {}) {
  const response = await api.post(
    "/extract",
    { text, city },
    { timeout: TIMEOUTS.extract, ...config },
  );
  return businessData(response);
}

export async function searchMeetup(slots, config = {}) {
  const response = await api.post("/search", slots, { timeout: TIMEOUTS.search, ...config });
  return businessData(response);
}

export async function finalizeMeetup(searchId, config = {}) {
  const response = await api.post(
    "/finalize",
    { search_id: searchId },
    { timeout: TIMEOUTS.finalize, ...config },
  );
  return businessData(response);
}

export async function fetchAudioBlob(audioUrl, config = {}) {
  const response = await api.get(audioUrl, {
    ...config,
    responseType: "blob",
    timeout: config.timeout ?? TIMEOUTS.audio,
    validateStatus: () => true,
  });
  const contentType = String(response.headers["content-type"] || "");
  const looksJson = contentType.includes("application/json");
  if (response.status >= 400 || looksJson) {
    let body = {};
    try {
      const text = await response.data.text();
      body = JSON.parse(text);
    } catch {
      body = {};
    }
    const error = new Error(body.error?.message || "音频下载失败。");
    error.response = { data: body };
    throw error;
  }
  return response.data;
}
