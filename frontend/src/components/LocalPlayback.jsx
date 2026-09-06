import { useEffect, useState } from "react";
import { recordingFileExtension } from "../audio/mime.js";

function formatDuration(durationMs) {
  const seconds = Math.max(1, Math.round(durationMs / 1000));
  return `${seconds} 秒`;
}

function formatSize(size) {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}

export default function LocalPlayback({ recording }) {
  const [objectUrl, setObjectUrl] = useState("");
  const filename = `meetup-recording.${recordingFileExtension(recording.mimeType)}`;

  useEffect(() => {
    const url = URL.createObjectURL(recording.blob);
    setObjectUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [recording.blob]);

  function handleDownload(event) {
    event.preventDefault();
    const url = URL.createObjectURL(recording.blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <section className="playback">
      <h2>本地试听</h2>
      <p>
        {formatDuration(recording.durationMs)}，{formatSize(recording.size)}
        {recording.mimeType ? `，${recording.mimeType}` : ""}
      </p>
      {objectUrl ? <audio controls src={objectUrl} /> : null}
      <button type="button" className="download-link" onClick={handleDownload}>
        下载本次录音
      </button>
    </section>
  );
}
