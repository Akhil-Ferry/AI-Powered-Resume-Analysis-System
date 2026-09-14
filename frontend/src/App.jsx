import { useState } from "react";
import StatusBar from "./components/StatusBar";
import ResumeUploader from "./components/ResumeUploader";
import JobAnalyzer from "./components/JobAnalyzer";
import JobMatcher from "./components/JobMatcher";
import "./App.css";

export default function App() {
  const [resume, setResume] = useState(null);

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI-Powered Resume Analyzer</h1>
        <p className="subtitle">Semantic resume matching | Live job listings | Vector embeddings</p>
      </header>

      <StatusBar />

      <main className="app-main">
        <ResumeUploader resume={resume} onResumeReady={setResume} />
        <JobAnalyzer resumeId={resume?.id} />
        <JobMatcher resumeId={resume?.id} />
      </main>

      <footer className="app-footer">
        <p>Built with Flask + React | Embeddings via OpenAI (optional) or local sentence-transformers</p>
      </footer>
    </div>
  );
}
