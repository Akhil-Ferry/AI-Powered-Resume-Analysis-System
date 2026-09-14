import { useState } from "react";
import StatusBar from "./components/StatusBar";
import ResumeWorkspace from "./components/ResumeWorkspace";
import ResumeFeedback from "./components/ResumeFeedback";
import JobAnalyzer from "./components/JobAnalyzer";
import JobMatcher from "./components/JobMatcher";
import "./App.css";

export default function App() {
  const [resume, setResume] = useState(null);
  const [revision, setRevision] = useState(0);
  return (
    <div className="app">
      <header className="app-header">
        <h1>AI-Powered Resume Analysis System</h1>
        <p className="subtitle">Build your resume | Improve your story | Find relevant roles</p>
      </header>
      <StatusBar />
      <main className="app-main">
        <ResumeWorkspace resume={resume} onResumeReady={setResume} />
        <JobAnalyzer key={`analysis-${resume?.id}-${resume?.updated_at}`} resumeId={resume?.id} onAnalyzed={() => setRevision(v => v + 1)} />
        <JobMatcher key={`jobs-${resume?.id}-${resume?.updated_at}`} resumeId={resume?.id} />
        {resume && <ResumeFeedback key={resume.id + resume.updated_at} resumeId={resume.id} revision={revision} />}
      </main>
      <footer className="app-footer">
        <p>Python | Flask | PostgreSQL | OpenAI API | NLP  Vector Embeddings</p>
        <p>Match scores measure text similarity; they are not hiring probabilities.</p>
      </footer>
    </div>
  );
}
