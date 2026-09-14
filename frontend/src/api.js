const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, options);
  let data;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const message = data?.error || `Request failed with status ${res.status}`;
    throw new Error(message);
  }
  return data;
}

export const api = {
  health: () => request("/api/health"),

  uploadResumeFile: (file) => {
    const formData = new FormData();
    formData.append("file", file);
    return request("/api/resume/upload", { method: "POST", body: formData });
  },

  uploadResumeText: (text) =>
    request("/api/resume/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),

  getResume: (id) => request(`/api/resume/${id}`),

  getResumeFeedback: (id) => request(`/api/resume/${id}/feedback`),

  deleteResume: (id) => request(`/api/resume/${id}`, { method: "DELETE" }),

  analyze: (resumeId, jobDescription, jobTags = []) =>
    request("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_id: resumeId, job_description: jobDescription, job_tags: jobTags }),
    }),

  listJobs: ({ search = "", location = "", remoteOnly = false, page = 1, limit = 25 } = {}) => {
    const params = new URLSearchParams({
      search,
      location,
      remote_only: String(remoteOnly),
      page: String(page),
      limit: String(limit),
    });
    return request(`/api/jobs?${params.toString()}`);
  },

  matchJobs: (resumeId, { search = "", location = "", remoteOnly = false, topN = 10 } = {}) =>
    request("/api/match-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_id: resumeId,
        search,
        location,
        remote_only: remoteOnly,
        top_n: topN,
      }),
    }),
};

export default api;
