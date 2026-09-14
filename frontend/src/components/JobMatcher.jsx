import { useState } from "react";
import api from "../api";
import BadgeList from "./BadgeList";

export default function JobMatcher({ resumeId }) {
  const [search, setSearch] = useState("");
  const [location, setLocation] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [matches, setMatches] = useState(null);
  const [savedOnly, setSavedOnly] = useState(false);

  async function handleSearch() {
    if (!resumeId) {
      setError("Add a resume first (step 1).");
      return;
    }
    setLoading(true);
    setError("");
    setMatches(null);
    try {
      const data = savedOnly
        ? await api.searchSavedJobs({ ...(search.trim() ? { query: search } : { resume_id: resumeId }), location, remote_only: remoteOnly, top_n: 10 })
        : await api.matchJobs(resumeId, { search, location, remoteOnly, topN: 10 });
      setMatches(data.matches || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card">
      <div className="card-header">
        <span className="step-badge">3</span>
        <h2>Find matching jobs</h2>
      </div>

      <label className="checkbox-label saved-search">
        <input type="checkbox" checked={savedOnly} onChange={e => { setSavedOnly(e.target.checked); setMatches(null); }} />
        Search previously saved jobs
      </label>
      {savedOnly && <p className="muted small">Describe a role to search by meaning, or leave the keyword blank to match your resume. Live searches save jobs for later.</p>}

      <div className="filters-row">
        <input
          type="text"
          placeholder="Keyword (e.g. python, backend)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <input
          type="text"
          placeholder="Location (optional)"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
        <label className="checkbox-label">
          <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
          Remote only
        </label>
      </div>
      <button className="btn btn-primary" onClick={handleSearch} disabled={loading || !resumeId}>
        {loading ? "Searching..." : "Find Matching Jobs"}
      </button>

      {error && <p className="error-text">{error}</p>}

      {matches && matches.length === 0 && <p className="muted">No matching jobs found. Try different filters.</p>}

      {matches && matches.length > 0 && (
        <div className="job-list">
          {matches.map((job, i) => (
            <div key={i} className="job-item">
              <div className="job-item-header">
                <div>
                  <div className="job-title">{job.title}</div>
                  <div className="muted small">
                    {job.company} | {job.location}
                  </div>
                </div>
                <div className="job-score">{job.match_score}%</div>
              </div>
              {job.matched_skills.length > 0 && (
                <div className="job-skills">
                  <BadgeList items={job.matched_skills} tone="success" />
                </div>
              )}
              {job.url && (
                <a href={job.url} target="_blank" rel="noreferrer" className="job-link">
                  View posting &rarr;
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
