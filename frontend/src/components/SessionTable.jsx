import { Link } from "react-router-dom";
import { formatValue, percent } from "../api";
export default function SessionTable({ sessions, onDelete }) {
  if (!sessions.length)
    return (
      <div className="py-14 text-center">
        <h2>No sessions yet</h2>
        <p className="mt-2 text-sm text-muted">
          Start a session or load the clearly marked demo data.
        </p>
        <Link className="btn mt-5" to="/">
          Set up a session
        </Link>
      </div>
    );
  return (
    <div className="overflow-x-auto">
      <table className="w-full whitespace-nowrap text-left text-sm">
        <thead className="bg-paper text-xs text-muted">
          <tr>
            {[
              "Participant / group",
              "Condition",
              "Trials",
              "Accuracy",
              "Overconfidence",
              "Calibration error",
              "Date",
              "Actions",
            ].map((t) => (
              <th className="px-4 py-3 font-medium" key={t}>
                {t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.session_id} className="border-t border-line">
              <td className="px-4 py-4">
                <span className="font-mono font-medium">
                  {s.participant_id}
                </span>
                <div className="mt-1 text-xs text-muted">
                  {s.group || "No group"}
                </div>
                {s.is_synthetic && (
                  <span className="badge mt-2">Synthetic data</span>
                )}
              </td>
              <td className="px-4 py-4">
                <span className="capitalize">
                  {s.condition.feedback} feedback
                </span>
                <div className="mt-1 text-xs text-muted">
                  {s.condition.difficulty} · {s.condition.categories} ·{" "}
                  {s.condition.interface}
                  {s.condition.time_limit === "20" ? " · 20s" : ""}
                </div>
              </td>
              <td className="px-4 py-4">
                {s.answered}/{s.n_trials}
              </td>
              <td className="px-4 py-4">
                {s.metrics ? percent(s.metrics.accuracy) : "In progress"}
              </td>
              <td className="px-4 py-4">
                {s.metrics ? formatValue(s.metrics.overconfidence, " pp") : "—"}
              </td>
              <td className="px-4 py-4">
                {s.metrics
                  ? formatValue(s.metrics.calibration_error, " pp")
                  : "—"}
              </td>
              <td className="px-4 py-4 text-xs text-muted">
                {new Date(s.started_at).toLocaleDateString()}
              </td>
              <td className="px-4 py-4">
                <Link
                  className="font-medium text-brand hover:underline"
                  to={
                    s.status === "complete"
                      ? `/report/${s.session_id}`
                      : `/session/${s.session_id}`
                  }
                >
                  {s.status === "complete" ? "View report" : "Resume"}
                </Link>
                {onDelete && (
                  <button
                    className="ml-4 text-xs text-red-700 hover:underline"
                    onClick={() => onDelete(s)}
                  >
                    Delete
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
