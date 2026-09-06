import { useEffect, useMemo } from "react";
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
  const objectUrl = useMemo(() => URL.createObjectURL(recording.blob), [recording.blob]);
  const filename = `meetup-recording.${recordingFileExtension(recording.mimeType)}`;

  useEffect(() => {
    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [objectUrl]);

  return (
    <section className="playback">
      <h2>本地试听</h2>
      <p>
        {formatDuration(recording.durationMs)}，{formatSize(recording.size)}
        {recording.mimeType ? `，${recording.mimeType}` : ""}
      </p>
      <audio controls src={objectUrl} />
      <a className="download-link" href={objectUrl} download={filename}>
        下载录音文件（供后续上传测试）
      </a>
    </section>
  );
}
