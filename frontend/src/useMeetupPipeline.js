import { useEffect, useRef, useState } from "react";
import {
  extractMeetup,
  fetchAudioBlob,
  finalizeMeetup,
  getHealth,
  isCanceled,
  readApiError,
  recognizeAudio,
  searchMeetup,
  uploadAudio,
} from "./api.js";

export const STAGE_LABELS = {
  health: "检查服务中",
  upload: "上传中",
  asr: "识别中",
  extract: "提取中",
  search: "找店中",
  finalize: "生成推荐中",
};

export function useMeetupPipeline() {
  const runIdRef = useRef(0);
  const abortRef = useRef(null);
  const audioRef = useRef(null);
  const objectUrlRef = useRef("");

  const [health, setHealth] = useState("");
  const [stage, setStage] = useState("");
  const [error, setError] = useState("");
  const [transcript, setTranscript] = useState("");
  const [extract, setExtract] = useState(null);
  const [search, setSearch] = useState(null);
  const [reply, setReply] = useState("");
  const [warning, setWarning] = useState("");
  const [audioUrl, setAudioUrl] = useState(null);
  const [needPlayButton, setNeedPlayButton] = useState(false);

  function stopAudio() {
    const element = audioRef.current;
    if (element) {
      element.pause();
      element.removeAttribute("src");
      element.load();
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = "";
    }
    setNeedPlayButton(false);
  }

  function abortRun() {
    runIdRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    stopAudio();
  }

  function resetResults() {
    setTranscript("");
    setExtract(null);
    setSearch(null);
    setReply("");
    setWarning("");
    setAudioUrl(null);
    setStage("");
  }

  function beginNewRound() {
    abortRun();
    resetResults();
    setError("");
  }

  function reportError(message) {
    setError(message);
    setStage("");
  }

  async function playFromUrl(url, signal) {
    const blob = await fetchAudioBlob(url, { signal });
    if (signal?.aborted) {
      return;
    }
    stopAudio();
    const objectUrl = URL.createObjectURL(blob);
    objectUrlRef.current = objectUrl;
    const element = audioRef.current;
    if (!element) {
      return;
    }
    element.src = objectUrl;
    try {
      await element.play();
      setNeedPlayButton(false);
    } catch {
      setNeedPlayButton(true);
    }
  }

  async function handleManualPlay() {
    const element = audioRef.current;
    if (!element) {
      return;
    }
    try {
      await element.play();
      setNeedPlayButton(false);
    } catch {
      setNeedPlayButton(true);
    }
  }

  async function runPipeline(recording, city) {
    beginNewRound();
    const runId = runIdRef.current;
    const controller = new AbortController();
    abortRef.current = controller;
    const signal = controller.signal;
    const alive = () => runId === runIdRef.current && !signal.aborted;
    const selectedCity = city.trim() || "杭州";
    let currentStage = "health";

    try {
      setStage("health");
      const healthData = await getHealth({ signal });
      if (!alive()) {
        return;
      }
      setHealth(healthData.status || "");
      if (healthData.status !== "ok") {
        setError("后端服务暂不可用，请稍后重试。");
        setStage("");
        return;
      }

      currentStage = "upload";
      setStage("upload");
      const file = new File([recording.blob], "meetup-recording.webm", {
        type: recording.mimeType || "audio/webm",
      });
      const uploaded = await uploadAudio(file, { signal });
      if (!alive()) {
        return;
      }
      const audioId = uploaded.audio_id;
      if (!audioId) {
        setError("上传失败，请重试。");
        setStage("");
        return;
      }

      currentStage = "asr";
      setStage("asr");
      const asr = await recognizeAudio(audioId, { signal });
      if (!alive()) {
        return;
      }
      setTranscript(asr.text || "");

      currentStage = "extract";
      setStage("extract");
      const slots = await extractMeetup(asr.text, selectedCity, { signal });
      if (!alive()) {
        return;
      }
      setExtract(slots);

      currentStage = "search";
      setStage("search");
      const found = await searchMeetup(
        {
          city_a: slots.city_a,
          address_a: slots.address_a,
          city_b: slots.city_b,
          address_b: slots.address_b,
          category: slots.category,
        },
        { signal },
      );
      if (!alive()) {
        return;
      }
      setSearch(found);

      currentStage = "finalize";
      setStage("finalize");
      const final = await finalizeMeetup(found.search_id, { signal });
      if (!alive()) {
        return;
      }
      setReply(final.reply_text || "");
      setWarning(final.warning || "");
      setAudioUrl(final.audio_url || null);
      setStage("");

      if (final.audio_url) {
        try {
          await playFromUrl(final.audio_url, signal);
        } catch (audioError) {
          if (!alive() || isCanceled(audioError)) {
            return;
          }
          setWarning((current) => current || "语音加载失败，已保留文字推荐。");
        }
      }
    } catch (error) {
      if (!alive() || isCanceled(error)) {
        return;
      }
      const parsed = readApiError(error, currentStage);
      setError(parsed.message);
      setStage("");
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    getHealth({ signal: controller.signal })
      .then((data) => setHealth(data.status || ""))
      .catch((error) => {
        if (isCanceled(error)) {
          return;
        }
        const parsed = readApiError(error, "health");
        setHealth("");
        setError(parsed.message);
      });
    return () => {
      controller.abort();
      abortRun();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount/unmount only
  }, []);

  return {
    health,
    stage,
    error,
    transcript,
    extract,
    search,
    reply,
    warning,
    audioUrl,
    needPlayButton,
    audioRef,
    beginNewRound,
    reportError,
    runPipeline,
    handleManualPlay,
  };
}
