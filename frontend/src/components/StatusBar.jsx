import { useEffect, useState } from "react";
import api from "../api";

export default function StatusBar() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api
      .health()
      .then(setStatus)
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <div className="status-bar status-bar-error">
        Backend unreachable - make sure the Flask API is running (see README).
      </div>
    );
  }

  if (!status) {
    return <div className="status-bar">Checking backend status...</div>;
  }

  return (
    <div className={`status-bar ${status.openai_enabled ? "status-bar-openai" : "status-bar-local"}`}>
      {status.openai_enabled
        ? "OpenAI API key detected - using GPT-powered embeddings & suggestions."
        : "Running on free local embeddings & heuristic suggestions. Add OPENAI_API_KEY in backend/.env to upgrade."}
    </div>
  );
}
