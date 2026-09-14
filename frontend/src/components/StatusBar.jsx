import { useEffect, useState } from "react";
import api from "../api";

export default function StatusBar() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const check = () => api.health().then(data => { if (active) { setStatus(data); setError(""); } })
      .catch(err => { if (active) setError(err.message); });
    check();
    const timer = setInterval(check, 30000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  if (error) return <div role="status" className="status-bar status-bar-error">{error}</div>;
  if (!status) return <div className="status-bar">Connecting...</div>;
  return <div role="status" className={`status-bar ${status.status === "ok" ? "status-bar-openai" : "status-bar-error"}`}>
    {status.status === "ok" ? "Connected | Resume analysis ready" : status.message}
  </div>;
}
