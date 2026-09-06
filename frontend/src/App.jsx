import { useEffect, useState } from "react";
import { getHealth } from "./api.js";

export default function App() {
  const [backendStatus, setBackendStatus] = useState("checking");

  useEffect(() => {
    let cancelled = false;

    getHealth()
      .then((response) => {
        if (cancelled) {
          return;
        }
        const status = response.data?.data?.status;
        setBackendStatus(status === "ok" ? "ok" : "error");
      })
      .catch(() => {
        if (!cancelled) {
          setBackendStatus("offline");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const statusText = {
    checking: "正在检查后端…",
    ok: "后端健康检查正常",
    error: "后端已响应，但健康检查结果异常",
    offline: "无法连接后端（可先启动 http://localhost:8003）",
  }[backendStatus];

  return (
    <main className="page">
      <h1>语音约碰面地点</h1>
      <p>第一版支持同一座城市内的两个人。默认城市：杭州。</p>
      <p className={`status status-${backendStatus}`}>{statusText}</p>
      <p className="hint">录音与找店功能尚未接入，本页仅用于确认前后端可以打开。</p>
    </main>
  );
}
