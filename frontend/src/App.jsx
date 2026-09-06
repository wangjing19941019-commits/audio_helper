import { useMemo, useState } from "react";
import { detectRecordingMimeType } from "./audio/mime.js";
import CitySelect from "./components/CitySelect.jsx";
import LocalPlayback from "./components/LocalPlayback.jsx";
import RecordButton from "./components/RecordButton.jsx";

export default function App() {
  const mimeType = useMemo(() => detectRecordingMimeType(), []);
  const [city, setCity] = useState("杭州");
  const [recording, setRecording] = useState(null);
  const [error, setError] = useState("");

  const unsupported = !mimeType;

  return (
    <main className="page">
      <h1>语音约碰面地点</h1>
      <p>第一版支持同一座城市内的两个人。按住按钮说话，松开结束。本轮只做本地录音，不调用找店接口。</p>

      <CitySelect value={city} onChange={setCity} />

      {unsupported ? (
        <p className="status status-error">
          当前浏览器不支持 WebM/Opus 录音，请更换 Chrome 或 Edge 后重试。
        </p>
      ) : (
        <RecordButton
          mimeType={mimeType}
          disabled={unsupported}
          onResult={setRecording}
          onError={setError}
        />
      )}

      {error ? <p className="status status-error">{error}</p> : null}

      {recording ? <LocalPlayback recording={recording} /> : null}
    </main>
  );
}
