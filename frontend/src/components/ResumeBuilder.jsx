import { useState } from "react";
import api from "../api";

const fields = [
  ["name", "Full name", false], ["headline", "Professional headline", false],
  ["email", "Email", false], ["phone", "Phone", false], ["location", "Location", false],
  ["summary", "Professional summary", true], ["skills", "Skills", true],
  ["experience", "Experience: roles, dates and achievement bullets", true],
  ["projects", "Projects: technologies and outcomes", true],
  ["education", "Education: qualifications, institutions and dates", true],
];
const empty = Object.fromEntries(fields.map(([key]) => [key, ""]));

export default function ResumeBuilder({ resume, onSaved }) {
  const [profile, setProfile] = useState(resume?.profile || empty);
  const [text, setText] = useState(resume?.text || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const structured = !resume || Boolean(resume.profile);
  const preview = structured
    ? [profile.name, profile.headline, [profile.email, profile.phone, profile.location].filter(Boolean).join(" | "),
       ...["summary", "skills", "experience", "projects", "education"].flatMap(key => profile[key] ? ["", key.toUpperCase(), profile[key]] : [])].join("\n")
    : text;

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = structured ? { profile } : { text };
      const data = resume ? await api.updateResume(resume.id, payload) : await api.buildResume(profile);
      onSaved(data.resume);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function download() {
    const url = URL.createObjectURL(new Blob([preview], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "resume.txt";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="card">
      <h2>{resume ? "Edit resume" : "Build your resume"}</h2>
      <p className="muted">Use your real experience and achievements. Save to prepare your resume for AI analysis.</p>
      <form onSubmit={save}>
        {structured ? <div className="builder-grid">{fields.map(([key, label, multiline]) =>
          <label key={key} className={multiline ? "wide" : ""}>
            {label}
            {multiline
              ? <textarea rows={key === "experience" ? 6 : 3} maxLength={10000} value={profile[key] || ""} onChange={e => setProfile({ ...profile, [key]: e.target.value })} />
              : <input type={key === "email" ? "email" : "text"} required={key === "name"} maxLength={500} value={profile[key] || ""} onChange={e => setProfile({ ...profile, [key]: e.target.value })} />}
          </label>)}</div>
          : <label>Resume content<textarea rows={18} maxLength={40000} value={text} onChange={e => setText(e.target.value)} /></label>}
        <div className="actions">
          <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Saving and preparing analysis..." : "Save resume"}</button>
          <button className="btn" type="button" disabled={!preview.trim()} onClick={download}>Download TXT</button>
          <button className="btn" type="button" disabled={!preview.trim()} onClick={() => window.print()}>Print / Save PDF</button>
        </div>
      </form>
      {error && <p role="alert" className="error-text">{error}</p>}
      <div className="resume-preview"><h3>Preview</h3><pre>{preview || "Your resume preview will appear here."}</pre></div>
    </section>
  );
}
