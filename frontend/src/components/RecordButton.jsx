import { useEffect, useRef, useState } from "react";
import { MAX_BYTES, MAX_DURATION_MS, MIN_DURATION_MS } from "../audio/mime.js";

function stopTracks(stream) {
  if (!stream) {
    return;
  }
  stream.getTracks().forEach((track) => track.stop());
}

export default function RecordButton({ mimeType, disabled, onResult, onError }) {
  const [recording, setRecording] = useState(false);
  const sessionRef = useRef(null);

  useEffect(() => {
    return () => {
      const session = sessionRef.current;
      if (!session) {
        return;
      }
      session.discarded = true;
      window.clearTimeout(session.maxTimer);
      if (session.recorder && session.recorder.state !== "inactive") {
        session.recorder.stop();
      }
      stopTracks(session.stream);
      sessionRef.current = null;
    };
  }, []);

  function fail(message) {
    const session = sessionRef.current;
    if (session) {
      session.discarded = true;
      window.clearTimeout(session.maxTimer);
      if (session.recorder && session.recorder.state !== "inactive") {
        try {
          session.recorder.stop();
        } catch {
          // ignore
        }
      }
      stopTracks(session.stream);
      sessionRef.current = null;
    }
    setRecording(false);
    onError(message);
  }

  function finishSession(session, blob) {
    stopTracks(session.stream);
    sessionRef.current = null;
    setRecording(false);

    const elapsedMs = Math.max(0, Date.now() - session.startedAt);
    if (elapsedMs < MIN_DURATION_MS) {
      onError("录音须在1到60秒之间，请重新录制。");
      return;
    }
    if (elapsedMs > MAX_DURATION_MS + 250) {
      onError("录音须在1到60秒之间，请重新录制。");
      return;
    }
    if (!blob || blob.size === 0) {
      onError("录制失败，请重试。");
      return;
    }
    if (blob.size > MAX_BYTES) {
      onError("录音文件不能超过5MB，请缩短录音后重试。");
      return;
    }
    onResult({
      blob,
      mimeType: blob.type || session.mimeType,
      durationMs: Math.min(elapsedMs, MAX_DURATION_MS),
      size: blob.size,
    });
  }

  function stopRecording() {
    const session = sessionRef.current;
    if (!session || session.stopping) {
      return;
    }
    session.stopping = true;
    window.clearTimeout(session.maxTimer);

    if (session.recorder && session.recorder.state !== "inactive") {
      try {
        session.recorder.stop();
      } catch {
        fail("录制失败，请重试。");
      }
      return;
    }

    if (session.pendingStream) {
      session.discarded = true;
      stopTracks(session.stream);
      sessionRef.current = null;
      setRecording(false);
      return;
    }

    fail("录制失败，请重试。");
  }

  async function startRecording(event) {
    if (disabled || !mimeType || sessionRef.current) {
      return;
    }
    onError("");
    onResult(null);

    const session = {
      mimeType,
      chunks: [],
      startedAt: Date.now(),
      stream: null,
      recorder: null,
      maxTimer: 0,
      discarded: false,
      stopping: false,
      pendingStream: true,
    };
    sessionRef.current = session;
    setRecording(true);

    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // capture is best-effort; stop still runs on pointerup/cancel
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      sessionRef.current = null;
      setRecording(false);
      if (error?.name === "NotAllowedError" || error?.name === "PermissionDeniedError") {
        onError("未获得麦克风权限，请在浏览器中允许后重试。");
        return;
      }
      if (error?.name === "NotFoundError") {
        onError("未找到麦克风，请检查设备后重试。");
        return;
      }
      onError("无法开始录音，请检查麦克风后重试。");
      return;
    }

    if (session.discarded || sessionRef.current !== session) {
      stopTracks(stream);
      return;
    }

    session.stream = stream;
    session.pendingStream = false;

    let recorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType });
    } catch {
      fail("当前浏览器无法按 WebM/Opus 录音，请更换 Chrome 或 Edge 后重试。");
      return;
    }

    session.recorder = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        session.chunks.push(event.data);
      }
    };
    recorder.onerror = () => {
      fail("录制失败，请重试。");
    };
    recorder.onstop = () => {
      window.clearTimeout(session.maxTimer);
      if (session.discarded) {
        stopTracks(session.stream);
        return;
      }
      const blob = new Blob(session.chunks, { type: session.mimeType });
      finishSession(session, blob);
    };

    try {
      recorder.start();
      session.startedAt = Date.now();
      session.maxTimer = window.setTimeout(() => {
        stopRecording();
      }, MAX_DURATION_MS);
    } catch {
      fail("录制失败，请重试。");
    }
  }

  function handlePointerDown(event) {
    if (event.button !== undefined && event.button !== 0) {
      return;
    }
    event.preventDefault();
    startRecording(event);
  }

  function handlePointerUp(event) {
    if (event.button !== undefined && event.button !== 0) {
      return;
    }
    event.preventDefault();
    stopRecording();
  }

  function handlePointerCancel() {
    stopRecording();
  }

  function handleLostPointerCapture() {
    if (sessionRef.current && !sessionRef.current.stopping) {
      stopRecording();
    }
  }

  return (
    <button
      type="button"
      className={`record-button${recording ? " is-recording" : ""}`}
      disabled={disabled}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
      onLostPointerCapture={handleLostPointerCapture}
      onContextMenu={(event) => event.preventDefault()}
    >
      {recording ? "正在录音，松开结束" : "按住说话"}
    </button>
  );
}
