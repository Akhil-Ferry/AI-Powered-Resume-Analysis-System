import { useEffect, useState } from "react";
import api from "../api";

export default function ResumeFeedback({ resumeId, revision }) {
  const [feedback, setFeedback] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api.getAnalysisHistory(resumeId).then(data => { if (active) setHistory(data.analyses); }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [resumeId, revision]);

  async function review() {
    setBusy(true);
    setError("");
    try {
      const data = await api.getResumeFeedback(resumeId);
      setFeedback(data.feedback);
      const saved = await api.getAnalysisHistory(resumeId);
      setHistory(saved.analyses);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <section className="card">
    <h2>Resume review & history</h2>
    <button className="btn btn-primary" disabled={busy} onClick={review}>{busy ? "Reviewing..." : "Get AI resume review"}</button>
    {error && <p role="alert" className="error-text">{error}</p>}
    {feedback && <ul className="suggestion-list">{feedback.map((tip, i) => <li key={i}>{tip}</li>)}</ul>}
    <h3>Recent saved reviews</h3>
    {!history.length && <p className="muted">Your completed reviews will appear here.</p>}
    {history.map(item => <details key={item.id} className="history-item">
      <summary>{item.job_description ? `Job match: ${item.match_score}%` : "General review"} | {new Date(item.created_at).toLocaleString()}</summary>
      {item.job_description && <p className="muted">{item.job_description}</p>}
      <ul className="suggestion-list">{item.suggestions.map((tip, i) => <li key={i}>{tip}</li>)}</ul>
    </details>)}
  </section>;
}
