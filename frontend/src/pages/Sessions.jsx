import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import SessionTable from "../components/SessionTable";
export default function Sessions() {
  const [sessions, setSessions] = useState(null);
  const [group, setGroup] = useState("");
  const [feedback, setFeedback] = useState("");
  const [synthetic, setSynthetic] = useState("");
  const [error, setError] = useState("");
  function load() {
    const p = new URLSearchParams();
    if (group) p.set("group", group);
    if (feedback) p.set("feedback", feedback);
    if (synthetic) p.set("is_synthetic", synthetic);
    return api(`/sessions?${p}`)
      .then(setSessions)
      .catch((e) => setError(e.message));
  }
  useEffect(() => {
    let live = true;
    setError("");
    const p = new URLSearchParams();
    if (group) p.set("group", group);
    if (feedback) p.set("feedback", feedback);
    if (synthetic) p.set("is_synthetic", synthetic);
    api(`/sessions?${p}`)
      .then((s) => {
        if (live) setSessions(s);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [group, feedback, synthetic]);
  async function remove(s) {
    if (
      !window.confirm(
        `Delete session for ${s.participant_id}, all its trials, and its report?`,
      )
    )
      return;
    try {
      await api(`/sessions/${s.session_id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <p className="eyebrow mb-2">THE RECORD</p>
          <h1>Sessions</h1>
          <p className="mt-3 text-muted">
            Review, resume, and manage your laboratory sessions.
          </p>
        </div>
        <Link to="/" className="btn">
          New session +
        </Link>
      </div>
      <div className="panel">
        <div className="mb-6 flex flex-wrap gap-4">
          <label className="field">
            Group
            <input
              value={group}
              onChange={(e) => setGroup(e.target.value)}
              placeholder="Exact group label"
            />
          </label>
          <label className="field">
            Feedback
            <select
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
            >
              <option value="">All feedback conditions</option>
              {["immediate", "delayed", "none"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Data source
            <select
              value={synthetic}
              onChange={(e) => setSynthetic(e.target.value)}
            >
              <option value="">All data</option>
              <option value="false">Participant sessions</option>
              <option value="true">Synthetic only</option>
            </select>
          </label>
        </div>
        {error && (
          <p className="error mb-5" role="alert">
            {error}
          </p>
        )}
        {sessions ? (
          <SessionTable sessions={sessions} onDelete={remove} />
        ) : (
          <p className="py-10 text-center text-muted">Loading sessions…</p>
        )}
      </div>
    </>
  );
}
