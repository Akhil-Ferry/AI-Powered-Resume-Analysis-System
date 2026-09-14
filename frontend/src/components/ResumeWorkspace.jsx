import { useCallback, useEffect, useState } from "react";
import api from "../api";
import ResumeBuilder from "./ResumeBuilder";
import ResumeUploader from "./ResumeUploader";

export default function ResumeWorkspace({ resume, onResumeReady }) {
  const [mode, setMode] = useState("upload");
  const [saved, setSaved] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await api.listResumes(page);
      setSaved(data.resumes);
      setPages(data.pages || 1);
      setError("");
    } catch (err) { setError(err.message); }
  }, [page]);

  useEffect(() => {
    let active = true;
    api.listResumes(page).then(data => {
      if (active) { setSaved(data.resumes); setPages(data.pages || 1); setError(""); }
    }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [page]);

  function ready(value) {
    onResumeReady(value);
    refresh();
    setMode("edit");
  }

  async function select(id) {
    setBusy(true);
    try {
      ready(await api.getResume(id));
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function remove() {
    if (!window.confirm("Delete this saved resume and its analysis history?")) return;
    setBusy(true);
    try {
      await api.deleteResume(resume.id);
      onResumeReady(null);
      setMode("upload");
      refresh();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <>
      <section className="card library">
        <h2>Your resumes</h2>
        <p className="muted">Choose a saved resume or create a new one.</p>
        <div className="actions">
          <label className="resume-picker">Saved resumes
            <select disabled={busy} value={saved.some(r => r.id === resume?.id) ? resume.id : ""} onChange={e => e.target.value && select(Number(e.target.value))}>
              <option value="">Select a resume</option>
              {saved.map(r => <option key={r.id} value={r.id}>{r.filename || r.text_preview.split("\n")[0] || "Resume"} | #{r.id}</option>)}
            </select>
          </label>
          <button className="btn" onClick={refresh}>Refresh</button>
          {resume && <button className="btn btn-danger" disabled={busy} onClick={remove}>Delete selected</button>}
        </div>
        {pages > 1 && <div className="actions">
          <button className="btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span>Page {page} of {pages}</span>
          <button className="btn" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
        </div>}
        {error && <p role="alert" className="error-text">{error}</p>}
        <div className="tabs" aria-label="Resume input">
          <button className={mode === "upload" ? "tab active" : "tab"} onClick={() => setMode("upload")}>Upload / paste</button>
          <button className={mode === "build" ? "tab active" : "tab"} onClick={() => setMode("build")}>Build new</button>
          {resume && <button className={mode === "edit" ? "tab active" : "tab"} onClick={() => setMode("edit")}>Edit selected #{resume.id}</button>}
        </div>
      </section>
      {mode === "upload" && <ResumeUploader resume={resume} onResumeReady={ready} />}
      {mode === "build" && <ResumeBuilder key="new" onSaved={ready} />}
      {mode === "edit" && resume && <ResumeBuilder key={resume.id + resume.updated_at} resume={resume} onSaved={ready} />}
      {resume && <p className="active-resume">Analyzing resume #{resume.id}: {resume.filename || resume.text_preview.split("\n")[0]}</p>}
    </>
  );
}
