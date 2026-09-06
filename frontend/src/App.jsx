import { useMemo, useState } from "react";
import { detectRecordingMimeType } from "./audio/mime.js";
import CitySelect from "./components/CitySelect.jsx";
import ExtractResult from "./components/ExtractResult.jsx";
import HealthBanner from "./components/HealthBanner.jsx";
import LocalPlayback from "./components/LocalPlayback.jsx";
import PoiList from "./components/PoiList.jsx";
import RecordButton from "./components/RecordButton.jsx";
import ReplyPanel from "./components/ReplyPanel.jsx";
import { STAGE_LABELS, useMeetupPipeline } from "./useMeetupPipeline.js";

export default function App() {
  const mimeType = useMemo(() => detectRecordingMimeType(), []);
  const [city, setCity] = useState("杭州");
  const [recording, setRecording] = useState(null);
  const pipeline = useMeetupPipeline();
  const unsupported = !mimeType;

  function handleRecordingResult(next) {
    if (!next) {
      setRecording(null);
      pipeline.beginNewRound();
      return;
    }
    setRecording(next);
    pipeline.runPipeline(next, city);
  }

  const stageLabel = STAGE_LABELS[pipeline.stage] || "";

  return (
    <main className="page">
      <h1>语音约碰面地点</h1>
      <p>
        第一版支持同一座城市内的两个人。按住按钮说话，松开后会上传录音并依次识别、提取地点、查找店铺和生成推荐。
      </p>

      <HealthBanner status={pipeline.health} error={pipeline.error} />
      <CitySelect value={city} onChange={setCity} />

      {unsupported ? (
        <p className="status status-error">
          当前浏览器不支持 WebM/Opus 录音，请更换 Chrome 或 Edge 后重试。
        </p>
      ) : (
        <RecordButton
          mimeType={mimeType}
          disabled={unsupported}
          onResult={handleRecordingResult}
          onError={(message) => {
            setRecording(null);
            pipeline.beginNewRound();
            pipeline.reportError(message);
          }}
        />
      )}

      {stageLabel ? <p className="status">{stageLabel}</p> : null}
      {pipeline.error ? <p className="status status-error">{pipeline.error}</p> : null}

      {recording ? <LocalPlayback recording={recording} /> : null}

      {pipeline.transcript ? (
        <section className="result-block">
          <h2>识别文字</h2>
          <p>{pipeline.transcript}</p>
        </section>
      ) : null}

      <ExtractResult extract={pipeline.extract} />
      <PoiList pois={pipeline.search?.pois} />
      <ReplyPanel
        reply={pipeline.reply}
        warning={pipeline.warning}
        audioUrl={pipeline.audioUrl}
        needPlayButton={pipeline.needPlayButton}
        onManualPlay={pipeline.handleManualPlay}
      />
      <audio
        ref={pipeline.audioRef}
        className={pipeline.audioUrl ? "reply-audio" : "reply-audio is-idle"}
        controls={Boolean(pipeline.audioUrl)}
      />
    </main>
  );
}
