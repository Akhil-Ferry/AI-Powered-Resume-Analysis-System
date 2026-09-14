import { useState } from "react";
import api from "../api";
import BadgeList from "./BadgeList";

export default function ResumeUploader({ resume, onResumeReady }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

  async function handleFile(file) {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.uploadResumeFile(file);
      onResumeReady(data.resume);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handlePasteSubmit() {
    if (!text.trim()) {
      setError("Paste some resume text first.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await api.uploadResumeText(text);
      onResumeReady(data.resume);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card">
      <div className="card-header">
        <span className="step-badge">1</span>
        <h2>Add Your Resume</h2>
      </div>

      <div
        className={`dropzone ${dragOver ? "dropzone-active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFile(e.dataTransfer.files?.[0]);
        }}
      >
        <p>Drag & drop a PDF / DOCX / TXT resume here</p>
        <p className="muted">or</p>
        <label className="file-input-label">
          Choose File
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            hidden
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </label>
      </div>

      <div className="or-divider">or paste resume text</div>

      <textarea
        rows={6}
        placeholder="Paste your resume text here..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button className="btn btn-primary" onClick={handlePasteSubmit} disabled={loading}>
        {loading ? "Processing..." : "Analyze Pasted Resume"}
      </button>

      {error && <p className="error-text">{error}</p>}

      {resume && (
        <div className="result-box">
          <p className="result-title">Resume ready (ID {resume.id})</p>
          <p>
            <strong>Skills detected:</strong>
          </p>
          <BadgeList items={resume.skills} />
          <p className="muted small">
            {resume.emails?.length ? `Email: ${resume.emails.join(", ")}` : ""}
            {resume.phones?.length ? ` | Phone: ${resume.phones.join(", ")}` : ""}
          </p>
          <p className="muted small">Embedding provider: {resume.embedding_source}</p>
        </div>
      )}
    </section>
  );
}
