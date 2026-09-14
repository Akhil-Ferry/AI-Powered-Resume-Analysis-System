import { useState } from "react";
import api from "../api";
import ScoreRing from "./ScoreRing";
import BadgeList from "./BadgeList";

export default function JobAnalyzer({ resumeId }) {
  const [jobDescription, setJobDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function handleAnalyze() {
    if (!resumeId) {
      setError("Add a resume first (step 1).");
      return;
    }
    if (!jobDescription.trim()) {
      setError("Paste a job description first.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.analyze(resumeId, jobDescription);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card">
      <div className="card-header">
        <span className="step-badge">2</span>
        <h2>Analyze Against a Job Description</h2>
      </div>

      <textarea
        rows={7}
        placeholder="Paste a job description here..."
        value={jobDescription}
        onChange={(e) => setJobDescription(e.target.value)}
      />
      <button className="btn btn-primary" onClick={handleAnalyze} disabled={loading}>
        {loading ? "Analyzing..." : "Analyze Match"}
      </button>

      {error && <p className="error-text">{error}</p>}

      {result && (
        <div className="result-box">
          <div className="analyze-summary">
            <ScoreRing score={result.match_score} />
            <div>
              <p className="result-title">Semantic Match Score</p>
              <p className="muted small">Suggestions powered by: {result.suggestions_source}</p>
            </div>
          </div>

          <p>
            <strong>Matched skills</strong>
          </p>
          <BadgeList items={result.matched_skills} tone="success" />

          <p>
            <strong>Missing skills</strong>
          </p>
          <BadgeList items={result.missing_skills} tone="warning" />

          <p>
            <strong>Suggestions</strong>
          </p>
          <ul className="suggestion-list">
            {result.suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
