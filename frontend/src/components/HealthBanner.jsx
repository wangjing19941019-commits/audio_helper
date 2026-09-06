export default function HealthBanner({ status, error }) {
  if (error && !status) {
    return null;
  }
  if (status === "ok") {
    return <p className="status status-ok">后端服务可用</p>;
  }
  if (status) {
    return <p className="status">{`后端状态：${status}`}</p>;
  }
  return <p className="status">正在检查后端服务…</p>;
}
