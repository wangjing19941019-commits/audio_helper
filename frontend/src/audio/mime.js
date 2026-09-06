const CANDIDATES = ["audio/webm;codecs=opus", "audio/webm"];

export const MAX_DURATION_MS = 60_000;
export const MIN_DURATION_MS = 1_000;
export const MAX_BYTES = 5 * 1024 * 1024;

export function detectRecordingMimeType() {
  if (typeof MediaRecorder === "undefined" || typeof MediaRecorder.isTypeSupported !== "function") {
    return null;
  }
  return CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

export function recordingFileExtension(mimeType) {
  return "webm";
}
